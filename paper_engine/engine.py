"""Event-driven, local SQLite PAPER trading engine, no exchange order interface.

A candle is a completed bar of a declared interval. Orders made after one bar
cannot fill before the following bar. Intrabar stops win ambiguous stop/target
collisions. Limit fills assume a resting order was filled after *trade-through*;
queue/latency effects remain a meaningful optimism in this simplified model.

The V6 trading_costs module is the sole source for estimated execution prices
and fees. All stored quote prices are mid references, not actual Kraken fills.
"""
from __future__ import annotations
from dataclasses import asdict, dataclass
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sqlite3
from uuid import uuid4

from data_layer.storage import Candle, validate as validate_candle
from trading_costs import (FeeSettings, Execution, TradeLedger,
                           estimate_execution, quantity_for_quote_budget,
                           ledger_to_log, load_settings)


@dataclass(frozen=True)
class RiskLimits:
    starting_cash: float = 1000.0
    max_order_quote: float = 50.0
    max_position_fraction: float = 0.05
    min_order_quote: float = 10.0
    daily_loss_limit: float = 0.02
    peak_drawdown_limit: float = 0.05

    def __post_init__(self):
        for k, v in asdict(self).items():
            if not math.isfinite(v) or v <= 0:
                raise ValueError(f'Invalid paper risk setting: {k}')
        if not (self.max_position_fraction <= 1 and self.daily_loss_limit < 1
                and self.peak_drawdown_limit < 1):
            raise ValueError('Exposure and drawdown fractions out of range')
        if self.min_order_quote > self.max_order_quote:
            raise ValueError('min_order_quote must not exceed max_order_quote')


def _dump(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _checked_positive(v, name):
    v = float(v)
    if not math.isfinite(v) or v <= 0:
        raise ValueError(f'{name} must be finite and positive')
    return v


class PaperEngine:
    """Single-pair, single-position simulator; every mutation is atomic.

    Each DB file is bound to immutable cost/risk assumptions. A restart reads
    those original settings; it cannot accidentally reprice existing trades.
    """
    def __init__(self, db_path: str | Path, *, settings: FeeSettings | None = None,
                 risk: RiskLimits | None = None, interval: int = 240):
        if interval not in (1, 5, 15, 30, 60, 240, 720, 1440):
            raise ValueError('Unsupported Kraken-style interval')
        self.path = Path(db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path, timeout=20, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA busy_timeout=20000')
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA foreign_keys=ON')
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS config (id INTEGER PRIMARY KEY CHECK(id=1),
             fee_json TEXT NOT NULL, risk_json TEXT NOT NULL, interval INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS wallet (id INTEGER PRIMARY KEY CHECK(id=1),
             cash REAL NOT NULL, initial_cash REAL NOT NULL, high_water REAL NOT NULL,
             day_utc TEXT, day_start_equity REAL NOT NULL, halted_reason TEXT,
             last_ts INTEGER, last_close REAL,
             last_volatility REAL NOT NULL DEFAULT 0, last_candle_hash TEXT);
        CREATE TABLE IF NOT EXISTS orders (
             id INTEGER PRIMARY KEY AUTOINCREMENT, client_id TEXT UNIQUE NOT NULL,
             side TEXT NOT NULL CHECK(side IN ('buy','sell')),
             kind TEXT NOT NULL CHECK(kind IN ('market','limit','protective_stop','protective_target')),
             status TEXT NOT NULL CHECK(status IN ('pending','filled','cancelled')),
             submitted_after_ts INTEGER NOT NULL,
             limit_mid REAL, budget_quote REAL, stop_pct REAL, target_pct REAL,
             filled_ts INTEGER, reason TEXT NOT NULL DEFAULT '');
        CREATE UNIQUE INDEX IF NOT EXISTS unique_pending_side ON orders(side) WHERE status='pending';
        CREATE TABLE IF NOT EXISTS position (
             id INTEGER PRIMARY KEY CHECK(id=1), quantity REAL NOT NULL,
             entry_ts INTEGER NOT NULL, entry_mid REAL NOT NULL,
             entry_outlay REAL NOT NULL, entry_execution TEXT NOT NULL,
             stop_mid REAL NOT NULL, target_mid REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS fills (
             id INTEGER PRIMARY KEY AUTOINCREMENT, order_id INTEGER NOT NULL REFERENCES orders(id),
             ts INTEGER NOT NULL, execution_json TEXT NOT NULL, outlay_or_receipt_quote REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS trades (
             id INTEGER PRIMARY KEY AUTOINCREMENT, entry_ts INTEGER NOT NULL,
             exit_ts INTEGER NOT NULL, exit_reason TEXT NOT NULL, quantity REAL NOT NULL,
             ledger_json TEXT NOT NULL, gross_pnl_quote REAL NOT NULL,
             fees_quote REAL NOT NULL, spread_quote REAL NOT NULL,
             slippage_quote REAL NOT NULL, net_pnl_quote REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS journal (
             id INTEGER PRIMARY KEY AUTOINCREMENT, ts INTEGER,
             type TEXT NOT NULL, details_json TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS equity_snapshots (
             ts INTEGER PRIMARY KEY, cash REAL NOT NULL, exit_value REAL NOT NULL,
             equity_net REAL NOT NULL, halted_reason TEXT);
        ''')
        cfg = self.db.execute('SELECT * FROM config WHERE id=1').fetchone()
        if not cfg:
            self.settings = settings or load_settings()
            self.risk = risk or RiskLimits()
            self.interval = interval
            self._assert_spot()
            with self._txn():
                self.db.execute('INSERT INTO config VALUES (1, ?, ?, ?)',
                                (_dump(asdict(self.settings)), _dump(asdict(self.risk)), interval))
                self.db.execute('INSERT INTO wallet VALUES (1, ?, ?, ?, NULL, ?, NULL, NULL, NULL, 0.0, NULL)',
                                (self.risk.starting_cash, self.risk.starting_cash,
                                 self.risk.starting_cash, self.risk.starting_cash))
        else:
            if settings is not None and _dump(asdict(settings)) != cfg['fee_json']:
                self.db.close()
                raise ValueError('Existing wallet fee assumptions differ; create a separate DB')
            if risk is not None and _dump(asdict(risk)) != cfg['risk_json']:
                self.db.close()
                raise ValueError('Existing wallet risk assumptions differ; create a separate DB')
            if interval != cfg['interval']:
                self.db.close()
                raise ValueError('Existing wallet interval differs')
            from trading_costs import FeeTier
            f = json.loads(cfg['fee_json'])
            f['tiers'] = tuple(FeeTier(**t) for t in f['tiers'])
            self.settings = FeeSettings(**f)
            self.risk = RiskLimits(**json.loads(cfg['risk_json']))
            self.interval = interval
            self._assert_spot()
        self.db.execute('PRAGMA foreign_keys=ON')

    @contextmanager
    def _txn(self):
        # isolation_level=None requires explicit BEGIN for true rollback/atomicity.
        self.db.execute('BEGIN IMMEDIATE')
        try:
            yield
            self.db.execute('COMMIT')
        except BaseException:
            self.db.execute('ROLLBACK')
            raise

    def _assert_spot(self):
        if self.settings.instrument != 'spot':
            raise ValueError('Paper V7 handles unlevered spot only; no derivatives')

    def close(self):
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def _wallet(self):
        return self.db.execute('SELECT * FROM wallet WHERE id=1').fetchone()

    def _pos(self):
        return self.db.execute('SELECT * FROM position WHERE id=1').fetchone()

    def _emit(self, name, ts, **info):
        self.db.execute('INSERT INTO journal(ts, type, details_json) VALUES (?, ?, ?)',
                        (ts, name, _dump(info)))

    def _pending(self, side):
        return self.db.execute("SELECT * FROM orders WHERE status='pending' AND side=?", (side,)).fetchone()

    def _cash_equity(self, mid, volatility=0.0):
        w = self._wallet()
        pos = self._pos()
        value = 0.0
        if pos:
            liquidation = estimate_execution(mid, pos['quantity'], 'sell', 'taker',
                                              self.settings, volatility)
            value = liquidation.executed_notional_quote - liquidation.fee_quote
        return float(w['cash']), value, float(w['cash'])+value

    def status(self):
        w = self._wallet()
        pos = self._pos()
        mid = w['last_close']
        cash, liquidation, eq = (self._cash_equity(mid,w['last_volatility']) if mid is not None
                                 else (w['cash'], 0.0, w['cash']))
        return dict(mode='PAPER_ONLY', exchange='kraken', pair='BTC/AUD',
                    interval_minutes=self.interval, last_ts=w['last_ts'],
                    cash_quote=cash, estimated_liquidation_value_quote=liquidation,
                    equity_net_quote=eq, halt_reason=w['halted_reason'],
                    position=(dict(pos) if pos else None),
                    pending=[dict(x) for x in self.db.execute(
                        "SELECT * FROM orders WHERE status='pending' ORDER BY id")])

    def place_buy(self, budget_quote: float, *, kind='market', limit_mid=None,
                  stop_pct: float = 0.045, target_pct: float = 0.075,
                  client_id: str | None = None) -> int:
        budget = _checked_positive(budget_quote, 'budget_quote')
        stop_pct = _checked_positive(stop_pct, 'stop_pct')
        target_pct = _checked_positive(target_pct, 'target_pct')
        if stop_pct >= 1 or target_pct > 10:
            raise ValueError('Invalid stop or target')
        if kind not in ('market', 'limit') or (kind == 'limit') != (limit_mid is not None):
            raise ValueError('Expected market without price or limit with price')
        if limit_mid is not None:
            limit_mid = _checked_positive(limit_mid, 'limit_mid')
        client_id = client_id or uuid4().hex
        with self._txn():
            existing = self.db.execute('SELECT * FROM orders WHERE client_id=?', (client_id,)).fetchone()
            if existing:
                expected=(kind,limit_mid,budget,stop_pct,target_pct)
                original=tuple(existing[k] for k in ('kind','limit_mid','budget_quote','stop_pct','target_pct'))
                if expected != original or existing['side'] != 'buy':
                    raise ValueError('client_id reused with different order parameters')
                return existing['id']  # exact-once retry semantics
            w = self._wallet()
            if w['last_ts'] is None:
                raise ValueError('Feed a completed candle before submitting orders')
            if w['halted_reason']:
                raise ValueError('Paper trading halted; buys are disabled')
            if self._pos() or self._pending('buy'):
                raise ValueError('One position or pending buy at a time')
            _, _, equity = self._cash_equity(w['last_close'],w['last_volatility'])
            permitted = min(self.risk.max_order_quote,
                            equity * self.risk.max_position_fraction, w['cash'])
            if budget < self.risk.min_order_quote - 1e-9 or budget > permitted + 1e-9:
                raise ValueError(f'Order violates risk/exposure cap: {permitted:.4f} maximum')
            cur = self.db.execute('''INSERT INTO orders
                (client_id, side, kind, status, submitted_after_ts, limit_mid,
                 budget_quote, stop_pct, target_pct) VALUES (?, 'buy', ?, 'pending', ?, ?, ?, ?, ?)''',
                (client_id, kind, w['last_ts'], limit_mid, budget, stop_pct, target_pct))
            self._emit('order_created', w['last_ts'], order_id=cur.lastrowid, side='buy', kind=kind)
            return cur.lastrowid

    def place_sell(self, *, kind='market', limit_mid=None, client_id: str | None = None) -> int:
        if kind not in ('market', 'limit') or (kind == 'limit') != (limit_mid is not None):
            raise ValueError('Expected market without price or limit with price')
        if limit_mid is not None:
            limit_mid = _checked_positive(limit_mid, 'limit_mid')
        client_id = client_id or uuid4().hex
        with self._txn():
            existing = self.db.execute('SELECT * FROM orders WHERE client_id=?', (client_id,)).fetchone()
            if existing:
                if existing['side']!='sell' or existing['kind']!=kind or existing['limit_mid']!=limit_mid:
                    raise ValueError('client_id reused with different order parameters')
                return existing['id']
            w=self._wallet()
            if not self._pos() or self._pending('sell'):
                raise ValueError('An open position and no pending sell are required')
            cur=self.db.execute('''INSERT INTO orders
                 (client_id, side, kind, status, submitted_after_ts, limit_mid)
                 VALUES (?, 'sell', ?, 'pending', ?, ?)''',
                 (client_id, kind, w['last_ts'], limit_mid))
            self._emit('order_created', w['last_ts'], order_id=cur.lastrowid, side='sell', kind=kind)
            return cur.lastrowid

    def cancel(self, order_id: int):
        with self._txn():
            w=self._wallet()
            cur=self.db.execute("UPDATE orders SET status='cancelled', reason='manual_cancel' WHERE id=? AND status='pending'", (order_id,))
            if not cur.rowcount: raise ValueError('Order not pending or not found')
            self._emit('order_cancelled', w['last_ts'], order_id=order_id)

    def _fill_buy(self, order, ts, mid, volatility, liquidity):
        quote = order['budget_quote']
        quantity = quantity_for_quote_budget(mid, quote, self.settings,
                                            liquidity=liquidity, volatility_frac=volatility)
        exe = estimate_execution(mid, quantity, 'buy', liquidity, self.settings, volatility)
        outlay = exe.executed_notional_quote + exe.fee_quote
        w=self._wallet()
        if outlay > w['cash'] + 1e-7:
            raise ValueError('Insufficient simulated cash on fill')
        self.db.execute('UPDATE wallet SET cash=cash-? WHERE id=1', (outlay,))
        self.db.execute('''INSERT INTO position VALUES(1,?,?,?,?,?,?,?)''',
                        (quantity, ts, mid, outlay, _dump(asdict(exe)),
                         mid*(1-order['stop_pct']), mid*(1+order['target_pct'])))
        self.db.execute("UPDATE orders SET status='filled', filled_ts=? WHERE id=?", (ts, order['id']))
        self.db.execute('INSERT INTO fills(order_id,ts,execution_json,outlay_or_receipt_quote) VALUES (?,?,?,?)',
                        (order['id'], ts, _dump(asdict(exe)), -outlay))
        self._emit('buy_fill', ts, order_id=order['id'], quantity_base=quantity, cash_outlay=outlay)

    def _ledger(self, pos, mid, liquidity, volatility):
        entry = Execution(**json.loads(pos['entry_execution']))
        sell = estimate_execution(mid, pos['quantity'], 'sell', liquidity, self.settings, volatility)
        gross = pos['quantity']*(mid-pos['entry_mid'])
        fees = entry.fee_quote+sell.fee_quote
        spread = entry.spread_quote+sell.spread_quote
        slippage = entry.slippage_quote+sell.slippage_quote
        outlay = entry.executed_notional_quote+entry.fee_quote
        received = sell.executed_notional_quote-sell.fee_quote
        net = received-outlay
        if not math.isclose(gross-fees-spread-slippage, net,
                            rel_tol=1e-9, abs_tol=1e-8):
            raise ArithmeticError('Paper ledger fails cost reconciliation')
        return TradeLedger(entry, sell, gross, fees, slippage, spread, 0.0, 0.0,
                           net, outlay, received, net/outlay)

    def _fill_sell(self, ts, mid, volatility, *, liquidity, reason, order=None):
        pos=self._pos()
        if not pos: raise ValueError('No position to sell')
        ledger=self._ledger(pos, mid, liquidity, volatility)
        if not math.isclose(ledger.entry_total_outlay_quote, pos['entry_outlay'], abs_tol=1e-8):
            raise ArithmeticError('Stored entry outlay differs from fee engine')
        self.db.execute('UPDATE wallet SET cash=cash+? WHERE id=1', (ledger.exit_total_received_quote,))
        if order is None:
            # Protective order is a recorded simulated order, never sent to a broker.
            kind = 'protective_stop' if reason.startswith('stop') else 'protective_target'
            cur=self.db.execute('''INSERT INTO orders(client_id,side,kind,status,
                    submitted_after_ts,filled_ts,reason)
                    VALUES (?,'sell',?,'filled',?,?,?)''',
                    (uuid4().hex, kind, pos['entry_ts'], ts, reason))
            order_id=cur.lastrowid
        else:
            order_id=order['id']
            self.db.execute("UPDATE orders SET status='filled',filled_ts=?,reason=? WHERE id=?", (ts, reason, order_id))
        self.db.execute('INSERT INTO fills(order_id,ts,execution_json,outlay_or_receipt_quote) VALUES (?,?,?,?)',
                        (order_id, ts, _dump(asdict(ledger.exit)), ledger.exit_total_received_quote))
        details={**ledger_to_log(ledger), 'entry_ts':pos['entry_ts'], 'exit_ts':ts,
                 'reason':reason, 'quantity_base':pos['quantity']}
        self.db.execute('''INSERT INTO trades(entry_ts,exit_ts,exit_reason,quantity,ledger_json,
                         gross_pnl_quote,fees_quote,spread_quote,slippage_quote,net_pnl_quote)
                         VALUES (?,?,?,?,?,?,?,?,?,?)''',
                        (pos['entry_ts'], ts, reason, pos['quantity'], _dump(details),
                         ledger.gross_pnl_quote, ledger.trading_fees_quote,
                         ledger.spread_quote, ledger.slippage_quote, ledger.net_pnl_quote))
        self.db.execute('DELETE FROM position WHERE id=1')
        self.db.execute("UPDATE orders SET status='cancelled',reason='position_closed' WHERE side='sell' AND status='pending'")
        self._emit('sell_fill', ts, order_id=order_id, reason=reason, net_pnl=ledger.net_pnl_quote)

    def _halt(self, reason, ts):
        w=self._wallet()
        if w['halted_reason']: return
        self.db.execute('UPDATE wallet SET halted_reason=? WHERE id=1', (reason,))
        self.db.execute("UPDATE orders SET status='cancelled',reason='risk_halt' WHERE side='buy' AND status='pending'")
        self._emit('risk_halt', ts, reason=reason)

    def on_candle(self, candle: Candle, *, volatility_frac: float = 0.,
                  allow_gap: bool = False) -> dict:
        """Consume one CLOSED candle, fill orders without same-bar lookahead.

        Stops/targets are deterministic but intrabar path is unknown. If stop
        and target both hit, choose stop. Candle gaps must be acknowledged.
        Identical resend is exactly-once; revised historical bars fail closed.
        """
        validate_candle(candle, self.interval)
        if not math.isfinite(volatility_frac) or not 0<=volatility_frac<=1:
            raise ValueError('volatility_frac must be in [0, 1]')
        digest=hashlib.sha256(_dump(asdict(candle)).encode()).hexdigest()
        with self._txn():
            w=self._wallet()
            if w['last_ts'] is not None:
                if candle.ts==w['last_ts'] and digest==w['last_candle_hash']:
                    return {'duplicate':True, **self.status()}
                if candle.ts<=w['last_ts']:
                    raise ValueError('Out-of-order or changed candle')
                if candle.ts-w['last_ts']!=self.interval*60 and not allow_gap:
                    raise ValueError('Candle gap: reload missing bars or explicitly allow_gap=True')
                if candle.ts-w['last_ts']!=self.interval*60:
                    self._emit('gap_acknowledged',candle.ts,previous_ts=w['last_ts'], gap_seconds=candle.ts-w['last_ts'])
            day=datetime.fromtimestamp(candle.ts,tz=timezone.utc).date().isoformat()
            if w['day_utc']!=day:
                _,_,start_equity=(self._cash_equity(w['last_close'],w['last_volatility'])
                                  if w['last_close'] else (w['cash'],0.,w['cash']))
                self.db.execute('UPDATE wallet SET day_utc=?,day_start_equity=? WHERE id=1',
                                (day,start_equity))
            # Existing protective stop/target at the new opening price wins
            # over queued discretionary orders if an adverse gap occurred.
            pos=self._pos()
            exited=False
            if pos and candle.open<=pos['stop_mid']:
                self._fill_sell(candle.ts,candle.open,volatility_frac,liquidity='taker',reason='stop_gap');exited=True
            elif pos and candle.open>=pos['target_mid']:
                self._fill_sell(candle.ts,candle.open,volatility_frac,liquidity='taker',reason='target_gap');exited=True
            if not exited and pos:
                sell=self._pending('sell')
                if sell and candle.ts>sell['submitted_after_ts'] and sell['kind']=='market':
                    self._fill_sell(candle.ts,candle.open,volatility_frac,liquidity='taker',reason='manual_market',order=sell);exited=True
            pos=self._pos()
            if pos and not exited:
                if candle.low<=pos['stop_mid']:
                    self._fill_sell(candle.ts,pos['stop_mid'],volatility_frac,liquidity='taker',reason='stop_intrabar');exited=True
                elif candle.high>=pos['target_mid']:
                    self._fill_sell(candle.ts,pos['target_mid'],volatility_frac,liquidity='taker',reason='target_intrabar');exited=True
                else:
                    sell=self._pending('sell')
                    if sell and candle.ts>sell['submitted_after_ts'] and sell['kind']=='limit' and candle.high>sell['limit_mid']:
                        self._fill_sell(candle.ts,sell['limit_mid'],volatility_frac,liquidity='maker',reason='manual_limit',order=sell)
                        exited=True
            opened=False
            if not exited and not self._pos() and not self._wallet()['halted_reason']:
                buy=self._pending('buy')
                if buy and candle.ts>buy['submitted_after_ts']:
                    if buy['kind']=='market':
                        self._fill_buy(buy,candle.ts,candle.open,volatility_frac,'taker');opened=True
                    elif candle.low<buy['limit_mid']:
                        self._fill_buy(buy,candle.ts,buy['limit_mid'],volatility_frac,'maker');opened=True
            # Protect fresh market AND limit fills. Intrabar order is unknowable
            # for limit entries, so conservatively assume any stop was hit
            # after entry. Never credit a same-bar limit-entry profit target.
            if opened:
                pos=self._pos()
                entry_order=self.db.execute('SELECT kind FROM orders WHERE filled_ts=? AND side="buy" ORDER BY id DESC LIMIT 1', (candle.ts,)).fetchone()
                if entry_order:
                    if candle.low<=pos['stop_mid']:
                        self._fill_sell(candle.ts,pos['stop_mid'],volatility_frac,liquidity='taker',reason='stop_intrabar');exited=True
                    elif entry_order['kind']=='market' and candle.high>=pos['target_mid']:
                        self._fill_sell(candle.ts,pos['target_mid'],volatility_frac,liquidity='taker',reason='target_intrabar');exited=True
            cash, liquid, eq=self._cash_equity(candle.close,volatility_frac)
            w=self._wallet()
            peak=max(w['high_water'],eq)
            self.db.execute('UPDATE wallet SET high_water=?,last_ts=?,last_close=?,last_volatility=?,last_candle_hash=? WHERE id=1',
                            (peak,candle.ts,candle.close,volatility_frac,digest))
            if eq< w['day_start_equity']*(1-self.risk.daily_loss_limit)-1e-9:
                self._halt('daily_loss',candle.ts)
            elif eq<peak*(1-self.risk.peak_drawdown_limit)-1e-9:
                self._halt('peak_drawdown',candle.ts)
            self.db.execute('''INSERT INTO equity_snapshots(ts,cash,exit_value,equity_net,halted_reason)
                               VALUES (?,?,?,?,?)''',
                            (candle.ts,cash,liquid,eq,self._wallet()['halted_reason']))
            self._assert_reconciled()
            return {'duplicate':False,'opened':opened,'exited':exited,**self.status()}

    def _assert_reconciled(self):
        """Cash must equal initial cash + realized trade net - open outlay."""
        w=self._wallet()
        realized=self.db.execute('SELECT COALESCE(SUM(net_pnl_quote),0) AS val FROM trades').fetchone()['val']
        pos=self._pos()
        expected=w['initial_cash']+realized-(pos['entry_outlay'] if pos else 0)
        if not math.isclose(w['cash'],expected,rel_tol=1e-10,abs_tol=1e-7):
            raise ArithmeticError(f'Wallet cash ledger mismatch: {w["cash"]} != {expected}')
        if w['cash'] < -1e-7:
            raise ArithmeticError('Cash balance below zero')

    def verify(self):
        self._assert_reconciled()
        bad=self.db.execute('''SELECT COUNT(*) AS n FROM trades
                              WHERE ABS(gross_pnl_quote-fees_quote-spread_quote-slippage_quote-net_pnl_quote)>1e-7''').fetchone()['n']
        if bad: raise ArithmeticError(f'{bad} trades failed gross-to-net reconciliation')
        return {'ok':True,'closed_trades':self.db.execute('SELECT COUNT(*) FROM trades').fetchone()[0],
                'fills':self.db.execute('SELECT COUNT(*) FROM fills').fetchone()[0]}

    def trades(self):
        return [json.loads(row['ledger_json']) for row in self.db.execute('SELECT ledger_json FROM trades ORDER BY id')]

    def orders(self):
        return [dict(row) for row in self.db.execute('SELECT * FROM orders ORDER BY id')]

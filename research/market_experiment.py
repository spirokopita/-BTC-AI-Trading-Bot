"""BTC/AUD paper-only, next-open, walk-forward market research. No order endpoints."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import statistics
import time
from urllib.parse import urlencode
from urllib.request import urlopen, Request
from trading_costs import FeeSettings, FeeTier, estimate_execution

PAIR_KEYS = {"XXBTZAUD", "XBTAUD", "XBT/AUD", "BTC/AUD"}
STEP = 240 * 60
STRATEGIES = ("sma", "momentum", "rsi", "breakout", "regime")

def parse_kraken(payload, now):
    if not isinstance(payload, dict) or payload.get('error') != []:
        raise ValueError('Kraken response contains errors or is malformed')
    result = payload.get('result')
    if not isinstance(result, dict):
        raise ValueError('Kraken response missing result')
    keys = [k for k in result if k != 'last']
    if len(keys) != 1 or keys[0] not in PAIR_KEYS:
        raise ValueError('Unexpected Kraken pair key')
    raw = result[keys[0]]
    if not isinstance(raw, list):
        raise ValueError('OHLC rows must be a list')
    bars = []
    for r in raw:
        if not isinstance(r, list) or len(r) < 8:
            raise ValueError('Invalid OHLC row')
        ts = int(r[0])
        if ts + STEP > now:
            continue
        op, hi, lo, cl, vol = (float(r[k]) for k in (1, 2, 3, 4, 6))
        if ts % STEP or not all(math.isfinite(v) for v in (op, hi, lo, cl, vol)):
            raise ValueError('Unaligned or non-finite OHLC')
        if min(op, hi, lo, cl) <= 0 or lo > min(op, cl) or hi < max(op, cl) or vol < 0:
            raise ValueError('Invalid OHLC envelope')
        bars.append((ts, op, hi, lo, cl, vol))
    if len(bars) < 620:
        raise ValueError(f'Insufficient completed candles for 2 folds: {len(bars)}')
    if len(set(b[0] for b in bars)) != len(bars):
        raise ValueError('Duplicate timestamps')
    gaps = [(a[0], b[0]) for a, b in zip(bars, bars[1:]) if b[0] - a[0] != STEP]
    if gaps:
        raise ValueError(f'Non-contiguous Kraken 4h candles; gaps={gaps[:4]}')
    return bars

def fetch_public(now=None):
    now = int(time.time()) if now is None else int(now)
    url = 'https://api.kraken.com/0/public/OHLC?' + urlencode({'pair': 'XBTAUD', 'interval': 240})
    with urlopen(Request(url, headers={'User-Agent': 'BTCAUD-paper-research/1.0'}), timeout=25) as response:
        raw = response.read(2_000_001)
    if len(raw) > 2_000_000:
        raise ValueError('Oversized Kraken response')
    return parse_kraken(json.loads(raw), now), hashlib.sha256(raw).hexdigest()

def signal(bars, i, name):
    """Decisions use completed close i; fills are at open i+1."""
    if i < 101:
        return False
    closes = [b[4] for b in bars[i-101:i+1]]
    c = closes[-1]
    if name == 'sma':
        return statistics.mean(closes[-10:]) > statistics.mean(closes[-20:])
    if name == 'momentum':
        return c > closes[-13] * 1.01
    if name == 'rsi':
        d = [closes[j] - closes[j-1] for j in range(len(closes)-14, len(closes))]
        gains = sum(max(v, 0) for v in d) / 14
        losses = sum(max(-v, 0) for v in d) / 14
        rsi = 100 if losses == 0 else 100 - 100 / (1 + gains / losses)
        return rsi < 35
    if name == 'breakout':
        return c > max(b[2] for b in bars[i-20:i])
    if name == 'regime':
        ma100 = statistics.mean(closes[-100:])
        recent = [closes[j]/closes[j-1]-1 for j in range(len(closes)-19, len(closes))]
        return c > ma100 and c > closes[-7] and statistics.pstdev(recent) < .035
    raise ValueError('Unknown strategy')

def simulate(bars, start, end, name, *, fee_multiplier=1):
    if not (102 <= start < end <= len(bars)) or end-start < 2:
        raise ValueError('Invalid backtest interval')
    cash, qty, entry_mid, entry_fill = 1000., 0., 0., None
    equity = [cash]
    totals = {'gross': 0., 'fees': 0., 'spread': 0., 'slippage': 0., 'net': 0.}
    trades = []
    costs = FeeSettings(tiers=(FeeTier(0, .0016*fee_multiplier, .0016*fee_multiplier),),
                        spread_bps=10*fee_multiplier, base_slippage_bps=5*fee_multiplier,
                        volatility_slippage_multiplier=0, size_slippage_bps=0,
                        max_slippage_bps=5*fee_multiplier)
    for j in range(start, end):
        price = bars[j][1]
        want = False if j == end-1 else signal(bars, j-1, name)
        if want and not qty:
            stake = min(50., .05*cash)
            probe = estimate_execution(price, stake/price, 'buy', 'taker', costs)
            qty = stake / (probe.execution_price * (1 + probe.fee_rate))
            entry_fill = estimate_execution(price, qty, 'buy', 'taker', costs)
            entry_mid = price
            cash -= entry_fill.executed_notional_quote + entry_fill.fee_quote
        elif not want and qty:
            exit_fill = estimate_execution(price, qty, 'sell', 'taker', costs)
            cash += exit_fill.executed_notional_quote - exit_fill.fee_quote
            gross = qty * (price-entry_mid)
            fees = entry_fill.fee_quote + exit_fill.fee_quote
            spread = entry_fill.spread_quote + exit_fill.spread_quote
            slip = entry_fill.slippage_quote + exit_fill.slippage_quote
            net = gross - fees - spread - slip
            if not math.isclose(net, exit_fill.executed_notional_quote-exit_fill.fee_quote-
                                entry_fill.executed_notional_quote-entry_fill.fee_quote, abs_tol=1e-8):
                raise AssertionError('Gross/cost/NET mismatch')
            for key, val in [('gross', gross), ('fees', fees), ('spread', spread),
                             ('slippage', slip), ('net', net)]:
                totals[key] += val
            trades.append({'exit_ts': bars[j][0], 'gross_aud': gross, 'fees_aud': fees,
                           'spread_aud': spread, 'slippage_aud': slip, 'net_aud': net})
            qty, entry_fill = 0., None
        mark = cash
        if qty:
            sell = estimate_execution(price, qty, 'sell', 'taker', costs)
            mark += sell.executed_notional_quote - sell.fee_quote
        equity.append(mark)
    peak, drawdown = equity[0], 0.
    for e in equity:
        peak = max(peak, e)
        drawdown = min(drawdown, e/peak-1)
    assert qty == 0 and math.isclose(cash-1000, totals['net'], abs_tol=1e-7)
    return {'strategy': name,
            'start_utc': datetime.fromtimestamp(bars[start][0],timezone.utc).isoformat(),
            'end_utc': datetime.fromtimestamp(bars[end-1][0],timezone.utc).isoformat(),
            'trades': len(trades), 'wins': sum(t['net_aud']>0 for t in trades),
            'losses': sum(t['net_aud']<0 for t in trades),
            'gross_aud': round(totals['gross'],6), 'fees_aud': round(totals['fees'],6),
            'spread_aud': round(totals['spread'],6), 'slippage_aud': round(totals['slippage'],6),
            'net_aud': round(totals['net'],6), 'net_return_pct': round((cash/1000-1)*100,6),
            'max_drawdown_pct': round(drawdown*100,6), 'trade_log': trades}

def experiment(bars):
    folds = []
    for train_end, test_start, test_end in ((360, 380, 500), (480, 500, 620)):
        train = {n: simulate(bars, 102, train_end, n) for n in STRATEGIES}
        eligible = [n for n in STRATEGIES if train[n]['trades'] >= 3 and train[n]['net_aud'] > 0]
        selected = max(eligible, key=lambda n: train[n]['net_aud']) if eligible else 'HOLD'
        test = {n: simulate(bars, test_start, test_end, n) for n in STRATEGIES}
        chosen = test[selected] if selected != 'HOLD' else {'net_aud':0.,'net_return_pct':0.,'trades':0}
        first, last = bars[test_start][1], bars[test_end-1][1]
        folds.append({'train_end_index':train_end, 'purge_bars':20,
                      'test_start_index':test_start,'test_end_exclusive':test_end,
                      'train_results':train, 'test_results':test,
                      'selected_FROM_TRAIN_ONLY':selected,'selected_test':chosen,
                      'market_buy_hold_gross_pct':round(100*(last/first-1),6)})
    return {'mode':'PAPER_ONLY_RESEARCH', 'pair':'Kraken BTC/AUD',
            'interval_minutes':240,'bars':len(bars),
            'first_completed_utc':datetime.fromtimestamp(bars[0][0],timezone.utc).isoformat(),
            'last_completed_utc':datetime.fromtimestamp(bars[-1][0],timezone.utc).isoformat(),
            'costs_per_side_bps':{'fee':16,'half_spread':5,'slippage':5},
            'initial_aud':1000,'max_order_aud':50, 'folds':folds,
            'news_signal_status':'NOT_TESTED: historical first-observed news corpus unavailable; no publication-time leakage permitted',
            'promotion':'REJECTED_PENDING_LONGER_UNTOUCHED_OOS',
            'warning':'Kraken API limited to ~120 days; insufficient for robust model selection. Terminal liquidation uses last test open; hypothetical fills only.'}

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output',default='audit/market-experiment.json')
    args = p.parse_args()
    bars, digest = fetch_public()
    report = experiment(bars)
    report['kraken_raw_response_sha256'] = digest
    report['fetched_at_utc'] = datetime.now(timezone.utc).isoformat()
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')
    print(json.dumps({'output':str(target),'bars':len(bars),'sha256':digest,
                      'fold_selected':[(f['selected_FROM_TRAIN_ONLY'],f['selected_test']['net_aud']) for f in report['folds']]},indent=2))

if __name__ == '__main__':
    main()

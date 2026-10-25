"""Restart-safe BTC/AUD PAPER ONLY decision loop.

All orders go to the local SQLite paper wallet. It contains no broker or
private exchange API. News evidence is point-in-time and retrospective
association, not proof of predictive power. In the absence of matured,
validated and fee-positive evidence, ENTRY IS DISABLED.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import sqlite3
import time

from backtester.engine import BacktestParameters, DonchianBreakout
from data_layer.storage import Candle, CandleStore
from news_intelligence.store import NewsStore
from news_intelligence.signals import event_study, train_signal_quality, event_signal_asof
from paper_engine import PaperEngine, RiskLimits
from trading_costs import minimum_break_even_move, expected_trade_edge


ALLOWED_SOURCES = ('kraken_public_api', 'kraken_csv:', 'kraken_zip:')


@dataclass(frozen=True)
class LoopSettings:
    interval: int = 240
    max_signal_age_seconds: int = 1800
    news_recency_seconds: int = 6 * 3600
    prefer_maker_entry: bool = True
    maker_entry_discount_bps: float = 10.
    limit_ttl_bars: int = 3
    min_net_edge: float = .005
    news_horizon_hours: int = 24
    min_train_events: int = 20
    min_validation_events: int = 10
    min_news_win_fraction: float = .55
    min_news_mean_net_pct: float = .25

    def __post_init__(self):
        BacktestParameters.for_interval(self.interval)
        if self.interval not in (60, 240, 1440):
            raise ValueError('Roadmap 7 news decision loop supports 60m, 240m or 1440m only')
        if self.news_horizon_hours * 60 % self.interval:
            raise ValueError('News horizon must be an exact number of candles')
        if not 0 < self.max_signal_age_seconds <= self.interval*60:
            raise ValueError('Invalid signal age')
        if not 0 < self.news_recency_seconds <= 48*3600:
            raise ValueError('Invalid news recency')
        if not 0 < self.min_net_edge <= .2:
            raise ValueError('Invalid net edge')
        if not 0 <= self.maker_entry_discount_bps <= 100 or not 1 <= self.limit_ttl_bars <= 20:
            raise ValueError('Invalid passive order constraints')
        if self.min_train_events < 10 or self.min_validation_events < 5:
            raise ValueError('Too little evidence for validated news gate')
        if not .5 <= self.min_news_win_fraction < 1:
            raise ValueError('Invalid news win fraction')


class DecisionJournal:
    """Audit and health file, independent of the wallet transactional ledger."""
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path,timeout=20)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.executescript('''
          CREATE TABLE IF NOT EXISTS decisions (
             candle_ts INTEGER PRIMARY KEY, decision TEXT NOT NULL,
             reason TEXT NOT NULL, evidence_json TEXT NOT NULL,
             recorded_at INTEGER NOT NULL);
          CREATE TABLE IF NOT EXISTS health (
             id INTEGER PRIMARY KEY AUTOINCREMENT, observed_at INTEGER NOT NULL,
             status TEXT NOT NULL, details TEXT NOT NULL);
        ''')
        self.db.commit()

    def close(self): self.db.close()
    def __enter__(self):return self
    def __exit__(self,*_):self.close()

    def has(self, ts: int) -> bool:
        return self.db.execute('SELECT 1 FROM decisions WHERE candle_ts=?',(ts,)).fetchone() is not None

    def log(self, ts: int, decision: str, reason: str, evidence: dict, now: int):
        with self.db:
            self.db.execute('''INSERT OR IGNORE INTO decisions
                VALUES (?, ?, ?, ?, ?)''',
                (ts,decision,reason,json.dumps(evidence,sort_keys=True,allow_nan=False),now))

    def heartbeat(self, status: str, details: str, now: int):
        with self.db:
            self.db.execute('INSERT INTO health(observed_at,status,details) VALUES(?,?,?)',
                            (now,status,details[:1000]))
            self.db.execute('DELETE FROM health WHERE id NOT IN (SELECT id FROM health ORDER BY id DESC LIMIT 500)')

    def recent(self, count=10):
        return [dict(row) for row in self.db.execute('SELECT * FROM decisions ORDER BY candle_ts DESC LIMIT ?', (count,))]


def checked_market_bars(market_db: Path, interval:int, now:int) -> list[Candle]:
    if not Path(market_db).is_file():
        raise ValueError('Missing market cache; import real Kraken BTC/AUD candles')
    with CandleStore(market_db) as store:
        raw=store.candles(interval=interval)
    if not raw: raise ValueError('No Kraken BTC/AUD candles; no paper signals permitted')
    for row in raw:
        if not row['source'].startswith(ALLOWED_SOURCES):
            raise ValueError('Unsupported candle provenance; BTC/USDT proxies are prohibited')
    bars=[Candle(x['ts'],x['o'],x['h'],x['l'],x['c'],x['v'],x['trades']) for x in raw
          if x['ts'] + interval * 60 <= now]
    # No gaps or disorder; never turn a Kraken zero-volume interval into a fabricated bar.
    step=interval*60
    from data_layer.storage import validate
    previous=None
    for bar in bars:
        validate(bar,interval)
        if previous is not None and bar.ts-previous!=step:
            raise ValueError('Missing/non-contiguous Kraken candles: fail closed')
        previous=bar.ts
    return bars


def validated_news_edge(article, articles, historical_bars, *, settings: LoopSettings,
                        fee_settings, stake: float) -> dict:
    """Only past, mature observations can contribute to this particular article.

    Take the lower train or holdout *gross* mean as a conservative proxy
    expected gross move, and then run it through the exact V6 net-cost gate.
    Article itself and any later data are never in its own training set.
    """
    cutoff=article.available_ts-1
    prior=[x for x in articles if x.available_ts<article.available_ts]
    step=settings.interval*60
    known=[b for b in historical_bars if b.ts+step<=cutoff]
    if len(known)<2 or len(prior)<settings.min_train_events+settings.min_validation_events:
        return {'approved':False,'reason':'insufficient_mature_news_history'}
    study=event_study(prior,known,interval=settings.interval,
                      horizons_hours=(settings.news_horizon_hours,),
                      fee_settings=fee_settings,quote_budget=stake,min_edge=settings.min_net_edge)
    quality=train_signal_quality(study,horizon_hours=settings.news_horizon_hours,
            as_of_ts=cutoff,min_train=settings.min_train_events,
            min_validation=settings.min_validation_events,
            min_mean_net_pct=settings.min_news_mean_net_pct,
            min_win_fraction=settings.min_news_win_fraction)
    signal=event_signal_asof(article,quality,decision_ts=cutoff+1)
    if signal['bias']!='research_candidate_long':
        return {'approved':False,'reason':'news_category_not_validated'}
    valid=set(signal['categories'])
    moves=[]
    for cat in valid:
        events=sorted((x for x in study['results'] if cat in x['category_tags']),
                      key=lambda e:(e['available_ts'],e['article_id']))
        split=int(len(events)*.7)
        train=[x for x in events[:split] if x['future_close_ts']<events[split]['available_ts']]
        test=events[split:]
        if train and test:
            moves.append(min(sum(x['gross_change_pct'] for x in train)/len(train),
                             sum(x['gross_change_pct'] for x in test)/len(test))/100)
    if not moves:
        return {'approved':False,'reason':'no_conservative_move_estimate'}
    return {'approved':True,'predicted_gross_move':min(max(moves),.20),
            'category':sorted(valid),'evidence_as_of':cutoff,
            'research_only':True,'qualified_tags_from_past_data':True}


class PaperStrategyLoop:
    """Makes paper-only decisions once per newly closed candle.

    Wallet candle transaction happens first. Existing stops and exits are
    processed even when there is no news/edge. New entries are allowed only
    with recent, statistically screened news and a fee-positive forecast.
    """
    def __init__(self, market_db: str|Path, news_db: str|Path,
                 wallet_db: str|Path, journal_db: str|Path,
                 *, config:LoopSettings|None=None, clock=time.time):
        self.market_db=Path(market_db);self.news_db=Path(news_db)
        self.wallet_db=Path(wallet_db);self.journal_db=Path(journal_db)
        self.config=config or LoopSettings();self.clock=clock

    def once(self, *, now: int|None=None, market_ok:bool=True, news_ok:bool=True) -> dict:
        now=int(self.clock()) if now is None else int(now)
        c=self.config;step=c.interval*60
        with DecisionJournal(self.journal_db) as journal:
            try:
                bars=checked_market_bars(self.market_db,c.interval,now)
                if not bars:raise ValueError('No completed market candles')
                # Public stale feed is a signal blocker, not an excuse to backfill
                # trading decisions as if we were present in the past.
                if now-(bars[-1].ts+step)>step+c.max_signal_age_seconds:
                    raise ValueError('Stale candle data: missing most recent completed Kraken interval')
                if not self.news_db.exists():
                    articles=[]
                else:
                    with NewsStore(self.news_db) as news: articles=news.items(end=now)
                strategy=DonchianBreakout(BacktestParameters.for_interval(c.interval))
                processed=0; decisions=0; traded=0; reports=[];last_close=None;atr=None
                with PaperEngine(self.wallet_db,interval=c.interval) as wallet:
                    initial=wallet.status()['last_ts']
                    if initial is not None and not any(bar.ts==initial for bar in bars):
                        raise ValueError('Wallet checkpoint missing from candle history')
                    for bar in bars:
                        # Only ATR from already completed prior bars is visible
                        # at the opening of this bar.
                        volatility=min(1.,atr/last_close) if atr is not None and last_close else 0.
                        old_state=wallet.status()
                        if old_state['last_ts'] is None or bar.ts>old_state['last_ts']:
                            wallet.on_candle(bar,volatility_frac=volatility)
                            processed+=1
                            new=True
                        else:new=False
                        buy,sell=strategy.observe(bar)
                        # Stale resting maker buys are cancelled, never chased
                        # as taker orders. Protective position exits are separate.
                        current=wallet.status()
                        for order in current['pending']:
                            if (order['side']=='buy' and order['kind']=='limit' and
                                bar.ts-order['submitted_after_ts']>=c.limit_ttl_bars*step):
                                wallet.cancel(order['id'])
                        tr=(bar.high-bar.low if last_close is None else
                            max(bar.high-bar.low,abs(bar.high-last_close),abs(bar.low-last_close)))
                        atr=tr if atr is None else (atr*13+tr)/14
                        last_close=bar.close
                        if not new or journal.has(bar.ts):continue
                        bar_close=bar.ts+step
                        decision='HOLD';reason='no_setup';evidence={'candle_close_ts':bar_close,'paper_only':True}
                        status=wallet.status()
                        is_fresh=0<=now-bar_close<=c.max_signal_age_seconds
                        if status['position'] is not None:
                            if sell and not status['pending']:
                                wallet.place_sell(client_id=f'loop-exit-{bar.ts}')
                                decision='SELL';reason='technical_exit';traded+=1
                            else:reason='position_managed_by_protective_orders'
                        elif status['halt_reason']:
                            reason='wallet_risk_halt'
                        elif status['pending']:
                            reason='pending_simulated_order'
                        elif not is_fresh:
                            reason='historical_or_stale_signal'
                        elif not market_ok or not news_ok:
                            reason='unhealthy_public_feeds'
                        elif buy:
                            stake=min(wallet.risk.max_order_quote,
                                      wallet.risk.max_position_fraction*status['equity_net_quote'],
                                      status['cash_quote'])*(1-1e-9)
                            recent=[a for a in articles if
                                  bar_close-c.news_recency_seconds<=a.available_ts<=bar_close
                                  and {'BTC','MARKET','MACRO'}.intersection(a.assets)
                                  and a.polarity>0]
                            if stake<wallet.risk.min_order_quote:
                                reason='stake_below_minimum'
                            elif not recent:
                                reason='no_recent_positive_relevant_news'
                            else:
                                best=None
                                for a in recent:
                                    quality=validated_news_edge(a,articles,bars,settings=c,
                                                fee_settings=wallet.settings,stake=stake)
                                    if quality['approved'] and (best is None or
                                       quality['predicted_gross_move']>best['predicted_gross_move']):
                                        best=quality
                                if best is None:
                                    reason='no_chronologically_validated_news_edge'
                                else:
                                    move=best['predicted_gross_move']
                                    liquidity='maker' if c.prefer_maker_entry else 'taker'
                                    ok,ledger=expected_trade_edge(bar.close,bar.close*(1+move),
                                        stake,wallet.settings,minimum_net_return=c.min_net_edge,
                                        volatility_frac=volatility,holding_hours=c.news_horizon_hours,
                                        entry_liquidity=liquidity)
                                    threshold=minimum_break_even_move(bar.close,stake,wallet.settings,
                                       volatility_frac=volatility,holding_hours=c.news_horizon_hours,
                                       min_net_edge=c.min_net_edge,entry_liquidity=liquidity)
                                    evidence.update({'estimated_gross_move_pct':move*100,
                                       'minimum_gross_move_pct':threshold*100,
                                       'predicted_net_return_pct':ledger.net_return_on_outlay*100,
                                       'news_category':best['category'],
                                       'evidence_as_of':best['evidence_as_of']})
                                    if ok and move>=threshold:
                                        if c.prefer_maker_entry:
                                            price=bar.close*(1-c.maker_entry_discount_bps/10000)
                                            wallet.place_buy(stake,kind='limit',limit_mid=price,
                                               client_id=f'loop-entry-{bar.ts}')
                                        else:
                                            wallet.place_buy(stake,kind='market',
                                               client_id=f'loop-entry-{bar.ts}')
                                        decision='BUY';reason='breakout_and_validated_news_net_edge';traded+=1
                                        evidence['order_type']='maker_limit' if c.prefer_maker_entry else 'market_taker'
                                    else:reason='forecast_below_full_round_trip_costs'
                        journal.log(bar.ts,decision,reason,evidence,now)
                        decisions+=1
                        if is_fresh:reports.append({'ts':bar.ts,'decision':decision,'reason':reason,**evidence})
                    audit=wallet.verify();state=wallet.status()
                    output={'paper_only':True,'processed_new_candles':processed,
                        'new_decisions':decisions,'new_orders':traded,
                        'status':state,'audit':audit,'recent_decisions':reports[-3:]}
                journal.heartbeat('OK',json.dumps({'processed':processed,'new_orders':traded}),now)
                return output
            except Exception as exc:
                journal.heartbeat('ERROR',f'{type(exc).__name__}: {exc}',now)
                raise

"""Research-only trade opportunity diagnostics with an explicit FUTURE-DATA boundary.

This is an oracle upper bound over a *restricted* menu of next-bar opening
executions, not an executable strategy, limit-order fill, or actual missed P&L.
Hindsight labels MUST NEVER be used as same-bar predictions. Trade selection,
model tuning and threshold setting are disallowed on held-out test outcomes.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Sequence
import math

from backtester.engine import BacktestParameters, DonchianBreakout, checked_candles
from data_layer.storage import Candle
from trading_costs import FeeSettings, quantity_for_quote_budget, settle_trade, load_settings


@dataclass(frozen=True)
class HindsightParameters:
    entry_delay_bars: int = 6       # extra opens AFTER next opening; future oracle only
    holding_bars: int = 60          # 10 days at 4h; exit opens after entry
    min_net_edge_pct: float = 0.0   # reported gain, not used for strategy decisions
    stake_quote: float = 50.0       # hypothetical capital per signal, not account total

    def __post_init__(self):
        if (not isinstance(self.entry_delay_bars,int) or not 0 <= self.entry_delay_bars <= 100
                or not isinstance(self.holding_bars,int) or not 1 <= self.holding_bars <= 2000):
            raise ValueError('Invalid hindsight horizons')
        if (not math.isfinite(self.stake_quote) or self.stake_quote <= 0 or
                not math.isfinite(self.min_net_edge_pct) or self.min_net_edge_pct < 0):
            raise ValueError('Invalid hypothetical stake or edge')


def _volatility_prior(bars: Sequence[Candle], at: int) -> float:
    """ATR-like volatility from bars strictly BEFORE hypothetical entry opening."""
    start=max(1,at-14)
    ranges=[max(bars[j].high-bars[j].low,
                abs(bars[j].high-bars[j-1].close),
                abs(bars[j].low-bars[j-1].close))
            for j in range(start,at)]
    return min(1.0, sum(ranges)/len(ranges)/bars[at-1].close) if ranges and at>0 else 0.0


def simulate_hindsight_trade(bars: Sequence[Candle], entry_idx: int, exit_idx: int,
                            *, settings: FeeSettings, stake_quote: float,
                            quantity_base: float | None = None) -> dict:
    """Conservatively compare two NEXT-OPEN mid prices with the unified V6 costs.

    entry_idx and exit_idx are distinct openings; the signal is from the
    PREVIOUS close. No candle high or low is treated as a fillable quote.
    """
    if not (1 <= entry_idx < exit_idx < len(bars)):
        raise ValueError('Open-to-open trade must enter after signal and exit later')
    entry=bars[entry_idx].open
    exit=bars[exit_idx].open
    volatility=_volatility_prior(bars,entry_idx)
    qty=(quantity_base if quantity_base is not None else
         quantity_for_quote_budget(entry,stake_quote,settings,volatility_frac=volatility))
    if not math.isfinite(qty) or qty <= 0:raise ValueError('Invalid BTC quantity')
    ledger=settle_trade(entry,exit,qty,settings,volatility_frac=volatility,
                        holding_hours=(exit_idx-entry_idx)*(bars[1].ts-bars[0].ts)/3600)
    return {'entry_ts':bars[entry_idx].ts,'exit_ts':bars[exit_idx].ts,
            'quantity_base':qty,'gross_pnl_quote':ledger.gross_pnl_quote,
            'fees_quote':ledger.trading_fees_quote,'spread_quote':ledger.spread_quote,
            'slippage_quote':ledger.slippage_quote,
            'net_pnl_quote':ledger.net_pnl_quote,
            'net_return_on_outlay_pct':100*ledger.net_return_on_outlay}


def _best_open_trade(bars: Sequence[Candle], *, start_idx: int, end_idx: int,
                    max_holding_bars: int, settings: FeeSettings, stake_quote: float,
                    quantity_base: float | None = None) -> dict | None:
    """Enumerate delayed entries and later opening exits, never bar extremes."""
    best=None
    for entry in range(start_idx,end_idx+1):
        for exit in range(entry+1,min(len(bars)-1,entry+max_holding_bars)+1):
            cand=simulate_hindsight_trade(bars,entry,exit,settings=settings,
                        stake_quote=stake_quote,quantity_base=quantity_base)
            if best is None or cand['net_pnl_quote']>best['net_pnl_quote']:
                best=cand
    return best


def chronological_folds(length: int, *, min_train_bars: int=600,
                        test_bars: int=180, purge_bars: int=66) -> list[dict]:
    """Expanding training + disjoint holdout windows, separated by embargo.

    Outcomes ending beyond train_end are not allowed in training. For a new
    fold, previous test data can enter training only after their labels mature.
    """
    if any(not isinstance(v,int) or v<=0 for v in
           (length,min_train_bars,test_bars,purge_bars)):
        raise ValueError('Positive integer fold lengths required')
    folds=[]
    start=min_train_bars+purge_bars
    while start+test_bars<=length:
        folds.append({'fold':len(folds)+1,'train_start_idx':0,
                      'train_end_exclusive':start-purge_bars,
                      'purge_start_idx':start-purge_bars,'test_start_idx':start,
                      'test_end_exclusive':start+test_bars,
                      'purge_bars':purge_bars})
        start+=test_bars
    return folds


def analyze_hindsight(candles: Sequence[Candle], backtest: dict,
                      *, settings: FeeSettings | None=None,
                      strategy_params: BacktestParameters | None=None,
                      hindsight_params: HindsightParameters | None=None,
                      score_start_idx: int=0, score_end_idx: int | None=None) -> dict:
    """Describe completed V8 trades and historically unexecuted entry signals.

    score_start_idx/end delimit a fold: only opportunities whose ENTIRE
    future window is inside the fold may be scored. Past bars before the fold
    can warm indicators, but never contribute scored outcomes.
    """
    strategy_params=strategy_params or BacktestParameters()
    settings=settings or load_settings()
    hp=hindsight_params or HindsightParameters()
    bars=checked_candles(candles,strategy_params.interval)
    end=len(bars) if score_end_idx is None else score_end_idx
    if not (0 <= score_start_idx<end<=len(bars)):
        raise ValueError('Invalid scoring region')
    index={b.ts:i for i,b in enumerate(bars)}
    # Closed trades only; don't score still-open positions as missed signals.
    trades=backtest.get('trades')
    if not isinstance(trades,list):raise ValueError('Backtest must contain V8 trade ledger list')
    actual_entries={int(t['entry_ts']) for t in trades}
    opportunity=[]
    for item in trades:
        entry_ts,exit_ts=int(item['entry_ts']),int(item['exit_ts'])
        if entry_ts not in index or exit_ts not in index:
            raise ValueError('Completed trade timestamp missing in candle history')
        i=index[entry_ts];j=index[exit_ts]
        if not (score_start_idx<=i<end) or j>=end:continue
        # Embargo: never inspect price beyond scoring partition.
        if i+hp.entry_delay_bars+hp.holding_bars>=end:continue
        volume=float(item['quantity_base']);actual_net=float(item['net_pnl_quote'])
        best=_best_open_trade(bars,start_idx=i,end_idx=i,
                            max_holding_bars=hp.holding_bars,settings=settings,
                            stake_quote=hp.stake_quote,quantity_base=volume)
        # Additional bounded *entry AND exit* hindsight search. This uses the
        # original simulated entry outlay as a fixed budget so different entry
        # prices cannot secretly increase position size or available capital.
        original_budget=(volume*float(item['entry_execution_price'])+
                         float(item['entry_fee_quote']))
        best_delayed=_best_open_trade(bars,start_idx=i,
                         end_idx=i+hp.entry_delay_bars,
                         max_holding_bars=hp.holding_bars,
                         settings=settings,stake_quote=original_budget)
        opportunity.append({'entry_ts':entry_ts,'actual_exit_ts':exit_ts,
            'actual_net_quote':actual_net,
            'best_next_open_exit_ts':best['exit_ts'],
            'best_next_open_net_quote':best['net_pnl_quote'],
            'best_next_open_gross_quote':best['gross_pnl_quote'],
            'best_next_open_fees_quote':best['fees_quote'],
            'best_next_open_spread_quote':best['spread_quote'],
            'best_next_open_slippage_quote':best['slippage_quote'],
            'difference_best_opens_minus_actual_quote':best['net_pnl_quote']-actual_net,
            'difference_nonnegative_quote':max(0.,best['net_pnl_quote']-actual_net),
            'best_delayed_entry_ts':best_delayed['entry_ts'],
            'best_delayed_exit_ts':best_delayed['exit_ts'],
            'best_delayed_net_quote':best_delayed['net_pnl_quote'],
            'best_delayed_fees_quote':best_delayed['fees_quote'],
            'best_delayed_gross_quote':best_delayed['gross_pnl_quote'],
            'difference_best_delayed_minus_actual_quote':best_delayed['net_pnl_quote']-actual_net,
            'delayed_entry_differs_from_actual':best_delayed['entry_ts']!=entry_ts,
            'best_exit_before_actual':best['exit_ts']<exit_ts,
            'best_exit_after_actual':best['exit_ts']>exit_ts})
    # Replay ONLY prior-close indicators. Missed opportunities are conditional
    # counterfactuals, never fake trades added to account P&L.
    strategy=DonchianBreakout(strategy_params)
    signals=[]
    for i,c in enumerate(bars):
        buy,_=strategy.observe(c)
        if not buy or i<score_start_idx or i>=end:continue
        start=i+1
        if start+hp.entry_delay_bars+hp.holding_bars>=end:continue
        if start>=len(bars):continue
        if bars[start].ts in actual_entries:continue
        best=_best_open_trade(bars,start_idx=start,
                     end_idx=start+hp.entry_delay_bars,
                     max_holding_bars=hp.holding_bars,
                     settings=settings,stake_quote=hp.stake_quote)
        signals.append({'signal_ts':c.ts,'next_executable_ts':bars[start].ts,
                 'hypothetical_best_entry_ts':best['entry_ts'],
                 'hypothetical_best_exit_ts':best['exit_ts'],
                 'hypothetical_best_net_quote':best['net_pnl_quote'],
                 'hypothetical_best_gross_quote':best['gross_pnl_quote'],
                 'hypothetical_best_fees_quote':best['fees_quote'],
                 'positive_hindsight':best['net_return_on_outlay_pct']>hp.min_net_edge_pct,
                 'execution_status':'unmatched_completed_trade',
                 'warning':'May overlap another position or pending order; not attainable cumulative profit'})
    return {'mode':'OFFLINE_HINDSIGHT_ONLY','paper_only':True,
       'future_used_for_decisions':False,'historical_future_used_for_diagnostics':True,
       'oracle_fill_assumption':'future next-bar OPEN fills selected with perfect hindsight; not executable predictions',
       'oracle_cost_model':'V6 taker on both sides, modeled spread and volatility/size slippage',
       'scored_range':[score_start_idx,end],
       'hindsight_parameters':asdict(hp),
       'completed_trades_scored':len(opportunity),
       'unmatched_signals_scored':len(signals),
       'unmatched_profitable_in_hindsight':sum(t['positive_hindsight'] for t in signals),
       'sum_nonnegative_exit_timing_gap_quote_not_earnable':sum(t['difference_nonnegative_quote'] for t in opportunity),
       'realized_completed_net_quote_scored':sum(t['actual_net_quote'] for t in opportunity),
       'trade_exit_diagnostics':opportunity,'unmatched_signal_diagnostics':signals}

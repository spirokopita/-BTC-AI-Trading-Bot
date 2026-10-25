"""Train-only parameter selection, purged chronological tests, and offline replay.

No ML is trained; this is a small, explicit strategy-parameter validation
harness. A held-out test period is NEVER consulted during parameter choice.
Future AI work must implement this same date firewall for labels/features.
"""
from __future__ import annotations
from dataclasses import asdict, replace
from pathlib import Path
import tempfile

from data_layer.storage import Candle
from backtester import BacktestParameters, run_backtest
from backtester.engine import checked_candles
from trading_costs import FeeSettings, load_settings
from paper_engine import RiskLimits
from .analysis import chronological_folds, HindsightParameters, analyze_hindsight


def validate_walk_forward(candles: list[Candle], *, candidates: tuple[BacktestParameters,...],
                          settings: FeeSettings | None=None,
                          risk: RiskLimits | None=None,
                          hindsight_params: HindsightParameters | None=None,
                          min_train_bars: int=720, test_bars: int=180,
                          purge_bars: int=100) -> dict:
    """Score net account returns and hindsight opportunity gaps out of sample.

    Purge must cover the hindsight outcome horizon. Each test starts a FRESH
    paper wallet warmed only with prior bars; no test-tuned parameters.
    """
    if not candidates or not all(x.interval==candidates[0].interval for x in candidates):
        raise ValueError('Candidates must share one interval')
    if purge_bars < (hindsight_params or HindsightParameters()).holding_bars + \
                    (hindsight_params or HindsightParameters()).entry_delay_bars:
        raise ValueError('Purge shorter than possible hindsight label horizon')
    if any(not isinstance(x,BacktestParameters) for x in candidates):
        raise ValueError('All candidates must be BacktestParameters')
    bars=checked_candles(candles,candidates[0].interval)
    folds=chronological_folds(len(bars),min_train_bars=min_train_bars,
                               test_bars=test_bars,purge_bars=purge_bars)
    if not folds:raise ValueError('Not enough candles for purged walk-forward evaluation')
    settings=settings or load_settings()
    risk=risk or RiskLimits()
    hp=hindsight_params or HindsightParameters()
    records=[]
    with tempfile.TemporaryDirectory(prefix='walkforward_paper_') as tmp:
        for fold in folds:
            end_train=fold['train_end_exclusive']
            test_start=fold['test_start_idx']
            test_end=fold['test_end_exclusive']
            scored=[]
            for index,p in enumerate(candidates):
                # Predeclared candidates evaluated exclusively on train-side data.
                train=run_backtest(bars[:end_train],Path(tmp)/f'f{fold["fold"]}_train{index}.sqlite',
                                   settings=settings,risk=risk,params=p)
                scored.append({'candidate':index,'train_net_return_pct':train['total_return_net_pct']})
            selected=max(scored,key=lambda x:(x['train_net_return_pct'],-x['candidate']))['candidate']
            chosen=candidates[selected]
            # Include pre-test history ONLY for indicator initialization. Test
            # trading begins AFTER embargo, with a clean starting balance.
            test=run_backtest(bars[:test_end],Path(tmp)/f'f{fold["fold"]}_test.sqlite',
                              settings=settings,risk=risk,params=chosen,
                              trade_after_ts=bars[test_start].ts)
            hindsight=analyze_hindsight(bars[:test_end],test,settings=settings,
                           strategy_params=chosen,hindsight_params=hp,
                           score_start_idx=test_start,score_end_idx=test_end)
            records.append({'fold':fold['fold'],
               'train_start_ts':bars[0].ts,
               'train_end_ts':bars[end_train-1].ts,
               'test_start_ts':bars[test_start].ts,
               'test_end_ts':bars[test_end-1].ts,
               'embargo_candles':purge_bars,
               'train_candidate_net_returns':scored,
               'selected_candidate_index_FROM_TRAIN_ONLY':selected,
               'selected_parameters':asdict(chosen),
               'test_net_return_pct':test['total_return_net_pct'],
               'test_completed_trades':test['completed_trades'],
               'test_net_win_rate_pct':test['net_win_rate_pct'],
               'test_max_drawdown_pct':test['max_drawdown_pct'],
               'test_sharpe':test['annualized_sharpe_zero_riskfree'],
               'test_total_fees_quote':test['total_trading_fees_quote'],
               'test_hindsight':hindsight})
    return {'mode':'PURGED_WALK_FORWARD_PAPER_ONLY',
      'historical_oracle_not_used_for_parameter_selection':True,
      'test_periods_nonoverlapping':True,
      'note':'Selected on training net returns only; test result is honest, not an optimised live forecast',
      'folds':records,'candidate_grid':[asdict(c) for c in candidates]}

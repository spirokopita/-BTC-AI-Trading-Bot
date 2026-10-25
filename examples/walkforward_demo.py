"""Synthetic, train-only walk-forward grid selection smoke run."""
from dataclasses import replace
import json
from pathlib import Path
from backtester import BacktestParameters
from hindsight import HindsightParameters
from hindsight.walkforward import validate_walk_forward
from examples.backtest_demo import make_bars


def main():
    params=BacktestParameters(breakout_bars=30,exit_low_bars=15,
                               fast_ema_bars=10,slow_ema_bars=30)
    result=validate_walk_forward(make_bars(),candidates=(params,replace(params,breakout_bars=60)),
             hindsight_params=HindsightParameters(entry_delay_bars=2,holding_bars=10),
             min_train_bars=300,test_bars=110,purge_bars=70)
    report={'provenance':'SYNTHETIC CANDLES: NOT KRAKEN OR A REAL TRADING TRACK RECORD',
            'future_oracle_used_to_pick_parameters':False,
            'folds':[{'fold':x['fold'],
                      'selected_candidate_index_from_train':x['selected_candidate_index_FROM_TRAIN_ONLY'],
                      'test_net_return_pct':x['test_net_return_pct'],
                      'test_completed_trades':x['test_completed_trades'],
                      'test_hindsight_trade_count':x['test_hindsight']['completed_trades_scored']}
                     for x in result['folds']]}
    path=Path(__file__).resolve().parents[1]/'reports'/'walkforward_synthetic_demo.json'
    path.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()

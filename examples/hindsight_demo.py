"""Deterministic SYNTHETIC hindsight software test; no genuine BTC prices."""
from pathlib import Path
import json
from tempfile import TemporaryDirectory
from backtester import compare_costs, BacktestParameters
from hindsight import analyze_hindsight, HindsightParameters
from examples.backtest_demo import make_bars


def main():
    with TemporaryDirectory() as directory:
        bars=make_bars()
        result=compare_costs(bars,Path(directory)/'replay')
        report=analyze_hindsight(bars,result['fee_on'])
        output={'provenance':'SYNTHETIC FABRICATED CANDLES - NOT HISTORICAL RETURNS',
                'net_account_return_pct':result['fee_on']['total_return_net_pct'],
                'trade_count':result['fee_on']['completed_trades'],
                'trade_diagnostics':report['trade_exit_diagnostics'],
                'missed_signal_count':report['unmatched_signals_scored'],
                'positive_what_if_count':report['unmatched_profitable_in_hindsight'],
                'sum_non_earnable_hindsight_exit_gap_quote':report['sum_nonnegative_exit_timing_gap_quote_not_earnable']}
        path=Path(__file__).resolve().parents[1]/'reports'/'hindsight_synthetic_demo.json'
        path.write_text(json.dumps(output,indent=2,allow_nan=False),encoding='utf-8')
        print(json.dumps({k:v for k,v in output.items() if k!='trade_diagnostics'},indent=2))

if __name__=='__main__':main()

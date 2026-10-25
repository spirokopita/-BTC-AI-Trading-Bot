"""Offline V8 backtest + V9 fee-aware future-analysis; input DB must exist."""
import argparse
from dataclasses import replace
import json
from pathlib import Path
from backtester.engine import candles_from_store, compare_costs, BacktestParameters
from trading_costs import load_settings
from .analysis import HindsightParameters, analyze_hindsight
from .walkforward import validate_walk_forward


def main(argv=None):
    p=argparse.ArgumentParser(description='PAPER-ONLY historical hindsight / purged walk-forward')
    p.add_argument('--market-db',default='data/market.sqlite')
    p.add_argument('--out',required=True,help='New, empty output directory')
    p.add_argument('--interval',type=int,default=240,choices=[1,5,15,30,60,240,720,1440])
    p.add_argument('--entry-delay',type=int,default=6)
    p.add_argument('--holding-bars',type=int,default=60)
    p.add_argument('--walk-forward',action='store_true')
    p.add_argument('--min-train',type=int,default=720)
    p.add_argument('--test-bars',type=int,default=180)
    p.add_argument('--purge-bars',type=int,default=100)
    args=p.parse_args(argv)
    src=Path(args.market_db)
    if not src.is_file():p.error('Missing historical Kraken BTC/AUD database')
    out=Path(args.out)
    if out.exists():p.error('Output directory exists; must be NEW (no overwrite)')
    pars=BacktestParameters.for_interval(args.interval)
    hp=HindsightParameters(entry_delay_bars=args.entry_delay,holding_bars=args.holding_bars)
    bars,provenance=candles_from_store(src,args.interval)
    # Validate BEFORE creating an output directory, including missing history.
    from backtester.engine import checked_candles
    try:
        checked_candles(bars,args.interval)
        if args.walk_forward:
            candidates=(pars,replace(pars,breakout_bars=pars.breakout_bars*2))
            report=validate_walk_forward(bars,candidates=candidates,hindsight_params=hp,
                min_train_bars=args.min_train,test_bars=args.test_bars,purge_bars=args.purge_bars)
        else:
            report=None
    except ValueError as e:p.error(str(e))
    out.mkdir(parents=True)
    if report is None:
        replay=compare_costs(bars,out/'backtest',params=pars)
        hindsight=analyze_hindsight(bars,replay['fee_on'],
                       strategy_params=pars,hindsight_params=hp)
        report={'replay':replay,'hindsight':hindsight}
    report['provenance']=provenance
    report['provenance']['verified_exchange_provenance']=False
    report['WARNING']='Historical outcomes include perfect hindsight; no new market advantage established'
    (out/'hindsight.json').write_text(json.dumps(report,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps({'mode':'PAPER_ONLY','output':str(out/'hindsight.json'),
       'provenance':provenance,'walk_forward':args.walk_forward},indent=2))

if __name__=='__main__':main()

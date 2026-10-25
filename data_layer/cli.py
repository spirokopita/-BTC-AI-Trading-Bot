"""CLI for local Kraken candle ingestion. No trading permissions or secrets."""
import argparse
import json
from pathlib import Path
from .storage import CandleStore,import_csv,import_kraken_zip,SUPPORTED
from .kraken import KrakenOHLC,sync


def main(argv=None):
    a=argparse.ArgumentParser(description='Kraken OHLCVT: paper-only historical data layer')
    a.add_argument('--db',default='data/market.sqlite',help='Persistent SQLite path')
    sub=a.add_subparsers(dest='cmd',required=True)
    sp=sub.add_parser('sync',help='Fetch recent CLOSED BTC/AUD candles from Kraken free public API')
    sp.add_argument('--intervals',nargs='+',type=int,default=[60,240,1440])
    imp=sub.add_parser('import-csv',help='Import Kraken OHLCVT timestamp/OHLC/volume/trades CSV')
    imp.add_argument('file',type=Path);imp.add_argument('--interval',type=int,required=True)
    zp=sub.add_parser('import-zip',help='Stream BTC/AUD files from official Kraken OHLCVT ZIP')
    zp.add_argument('file',type=Path);zp.add_argument('--intervals',nargs='+',type=int,default=[60,240,1440])
    rp=sub.add_parser('report',help='Describe stored coverage, no artificial candle filling')
    rp.add_argument('--intervals',nargs='+',type=int,default=[60,240,1440])
    ep=sub.add_parser('export',help='Export raw UTC Unix-time candle CSV for backtesting')
    ep.add_argument('file',type=Path);ep.add_argument('--interval',type=int,required=True)
    args=a.parse_args(argv)
    intervals=getattr(args,'intervals',[getattr(args,'interval',240)])
    if any(x not in SUPPORTED for x in intervals):a.error(f'Valid minute intervals: {SUPPORTED}')
    with CandleStore(args.db) as store:
        if args.cmd=='sync':
            api=KrakenOHLC()
            results=[sync(store,api,i) for i in args.intervals]
        elif args.cmd=='import-csv':results=import_csv(store,args.file,args.interval)
        elif args.cmd=='import-zip':results=import_kraken_zip(store,args.file,args.intervals)
        elif args.cmd=='export':results={'exported_rows':store.export_csv(args.file,interval=args.interval),'file':str(args.file)}
        else:
            results=[]
            for i in args.intervals:
                cover=store.coverage(interval=i)
                gaps=store.gaps(interval=i)
                results.append({'interval':i,'coverage':cover,'gaps':gaps[:50],
                      'gap_count':len(gaps),'missing_intervals_total':sum(x['missing_intervals'] for x in gaps),
                      'important':'Gaps can also mean zero trades; we do not fill them'})
        print(json.dumps(results,indent=2))
    return results


if __name__=='__main__':main()

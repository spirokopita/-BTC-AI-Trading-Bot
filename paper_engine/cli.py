"""Local CLI for a PAPER wallet. Never sends orders outside SQLite."""
import argparse
import csv
import json
from pathlib import Path
from data_layer.storage import Candle
from .engine import PaperEngine, RiskLimits


def main(argv=None):
    p=argparse.ArgumentParser(description='Offline BTC/AUD simulator. PAPER TRADES ONLY.')
    p.add_argument('--db',default='data/paper_wallet.sqlite')
    p.add_argument('--interval',type=int,default=240)
    sub=p.add_subparsers(dest='command',required=True)
    init=sub.add_parser('init')
    init.add_argument('--starting-cash',type=float,default=1000)
    buy=sub.add_parser('buy')
    buy.add_argument('--budget',type=float,required=True)
    buy.add_argument('--limit',type=float)
    buy.add_argument('--stop-pct',type=float,default=.045)
    buy.add_argument('--target-pct',type=float,default=.075)
    buy.add_argument('--client-id')
    sell=sub.add_parser('sell')
    sell.add_argument('--limit',type=float)
    sell.add_argument('--client-id')
    cancel=sub.add_parser('cancel')
    cancel.add_argument('order_id',type=int)
    tick=sub.add_parser('candle')
    for k in ('ts','open','high','low','close','volume'):
        tick.add_argument('--'+k,type=int if k=='ts' else float,required=True)
    tick.add_argument('--volatility',type=float,default=0.)
    tick.add_argument('--allow-gap',action='store_true')
    replay=sub.add_parser('replay-csv')
    replay.add_argument('file',type=Path)
    replay.add_argument('--limit',type=int)
    replay.add_argument('--allow-gap',action='store_true')
    for cmd in ('status','orders','trades','verify'):
        sub.add_parser(cmd)
    args=p.parse_args(argv)
    kw={'risk':RiskLimits(starting_cash=args.starting_cash)} if args.command=='init' else {}
    with PaperEngine(args.db,interval=args.interval,**kw) as engine:
        if args.command=='init': result=engine.status()
        elif args.command=='buy':
            oid=engine.place_buy(args.budget,kind='limit' if args.limit is not None else 'market',
                limit_mid=args.limit,stop_pct=args.stop_pct,target_pct=args.target_pct,client_id=args.client_id)
            result={'paper_order_id':oid,'status':'pending'}
        elif args.command=='sell':
            oid=engine.place_sell(kind='limit' if args.limit is not None else 'market',
                  limit_mid=args.limit,client_id=args.client_id)
            result={'paper_order_id':oid,'status':'pending'}
        elif args.command=='cancel':engine.cancel(args.order_id);result={'cancelled':args.order_id}
        elif args.command=='candle':
            result=engine.on_candle(Candle(args.ts,args.open,args.high,args.low,args.close,args.volume),
                                    volatility_frac=args.volatility,allow_gap=args.allow_gap)
        elif args.command=='replay-csv':
            count=0; skipped=0
            if args.limit is not None and args.limit<=0:
                raise ValueError('--limit must be > 0')
            previous=engine.status()['last_ts']
            with args.file.open(newline='') as stream:
                for r in csv.DictReader(stream):
                    c=Candle(int(r['timestamp']),float(r['open']),float(r['high']),
                             float(r['low']),float(r['close']),float(r['volume']))
                    if previous is not None and c.ts<previous:
                        skipped+=1
                        continue
                    result_one=engine.on_candle(c,allow_gap=args.allow_gap)
                    if result_one['duplicate']:
                        skipped+=1
                        continue
                    count+=1
                    if args.limit is not None and count>=args.limit:break
            result={'candles_processed':count,'already_processed_skipped':skipped,
                    'status':engine.status()}
        elif args.command=='status':result=engine.status()
        elif args.command=='orders':result=engine.orders()
        elif args.command=='trades':result=engine.trades()
        else:result=engine.verify()
    print(json.dumps(result,indent=2,sort_keys=True,allow_nan=False))

if __name__=='__main__':main()

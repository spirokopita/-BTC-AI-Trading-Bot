"""Run an unattended local paper-only BTC/AUD strategy loop.

`serve` uses read-only public market/news requests. There is no private Kraken
trading interface or key. To stop press Ctrl-C or stop the systemd service.
"""
from __future__ import annotations
import argparse
from contextlib import contextmanager
import fcntl
import json
from pathlib import Path
import sys
import time

from data_layer.kraken import KrakenOHLC, sync as market_sync
from data_layer.storage import CandleStore
from news_intelligence.cli import sync as news_sync
from news_intelligence.store import NewsStore
from strategy_loop.engine import PaperStrategyLoop,LoopSettings,DecisionJournal


@contextmanager
def instance_lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a+') as file:
        try:fcntl.flock(file.fileno(),fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as e:raise RuntimeError('Another paper loop is running') from e
        yield
        fcntl.flock(file.fileno(),fcntl.LOCK_UN)


def collect(market:Path, news:Path, interval:int, *, now:int,
            market_fetch=market_sync, news_fetch=news_sync) -> tuple[dict,bool,bool]:
    """Sources fail independently. Neither a failed source nor stale cache can authorize buys."""
    report={'paper_only':True,'market':None,'news':None}
    try:
        with CandleStore(market) as db:
            report['market']=market_fetch(db,KrakenOHLC(),interval)
        market_ok=True
    except Exception as exc:
        report['market']={'error':f'{type(exc).__name__}: {exc}'}
        market_ok=False
    try:
        with NewsStore(news) as db: report['news']=news_fetch(db,now=now)
        news_ok=bool(report['news']['feeds']) and all(item.get('status')!='error' for item in report['news']['feeds'])
    except Exception as exc:
        report['news']={'error':f'{type(exc).__name__}: {exc}'}
        news_ok=False
    return report,market_ok,news_ok


def parser():
    ap=argparse.ArgumentParser(description='BTC/AUD 24/7 PAPER ONLY bot (never sends exchange orders)')
    ap.add_argument('command',choices=['once','serve','status'])
    ap.add_argument('--market-db',default='data/market.sqlite')
    ap.add_argument('--news-db',default='data/news.sqlite')
    ap.add_argument('--wallet-db',default='data/loop_wallet.sqlite')
    ap.add_argument('--journal-db',default='data/loop_journal.sqlite')
    ap.add_argument('--interval',type=int,choices=[60,240,1440],default=240)
    ap.add_argument('--poll-seconds',type=int,default=60)
    ap.add_argument('--sync-seconds',type=int,default=900)
    ap.add_argument('--no-network',action='store_true',help='Use only existing cached candles and news')
    return ap


def main(argv=None):
    ap=parser();args=ap.parse_args(argv)
    if args.poll_seconds<10 or args.sync_seconds<60:
        ap.error('poll-seconds >=10 and sync-seconds >=60 are required')
    market=Path(args.market_db);news=Path(args.news_db)
    wallet=Path(args.wallet_db);journal=Path(args.journal_db)
    loop=PaperStrategyLoop(market,news,wallet,journal,config=LoopSettings(interval=args.interval))
    if args.command=='status':
        with DecisionJournal(journal) as db:
            print(json.dumps({'paper_only':True,'decisions':db.recent()},indent=2));return
    with instance_lock(journal.with_suffix('.lock')):
        failures=0;last_sync=None;feed_ok=(False,False)
        while True:
            now=int(time.time())
            try:
                if not args.no_network and (last_sync is None or now-last_sync>=args.sync_seconds):
                    report,*feed_ok=collect(market,news,args.interval,now=now)
                    last_sync=now
                else:report={'mode':'local_cache','network':'not_attempted'}
                # --no-network is intentionally allowed for OFFLINE paper replay;
                # no external network health claim is made.
                state=loop.once(now=now,market_ok=feed_ok[0] if not args.no_network else True,
                                news_ok=feed_ok[1] if not args.no_network else True)
                print(json.dumps({'run_utc':now,'collection':report,'paper_loop':state},
                                 default=str,allow_nan=False),flush=True)
                failures=0
            except Exception as exc:
                failures+=1
                print(json.dumps({'paper_only':True,'status':'error','utc':now,
                                  'exception':f'{type(exc).__name__}: {exc}'}),
                      file=sys.stderr,flush=True)
                if args.command=='once':raise
            if args.command=='once':break
            # Bounded exponential wait, so intermittent failures don't spin CPU.
            time.sleep(min(max(10,args.poll_seconds)*(2**min(failures,4)),600))


if __name__=='__main__':main()

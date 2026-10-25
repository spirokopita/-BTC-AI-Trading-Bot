"""News ingestion/event-study CLI. Network read-only; trading always paper-only."""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import time
from data_layer.storage import CandleStore,Candle
from .feeds import DEFAULT_FEEDS,fetch_feed,FeedSource,parse_feed
from .store import NewsStore
from .signals import event_study,train_signal_quality,category_impact_summary


def iso_ts(value):
    if value is None:return int(time.time())
    d=datetime.fromisoformat(value.replace('Z','+00:00'))
    if d.tzinfo is None:raise ValueError('Timestamp must have timezone')
    return int(d.astimezone(timezone.utc).timestamp())


def sync(db: NewsStore, *, now:int|None=None, fetcher=fetch_feed):
    """Read only news feeds. Errors per feed are persisted; other feeds continue."""
    now=int(time.time()) if now is None else int(now)
    reports=[]
    for source in DEFAULT_FEEDS:
        prior=db.feed_headers(source.name)
        try:
            data=fetcher(source,observed_at=now,etag=prior.get('etag'),
                last_modified=prior.get('last_modified'))
            result=db.ingest(data.get('items',[]))
            db.record_feed_attempt(source.name,now,success=True,etag=data.get('etag'),
                                   last_modified=data.get('last_modified'))
            reports.append({'feed':source.name,'status':'not_modified' if data['not_modified'] else 'ok',**result})
        except Exception as exc:
            db.record_feed_attempt(source.name,now,success=False,error=f'{type(exc).__name__}: {exc}')
            reports.append({'feed':source.name,'status':'error','error':f'{type(exc).__name__}: {exc}'})
    return {'paper_only':True,'feeds':reports,'total_inserted':sum(x.get('inserted',0) for x in reports)}


def study_from_dbs(*, news_db:Path,market_db:Path,interval:int,
                   horizons_hours:tuple[int,...],as_of_ts:int):
    if not news_db.is_file() or not market_db.is_file():
        raise ValueError('News and market databases must exist; import actual market data first')
    with NewsStore(news_db) as news:
        items=news.items(end=as_of_ts)
    if not items:raise ValueError('News database has no observed articles by as-of time')
    with CandleStore(market_db) as prices:
        src=[row for row in prices.candles(interval=interval,end=as_of_ts)
             if row['ts']+interval*60 <= as_of_ts]
    bars=[Candle(x['ts'],x['o'],x['h'],x['l'],x['c'],x['v'],x['trades']) for x in src]
    if not bars:raise ValueError('Genuine Kraken BTC/AUD candle store is empty')
    if not all(x['source'].startswith(('kraken_zip:','kraken_csv:','kraken_api:')) for x in src):
        raise ValueError('Unknown OHLC source; refusing retrospective price attribution')
    studied=event_study(items,bars,interval=interval,horizons_hours=horizons_hours)
    studied['category_impact_summary']=category_impact_summary(studied)
    studied['news_count']=len(items)
    studied['market_candles']=len(bars)
    studied['market_provenance']={'source_claims':sorted(set(x['source'] for x in src)),
                                  'genuine_verified_by_external_authority':False}
    # Does NOT expose signal for news observed after the as_of timestamp.
    studied['quality_by_horizon']={str(h):train_signal_quality(studied,horizon_hours=h,
                                         as_of_ts=as_of_ts) for h in horizons_hours}
    return studied


def main(argv=None):
    ap=argparse.ArgumentParser(description='BTC/AUD news intelligence (NO TRADING)')
    ap.add_argument('--news-db',default='data/news.sqlite')
    sub=ap.add_subparsers(dest='command',required=True)
    sub.add_parser('sync',help='Read configured HTTPS RSS feeds and cache with first-seen timestamps')
    p=sub.add_parser('report',help='Fee-aware observed-news correlation with cached BTC/AUD OHLC')
    p.add_argument('--market-db',default='data/market.sqlite')
    p.add_argument('--interval',type=int,default=240,choices=(60,240,1440))
    p.add_argument('--horizons',default='4,24,48',help='Hours, divisible by selected interval')
    p.add_argument('--as-of',default=None,help='ISO8601 with timezone; defaults to now')
    p.add_argument('--output',required=True)
    args=ap.parse_args(argv)
    try:
        if args.command=='sync':
            with NewsStore(args.news_db) as db:result=sync(db)
        else:
            horizons=tuple(int(s) for s in args.horizons.split(','))
            if not horizons:raise ValueError('At least one horizon needed')
            result=study_from_dbs(news_db=Path(args.news_db),market_db=Path(args.market_db),
                    interval=args.interval,horizons_hours=horizons,as_of_ts=iso_ts(args.as_of))
            path=Path(args.output)
            if path.exists():raise ValueError('Refuse to overwrite existing news analysis')
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text(json.dumps(result,indent=2,allow_nan=False),encoding='utf-8')
        print(json.dumps(result if args.command=='sync' else {
            'paper_only':True,'article_count':result['news_count'],
            'scored_observations':len(result['results']),'output':str(path),
            'qualified_by_horizon':{h:v['qualified_categories'] for h,v in result['quality_by_horizon'].items()}},indent=2))
    except (ValueError,OSError) as exc:ap.error(str(exc))

if __name__=='__main__':main()

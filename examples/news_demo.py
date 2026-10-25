"""Fabricated news and price series ONLY, for non-predictive software checks."""
from datetime import datetime,timezone
import json
from pathlib import Path
from data_layer.storage import Candle
from news_intelligence import FeedSource,NewsStore,parse_feed,event_study,train_signal_quality
import tempfile


def main():
    base=int(datetime(2026,1,1,tzinfo=timezone.utc).timestamp());step=14400
    candles=[]
    for i in range(120):
        close=100+i*.1
        candles.append(Candle(base+i*step,close,close+.3,close-.3,close,10))
    news=f'''<rss><channel><item><title>Bitcoin ETF approved, inflows rise</title>
        <link>https://example.org/fabricated-etf-story</link>
        <pubDate>Fri, 02 Jan 2026 00:00:00 GMT</pubDate></item></channel></rss>'''
    with tempfile.TemporaryDirectory() as tmp:
        with NewsStore(Path(tmp)/'news.sqlite') as db:
            parsed=parse_feed(news.encode(),FeedSource('synthetic','https://example.org/rss'),
                            observed_at=base+8*step)
            db.ingest(parsed)
            studied=event_study(db.items(),candles,interval=240,horizons_hours=(4,24))
            qualified=train_signal_quality(studied,horizon_hours=24,as_of_ts=base+100*step)
            out={'label':'FABRICATED STORY AND PRICES / NOT BITCOIN MARKET EVIDENCE',
                 'scored':len(studied['results']),'qualified_categories':qualified['qualified_categories'],
                 'first_event':studied['results'][0]}
            path=Path(__file__).resolve().parents[1]/'reports'/'news_synthetic_demo.json'
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text(json.dumps(out,indent=2),encoding='utf-8')
            print(json.dumps(out,indent=2))

if __name__=='__main__':main()

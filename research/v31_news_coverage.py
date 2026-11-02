"""V31 historical news coverage check: descriptive convenience sample, NOT a signal.
Article publication times are retrospective and revisions may be unobserved.
"""
from __future__ import annotations
import argparse, hashlib, json
from datetime import datetime, timezone
from pathlib import Path
from research.kraken_archive import load
from research.v30_matched_news import matched_study

DAY=86400
KIND="RETROSPECTIVE_CONVENIENCE_SAMPLE_NOT_FIRST_OBSERVED_NOT_REPRESENTATIVE"

def utc_timestamp(value):
    if not isinstance(value,str) or not value.endswith("Z"):
        raise ValueError("Explicit UTC publication timestamp required")
    return int(datetime.fromisoformat(value.replace("Z","+00:00")).timestamp())

def parse_news(path):
    raw=Path(path).read_bytes()
    data=json.loads(raw)
    if data.get("dataset_type")!=KIND: raise ValueError("Wrong news provenance")
    seen_ids=set(); seen_urls=set(); clustered={}
    for item in data["articles"]:
        pub=utc_timestamp(item["published_at_utc"])
        rev=utc_timestamp(item.get("updated_at_utc",item["published_at_utc"]))
        if rev<pub or item["id"] in seen_ids or item["url"] in seen_urls:
            raise ValueError("Invalid revision, duplicate ID or URL")
        if not item["url"].startswith("https://") or item["polarity"] not in (-1,0,1):
            raise ValueError("Invalid source or polarity")
        if not item.get("displayed_time") or not item.get("cluster"):
            raise ValueError("Missing timestamp provenance or event cluster")
        seen_ids.add(item["id"]);seen_urls.add(item["url"])
        # +24h is a conservative availability scenario, not proof of first-seen.
        available=max(pub,rev)+DAY
        row=dict(id=item["id"],category=item["category"],sentiment=item["polarity"],
            available_ts=available,published_ts=pub,market_following=item["market_following"],
            cluster=item["cluster"],url=item["url"])
        if row["cluster"] not in clustered or row["available_ts"]<clustered[row["cluster"]]["available_ts"]:
            clustered[row["cluster"]]=row
    chosen=sorted(clustered.values(),key=lambda e:e["available_ts"])
    return chosen,dict(raw_articles=len(data["articles"]),unique_clusters=len(chosen),
        duplicate_articles=len(data["articles"])-len(chosen),
        market_following_clusters=sum(x["market_following"] for x in chosen),
        neutral_clusters=sum(x["sentiment"]==0 for x in chosen),
        sha256=hashlib.sha256(raw).hexdigest())

def run(bars,news_path,market):
    events,prov=parse_news(news_path)
    # No price-dependent event selection; all first-of-cluster articles are retained.
    report=matched_study(bars,events)
    return dict(mode="PAPER_ONLY_RETROSPECTIVE_DESCRIPTIVE_V31",
        market=market,news=prov,matched=report,
        selection="HOLD",promotion="REJECTED_NO_UNTOUCHED_NEWS_EDGE",
        limitations=["11 convenience-sampled articles, NOT representative or random",
            "Source versions not archived; retrospective publication times are NOT first-observed",
            "24h information latency is an assumption, NOT verified historical accessibility",
            "Two market-following stories are included to expose price-reporting leakage risk",
            "Overlapping articles grouped by topic; matched controls are observational",
            "No headline-based strategy trained or promoted; 80bps current fee scenario"])
def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument("--csv",default=None)
    p.add_argument("--news",default="data/historical_news_supplement_v31.json")
    p.add_argument("--output",default="audit/v31-news-coverage.json")
    a=p.parse_args(argv)
    bars,market=load(a.csv)
    report=run(bars,a.news,market)
    out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,indent=2,allow_nan=False)+"\n")
    print(json.dumps(dict(news=report["news"],summary=report["matched"]["summary"],
        omissions=report["matched"]["omissions"],selection="HOLD"),indent=2))
if __name__=="__main__":main()

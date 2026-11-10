"""V40 outcome-independent bounded monthly historical news metadata sampling.
Reuses V38 allowlisted public adapter with <=12 monthly requests per invocation.
No article bodies, invented historical first-seen timestamps, or paid services.
"""
from __future__ import annotations
import argparse
import collections
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

MONTH_PRIORITY = (2, 5, 8, 11, 3, 6, 9, 12)
QUARTERLY = frozenset((1, 4, 7, 10))
MAX_MONTHS_PER_RUN = 12

def candidate_months(limit=MAX_MONTHS_PER_RUN):
    if not 1 <= limit <= MAX_MONTHS_PER_RUN:
        raise ValueError("Monthly request cap exceeded")
    months = []
    for m in MONTH_PRIORITY:
        for year in range(2020, 2027):
            if year == 2026 and m > 10:
                continue
            if m in QUARTERLY:
                raise AssertionError("Unexpected repeat of quarterly sample")
            months.append(f"{year}-{m:02d}")
    return tuple(months[:limit])

def sample_months(months, retrieved_at, fetcher=None):
    """Single-threaded monthly adapter; always restore global V38 config."""
    from research import v38_archive_ingest as ingest
    if len(months) > MAX_MONTHS_PER_RUN or len(set(months)) != len(months):
        raise ValueError("Invalid sampling plan")
    fetcher = fetcher or ingest.source_fetch
    original = ingest.MONTHS
    rows = []
    status = {}
    try:
        for month in months:
            if month not in candidate_months(MAX_MONTHS_PER_RUN):
                raise ValueError("Month outside predeclared plan")
            ingest.MONTHS = (month,)
            try:
                new, note = fetcher("cryptocurrency_cv", retrieved_at)
                ok = note == "OK_DATE_FILTERS_VERIFIED"
                for row in new:
                    if "cryptocurrency_cv" not in row.get("source_ids", []):
                        raise ValueError("Unexpected news source")
                    if not row.get("published_at_utc", "").startswith(month):
                        raise ValueError("Article outside requested UTC month")
                    if row.get("first_verified_capture_at_utc"):
                        raise ValueError("API metadata is not independently verified WARC")
                rows.extend(new)
                status[month] = {"rows":len(new),"status":note,
                                 "ok":ok,"zero_rows":len(new)==0}
            except Exception as exc:
                status[month] = {"rows":0,
                    "status":type(exc).__name__+": "+str(exc)[:220],
                    "ok":False,"zero_rows":True}
    finally:
        ingest.MONTHS = original
    return ingest.merge(rows), status

def build(months, retrieved_at, fetcher=None, bars=None):
    from research import v38_archive_ingest as ingest
    rows, status = sample_months(months, retrieved_at, fetcher)
    months_counts = collections.Counter(r["published_at_utc"][:7] for r in rows)
    return {"schema":"v38_metadata_provenance_1",
        "retrieved_at_utc":retrieved_at,
        "source_status":{"cryptocurrency_cv":{"fetched_rows":len(rows),
            "status":"V40_MONTHLY_12_OR_FEWER_BOUNDED_PUBLIC_REQUESTS",
            "per_month":status}},
        "raw_normalized_rows":len(rows),"deduplicated_rows":len(rows),
        "historical_article_version_rows":len(rows),
        "archive_months_requested":list(months),
        "archive_months_with_crypto_rows":dict(sorted(months_counts.items())),
        "archive_months_missing_crypto":[m for m in months if months_counts[m]==0],
        "historically_verified_capture_rows":0,
        "months":dict(sorted(months_counts.items())),
        "official_event_date_only_months":{},"official_release_clock_rows":0,
        "target_2020_2026":10000,"target_met":len(rows)>=10000,
        "market_join":ingest.join_market(rows,bars) if bars else
            {"status":"NOT_ATTEMPTED_NO_VERIFIED_BARS"},
        "market_fetch":"OFFICIAL_KRAKEN_ARCHIVE" if bars else "NOT_ATTEMPTED",
        "costs_bps":{"taker_each_side":80,"half_spread_each_side":5,
                     "slippage_each_side":5},
        "max_paper_entry_aud":100,"paper_starting_cash_aud":1000,
        "android_strategy":"HOLD",
        "notes":["Article metadata only; publisher rights retained",
            "API published_at is retrospective, NOT first-verified crawl",
            "No verified as-of news signal created from source claims",
            "Sampling calendar fixed independently of BTC returns",
            "Cumulative article target assessed by separate persist job"],
        "records":rows}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--output",default="audit/v40-monthly-news.json")
    ap.add_argument("--with-kraken",action="store_true")
    a=ap.parse_args()
    bars=None
    market_error=None
    if a.with_kraken:
        try:
            from research.v33_cross_regime import archive
            from research.v32_segments import segments
            allbars,_=archive()
            left,right=max(segments(allbars,1000),key=lambda pair:pair[1]-pair[0])
            bars=allbars[left:right]
        except Exception as exc:
            market_error=type(exc).__name__+": "+str(exc)[:180]
    now=datetime.now(timezone.utc).isoformat()
    audit=build(candidate_months(),now,bars=bars)
    if market_error:
        audit["market_fetch"]="BLOCKED: "+market_error
    p=Path(a.output)
    p.parent.mkdir(parents=True,exist_ok=True)
    raw=(json.dumps(audit,sort_keys=True,indent=2,ensure_ascii=False)+"\n").encode()
    p.write_bytes(raw)
    print(json.dumps({"sha256":hashlib.sha256(raw).hexdigest(),
        "rows":len(audit["records"]),
        "months":audit["source_status"]["cryptocurrency_cv"]["per_month"],
        "market_join":audit["market_join"],
        "paper_policy":audit["android_strategy"]}))

if __name__=="__main__":
    main()

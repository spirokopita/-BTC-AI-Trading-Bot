"""V41 persistent, bounded monthly historical article sampling.

The cursor tracks attempted, completed, empty and retryable months separately.
Only metadata is retained; publication/retrieval/capture timestamps remain distinct.
No API publication timestamp is ever promoted to a historical first-observed time.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

MAX_MONTHS_PER_RUN = 12
CURSOR_PATH = "data/historical_news_sampling_cursor_v41.json"
SCHEMA = "v41_monthly_sampling_cursor_1"


def month_scope():
    return tuple(f"{year}-{month:02d}"
                 for year in range(2020, 2027)
                 for month in range(1, 11))


def load_cursor(path=CURSOR_PATH):
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError("Persistent V41 sampling cursor missing")
    doc = json.loads(p.read_text(encoding="utf-8"))
    if doc.get("schema") != SCHEMA:
        raise ValueError("Unknown monthly cursor schema")
    for field in ("attempted_months", "completed_months", "retry_months"):
        values = doc.get(field)
        if not isinstance(values, list) or len(values) != len(set(values)):
            raise ValueError("Invalid cursor field: " + field)
    scope = set(month_scope())
    if not set(doc["attempted_months"]).issubset(scope):
        raise ValueError("Cursor contains months outside frozen scope")
    if not set(doc["completed_months"]).issubset(set(doc["attempted_months"])):
        raise ValueError("Completed months must have been attempted")
    if not set(doc["retry_months"]).issubset(set(doc["attempted_months"])):
        raise ValueError("Retry months must have been attempted")
    return doc


def candidate_months(cursor, limit=MAX_MONTHS_PER_RUN):
    if not 1 <= limit <= MAX_MONTHS_PER_RUN:
        raise ValueError("Monthly request cap exceeded")
    attempted = set(cursor["attempted_months"])
    retry = [m for m in cursor["retry_months"] if m in attempted]
    remaining = [m for m in month_scope() if m not in attempted]
    ordered = list(dict.fromkeys(retry + remaining))
    return tuple(ordered[:limit])


def retryable_status(status):
    text = str(status).lower()
    return any(token in text for token in (
        "429", "500", "502", "503", "504", "timeout",
        "timed out", "urlerror", "temporarily unavailable",
        "connection reset", "remote end closed",
    ))


def sample_months(months, retrieved_at, fetcher=None):
    """Single-threaded source calls; restore V38 MONTHS even after failures."""
    from research import v38_archive_ingest as ingest
    if len(months) > MAX_MONTHS_PER_RUN or len(set(months)) != len(months):
        raise ValueError("Invalid sampling plan")
    if any(m not in month_scope() for m in months):
        raise ValueError("Month outside frozen 2020-01..2026-10 scope")
    fetcher = fetcher or ingest.source_fetch
    original = ingest.MONTHS
    rows = []
    status = {}
    try:
        for month in months:
            ingest.MONTHS = (month,)
            try:
                new, note = fetcher("cryptocurrency_cv", retrieved_at)
                ok = note == "OK_DATE_FILTERS_VERIFIED"
                for row in new:
                    if "cryptocurrency_cv" not in row.get("source_ids", []):
                        raise ValueError("Unexpected source in monthly response")
                    if not row.get("published_at_utc", "").startswith(month):
                        raise ValueError("Article outside requested UTC publication month")
                    if row.get("first_verified_capture_at_utc"):
                        raise ValueError("Archive API metadata is not WARC capture proof")
                    if row.get("availability_confidence") == "verified_crawl":
                        raise ValueError("Retrospective API row mislabeled as verified crawl")
                rows.extend(new)
                status[month] = {
                    "rows": len(new), "status": note, "ok": ok,
                    "zero_rows": len(new) == 0,
                    "retryable": (not ok and retryable_status(note)),
                }
            except Exception as exc:
                note = type(exc).__name__ + ": " + str(exc)[:220]
                status[month] = {
                    "rows": 0, "status": note, "ok": False,
                    "zero_rows": True, "retryable": retryable_status(note),
                }
    finally:
        ingest.MONTHS = original
    return ingest.merge(rows), status


def advance_cursor(cursor, months, status, retrieved_at):
    updated = json.loads(json.dumps(cursor))
    attempted = set(updated["attempted_months"])
    completed = set(updated["completed_months"])
    retry = set(updated["retry_months"])
    history = list(updated.get("attempt_history", []))
    for month in months:
        result = status[month]
        attempted.add(month)
        if result["ok"]:
            completed.add(month)
            retry.discard(month)
        elif result.get("retryable"):
            retry.add(month)
        else:
            retry.discard(month)
        history.append({
            "month": month, "retrieved_at_utc": retrieved_at,
            "rows": int(result["rows"]), "status": str(result["status"]),
            "ok": bool(result["ok"]), "retryable": bool(result.get("retryable")),
        })
    updated["attempted_months"] = sorted(attempted)
    updated["completed_months"] = sorted(completed)
    updated["retry_months"] = sorted(retry)
    updated["attempt_history"] = history[-200:]
    updated["last_retrieval_utc"] = retrieved_at
    updated["remaining_month_count"] = len(
        [m for m in month_scope() if m not in attempted])
    return updated


def build(retrieved_at, *, cursor_path=CURSOR_PATH, fetcher=None, bars=None):
    from research import v38_archive_ingest as ingest
    cursor = load_cursor(cursor_path)
    before = set(cursor["attempted_months"])
    months = candidate_months(cursor)
    rows, per_month = sample_months(months, retrieved_at, fetcher)
    if bars:
        market_join = ingest.join_market(rows, bars)
    else:
        market_join = {"status": "NOT_ATTEMPTED_NO_VERIFIED_BARS"}
    advanced = advance_cursor(cursor, months, per_month, retrieved_at)
    month_counts = collections.Counter(
        r["published_at_utc"][:7] for r in rows)
    raw = json.dumps(rows, sort_keys=True, ensure_ascii=False,
                     separators=(",", ":")).encode()
    return {
        "schema": "v38_metadata_provenance_1",
        "retrieved_at_utc": retrieved_at,
        "source_status": {
            "cryptocurrency_cv": {
                "fetched_rows": len(rows),
                "status": "V41_PERSISTENT_UNSAMPLED_MONTH_CURSOR",
                "per_month": per_month,
            }
        },
        "raw_normalized_rows": len(rows),
        "deduplicated_rows": len(rows),
        "historical_article_version_rows": len(rows),
        "archive_months_requested": list(months),
        "archive_months_with_crypto_rows": dict(sorted(month_counts.items())),
        "archive_months_missing_crypto": [
            m for m in months if month_counts[m] == 0],
        "historically_verified_capture_rows": 0,
        "months": dict(sorted(month_counts.items())),
        "official_event_date_only_months": {},
        "official_release_clock_rows": 0,
        "target_2020_2026": 10000,
        "target_met": len(rows) >= 10000,
        "market_join": market_join,
        "market_fetch": "OFFICIAL_KRAKEN_ARCHIVE" if bars else "NOT_ATTEMPTED",
        "costs_bps": {"taker_each_side": 80, "half_spread_each_side": 5,
                      "slippage_each_side": 5},
        "max_paper_entry_aud": 100,
        "paper_starting_cash_aud": 1000,
        "android_strategy": "HOLD",
        "cursor_before_attempted_months": sorted(before),
        "cursor_after": advanced,
        "cursor_remaining_months": advanced["remaining_month_count"],
        "source_response_rows_sha256": hashlib.sha256(raw).hexdigest(),
        "notes": [
            "Metadata only; publisher article text rights retained",
            "API publication timestamps are retrospective and NOT first-verified crawl times",
            "No source-claimed first_seen value is used for point-in-time availability",
            "Month selection is calendar-based and independent of BTC returns",
            "Empty successful months are completed; transient failures are retried first",
        ],
        "records": rows,
    }


def bars_from_json(path):
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    if doc.get("schema") != "v41_kraken_ohlcvt_1":
        raise ValueError("Unknown verified market-bar schema")
    bars = doc.get("bars")
    if not isinstance(bars, list) or not bars:
        raise ValueError("Missing market bars")
    from research.v32_segments import segments
    eligible = segments(bars, 1000)
    if not eligible:
        raise ValueError("No gap-free market segment for news join")
    left, right = max(eligible, key=lambda pair: pair[1] - pair[0])
    return bars[left:right]


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="audit/v41-monthly-news.json")
    parser.add_argument("--cursor", default=CURSOR_PATH)
    parser.add_argument("--bars-json", default="audit/v41-market-bars.json")
    args = parser.parse_args(argv)
    bars = bars_from_json(args.bars_json)
    now = datetime.now(timezone.utc).isoformat()
    audit = build(now, cursor_path=args.cursor, bars=bars)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(audit, indent=2, ensure_ascii=False,
                      sort_keys=True, allow_nan=False) + "\n").encode()
    out.write_bytes(raw)
    print(json.dumps({
        "sha256": hashlib.sha256(raw).hexdigest(),
        "rows": len(audit["records"]),
        "months": audit["archive_months_requested"],
        "per_month": audit["source_status"]["cryptocurrency_cv"]["per_month"],
        "cursor_remaining": audit["cursor_remaining_months"],
        "market_join": audit["market_join"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()

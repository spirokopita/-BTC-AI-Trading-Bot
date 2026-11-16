"""V42 bounded Common Crawl version-proof probe; metadata/digest only.

Samples at most one outcome-independent cryptocurrency.cv article per month
from the current V41 monthly batch, checks two post-publication Common Crawl
indexes per URL, and stores exact CDX capture metadata. No WARC article bodies
are downloaded or redistributed. The selected-index probe is not exhaustive;
the earliest returned capture is only the earliest independently verified
capture among the indexes actually queried.
"""
from __future__ import annotations

import argparse
import bisect
import hashlib
import json
import time
import urllib.error
import urllib.parse
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from research.v38_archive_ingest import canonical, merge, normalize, request
from research.v32_segments import segments
from research.v48_news_proof_gate import classify

MAX_ARTICLES = 12
MAX_INDEXES_PER_ARTICLE = 2
COLLINFO_URL = "https://index.commoncrawl.org/collinfo.json"
USER_AGENT_NOTE = (
    "Common Crawl CDX metadata/digests only; no WARC body retrieved; "
    "only first two chronological post-publication indexes queried"
)


def parse_utc(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def select_articles(records, limit=MAX_ARTICLES):
    """Choose one URL per publication month using URL hash, never outcomes."""
    if not 1 <= limit <= MAX_ARTICLES:
        raise ValueError("WARC probe limit must be 1..12")
    grouped = defaultdict(list)
    for row in records:
        if "cryptocurrency_cv" not in row.get("source_ids", []):
            continue
        url = canonical(row.get("canonical_url") or row.get("url"))
        published = parse_utc(row.get("published_at_utc"))
        if not url or published is None:
            continue
        grouped[published.strftime("%Y-%m")].append((url, row))
    chosen = []
    used = set()
    for month in sorted(grouped):
        candidates = sorted(
            grouped[month],
            key=lambda item: hashlib.sha256(item[0].encode()).hexdigest(),
        )
        url, row = candidates[0]
        if url not in used:
            chosen.append((url, row))
            used.add(url)
        if len(chosen) >= limit:
            return chosen
    remainder = sorted(
        ((url, row) for values in grouped.values()
         for url, row in values if url not in used),
        key=lambda item: item[0],
    )
    for url, row in remainder:
        chosen.append((url, row))
        used.add(url)
        if len(chosen) >= limit:
            break
    return chosen


def _index_epoch(value):
    parsed = parse_utc(value)
    return parsed.timestamp() if parsed else None


def indexes_for_article(indexes, published_at_utc, limit=MAX_INDEXES_PER_ARTICLE):
    """Return first two chronological snapshots whose coverage reaches publication."""
    if not 1 <= limit <= MAX_INDEXES_PER_ARTICLE:
        raise ValueError("Index probe limit must be 1..2")
    published = _index_epoch(published_at_utc)
    eligible = []
    for index in indexes:
        if not isinstance(index, dict):
            continue
        if not str(index.get("id", "")).startswith("CC-MAIN-"):
            continue
        start = _index_epoch(index.get("from"))
        end = _index_epoch(index.get("to"))
        if not index.get("cdx-api"):
            continue
        if published is not None and end is not None and end < published:
            continue
        eligible.append((start if start is not None else float("inf"), index))
    eligible.sort(key=lambda item: (item[0], item[1].get("id", "")))
    return [item[1] for item in eligible[:limit]]


def _bounded_request(url, fetcher=request, attempts=3):
    for attempt in range(attempts):
        try:
            return fetcher(url, max_bytes=250_000)
        except urllib.error.HTTPError as exc:
            retryable = exc.code == 429 or 500 <= exc.code <= 599
            if not retryable or attempt + 1 >= attempts:
                raise
            try:
                delay = float(exc.headers.get("Retry-After", "2"))
            except (ValueError, TypeError, AttributeError):
                delay = 2.0
            time.sleep(min(8.0, max(1.0, delay, 2.0 ** attempt)))
    raise RuntimeError("Unreachable bounded request state")


def probe(records, retrieved_at_utc, *, indexes=None, fetcher=request, limit=MAX_ARTICLES):
    """Fetch only URL-specific CDX index metadata; never download WARC payloads."""
    retrieved = parse_utc(retrieved_at_utc)
    if retrieved is None:
        raise ValueError("retrieved_at_utc must be timezone-aware UTC")
    if indexes is None:
        indexes = json.loads(_bounded_request(COLLINFO_URL, fetcher).decode("utf-8"))
    targets = select_articles(records, limit=limit)
    captures = []
    failures = []
    requests_attempted = 0
    successful_queries = 0
    for target, article in targets:
        selected_indexes = indexes_for_article(
            indexes, article.get("published_at_utc")
        )
        if not selected_indexes:
            failures.append({"url": target, "status": "NO_POST_PUBLICATION_INDEX"})
            continue
        for index in selected_indexes:
            params = [
                ("url", target),
                ("output", "json"),
                ("matchType", "exact"),
                ("filter", "status:200"),
                ("filter", "mime:text/html"),
                ("fl", "timestamp,url,digest,filename,status,mime"),
            ]
            url = index["cdx-api"] + "?" + urllib.parse.urlencode(params)
            requests_attempted += 1
            try:
                raw = _bounded_request(url, fetcher)
                successful_queries += 1
                for line in raw.decode("utf-8").splitlines():
                    if not line.strip():
                        continue
                    cdx = json.loads(line)
                    normalized = normalize(
                        "common_crawl", cdx, retrieved_at_utc,
                        index_version=index["id"],
                    )
                    if not normalized or normalized["canonical_url"] != target:
                        continue
                    try:
                        offset = int(cdx.get("offset"))
                        length = int(cdx.get("length"))
                    except (TypeError, ValueError):
                        continue
                    if (offset < 0 or length <= 0
                            or str(cdx.get("status")) != "200"
                            or cdx.get("mime") != "text/html"):
                        continue
                    captured = parse_utc(
                        normalized.get("first_verified_capture_at_utc")
                    )
                    published = parse_utc(article.get("published_at_utc"))
                    if captured is None or (published and captured < published):
                        continue
                    normalized.update({
                        "capture_offset": offset,
                        "capture_length": length,
                        "capture_mime": cdx.get("mime"),
                        "capture_status": str(cdx.get("status")),
                        "url": target,
                        "source_ids": ["common_crawl"],
                        "sampling_class": "independent_warc_capture_version_probe",
                        "capture_probe_scope": (
                            "first two chronological post-publication indexes "
                            "queried; not exhaustive earliest Common Crawl capture"
                        ),
                        "original_publisher": article.get("original_publisher"),
                        "title": article.get("title", ""),
                        "published_at_utc": article.get("published_at_utc"),
                        "updated_at_utc": article.get("updated_at_utc"),
                        "license": (
                            "Common Crawl CDX index metadata only; no WARC body "
                            "downloaded; publisher article rights remain"
                        ),
                        "capture_type": "common_crawl_index_digest",
                        "version_hash_algorithm": "sha1_base32",
                        "capture_reference": normalized.get("capture_reference"),
                        "index_version": index["id"],
                        "first_verified_capture_at_utc": normalized.get(
                            "first_verified_capture_at_utc"
                        ),
                        "verified_capture_at_utc": normalized.get(
                            "first_verified_capture_at_utc"
                        ),
                        "retrieved_at_utc": retrieved_at_utc,
                    })
                    proof = classify(
                        normalized, retrieved_at_utc, latency_seconds=3600
                    )
                    if proof["reason"] in (
                        "INVALID_CAPTURE_REFERENCE", "INVALID_PROVENANCE_TIME",
                        "INCONSISTENT_CHRONOLOGY", "NO_VERSION_HASH",
                        "NO_INDEPENDENT_CAPTURE_PROOF",
                    ):
                        failures.append({
                            "url": target, "index": index["id"],
                            "status": "V48_REJECTED_" + proof["reason"],
                        })
                        continue
                    captures.append(normalized)
            except Exception as exc:
                failures.append({
                    "url": target, "index": index["id"],
                    "status": type(exc).__name__ + ": " + str(exc)[:180],
                })
    captures = merge(captures)
    status = (
        "OK_CAPTURE_PROOFS_FOUND" if captures and not failures
        else "PARTIAL_CAPTURE_PROOFS_WITH_FAILURES" if captures
        else "NO_MATCHING_CAPTURES" if successful_queries and not failures
        else "BLOCKED_OR_FAILED"
    )
    return captures, {
        "status": status,
        "access_class": "FREE_PUBLIC_METADATA",
        "attempted_article_urls": len(targets),
        "requests_attempted": requests_attempted,
        "successful_index_queries": successful_queries,
        "verified_capture_versions": len(captures),
        "failed_or_rejected": len(failures),
        "failures": failures[:40],
        "body_downloaded": False,
        "index_selection_scope": (
            "first two chronological post-publication indexes per sampled URL; "
            "absence in these indexes does not prove absence from all Common Crawl"
        ),
        "license_note": USER_AGENT_NOTE,
    }


def strict_market_join(capture_records, bars, minimum_segment_bars=1000):
    """Find first gap-safe bar OPEN after V48 capture availability + latency."""
    eligible_opens = []
    for left, right in segments(bars, minimum_segment_bars):
        eligible_opens.extend(float(row[0]) for row in bars[left:right])
    eligible_opens.sort()
    examples = []
    eligible_versions = 0
    for row in capture_records:
        proof = classify(
            row, datetime.now(timezone.utc).timestamp(), latency_seconds=3600
        )
        if not proof["eligible"]:
            continue
        available = float(proof["available_at_utc"])
        pos = bisect.bisect_left(eligible_opens, available)
        if pos >= len(eligible_opens):
            continue
        bar_ts = int(eligible_opens[pos])
        eligible_versions += 1
        if len(examples) < 20:
            examples.append({
                "url": row["url"],
                "version_hash": row.get("version_hash"),
                "capture_at_utc": row["first_verified_capture_at_utc"],
                "available_at_utc": datetime.fromtimestamp(
                    available, timezone.utc
                ).isoformat(),
                "first_eligible_bar_open_utc": datetime.fromtimestamp(
                    bar_ts, timezone.utc
                ).isoformat(),
            })
    return {
        "status": "OK_GAP_SAFE_ASOF" if eligible_opens else "NO_ELIGIBLE_MARKET_SEGMENT",
        "market_bars": len(eligible_opens),
        "strict_asof_eligible": eligible_versions,
        "asof_rule": (
            "V48 exact Common Crawl SHA1-base32 capture reference + one-hour "
            "latency; first gap-safe completed-bar OPEN at or after availability"
        ),
        "examples": examples,
    }


def enrich_audit(audit, captures, status, bars):
    """Preserve V41 cursor fields while adding separately counted capture versions."""
    if (audit.get("schema") != "v38_metadata_provenance_1"
            or audit.get("android_strategy") != "HOLD"
            or audit.get("max_paper_entry_aud") != 100):
        raise ValueError("V41 source audit safety/schema mismatch")
    from research import v38_archive_ingest as ingest
    records = ingest.merge(audit["records"] + captures)
    updated = dict(audit)
    updated["records"] = records
    updated["deduplicated_rows"] = len(records)
    updated["raw_normalized_rows"] = audit["raw_normalized_rows"] + len(captures)
    updated["historically_verified_capture_rows"] = sum(
        bool(row.get("first_verified_capture_at_utc")) for row in records
    )
    updated["source_status"] = dict(audit["source_status"])
    updated["source_status"]["common_crawl"] = dict(status)
    updated["source_status"]["common_crawl"]["fetched_rows"] = len(captures)
    updated["retrieved_at_utc"] = datetime.now(timezone.utc).isoformat()
    join = dict(audit.get("market_join") or {})
    strict = strict_market_join(captures, bars)
    join.update({
        "strict_asof_eligible": strict["strict_asof_eligible"],
        "strict_asof_rule": strict["asof_rule"],
        "strict_asof_examples": strict["examples"],
        "capture_market_join_status": strict["status"],
    })
    updated["market_join"] = join
    updated["source_response_rows_sha256"] = hashlib.sha256(
        json.dumps(records, sort_keys=True, ensure_ascii=False,
                   separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    updated.setdefault("notes", []).append(
        "V42 Common Crawl probes retain only CDX capture metadata/digests; "
        "no WARC article body was downloaded; capture rows are not counted "
        "as additional distinct articles. Only the first two chronological "
        "post-publication indexes per sampled URL were queried."
    )
    if len(updated["records"]) != updated["deduplicated_rows"]:
        raise AssertionError("V42 enriched source row count mismatch")
    return updated


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit", default="audit/v42-monthly-news.json")
    parser.add_argument("--bars-json", default="audit/v42-market-bars.json")
    parser.add_argument("--output", default="audit/v42-monthly-news-enriched.json")
    parser.add_argument("--limit", type=int, default=MAX_ARTICLES)
    args = parser.parse_args(argv)
    audit = json.loads(Path(args.audit).read_text(encoding="utf-8"))
    bars_doc = json.loads(Path(args.bars_json).read_text(encoding="utf-8"))
    bars = bars_doc["bars"]
    retrieved = datetime.now(timezone.utc).isoformat()
    captures, status = probe(audit["records"], retrieved, limit=args.limit)
    enriched = enrich_audit(audit, captures, status, bars)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(enriched, indent=2, ensure_ascii=False,
                     sort_keys=True, allow_nan=False) + "\n"
    output.write_text(raw, encoding="utf-8")
    readback = json.loads(output.read_text(encoding="utf-8"))
    if (len(readback["records"]) != readback["deduplicated_rows"]
            or readback["source_status"]["common_crawl"]["verified_capture_versions"]
            != len(captures)):
        raise AssertionError("V42 enriched audit read-back mismatch")
    print(json.dumps({
        "output": str(output),
        "capture_versions": len(captures),
        "strict_asof_eligible": enriched["market_join"]["strict_asof_eligible"],
        "source_status": status,
    }, sort_keys=True))


if __name__ == "__main__":
    main()

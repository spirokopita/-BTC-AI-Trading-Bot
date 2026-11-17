"""V44: bounded Common Crawl CDX probe with alternate URL-key matching.

The previous V43 probe used exact URL matching on two indexes and returned
two HTTP 404s. This version tests exact/prefix matching and a www host alias
on up to three later indexes, skipping those two previously queried indexes
for the same ODaily URL. It downloads CDX metadata only, never WARC bodies.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlsplit

from research.v44_asof_join import strict_asof_join

COLLINFO_URL = "https://index.commoncrawl.org/collinfo.json"
MAX_INDEXES = 3
MAX_VARIANTS = 3
MAX_REQUESTS = MAX_INDEXES * MAX_VARIANTS
MAX_BYTES = 250_000
PREVIOUSLY_FAILED_ODAILY_INDEXES = {"CC-MAIN-2022-21", "CC-MAIN-2022-27"}


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


def canonical_url(value):
    if not isinstance(value, str):
        raise ValueError("URL must be a string")
    parsed = urlsplit(value)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError("Invalid article URL")
    host = parsed.hostname.lower()
    if host.startswith("www."):
        host = host[4:]
    path = unquote(parsed.path or "/").rstrip("/") or "/"
    return host + path


def url_variants(value):
    parsed = urlsplit(value)
    host = parsed.hostname.lower()
    path = unquote(parsed.path or "/").rstrip("/") or "/"
    canonical_host = host[4:] if host.startswith("www.") else host
    variants = [
        {"url": f"{parsed.scheme}://{host}{path}", "match_type": "exact",
         "label": "original_exact"},
        {"url": f"{parsed.scheme}://{host}{path.rstrip('/')}",
         "match_type": "prefix", "label": "original_prefix"},
        {"url": f"https://www.{canonical_host}{path.rstrip('/')}",
         "match_type": "prefix", "label": "www_https_prefix"},
    ]
    seen = set()
    result = []
    for item in variants:
        key = (item["url"], item["match_type"])
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result[:MAX_VARIANTS]


def _index_epoch(value):
    parsed = parse_utc(value)
    if parsed is not None:
        return parsed.timestamp()
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    # Common Crawl collinfo from/to values are currently offset-naive;
    # retain the explicit UTC interpretation in the output provenance.
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).timestamp()


def indexes_for_article(indexes, published_at_utc, *, skip_ids=(),
                         limit=MAX_INDEXES):
    published = parse_utc(published_at_utc)
    if published is None:
        raise ValueError("Article publication timestamp must be timezone-aware")
    eligible = []
    for item in indexes:
        if not isinstance(item, dict):
            continue
        index_id = item.get("id")
        if not isinstance(index_id, str) or not index_id.startswith("CC-MAIN-"):
            continue
        if index_id in set(skip_ids):
            continue
        end = _index_epoch(item.get("to"))
        start = _index_epoch(item.get("from"))
        if end is None or end < published.timestamp() or not item.get("cdx-api"):
            continue
        eligible.append((start if start is not None else float("inf"), index_id, item))
    eligible.sort(key=lambda value: (value[0], value[1]))
    return [value[2] for value in eligible[:limit]]


def _fetch(url, max_bytes=MAX_BYTES):
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname != "index.commoncrawl.org":
        raise ValueError("Unapproved Common Crawl endpoint")
    request = urllib.request.Request(url, headers={
        "User-Agent": "BTC-AUD-PAPER-research/44 (bounded CDX metadata probe)",
        "Accept": "application/json,text/plain,*/*",
    })
    with urllib.request.urlopen(request, timeout=25) as response:
        body = response.read(max_bytes + 1)
    if len(body) > max_bytes:
        raise ValueError("Common Crawl response exceeded byte limit")
    return body


def _digest_valid(value):
    return isinstance(value, str) and re.fullmatch(r"[A-Z2-7]{32}", value) is not None


def _capture_row(cdx, target, article, index, retrieved_at_utc):
    if canonical_url(cdx.get("url")) != canonical_url(target):
        return None
    if str(cdx.get("status")) != "200" or cdx.get("mime") != "text/html":
        return None
    digest = cdx.get("digest")
    filename = cdx.get("filename")
    if not _digest_valid(digest) or not isinstance(filename, str) or "/warc/" not in filename:
        return None
    try:
        offset = int(cdx.get("offset"))
        length = int(cdx.get("length"))
    except (TypeError, ValueError):
        return None
    timestamp = cdx.get("timestamp")
    if not isinstance(timestamp, str) or not re.fullmatch(r"\d{14}", timestamp):
        return None
    captured = datetime.strptime(timestamp, "%Y%m%d%H%M%S").replace(
        tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
    published = parse_utc(article.get("published_at_utc"))
    if offset < 0 or length <= 0 or (published and
            parse_utc(captured).timestamp() < published.timestamp()):
        return None
    reference = (
        f"https://data.commoncrawl.org/{filename}"
        f"#offset={offset}&length={length}"
    )
    return {
        "schema": "v44_common_crawl_capture_metadata_1",
        "url": target,
        "canonical_url": target,
        "source_ids": sorted(set(article.get("source_ids", [])) | {"common_crawl"}),
        "original_publisher": article.get("original_publisher"),
        "title": article.get("title"),
        "published_at_utc": article.get("published_at_utc"),
        "updated_at_utc": article.get("updated_at_utc"),
        "capture_source": "common_crawl",
        "capture_type": "common_crawl_index_digest",
        "version_hash": digest,
        "version_hash_algorithm": "sha1_base32",
        "verified_capture_at_utc": captured,
        "first_verified_capture_at_utc": captured,
        "retrieved_at_utc": retrieved_at_utc,
        "index_version": index.get("id"),
        "index_collection_from_utc": index.get("from"),
        "index_collection_to_utc": index.get("to"),
        "index_timezone_assumption": "offset-naive Common Crawl collinfo times interpreted as UTC",
        "capture_reference": reference,
        "capture_offset": offset,
        "capture_length": length,
        "capture_mime": "text/html",
        "capture_status": "200",
        "license": "Common Crawl CDX metadata/digest only; no WARC body downloaded; publisher rights remain",
    }


def select_target(records, preferred_url=None):
    if preferred_url:
        wanted = canonical_url(preferred_url)
        for row in records:
            url = row.get("canonical_url") or row.get("url")
            if url and canonical_url(url) == wanted:
                return url, row
    eligible = []
    for row in records:
        if "cryptocurrency_cv" not in row.get("source_ids", []):
            continue
        url = row.get("canonical_url") or row.get("url")
        published = row.get("published_at_utc")
        if url and parse_utc(published):
            eligible.append((url, row))
    if not eligible:
        raise ValueError("No outcome-independent cryptocurrency.cv article to probe")
    eligible.sort(key=lambda item: (
        hashlib.sha256(canonical_url(item[0]).encode()).hexdigest(),
        item[0],
    ))
    return eligible[0]


def probe(records, retrieved_at_utc, *, indexes=None, fetcher=None,
          preferred_url=None, bars=None, market_provenance=None):
    retrieved = parse_utc(retrieved_at_utc)
    if retrieved is None:
        raise ValueError("retrieved_at_utc must be timezone-aware")
    fetcher = fetcher or _fetch
    target, article = select_target(records, preferred_url)
    if indexes is None:
        indexes = json.loads(fetcher(COLLINFO_URL).decode("utf-8"))
    skip = ()
    if canonical_url(target) == "odaily.news/newsflash/280563":
        skip = PREVIOUSLY_FAILED_ODAILY_INDEXES
    chosen = indexes_for_article(
        indexes, article["published_at_utc"], skip_ids=skip,
    )
    queries, captures, failures = [], [], []
    requests_attempted = 0
    successful_queries = 0
    for index in chosen:
        for variant in url_variants(target):
            params = [
                ("url", variant["url"]),
                ("output", "json"),
                ("matchType", variant["match_type"]),
                ("filter", "status:200"),
                ("filter", "mime:text/html"),
                ("fl", "timestamp,url,digest,filename,status,mime,offset,length"),
            ]
            query_url = index["cdx-api"] + "?" + urllib.parse.urlencode(params)
            requests_attempted += 1
            status = "OK"
            try:
                raw = fetcher(query_url)
                successful_queries += 1
                for line in raw.decode("utf-8").splitlines():
                    if not line.strip():
                        continue
                    cdx = json.loads(line)
                    row = _capture_row(cdx, target, article, index,
                                       retrieved_at_utc)
                    if row is not None:
                        captures.append(row)
            except urllib.error.HTTPError as exc:
                status = f"HTTP_{exc.code}"
                failures.append({
                    "index": index["id"], "variant": variant["label"],
                    "url": variant["url"], "status": status,
                })
            except Exception as exc:
                status = f"{type(exc).__name__}: {str(exc)[:180]}"
                failures.append({
                    "index": index["id"], "variant": variant["label"],
                    "url": variant["url"], "status": status,
                })
            queries.append({
                "index": index["id"], "variant": variant["label"],
                "match_type": variant["match_type"],
                "status": status,
            })
            time.sleep(0.25)
    # Exact version rows are unique by capture digest + WARC reference.
    unique = {}
    for row in captures:
        unique[(row["version_hash"], row["capture_reference"])] = row
    captures = sorted(unique.values(), key=lambda row: (
        row["verified_capture_at_utc"], row["capture_reference"]))
    market_join = (
        strict_asof_join(captures, bars, market_provenance)
        if bars is not None else {
            "mode": "V44_STRICT_ASOF_KRAKEN_4H_JOIN",
            "status": "NOT_RUN_NO_BARS",
            "strict_asof_eligible": 0,
            "pending_after_last_bar": len(captures),
            "proof_rejected": 0,
            "no_lookahead": True,
        }
    )
    return {
        "mode": "V44_COMMON_CRAWL_ALTERNATE_URLKEY_PROBE",
        "target_url": target,
        "target_published_at_utc": article.get("published_at_utc"),
        "retrieved_at_utc": retrieved_at_utc,
        "index_selection": "first three post-publication indexes after optional known-failure skip",
        "url_match_variants": [item["label"] for item in url_variants(target)],
        "requests_attempted": requests_attempted,
        "successful_index_queries": successful_queries,
        "verified_capture_versions": len(captures),
        "capture_rows": captures,
        "market_join": market_join,
        "queries": queries,
        "failures": failures,
        "body_downloaded": False,
        "index_timezone_assumption": "offset-naive Common Crawl collinfo times interpreted as UTC",
        "status": "CAPTURE_FOUND" if captures else "NO_CAPTURE_VERIFIED",
        "limits": {"indexes": MAX_INDEXES, "variants_per_index": MAX_VARIANTS,
                   "requests": MAX_REQUESTS},
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit", required=True)
    parser.add_argument("--output", default="audit/v44-warc-capture.json")
    parser.add_argument("--preferred-url",
                        default="https://odaily.news/newsflash/280563")
    parser.add_argument("--bars-json", default=None)
    parser.add_argument("--market-report", default=None)
    args = parser.parse_args(argv)
    audit = json.loads(Path(args.audit).read_text(encoding="utf-8"))
    bars = None
    market_provenance = {}
    if args.bars_json:
        bars_doc = json.loads(Path(args.bars_json).read_text(encoding="utf-8"))
        bars = bars_doc.get("bars")
        if not isinstance(bars, list) or not bars:
            raise ValueError("Official Kraken archive bars missing")
        if args.market_report:
            market_doc = json.loads(Path(args.market_report).read_text(encoding="utf-8"))
            market_provenance = market_doc.get("market", market_doc)
    try:
        report = probe(
            audit.get("records", []),
            datetime.now(timezone.utc).isoformat(),
            preferred_url=args.preferred_url,
            bars=bars, market_provenance=market_provenance,
        )
    except Exception as exc:
        report = {
            "mode": "V44_COMMON_CRAWL_ALTERNATE_URLKEY_PROBE",
            "status": "BLOCKED_OR_FAILED",
            "error": f"{type(exc).__name__}: {str(exc)[:240]}",
            "requests_attempted": 0,
            "successful_index_queries": 0,
            "verified_capture_versions": 0,
            "capture_rows": [],
            "market_join": {
                "mode": "V44_STRICT_ASOF_KRAKEN_4H_JOIN",
                "status": "BLOCKED_OR_FAILED",
                "strict_asof_eligible": 0,
                "pending_after_last_bar": 0,
                "proof_rejected": 0,
                "no_lookahead": True,
            },
            "body_downloaded": False,
        }
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()
    target.write_bytes(raw)
    print(json.dumps({
        "sha256": hashlib.sha256(raw).hexdigest(),
        "target": report["target_url"],
        "requests": report["requests_attempted"],
        "successful_queries": report["successful_index_queries"],
        "captures": report["verified_capture_versions"],
        "status": report["status"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()

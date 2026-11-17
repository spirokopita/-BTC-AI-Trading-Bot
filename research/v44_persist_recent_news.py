"""Persist V44 exact publisher-response hashes without historical backdating."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


def _epoch(value):
    if not isinstance(value, str):
        raise ValueError("Timestamp must be a string")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Timestamp must include timezone")
    return parsed.timestamp()


def merge_rows(existing, incoming):
    merged = {}
    for row in list(existing) + list(incoming):
        url = row.get("url")
        digest = row.get("content_sha256")
        if not isinstance(url, str) or not url.startswith("https://"):
            raise ValueError("Invalid V44 publisher URL")
        if not isinstance(digest, str) or len(digest) != 64:
            raise ValueError("Invalid V44 response SHA256")
        if row.get("version_capture_sha256") != digest:
            raise ValueError("Response and capture hashes differ")
        capture = row.get("verified_capture_at_utc")
        retrieved = row.get("retrieved_at_utc")
        if _epoch(capture) > _epoch(retrieved):
            raise ValueError("Capture occurs after retrieval")
        key = (url, digest)
        if key not in merged:
            item = dict(row)
            item["retrieval_history_utc"] = sorted(set(
                item.get("retrieval_history_utc", []) + [retrieved]))
            merged[key] = item
            continue
        item = merged[key]
        history = set(item.get("retrieval_history_utc", []))
        history.update(row.get("retrieval_history_utc", []))
        history.add(retrieved)
        if _epoch(capture) < _epoch(item["verified_capture_at_utc"]):
            item["verified_capture_at_utc"] = capture
            item["first_verified_observed_at_utc"] = row.get(
                "first_verified_observed_at_utc", capture)
        if _epoch(retrieved) < _epoch(item["retrieved_at_utc"]):
            item["retrieved_at_utc"] = retrieved
        item["retrieval_history_utc"] = sorted(history)
    return sorted(merged.values(), key=lambda row: (
        row["verified_capture_at_utc"], row["url"], row["content_sha256"]))


def jsonl_bytes(rows):
    return "".join(json.dumps(row, sort_keys=True, ensure_ascii=False,
                              separators=(",", ":")) + "\n"
                   for row in rows).encode("utf-8")


def merge_warc_captures(existing_rows, capture_rows):
    """Attach verified Common Crawl versions to the sampled article corpus."""
    rows = [dict(row) for row in existing_rows]
    added = 0
    for capture in capture_rows:
        if capture.get("capture_type") != "common_crawl_index_digest":
            raise ValueError("Unexpected V44 WARC capture type")
        digest = capture.get("version_hash")
        if not isinstance(digest, str) or len(digest) != 32:
            raise ValueError("Invalid Common Crawl digest")
        if not capture.get("capture_reference") or "/warc/" not in capture["capture_reference"]:
            raise ValueError("Missing Common Crawl WARC reference")
        if not str(capture.get("index_version", "")).startswith("CC-MAIN-"):
            raise ValueError("Missing Common Crawl index version")
        url = capture["canonical_url"]
        existing = next((row for row in rows
                         if row.get("canonical_url") == url
                         and row.get("version_hash") == digest), None)
        if existing is not None:
            history = set(existing.get("capture_retrieval_history_utc", []))
            history.add(capture["retrieved_at_utc"])
            existing["capture_retrieval_history_utc"] = sorted(history)
            existing["our_last_retrieved_at_utc"] = max(
                existing.get("our_last_retrieved_at_utc", capture["retrieved_at_utc"]),
                capture["retrieved_at_utc"])
            continue
        base = next((row for row in rows
                     if row.get("canonical_url") == url
                     and not row.get("version_hash")), None)
        if base is not None:
            rows.remove(base)
            merged = dict(base)
        else:
            merged = {
                "url": capture["url"],
                "canonical_url": url,
                "title": capture.get("title"),
                "original_publisher": capture.get("original_publisher"),
                "published_at_utc": capture.get("published_at_utc"),
                "updated_at_utc": capture.get("updated_at_utc"),
                "source_ids": capture.get("source_ids", []),
                "sampling_class": "unspecified",
            }
        first_retrieved = (
            merged.get("our_first_retrieved_at_utc")
            or merged.get("retrieved_at_utc")
            or capture["retrieved_at_utc"]
        )
        merged.update({
            "url": capture["url"],
            "canonical_url": url,
            "source_ids": sorted(set(
                merged.get("source_ids", []) + capture.get("source_ids", []))),
            "version_hash": digest,
            "version_hash_algorithm": "sha1_base32",
            "capture_source": "common_crawl",
            "capture_type": "common_crawl_index_digest",
            "availability_confidence": "verified_crawl",
            "first_verified_capture_at_utc": capture["verified_capture_at_utc"],
            "verified_capture_at_utc": capture["verified_capture_at_utc"],
            "retrieved_at_utc": capture["retrieved_at_utc"],
            "our_first_retrieved_at_utc": first_retrieved,
            "our_last_retrieved_at_utc": capture["retrieved_at_utc"],
            "capture_reference": capture["capture_reference"],
            "index_version": capture["index_version"],
            "capture_offset": capture["capture_offset"],
            "capture_length": capture["capture_length"],
            "capture_mime": capture["capture_mime"],
            "capture_status": capture["capture_status"],
            "index_timezone_assumption": capture["index_timezone_assumption"],
            "published_at_utc": merged.get("published_at_utc")
                or capture.get("published_at_utc"),
            "updated_at_utc": capture.get("updated_at_utc")
                or merged.get("updated_at_utc"),
        })
        rows.append(merged)
        added += 1
    rows.sort(key=lambda row: (
        row.get("published_at_utc") or row.get("official_event_date_only") or "",
        row.get("canonical_url", ""),
        row.get("version_hash") or "",
    ))
    return rows, added


def persist_warc_capture_audit(warc_audit_path, rows_path, manifest_path):
    from research.v38_persist_sample import build

    audit = json.loads(Path(warc_audit_path).read_text(encoding="utf-8"))
    if audit.get("mode") != "V44_COMMON_CRAWL_ALTERNATE_URLKEY_PROBE":
        raise ValueError("Unexpected V44 WARC audit mode")
    data_path = Path(rows_path)
    manifest_file = Path(manifest_path)
    rows = [json.loads(line) for line in data_path.read_text(
        encoding="utf-8").splitlines() if line.strip()]
    rows, added = merge_warc_captures(rows, audit.get("capture_rows", []))
    if added:
        previous = json.loads(manifest_file.read_text(encoding="utf-8"))
        v38_audit = {
            "schema": "v38_metadata_provenance_1",
            "android_strategy": "HOLD",
            "max_paper_entry_aud": 100,
            "records": [],
            "deduplicated_rows": 0,
            "retrieved_at_utc": audit["retrieved_at_utc"],
            "source_status": previous.get("source_status_latest", {}),
            "market_join": audit.get("market_join") or previous.get("market_join_latest", {
                "strict_asof_eligible": 0,
                "note": "V44 WARC metadata added; no market bars supplied",
            }),
        }
        rows, manifest = build(v38_audit, rows)
        raw = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
                      for row in rows).encode("utf-8")
        manifest["rows_sha256"] = hashlib.sha256(raw).hexdigest()
        manifest["v44_warc_probe_status"] = audit.get("status")
        manifest["v44_warc_capture_rows_added"] = added
        data_path.write_bytes(raw)
        manifest_file.write_text(json.dumps(
            manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8")
        readback = data_path.read_bytes()
        if hashlib.sha256(readback).hexdigest() != manifest["rows_sha256"]:
            raise AssertionError("V44 WARC corpus hash read-back failed")
        check = [json.loads(line) for line in readback.decode().splitlines() if line.strip()]
        if len(check) != manifest["rows_cumulative_deduplicated"]:
            raise AssertionError("V44 WARC corpus row-count read-back failed")
    return {
        "status": audit.get("status"),
        "capture_rows_seen": len(audit.get("capture_rows", [])),
        "capture_rows_added": added,
        "corpus_updated": bool(added),
    }


def persist(audit_path, data_path, manifest_path, warc_audit_path=None,
            market_rows_path="data/historical_news_sample_v38.jsonl",
            market_manifest_path="data/historical_news_manifest_v38.json"):
    audit = json.loads(Path(audit_path).read_text(encoding="utf-8"))
    if audit.get("mode") != "V44_PROSPECTIVE_FIRST_OBSERVED_PUBLISHER_SNAPSHOTS":
        raise ValueError("Unexpected V44 capture audit mode")
    data = Path(data_path)
    existing = [
        json.loads(line) for line in data.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ] if data.exists() else []
    rows = merge_rows(existing, audit.get("records", []))
    raw = jsonl_bytes(rows)
    data.parent.mkdir(parents=True, exist_ok=True)
    data.write_bytes(raw)
    counts = Counter(row.get("source_id", "unknown") for row in rows)
    warc_summary = None
    if warc_audit_path:
        warc_summary = persist_warc_capture_audit(
            warc_audit_path, market_rows_path, market_manifest_path)
    manifest = {
        "schema": "v44_first_observed_metadata_manifest_1",
        "retrieved_at_utc": audit.get("retrieved_at_utc"),
        "version_rows_cumulative": len(rows),
        "unique_urls": len({row["url"] for row in rows}),
        "source_counts": dict(sorted(counts.items())),
        "rows_sha256": hashlib.sha256(raw).hexdigest(),
        "historical_backfill": False,
        "paper_only": True,
        "raw_publisher_bodies_redistributed": False,
        "last_run_source_status": audit.get("source_status", {}),
        "last_run_failures": audit.get("failures", []),
        "market_join": audit.get("market_join"),
        "warc_persistence": warc_summary,
    }
    manifest_path = Path(manifest_path)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(
        manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8")
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit", default="audit/v44-recent-news-capture.json")
    parser.add_argument("--data", default="data/v44_recent_news_observations.jsonl")
    parser.add_argument("--manifest", default="data/v44_recent_news_manifest.json")
    parser.add_argument("--warc-audit", default=None)
    parser.add_argument("--market-rows", default="data/historical_news_sample_v38.jsonl")
    parser.add_argument("--market-manifest", default="data/historical_news_manifest_v38.json")
    args = parser.parse_args(argv)
    result = persist(
        args.audit, args.data, args.manifest,
        warc_audit_path=args.warc_audit,
        market_rows_path=args.market_rows,
        market_manifest_path=args.market_manifest,
    )
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()

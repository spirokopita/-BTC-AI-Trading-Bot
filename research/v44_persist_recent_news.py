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


def persist(audit_path, data_path, manifest_path):
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
    args = parser.parse_args(argv)
    result = persist(args.audit, args.data, args.manifest)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()

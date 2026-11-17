"""Persist only direct news version hashes observed on a main-branch run."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


DATA_PATH = Path("data/news_capture_observations_v44.jsonl")
MANIFEST_PATH = Path("data/news_capture_manifest_v44.json")


def merge_capture(audit_path, *, data_path=DATA_PATH, manifest_path=MANIFEST_PATH):
    audit = json.loads(Path(audit_path).read_text(encoding="utf-8"))
    if audit.get("schema") != "v44_direct_news_capture_1":
        raise ValueError("Unknown V44 capture audit schema")
    data_path = Path(data_path)
    manifest_path = Path(manifest_path)
    existing = {}
    if data_path.exists():
        for line in data_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            key = (row.get("url"), row.get("capture_version_hash"))
            if not all(key):
                raise ValueError("Persisted capture row missing URL or version hash")
            existing[key] = row

    inserted = 0
    for row in audit.get("records", []):
        if row.get("status") != "CAPTURED_METADATA_HASH_ONLY":
            continue
        first_seen = row.get("first_persisted_observation_at_utc")
        digest = row.get("capture_version_hash")
        if not first_seen or not digest or row.get("body_stored") is not False:
            continue
        key = (row["url"], digest)
        if key not in existing:
            clean = dict(row)
            clean["observation_count"] = 1
            clean["last_retrieved_at_utc"] = row["retrieved_at_utc"]
            existing[key] = clean
            inserted += 1
        else:
            current = existing[key]
            current["observation_count"] = int(current.get("observation_count", 1)) + 1
            current["last_retrieved_at_utc"] = max(
                current.get("last_retrieved_at_utc", ""),
                row.get("retrieved_at_utc", ""),
            )
            current["first_persisted_observation_at_utc"] = min(
                current["first_persisted_observation_at_utc"], first_seen
            )

    rows = sorted(existing.values(), key=lambda row: (
        row["url"], row["first_persisted_observation_at_utc"],
        row["capture_version_hash"],
    ))
    data_path.parent.mkdir(parents=True, exist_ok=True)
    raw = "".join(json.dumps(row, sort_keys=True, ensure_ascii=False,
                             separators=(",", ":")) + "\n" for row in rows).encode()
    data_path.write_bytes(raw)
    source_counts = {}
    for row in rows:
        source_counts[row.get("publisher", "unknown")] = (
            source_counts.get(row.get("publisher", "unknown"), 0) + 1
        )
    manifest = {
        "schema": "v44_news_capture_manifest_1",
        "rows": len(rows),
        "distinct_urls": len({row["url"] for row in rows}),
        "distinct_versions": len({(row["url"], row["capture_version_hash"]) for row in rows}),
        "new_versions_inserted_this_run": inserted,
        "latest_retrieval_utc": max((row.get("last_retrieved_at_utc", "")
                                     for row in rows), default=None),
        "source_version_rows": dict(sorted(source_counts.items())),
        "rows_sha256": hashlib.sha256(raw).hexdigest(),
        "body_bytes_stored": 0,
        "policy": "Direct response SHA256 only; first persisted observation is the main-run fetch time, never publisher publication time",
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                             encoding="utf-8")
    check = data_path.read_bytes()
    if hashlib.sha256(check).hexdigest() != manifest["rows_sha256"]:
        raise AssertionError("V44 capture manifest read-back hash mismatch")
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit", default="audit/v44-live-news-capture.json")
    args = parser.parse_args(argv)
    result = merge_capture(args.audit)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()

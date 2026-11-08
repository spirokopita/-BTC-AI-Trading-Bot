"""V38 cumulative, idempotent metadata-only archive checkpoint.

This file never converts retrospective publication dates or API first_seen
into independently verified historical first-observed timestamps.
"""
from __future__ import annotations
import argparse
import collections
import hashlib
import json
from pathlib import Path

def key(r):
    return (r["canonical_url"], r.get("version_hash") or "UNVERIFIED_VERSION")

def update(existing, new):
    by_key = {}
    for r in existing + new:
        k = key(r)
        seen = r.get("our_first_retrieved_at_utc") or r["retrieved_at_utc"]
        last = r.get("our_last_retrieved_at_utc") or r["retrieved_at_utc"]
        if k not in by_key:
            row = dict(r)
            row["our_first_retrieved_at_utc"] = seen
            row["our_last_retrieved_at_utc"] = last
            by_key[k] = row
        else:
            old = by_key[k]
            old["source_ids"] = sorted(set(old["source_ids"] + r["source_ids"]))
            old["our_first_retrieved_at_utc"] = min(
                old["our_first_retrieved_at_utc"], seen)
            old["our_last_retrieved_at_utc"] = max(
                old["our_last_retrieved_at_utc"], last)
            if r.get("official_release_at_utc") and not old.get("official_release_at_utc"):
                old["official_release_at_utc"] = r["official_release_at_utc"]
                old["official_release_time_provenance"] = r.get(
                    "official_release_time_provenance")
            # Never overwrite original version text/metadata with future revisions.
    return sorted(by_key.values(), key=lambda r: (
        r.get("published_at_utc") or r.get("official_event_date_only") or "",
        r["canonical_url"], r.get("version_hash") or ""))

def build(audit, existing):
    if audit.get("schema") != "v38_metadata_provenance_1":
        raise ValueError("Unknown source audit schema")
    if audit.get("android_strategy") != "HOLD" or audit.get("max_paper_entry_aud") != 100:
        raise ValueError("Paper-only safety contract")
    new = audit["records"]
    if len(new) != audit["deduplicated_rows"]:
        raise ValueError("Source audit row count mismatch")
    rows = update(existing, new)
    for r in rows:
        if r.get("availability_confidence") == "verified_crawl":
            if not (r.get("first_verified_capture_at_utc") and r.get("version_hash")
                    and r.get("capture_reference")):
                raise ValueError("Claimed verified crawl lacks provenance")
        elif r.get("first_verified_capture_at_utc"):
            raise ValueError("Inconsistent historical capture provenance")
    months = collections.Counter((r.get("published_at_utc") or "")[:7] or "unknown"
                                 for r in rows)
    sources = collections.Counter(s for r in rows for s in r["source_ids"])
    manifest = {
        "schema": "v38_cumulative_metadata_1",
        "latest_retrieval_utc": audit["retrieved_at_utc"],
        "source_status_latest": audit["source_status"],
        "rows_cumulative_deduplicated": len(rows),
        "rows_new_in_latest_sample": len(new),
        "historical_verified_crawl_rows": sum(bool(r.get("first_verified_capture_at_utc"))
                                              for r in rows),
        "official_release_clock_rows": sum(bool(r.get("official_release_at_utc"))
                                          for r in rows),
        "months_by_publication": dict(sorted(months.items())),
        "source_counts_not_exclusive": dict(sorted(sources.items())),
        "market_join_latest": audit["market_join"],
        "target": 10000, "target_met": len(rows) >= 10000,
        "no_lookahead": "Historical as-of uses only verified WARC captures; source-claimed first_seen and our 2026 retrieval cannot backdate history",
        "paper_only": True, "android_policy": "HOLD",
    }
    return rows, manifest

def persist(audit_path, rows_path, manifest_path):
    audit = json.loads(Path(audit_path).read_text(encoding="utf-8"))
    p = Path(rows_path)
    existing = ([json.loads(line) for line in p.read_text(encoding="utf-8").splitlines()
                 if line.strip()] if p.exists() else [])
    rows, manifest = build(audit, existing)
    raw = "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n"
                  for r in rows).encode("utf-8")
    manifest["rows_sha256"] = hashlib.sha256(raw).hexdigest()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(raw)
    Path(manifest_path).write_text(json.dumps(manifest, indent=2,
        ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    # Read-back verifies bytes and exact row count before Git commit.
    assert hashlib.sha256(p.read_bytes()).hexdigest() == manifest["rows_sha256"]
    assert len([x for x in p.read_text(encoding="utf-8").splitlines() if x]) == len(rows)
    return manifest

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--audit",default="audit/v38-archive-ingestion.json")
    ap.add_argument("--rows",default="data/historical_news_sample_v38.jsonl")
    ap.add_argument("--manifest",default="data/historical_news_manifest_v38.json")
    a=ap.parse_args()
    print(json.dumps(persist(a.audit,a.rows,a.manifest),sort_keys=True))
if __name__=="__main__":main()

"""Idempotently persist V41 month attempts after main-branch CI succeeds."""
from __future__ import annotations
import argparse
import json
from pathlib import Path

from research.v41_monthly_news import (
    SCHEMA, CURSOR_PATH, month_scope, advance_cursor,
)


def merge_cursor(cursor, audit):
    if audit.get("schema") != "v38_metadata_provenance_1":
        raise ValueError("Unknown V41 audit schema")
    if audit.get("android_strategy") != "HOLD" or audit.get("max_paper_entry_aud") != 100:
        raise ValueError("Paper-only safety contract")
    months = audit.get("archive_months_requested", [])
    per_month = audit.get("source_status", {}).get(
        "cryptocurrency_cv", {}).get("per_month", {})
    if len(months) > 12 or len(months) != len(set(months)):
        raise ValueError("Invalid bounded month batch")
    if set(months) != set(per_month):
        raise ValueError("Per-month status does not match request batch")
    before = set(audit.get("cursor_before_attempted_months", []))
    if before != set(cursor["attempted_months"]):
        raise ValueError("Stale cursor: main changed since this audit was created")
    return advance_cursor(cursor, months, per_month, audit["retrieved_at_utc"])


def persist(audit_path, cursor_path=CURSOR_PATH):
    audit = json.loads(Path(audit_path).read_text(encoding="utf-8"))
    path = Path(cursor_path)
    cursor = json.loads(path.read_text(encoding="utf-8"))
    if cursor.get("schema") != SCHEMA:
        raise ValueError("Unknown cursor schema")
    updated = merge_cursor(cursor, audit)
    raw = json.dumps(updated, indent=2, sort_keys=True) + "\n"
    path.write_text(raw, encoding="utf-8")
    readback = json.loads(path.read_text(encoding="utf-8"))
    if readback != updated:
        raise AssertionError("Cursor read-back mismatch")
    if not set(readback["attempted_months"]).issubset(set(month_scope())):
        raise AssertionError("Cursor escaped frozen month scope")
    return readback


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit", default="audit/v41-monthly-news.json")
    parser.add_argument("--cursor", default=CURSOR_PATH)
    args = parser.parse_args()
    print(json.dumps(persist(args.audit, args.cursor), sort_keys=True))


if __name__ == "__main__":
    main()

"""V41 monthly cursor tests: bounded, idempotent, retry-aware, no backdating."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import types

from research.v41_monthly_news import (
    SCHEMA, month_scope, load_cursor, candidate_months, sample_months,
    advance_cursor, retryable_status, build,
)
from research.v41_persist_cursor import merge_cursor


def cursor_fixture():
    attempted = [f"{y}-{m:02d}" for y in range(2020, 2027)
                 for m in (1, 4, 7, 10)]
    attempted += [f"{y}-02" for y in range(2020, 2027)]
    attempted += [f"{y}-05" for y in range(2020, 2025)]
    attempted = sorted(set(attempted))
    return {
        "schema": SCHEMA, "scope_start_month": "2020-01",
        "scope_end_month": "2026-10", "source": "cryptocurrency_cv",
        "attempted_months": attempted, "completed_months": attempted,
        "retry_months": [], "attempt_history": [],
    }


class V41MonthlyCursorTests(unittest.TestCase):
    def test_scope_and_batch_are_bounded_and_nonrepeating(self):
        cursor = cursor_fixture()
        months = candidate_months(cursor)
        self.assertEqual(len(months), 12)
        self.assertEqual(len(set(months)), 12)
        self.assertTrue(all(m not in cursor["attempted_months"] for m in months))
        self.assertEqual(months[:6], (
            "2020-03", "2020-06", "2020-08",
            "2020-09", "2020-11", "2020-12"))
        self.assertEqual(len(month_scope()), 82)
        with self.assertRaises(ValueError):
            candidate_months(cursor, 13)

    def test_retryable_months_are_prioritized(self):
        cursor = cursor_fixture()
        cursor["attempted_months"].append("2020-03")
        cursor["retry_months"].append("2020-03")
        self.assertEqual(candidate_months(cursor)[0], "2020-03")
        self.assertTrue(retryable_status("HTTP Error 503: Service Unavailable"))
        self.assertFalse(retryable_status("HTTP Error 404: Not Found"))

    def test_sample_restores_global_months_and_rejects_backdated_capture(self):
        fake = types.ModuleType("research.v38_archive_ingest")
        fake.MONTHS = ("2020-01",)
        fake.merge = lambda rows: list(rows)
        def fetch(source, at):
            month = fake.MONTHS[0]
            return ([{
                "canonical_url": "https://example.org/" + month,
                "source_ids": ["cryptocurrency_cv"],
                "published_at_utc": month + "-15T12:00:00+00:00",
                "first_verified_capture_at_utc": None,
            }], "OK_DATE_FILTERS_VERIFIED")
        with patch.dict("sys.modules", {"research.v38_archive_ingest": fake}):
            rows, status = sample_months(("2020-03",), "2026-11-16T00:00:00Z", fetch)
        self.assertEqual(fake.MONTHS, ("2020-01",))
        self.assertEqual(len(rows), 1)
        self.assertTrue(status["2020-03"]["ok"])
        def bad(source, at):
            return ([{
                "source_ids": ["cryptocurrency_cv"],
                "published_at_utc": "2020-03-15T12:00:00+00:00",
                "first_verified_capture_at_utc": "2020-03-15T12:00:00+00:00",
            }], "OK_DATE_FILTERS_VERIFIED")
        with patch.dict("sys.modules", {"research.v38_archive_ingest": fake}):
            rows, status = sample_months(("2020-03",), "2026-11-16T00:00:00Z", bad)
        self.assertEqual(rows, [])
        self.assertFalse(status["2020-03"]["ok"])

    def test_advance_cursor_records_empty_success_and_retries_transient(self):
        cursor = cursor_fixture()
        months = ("2020-03", "2020-06")
        status = {
            "2020-03": {"rows": 0, "status": "OK_DATE_FILTERS_VERIFIED",
                        "ok": True, "retryable": False},
            "2020-06": {"rows": 0, "status": "HTTP Error 503",
                        "ok": False, "retryable": True},
        }
        updated = advance_cursor(cursor, months, status, "2026-11-16T00:00:00Z")
        self.assertIn("2020-03", updated["completed_months"])
        self.assertIn("2020-06", updated["retry_months"])
        self.assertEqual(updated["remaining_month_count"],
                         len([m for m in month_scope() if m not in updated["attempted_months"]]))

    def test_merge_cursor_rejects_stale_and_is_idempotent_for_attempt_history(self):
        cursor = cursor_fixture()
        months = candidate_months(cursor, 1)
        month = months[0]
        audit = {
            "schema": "v38_metadata_provenance_1",
            "android_strategy": "HOLD", "max_paper_entry_aud": 100,
            "archive_months_requested": [month],
            "cursor_before_attempted_months": cursor["attempted_months"],
            "retrieved_at_utc": "2026-11-16T00:00:00Z",
            "source_status": {"cryptocurrency_cv": {"per_month": {
                month: {"rows": 0, "status": "OK_DATE_FILTERS_VERIFIED",
                        "ok": True, "retryable": False}}}},
        }
        updated = merge_cursor(cursor, audit)
        self.assertIn(month, updated["completed_months"])
        with self.assertRaises(ValueError):
            merge_cursor(updated, audit)

    def test_build_requires_cursor_and_keeps_paper_only(self):
        cursor = cursor_fixture()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cursor.json"
            path.write_text(json.dumps(cursor))
            fake = types.ModuleType("research.v38_archive_ingest")
            fake.MONTHS = ("2020-01",)
            fake.merge = lambda rows: list(rows)
            fake.join_market = lambda rows, bars: {
                "retrospective_time_aligned": 0, "strict_asof_eligible": 0}
            with patch.dict("sys.modules", {"research.v38_archive_ingest": fake}):
                def empty(source, at):
                    return [], "OK_DATE_FILTERS_VERIFIED"
                report = build("2026-11-16T00:00:00Z",
                               cursor_path=path, fetcher=empty, bars=[(1,1,1,1,1,1)])
        self.assertEqual(report["android_strategy"], "HOLD")
        self.assertEqual(report["max_paper_entry_aud"], 100)
        self.assertEqual(len(report["archive_months_requested"]), 12)
        self.assertEqual(report["historically_verified_capture_rows"], 0)
        self.assertEqual(report["historical_article_version_rows"], 0)

    def test_no_cursor_means_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileNotFoundError):
                load_cursor(Path(tmp) / "missing.json")


if __name__ == "__main__":
    unittest.main()

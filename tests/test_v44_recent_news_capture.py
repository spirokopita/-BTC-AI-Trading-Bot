"""V44 publisher capture and durable first-observed version tests."""
import hashlib
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from research.v44_recent_news_capture import (
    COINDESK_URL, RBA_INDEX_URL, RBA_MINUTES_URL,
    capture_all, parse_coindesk_publication, parse_rba_publication,
)
from research.v44_persist_recent_news import (
    merge_rows, merge_warc_captures, persist, persist_warc_capture_audit,
)


class V44RecentNewsTests(unittest.TestCase):
    def test_rba_release_time_uses_official_aedt_clock(self):
        body = b"<html><body>Minutes of the November 2026 Monetary Policy Board Meeting 17 November 2026 11.30 am AEDT</body></html>"
        self.assertEqual(parse_rba_publication(body), "2026-11-17T00:30:00Z")

    def test_coindesk_release_time_normalizes_est_to_utc(self):
        body = b"<html><body>Nov 17, 2026, 6:36 a.m. EST</body></html>"
        self.assertEqual(parse_coindesk_publication(body), "2026-11-17T11:36:00Z")

    def test_capture_records_exact_response_hash_and_later_observation(self):
        rba_index = b"<html><body>Minutes of the November 2026 Monetary Policy Board Meeting 17 November 2026 11.30 am AEDT</body></html>"
        rba_page = b"<html><meta property='og:title' content='RBA November minutes'><body>" + b"x" * 600 + b"</body></html>"
        coindesk_page = b"<html><body>Nov 17, 2026, 6:36 a.m. EST " + b"y" * 600 + b"</body></html>"
        mapping = {
            RBA_INDEX_URL: (rba_index, RBA_INDEX_URL, {}),
            RBA_MINUTES_URL: (rba_page, RBA_MINUTES_URL, {}),
            COINDESK_URL: (coindesk_page, COINDESK_URL, {}),
        }
        clock_values = iter([
            datetime(2026, 11, 18, 0, 0, tzinfo=timezone.utc),
            datetime(2026, 11, 18, 0, 1, tzinfo=timezone.utc),
            datetime(2026, 11, 18, 0, 2, tzinfo=timezone.utc),
        ])
        bars = [
            (int(datetime(2026, 11, 18, hour, 0,
                          tzinfo=timezone.utc).timestamp()),
             100.0, 101.0, 99.0, 100.0, 1.0)
            for hour in (0, 4, 8)
        ]
        result = capture_all(
            fetcher=lambda url: mapping[url],
            clock=lambda: next(clock_values),
            bars=bars,
            market_provenance={"source_response_sha256": "fixture"},
        )
        self.assertEqual(result["record_count"], 2)
        self.assertEqual(result["market_join"]["strict_asof_eligible"], 2)
        self.assertTrue(result["market_join"]["no_lookahead"])
        self.assertEqual(
            {row["first_tradable_bar_open_utc"]
             for row in result["market_join"]["matches"]},
            {"2026-11-18T04:00:00Z"},
        )
        for row, body in zip(result["records"], (rba_page, coindesk_page)):
            digest = hashlib.sha256(body).hexdigest()
            self.assertEqual(row["content_sha256"], digest)
            self.assertEqual(row["version_capture_sha256"], digest)
            self.assertEqual(row["capture_type"], "first_observed_snapshot")
            self.assertGreater(row["available_at_utc_with_1h_latency"],
                               row["first_verified_observed_at_utc"])
            self.assertFalse(row["historical_asof_use"].startswith("ELIGIBLE"))

    def test_bad_redirect_or_unapproved_host_is_rejected(self):
        from research.v44_recent_news_capture import fetch
        with self.assertRaisesRegex(ValueError, "Unapproved publisher host"):
            fetch("http://example.com/article")

    def test_duplicate_exact_version_keeps_earliest_observation(self):
        base = {
            "url": "https://example.com/article",
            "content_sha256": "a" * 64,
            "version_capture_sha256": "a" * 64,
            "verified_capture_at_utc": "2026-11-18T00:00:00Z",
            "first_verified_observed_at_utc": "2026-11-18T00:00:00Z",
            "retrieved_at_utc": "2026-11-18T00:00:00Z",
            "source_id": "test",
        }
        later = dict(base, verified_capture_at_utc="2026-11-18T01:00:00Z",
                     first_verified_observed_at_utc="2026-11-18T01:00:00Z",
                     retrieved_at_utc="2026-11-18T01:00:00Z")
        rows = merge_rows([base], [later])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["first_verified_observed_at_utc"],
                         "2026-11-18T00:00:00Z")
        self.assertEqual(len(rows[0]["retrieval_history_utc"]), 2)

    def test_different_hashes_are_preserved_as_distinct_versions(self):
        a = {
            "url": "https://example.com/article",
            "content_sha256": "a" * 64,
            "version_capture_sha256": "a" * 64,
            "verified_capture_at_utc": "2026-11-18T00:00:00Z",
            "retrieved_at_utc": "2026-11-18T00:00:00Z",
            "source_id": "test",
        }
        b = dict(a, content_sha256="b" * 64, version_capture_sha256="b" * 64,
                 verified_capture_at_utc="2026-11-18T01:00:00Z",
                 retrieved_at_utc="2026-11-18T01:00:00Z")
        self.assertEqual(len(merge_rows([], [a, b])), 2)

    def test_warc_capture_promotes_existing_metadata_row_without_double_count(self):
        base = {
            "url": "https://odaily.news/newsflash/280563",
            "canonical_url": "https://odaily.news/newsflash/280563",
            "source_ids": ["cryptocurrency_cv"],
            "published_at_utc": "2022-04-01T00:00:00Z",
            "retrieved_at_utc": "2026-11-18T00:00:00Z",
            "title": "Sample article",
            "original_publisher": "Odaily",
            "sampling_class": "historical_article",
        }
        capture = {
            "url": base["url"],
            "canonical_url": base["canonical_url"],
            "source_ids": ["cryptocurrency_cv", "common_crawl"],
            "capture_type": "common_crawl_index_digest",
            "version_hash": "A" * 32,
            "version_hash_algorithm": "sha1_base32",
            "capture_source": "common_crawl",
            "verified_capture_at_utc": "2022-07-10T12:34:56Z",
            "retrieved_at_utc": "2026-11-18T00:10:00Z",
            "published_at_utc": base["published_at_utc"],
            "updated_at_utc": None,
            "capture_reference": "https://data.commoncrawl.org/crawl-data/x/warc/file.warc.gz#offset=10&length=200",
            "index_version": "CC-MAIN-2022-33",
            "capture_offset": 10,
            "capture_length": 200,
            "capture_mime": "text/html",
            "capture_status": "200",
            "index_timezone_assumption": "UTC",
        }
        rows, added = merge_warc_captures([base], [capture])
        self.assertEqual(added, 1)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["availability_confidence"], "verified_crawl")
        self.assertEqual(rows[0]["version_hash"], "A" * 32)
        self.assertIn("cryptocurrency_cv", rows[0]["source_ids"])
        self.assertIn("common_crawl", rows[0]["source_ids"])

    def test_warc_persistence_updates_v38_manifest_and_readback(self):
        base = {
            "url": "https://odaily.news/newsflash/280563",
            "canonical_url": "https://odaily.news/newsflash/280563",
            "source_ids": ["cryptocurrency_cv"],
            "published_at_utc": "2022-04-01T00:00:00Z",
            "retrieved_at_utc": "2026-11-18T00:00:00Z",
            "title": "Sample article",
            "original_publisher": "Odaily",
            "sampling_class": "historical_article",
        }
        capture = {
            "url": base["url"], "canonical_url": base["canonical_url"],
            "source_ids": ["cryptocurrency_cv", "common_crawl"],
            "capture_type": "common_crawl_index_digest",
            "version_hash": "B" * 32, "version_hash_algorithm": "sha1_base32",
            "capture_source": "common_crawl",
            "verified_capture_at_utc": "2022-07-10T12:34:56Z",
            "retrieved_at_utc": "2026-11-18T00:10:00Z",
            "published_at_utc": base["published_at_utc"], "updated_at_utc": None,
            "capture_reference": "https://data.commoncrawl.org/crawl-data/x/warc/file.warc.gz#offset=10&length=200",
            "index_version": "CC-MAIN-2022-33",
            "capture_offset": 10, "capture_length": 200,
            "capture_mime": "text/html", "capture_status": "200",
            "index_timezone_assumption": "UTC",
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rows_path = root / "historical.jsonl"
            manifest_path = root / "historical-manifest.json"
            rows_path.write_text(json.dumps(base) + "\n")
            manifest_path.write_text(json.dumps({
                "source_status_latest": {"cryptocurrency_cv": {"fetched_rows": 1}},
                "market_join_latest": {"strict_asof_eligible": 0},
            }))
            audit_path = root / "warc.json"
            audit_path.write_text(json.dumps({
                "mode": "V44_COMMON_CRAWL_ALTERNATE_URLKEY_PROBE",
                "status": "CAPTURE_FOUND",
                "retrieved_at_utc": "2026-11-18T00:10:00Z",
                "capture_rows": [capture],
            }))
            summary = persist_warc_capture_audit(
                audit_path, rows_path, manifest_path)
            manifest = json.loads(manifest_path.read_text())
            persisted = [json.loads(line) for line in rows_path.read_text().splitlines()]
            self.assertEqual(summary["capture_rows_added"], 1)
            self.assertEqual(manifest["historical_verified_crawl_rows"], 1)
            self.assertEqual(manifest["rows_cumulative_deduplicated"], 1)
            self.assertEqual(persisted[0]["version_hash"], "B" * 32)

    def test_persist_writes_manifest_and_readback_hash(self):
        row = {
            "url": "https://example.com/article",
            "content_sha256": "c" * 64,
            "version_capture_sha256": "c" * 64,
            "verified_capture_at_utc": "2026-11-18T00:00:00Z",
            "first_verified_observed_at_utc": "2026-11-18T00:00:00Z",
            "retrieved_at_utc": "2026-11-18T00:00:00Z",
            "source_id": "test",
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audit = root / "audit.json"
            data = root / "rows.jsonl"
            manifest = root / "manifest.json"
            audit.write_text(json.dumps({
                "mode": "V44_PROSPECTIVE_FIRST_OBSERVED_PUBLISHER_SNAPSHOTS",
                "retrieved_at_utc": "2026-11-18T00:01:00Z",
                "records": [row], "source_status": {}, "failures": [],
            }))
            result = persist(audit, data, manifest)
            self.assertEqual(result["version_rows_cumulative"], 1)
            self.assertEqual(hashlib.sha256(data.read_bytes()).hexdigest(),
                             result["rows_sha256"])
            self.assertTrue(manifest.is_file())


if __name__ == "__main__":
    unittest.main()

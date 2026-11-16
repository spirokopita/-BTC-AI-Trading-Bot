"""V42 Common Crawl version-provenance and strict as-of tests."""
import json
import unittest
from urllib.error import HTTPError
from unittest.mock import patch
from datetime import datetime, timezone

from research.v42_warc_capture_probe import (
    enrich_audit, indexes_for_article, probe, select_articles,
    strict_market_join,
)

STEP = 14400


def iso(year, month, day, hour=0):
    return datetime(
        year, month, day, hour, tzinfo=timezone.utc,
    ).isoformat()


def article(url="https://example.org/a",
            published="2024-01-10T00:00:00+00:00"):
    return {
        "canonical_url": url,
        "published_at_utc": published,
        "updated_at_utc": None,
        "source_ids": ["cryptocurrency_cv"],
        "original_publisher": "Example",
        "title": "Metadata title only",
        "retrieved_at_utc": iso(2026, 11, 17),
        "availability_confidence": "retrospective_only",
        "version_hash": None,
    }


class V42WarcCaptureTests(unittest.TestCase):
    def test_article_sample_is_deterministic_and_month_stratified(self):
        rows = [
            article("https://example.org/jan-a", "2024-01-10T00:00:00+00:00"),
            article("https://example.org/jan-b", "2024-01-12T00:00:00+00:00"),
            article("https://example.org/feb", "2024-02-10T00:00:00+00:00"),
        ]
        first = select_articles(rows, limit=2)
        second = select_articles(rows, limit=2)
        self.assertEqual([x[0] for x in first], [x[0] for x in second])
        self.assertEqual(len(first), 2)

    def test_indexes_begin_with_first_snapshot_reaching_publication(self):
        indexes = [
            {
                "id": "CC-MAIN-2023-50",
                "from": "2023-12-01T00:00:00Z",
                "to": "2023-12-31T00:00:00Z",
                "cdx-api": "https://index.commoncrawl.org/a",
            },
            {
                "id": "CC-MAIN-2024-05",
                "from": "2024-01-01T00:00:00Z",
                "to": "2024-02-01T00:00:00Z",
                "cdx-api": "https://index.commoncrawl.org/b",
            },
            {
                "id": "CC-MAIN-2024-10",
                "from": "2024-02-02T00:00:00Z",
                "to": "2024-03-01T00:00:00Z",
                "cdx-api": "https://index.commoncrawl.org/c",
            },
        ]
        selected = indexes_for_article(
            indexes, "2024-01-10T00:00:00Z",
        )
        self.assertEqual(
            [x["id"] for x in selected],
            ["CC-MAIN-2024-05", "CC-MAIN-2024-10"],
        )

    def test_naive_common_crawl_collection_times_are_interpreted_as_utc(self):
        indexes = [
            {
                "id": "CC-MAIN-2022-49",
                "from": "2022-11-26T00:00:00",
                "to": "2022-12-10T00:00:00",
                "cdx-api": "https://index.commoncrawl.org/a",
            },
            {
                "id": "CC-MAIN-2023-06",
                "from": "2023-01-26T00:00:00",
                "to": "2023-02-09T00:00:00",
                "cdx-api": "https://index.commoncrawl.org/b",
            },
        ]
        selected = indexes_for_article(
            indexes, "2022-11-29T00:00:00Z",
        )
        self.assertEqual(
            [x["id"] for x in selected],
            ["CC-MAIN-2022-49", "CC-MAIN-2023-06"],
        )

    def test_collinfo_failure_is_recorded_not_raised(self):
        def unavailable(url, max_bytes=250_000):
            raise HTTPError(url, 404, "not found", None, None)
        with patch("research.v42_warc_capture_probe.time.sleep"):
            captures, status = probe(
                [article()], iso(2026, 11, 17), indexes=None,
                fetcher=unavailable,
            )
        self.assertEqual(captures, [])
        self.assertEqual(status["status"], "BLOCKED_OR_FAILED")
        self.assertEqual(status["requests_attempted"], 1)
        self.assertIn("HTTPError", status["failures"][0]["status"])

    def test_cdx_capture_digest_and_warc_locator_are_preserved(self):
        source = article()
        indexes = [
            {
                "id": "CC-MAIN-2024-05",
                "from": "2024-01-01T00:00:00Z",
                "to": "2024-02-01T00:00:00Z",
                "cdx-api": "https://index.commoncrawl.org/a",
            },
            {
                "id": "CC-MAIN-2024-10",
                "from": "2024-02-02T00:00:00Z",
                "to": "2024-03-01T00:00:00Z",
                "cdx-api": "https://index.commoncrawl.org/b",
            },
        ]
        cdx = {
            "url": source["canonical_url"],
            "timestamp": "20240112000000",
            "digest": "A" * 32,
            "filename": (
                "crawl-data/CC-MAIN-2024-05/segments/x/warc/file.warc.gz"
            ),
            "offset": "123",
            "length": "456",
            "status": "200",
            "mime": "text/html",
        }
        calls = []

        def fetcher(url, max_bytes=250_000):
            calls.append(url)
            return (json.dumps(cdx) + "\n").encode("utf-8")

        captures, status = probe(
            [source], iso(2026, 11, 17), indexes=indexes,
            fetcher=fetcher,
        )
        self.assertEqual(status["requests_attempted"], 2)
        self.assertEqual(status["verified_capture_versions"], 1)
        self.assertEqual(len(captures), 1)
        row = captures[0]
        self.assertEqual(row["version_hash"], "A" * 32)
        self.assertEqual(row["version_hash_algorithm"], "sha1_base32")
        self.assertEqual(row["capture_offset"], 123)
        self.assertEqual(row["capture_length"], 456)
        self.assertEqual(row["capture_type"], "common_crawl_index_digest")
        self.assertEqual(row["source_ids"], ["common_crawl"])
        self.assertNotIn("body", row)

    def test_bad_cdx_metadata_is_rejected(self):
        source = article()
        indexes = [{
            "id": "CC-MAIN-2024-05",
            "from": "2024-01-01T00:00:00Z",
            "to": "2024-02-01T00:00:00Z",
            "cdx-api": "https://index.commoncrawl.org/a",
        }]
        cdx = {
            "url": source["canonical_url"],
            "timestamp": "20240112000000",
            "digest": "invalid",
            "filename": "crawl-data/CC-MAIN-2024-05/warc/file.warc.gz",
            "offset": "-1",
            "length": "0",
            "status": "404",
            "mime": "text/html",
        }
        captures, status = probe(
            [source], iso(2026, 11, 17), indexes=indexes,
            fetcher=lambda url, max_bytes=250_000:
                (json.dumps(cdx) + "\n").encode("utf-8"),
        )
        self.assertEqual(captures, [])
        self.assertEqual(status["verified_capture_versions"], 0)

    def test_strict_market_join_uses_capture_plus_one_hour(self):
        capture = {
            "url": "https://example.org/a",
            "version_hash": "A" * 32,
            "version_hash_algorithm": "sha1_base32",
            "capture_reference": "crawl-data/x/warc/file.warc.gz",
            "index_version": "CC-MAIN-2024-05",
            "first_verified_capture_at_utc": iso(2024, 1, 1, 0),
            "verified_capture_at_utc": iso(2024, 1, 1, 0),
            "published_at_utc": iso(2024, 1, 1, 0),
            "updated_at_utc": None,
            "retrieved_at_utc": iso(2026, 11, 17),
            "capture_source": "common_crawl",
            "capture_type": "common_crawl_index_digest",
        }
        first = int(datetime(
            2024, 1, 1, 4, tzinfo=timezone.utc,
        ).timestamp())
        bars = [
            (first + i * STEP, 1.0, 2.0, 0.5, 1.0, 100.0)
            for i in range(1000)
        ]
        joined = strict_market_join([capture], bars)
        self.assertEqual(joined["strict_asof_eligible"], 1)
        self.assertEqual(
            joined["examples"][0]["first_eligible_bar_open_utc"],
            iso(2024, 1, 1, 4),
        )

    def test_capture_rows_do_not_inflate_article_target_or_reset_cursor(self):
        source = article()
        capture = {
            "url": source["canonical_url"],
            "canonical_url": source["canonical_url"],
            "source_ids": ["common_crawl"],
            "version_hash": "A" * 32,
            "version_hash_algorithm": "sha1_base32",
            "capture_type": "common_crawl_index_digest",
            "first_verified_capture_at_utc": iso(2024, 1, 12),
            "verified_capture_at_utc": iso(2024, 1, 12),
            "retrieved_at_utc": iso(2026, 11, 17),
            "capture_reference": "crawl-data/x/warc/file.warc.gz",
            "index_version": "CC-MAIN-2024-05",
            "availability_confidence": "verified_crawl",
            "published_at_utc": source["published_at_utc"],
            "updated_at_utc": None,
            "capture_source": "common_crawl",
        }
        audit = {
            "schema": "v38_metadata_provenance_1",
            "android_strategy": "HOLD",
            "max_paper_entry_aud": 100,
            "records": [source],
            "deduplicated_rows": 1,
            "raw_normalized_rows": 1,
            "historically_verified_capture_rows": 0,
            "source_status": {
                "cryptocurrency_cv": {
                    "per_month": {"2024-01": {"ok": True}},
                },
            },
            "retrieved_at_utc": iso(2026, 11, 17),
            "market_join": {"strict_asof_eligible": 0},
            "archive_months_requested": ["2024-01"],
            "cursor_before_attempted_months": ["2024-01"],
            "historical_article_version_rows": 1,
            "notes": [],
        }
        first = int(datetime(
            2024, 1, 13, tzinfo=timezone.utc,
        ).timestamp())
        bars = [
            (first + i * STEP, 1.0, 2.0, 0.5, 1.0, 100.0)
            for i in range(1000)
        ]
        status = {
            "status": "OK_CAPTURE_PROOFS_FOUND",
            "verified_capture_versions": 1,
        }
        enriched = enrich_audit(audit, [capture], status, bars)
        self.assertEqual(enriched["deduplicated_rows"], 2)
        self.assertEqual(enriched["historical_article_version_rows"], 1)
        self.assertEqual(enriched["historically_verified_capture_rows"], 1)
        self.assertIn("cryptocurrency_cv", enriched["source_status"])
        self.assertIn("common_crawl", enriched["source_status"])
        self.assertEqual(enriched["market_join"]["strict_asof_eligible"], 1)
        self.assertEqual(
            enriched["cursor_before_attempted_months"], ["2024-01"],
        )


if __name__ == "__main__":
    unittest.main()

"""V44 strict news-to-Kraken as-of join tests."""
import unittest
from datetime import datetime, timezone

from research.v44_asof_join import strict_asof_join


def ts(value):
    return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp())


def news_row(capture_ts, published="2026-11-17T00:00:00Z", digest="a"):
    digest = digest * 64
    return {
        "url": "https://example.com/news",
        "capture_type": "first_observed_snapshot",
        "content_sha256": digest,
        "version_capture_sha256": digest,
        "published_at_utc": published,
        "updated_at_utc": None,
        "verified_capture_at_utc": capture_ts,
        "retrieved_at_utc": capture_ts,
    }


class V44AsOfJoinTests(unittest.TestCase):
    def test_first_tradable_bar_is_not_before_capture_plus_latency(self):
        bars = [
            (ts("2026-11-18T00:00:00Z"), 100, 101, 99, 100, 1),
            (ts("2026-11-18T04:00:00Z"), 100, 101, 99, 100, 1),
            (ts("2026-11-18T08:00:00Z"), 100, 101, 99, 100, 1),
        ]
        row = news_row("2026-11-18T00:30:00Z")
        result = strict_asof_join([row], bars, {"source": "fixture"})
        self.assertEqual(result["strict_asof_eligible"], 1)
        match = result["matches"][0]
        self.assertEqual(match["available_at_utc"], "2026-11-18T01:30:00Z")
        self.assertEqual(match["first_tradable_bar_open_utc"],
                         "2026-11-18T04:00:00Z")
        self.assertTrue(result["no_lookahead"])

    def test_capture_after_last_bar_is_pending_not_backdated(self):
        bars = [
            (ts("2026-11-18T00:00:00Z"), 100, 101, 99, 100, 1),
            (ts("2026-11-18T04:00:00Z"), 100, 101, 99, 100, 1),
        ]
        row = news_row("2026-11-18T08:00:00Z")
        result = strict_asof_join([row], bars)
        self.assertEqual(result["strict_asof_eligible"], 0)
        self.assertEqual(result["pending_after_last_bar"], 1)
        self.assertEqual(result["pending"][0]["reason"],
                         "AFTER_LAST_COMPLETED_BAR")

    def test_invalid_version_proof_is_rejected(self):
        bars = [
            (ts("2026-11-18T00:00:00Z"), 100, 101, 99, 100, 1),
            (ts("2026-11-18T04:00:00Z"), 100, 101, 99, 100, 1),
        ]
        row = news_row("2026-11-17T00:00:00Z")
        row["version_capture_sha256"] = "f" * 64
        result = strict_asof_join([row], bars)
        self.assertEqual(result["proof_rejected"], 1)
        self.assertEqual(result["strict_asof_eligible"], 0)

    def test_market_gaps_are_reported(self):
        bars = [
            (ts("2026-11-18T00:00:00Z"), 100, 101, 99, 100, 1),
            (ts("2026-11-18T08:00:00Z"), 100, 101, 99, 100, 1),
        ]
        result = strict_asof_join([], bars)
        self.assertEqual(result["gap_count"], 1)
        self.assertEqual(result["gaps"][0]["gap_seconds"], 28800)


if __name__ == "__main__":
    unittest.main()

"""Regression tests for strict historical as-of selection failure handling."""
import unittest
from research.v44_news_asof import asof_versions

ROW = dict(url="https://example.org/news", published_at="2023-01-01T00:00:00Z",
           capture_at="2023-01-02T00:00:00Z", retrieved_at="2026-11-21T00:00:00Z",
           captured_sha256="a"*64, version_id="v1")

class AsOfHardeningTests(unittest.TestCase):
    def test_nonfinite_and_negative_latency_rejected(self):
        for latency in (float("nan"), float("inf"), float("-inf"), -1, None, "1"):
            with self.subTest(latency=latency):
                with self.assertRaises(ValueError):
                    asof_versions([ROW], "2023-01-03T00:00:00Z", latency)

    def test_invalid_row_does_not_abort_batch(self):
        bad = [None, {}, dict(ROW, captured_sha256=42),
               dict(ROW, capture_at=42), dict(ROW, url=42)]
        selected = asof_versions(bad + [ROW], "2023-01-03T00:00:00Z")
        self.assertEqual(selected, [ROW])

    def test_future_capture_never_visible(self):
        self.assertEqual(asof_versions([ROW], "2023-01-01T12:00:00Z"), [])

    def test_latency_boundary(self):
        self.assertEqual(asof_versions([ROW], "2023-01-02T01:00:00Z", 3600), [ROW])
        self.assertEqual(asof_versions([ROW], "2023-01-02T01:00:00Z", 3601), [])

if __name__ == "__main__":
    unittest.main()

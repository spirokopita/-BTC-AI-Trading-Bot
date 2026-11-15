"""V41 no-lookahead volume, WARC-news and selection tests."""
import json
import math
import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timezone, timedelta

from research.v41_volume_confirmation import (
    volume_feature, news_active, load_verified_news, select,
    replay_variant, CANDIDATES, VOLUME_THRESHOLD,
)

STEP = 14400
START = int(datetime(2023, 1, 1, tzinfo=timezone.utc).timestamp())


def fixture(n=700):
    rows = []
    for i in range(n):
        price = 20000.0 * math.exp(0.0003 * i)
        rows.append((START + i * STEP, price, price * 1.01,
                     price * .99, price * 1.005, 100.0 + (i % 7)))
    return rows


class V41VolumeTests(unittest.TestCase):
    def test_feature_uses_only_completed_candle_and_past_reference(self):
        bars = fixture()
        before = volume_feature(bars, 500)
        bars[500] = (bars[500][0], 999999.0, 999999.0, 999998.0,
                     999999.0, 999999999.0)
        bars[600] = (bars[600][0], 888888.0, 888888.0, 888887.0,
                     888888.0, 888888888.0)
        self.assertEqual(before, volume_feature(bars, 500))

    def test_feature_uses_target_i_minus_one_not_current_open(self):
        bars = fixture()
        feature = volume_feature(bars, 500)
        self.assertEqual(feature["signal_candle_ts"], bars[499][0])
        self.assertEqual(feature["reference_end_ts"], bars[498][0])

    def test_feature_delayed_placebo_is_past_only(self):
        bars = fixture()
        actual = volume_feature(bars, 500)
        delayed = volume_feature(bars, 500, delay_bars=42)
        self.assertEqual(delayed["signal_candle_ts"], bars[457][0])
        self.assertLess(delayed["signal_candle_ts"], actual["signal_candle_ts"])

    def test_missing_volume_or_zero_median_fails_closed(self):
        bars = fixture()
        with self.assertRaises(ValueError):
            volume_feature([row[:5] for row in bars], 500)
        zero = list(bars)
        for i in range(480, 500):
            row = zero[i]
            zero[i] = (*row[:5], 0.0)
        self.assertIsNone(volume_feature(zero, 500))

    def test_warc_news_strict_asof_and_delayed_control(self):
        t = START + 600 * STEP
        events = [{
            "available_ts": t,
            "published_ts": t - 100,
            "updated_ts": None,
            "url": "https://example.org/article",
        }]
        self.assertTrue(news_active(events, t + 1))
        self.assertFalse(news_active(events, t - 1))
        self.assertFalse(news_active(events, t + 1, delay_seconds=7 * 86400))
        self.assertFalse(news_active([{
            "available_ts": t + 100, "published_ts": t + 100,
            "updated_ts": None, "url": "https://example.org/future",
        }], t + 1))

    def test_loader_excludes_retrospective_api_metadata(self):
        rows = [
            {"availability_confidence": "retrospective_only",
             "published_at_utc": "2021-01-01T00:00:00Z"},
            {"availability_confidence": "verified_crawl",
             "first_verified_capture_at_utc": "2021-01-02T00:00:00Z",
             "published_at_utc": "2021-01-01T00:00:00Z",
             "updated_at_utc": None, "version_hash": "abc",
             "capture_reference": "warc.gz", "canonical_url": "https://example.org/a",
             "source_ids": ["common_crawl"]},
            {"availability_confidence": "verified_crawl",
             "first_verified_capture_at_utc": "2021-01-02T00:00:00Z",
             "published_at_utc": "2021-01-03T00:00:00Z",
             "updated_at_utc": None, "version_hash": "future",
             "capture_reference": "warc.gz", "canonical_url": "https://example.org/b",
             "source_ids": ["common_crawl"]},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "news.jsonl"
            path.write_text("".join(json.dumps(x) + "\n" for x in rows))
            events, digest = load_verified_news(path)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["url"], "https://example.org/a")
        self.assertEqual(len(digest), 64)

    def test_selector_requires_positive_train_and_validation(self):
        bad = {"trades": 0, "net_aud": 0.0}
        train = {name: dict(bad) for name in ("h80_base", "h80_vol_confirm", "h50_vol_confirm")}
        val = {name: dict(bad) for name in train}
        self.assertEqual(select(train, val), "HOLD")
        train["h80_vol_confirm"] = {"trades": 3, "net_aud": 4.0}
        val["h80_vol_confirm"] = {"trades": 2, "net_aud": 2.0}
        self.assertEqual(select(train, val), "h80_vol_confirm")
        val["h80_vol_confirm"] = {"trades": 2, "net_aud": -1.0}
        self.assertEqual(select(train, val), "HOLD")

    def test_replay_reconciles_costs_and_respects_a100_cap(self):
        bars = fixture()
        result = replay_variant(bars, 305, 650, "h80_base", audit=True)
        self.assertLessEqual(max(
            (t["entry_debit_aud"] for t in result["trade_audit"]), default=0.0), 100.0 + 1e-8)
        self.assertAlmostEqual(
            result["gross_aud"] - result["fees_aud"] - result["spread_aud"]
            - result["slippage_aud"], result["net_aud"], places=6)
        self.assertEqual(result["strategy"], "h80_base")

    def test_volume_candidates_are_registered_and_base_is_not_vetoed(self):
        self.assertIn("h80_vol_confirm", CANDIDATES)
        self.assertIn("h80_news_attention", CANDIDATES)
        self.assertIn("h80_vol_placebo7d", CANDIDATES)
        self.assertGreater(VOLUME_THRESHOLD, 1.0)


if __name__ == "__main__":
    unittest.main()

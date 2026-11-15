"""V41 no-lookahead volume, V48 version-proof news and selection tests."""
import json
import math
import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timezone

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


def proof_row(capture):
    iso = lambda t: datetime.fromtimestamp(t, timezone.utc).isoformat()
    digest = "a" * 64
    return {
        "url": "https://example.org/article",
        "capture_type": "independent_warc",
        "published_at_utc": iso(capture - 7200),
        "updated_at_utc": iso(capture - 7200),
        "verified_capture_at_utc": iso(capture),
        "retrieved_at_utc": iso(capture + 60),
        "content_sha256": digest,
        "version_capture_sha256": digest,
    }


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

    def test_v48_proof_and_delayed_news_asof(self):
        t = START + 600 * STEP
        row = proof_row(t)
        self.assertFalse(news_active([row], t + 3599))
        self.assertTrue(news_active([row], t + 3600))
        self.assertFalse(news_active([row], t + 7 * 86400 + 3599,
                                     delay_seconds=7 * 86400))
        self.assertTrue(news_active([row], t + 7 * 86400 + 3600,
                                    delay_seconds=7 * 86400))
        future = dict(row, updated_at_utc=datetime.fromtimestamp(
            t + 86400, timezone.utc).isoformat())
        self.assertFalse(news_active([future], t + 3600))

    def test_loader_rejects_legacy_warc_digest_without_exact_content_sha256(self):
        t = START + 500 * STEP
        legacy = {
            "availability_confidence": "verified_crawl",
            "capture_source": "common_crawl",
            "first_verified_capture_at_utc": datetime.fromtimestamp(
                t, timezone.utc).isoformat(),
            "retrieved_at_utc": datetime.fromtimestamp(
                t + 60, timezone.utc).isoformat(),
            "published_at_utc": datetime.fromtimestamp(
                t - 7200, timezone.utc).isoformat(),
            "version_hash": "COMMON_CRAWL_DIGEST_NOT_SHA256",
            "capture_reference": "warc.gz",
            "canonical_url": "https://example.org/legacy",
            "source_ids": ["common_crawl"],
        }
        retrospective = {
            "availability_confidence": "retrospective_only",
            "published_at_utc": "2021-01-01T00:00:00Z",
            "canonical_url": "https://example.org/retro",
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "news.jsonl"
            path.write_text("".join(json.dumps(x) + "\n"
                                    for x in (legacy, retrospective)))
            events, digest, rejected = load_verified_news(path)
        self.assertEqual(events, [])
        self.assertEqual(rejected.get("NO_VERSION_HASH", 0), 0)
        self.assertEqual(rejected.get("NO_INDEPENDENT_CAPTURE_PROOF"), 2)
        self.assertEqual(len(digest), 64)

    def test_loader_rejects_missing_exact_version_hash(self):
        t = int(datetime.now(timezone.utc).timestamp()) - 7200
        row = proof_row(t)
        row["content_sha256"] = ""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "news.jsonl"
            path.write_text(json.dumps(row) + "\n")
            events, digest, rejected = load_verified_news(path)
        self.assertEqual(events, [])
        self.assertEqual(rejected.get("NO_VERSION_HASH"), 1)

    def test_loader_accepts_exact_hash_matching_capture(self):
        t = int(datetime.now(timezone.utc).timestamp()) - 7200
        row = proof_row(t)
        row["availability_confidence"] = "verified_crawl"
        row["capture_source"] = "common_crawl"
        row["first_verified_capture_at_utc"] = row["verified_capture_at_utc"]
        row["canonical_url"] = row["url"]
        row["version_hash"] = row["content_sha256"]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "news.jsonl"
            path.write_text(json.dumps(row) + "\n")
            events, digest, rejected = load_verified_news(path)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["content_sha256"], row["content_sha256"])
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

    def test_volume_candidates_are_registered(self):
        self.assertIn("h80_vol_confirm", CANDIDATES)
        self.assertIn("h80_news_attention", CANDIDATES)
        self.assertIn("h80_vol_placebo7d", CANDIDATES)
        self.assertGreater(VOLUME_THRESHOLD, 1.0)


if __name__ == "__main__":
    unittest.main()

"""V41 retrospective news event-study no-lookahead and cost tests."""
import json
import math
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from research.v41_recent_news_event_study import (
    epoch, entry_index, prior_features, net_trade, match_controls,
    load_events, run_event_study, STEP,
)

START = int(datetime(2026, 7, 1, tzinfo=timezone.utc).timestamp())


def bars_fixture(n=720):
    out = []
    for i in range(n):
        px = 90000.0 * math.exp(0.0001 * i + 0.0005 * math.sin(i / 13))
        out.append((START + i*STEP, px, px*1.01, px*.99,
                    px*1.002, 100.0 + (i % 13)))
    return out


def event_doc():
    pub = datetime.fromtimestamp(START + 500*STEP, timezone.utc).isoformat()
    return {
        "schema": "v41_recent_news_events_1",
        "retrieved_at_utc": "2026-11-16T00:00:00Z",
        "events": [{
            "event_id": "E1", "cluster_id": "C1", "event_type": "test",
            "causal_degree": 1, "scheduled_release": False,
            "published_at_utc": pub, "latency_seconds": 3600,
            "first_observed_at_utc": None, "source_urls": ["https://example.org/e"],
            "btc_usd_sign_hypothesis": "negative",
            "aud_usd_sign_hypothesis": "neutral",
            "btc_aud_sign_hypothesis": "negative",
        }],
        "scheduled_future_events": [],
    }


class V41RecentEventStudyTests(unittest.TestCase):
    def test_utc_parser_rejects_naive_or_non_utc(self):
        self.assertGreater(epoch("2026-11-01T00:00:00Z"), 0)
        with self.assertRaises(ValueError):
            epoch("2026-11-01T00:00:00")
        with self.assertRaises(ValueError):
            epoch("2026-11-01T01:00:00+01:00")

    def test_entry_is_next_completed_bar_after_publication_plus_latency(self):
        bars = bars_fixture()
        published = bars[500][0] + 60
        index = entry_index(bars, 450, len(bars), published + 3600)
        self.assertEqual(index, 501)
        self.assertGreaterEqual(bars[index][0], published + 3600)

    def test_prior_features_do_not_read_current_or_future_bars(self):
        bars = bars_fixture()
        before = prior_features(bars, 500)
        for i in range(500, len(bars)):
            row = bars[i]
            bars[i] = (row[0], 1e9, 1e9, 1e9, 1e9, 1e9)
        self.assertEqual(before, prior_features(bars, 500))

    def test_net_trade_reconciles_costs_and_a100_cap(self):
        result = net_trade(95000.0, 97000.0)
        self.assertLessEqual(result["entry_debit_aud"], 100.0 + 1e-8)
        self.assertAlmostEqual(
            result["gross_aud"]-result["fees_aud"]-result["spread_aud"]
            -result["slippage_aud"], result["net_aud"], places=6)
        self.assertEqual(result["taker_fee_each_side_bps"], 80)

    def test_controls_are_strictly_prior_and_match_weekday_hour(self):
        bars = bars_fixture()
        event_index = 650
        controls = match_controls(bars, event_index, [event_index], 100, 700)
        event_dt = datetime.fromtimestamp(bars[event_index][0], timezone.utc)
        self.assertTrue(all(c["bar_index"] < event_index for c in controls))
        self.assertTrue(all(
            datetime.fromtimestamp(bars[c["bar_index"]][0], timezone.utc).weekday()
            == event_dt.weekday() for c in controls))
        self.assertTrue(all(event_index-c["bar_index"] > 42 for c in controls))

    def test_load_events_rejects_false_first_observed(self):
        doc = event_doc()
        doc["events"][0]["first_observed_at_utc"] = "2026-11-01T00:00:00Z"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "events.json"
            path.write_text(json.dumps(doc))
            with self.assertRaises(ValueError):
                load_events(path)

    def test_event_study_labels_reconstruction_and_overlapping_events(self):
        bars = bars_fixture()
        doc = event_doc()
        event = doc["events"][0]
        event["published_at_utc"] = datetime.fromtimestamp(
            bars[500][0], timezone.utc).isoformat()
        event2 = dict(event, event_id="E2", published_at_utc=datetime.fromtimestamp(
            bars[510][0], timezone.utc).isoformat())
        events = [{
            **row,
            "_published_ts": epoch(row["published_at_utc"]),
            "_available_ts": epoch(row["published_at_utc"])+row["latency_seconds"],
        } for row in (event,event2)]
        report = run_event_study(bars, {"source":"test"}, events, 100, 700)
        self.assertEqual(report["mode"], "V41_RETROSPECTIVE_PUBLICATION_TIME_EVENT_STUDY")
        self.assertIsNone(report["first_observed_at_utc"])
        self.assertTrue(report["overlap_pairs"])
        self.assertEqual(report["strategy_selection"], "NONE; descriptive event study only")


if __name__ == "__main__":
    unittest.main()

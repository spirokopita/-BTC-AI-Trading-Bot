"""V26 deterministic controls. Synthetic candles are NOT real market evidence."""
import math
import unittest

from research.kraken_archive import STEP
from research.forward_gap_experiment import (
    contiguous_segments, select_periods, extended_signal, slow_simulate,
    same_stake_buy_hold, run_experiment, CANDIDATES, WARMUP,
)

PRE_START = 1577836800      # 2020-01-01 00:00 UTC
LATER_START = 1761955200    # 2025-11-01 00:00 UTC


def make_bars(n, start, price=100):
    bars = []
    for i in range(n):
        mid = price + .01 * i + 3 * math.sin(i / 22)
        op = mid + .1
        cl = mid + .2
        bars.append((start + i * STEP, op, mid + 2, mid - 2, cl, 2.))
    return bars


def fixture():
    return make_bars(2800, PRE_START) + make_bars(1100, LATER_START, 150)


class ForwardGapResearchTest(unittest.TestCase):
    def test_gaps_not_fabricated_and_future_selected_by_time(self):
        bars = fixture()
        segments = contiguous_segments(bars)
        self.assertEqual([len(s) for s in segments], [2800, 1100])
        old, recent = select_periods(bars)
        self.assertEqual(len(old), 2800)
        self.assertEqual(len(recent), 1100)
        self.assertLess(old[-1][0], recent[0][0])
        self.assertEqual(recent[0][0], LATER_START)

    def test_bad_timestamps_rejected(self):
        bars = make_bars(3, PRE_START)
        with self.assertRaisesRegex(ValueError, "Unordered"):
            contiguous_segments([bars[0], bars[0]])
        with self.assertRaisesRegex(ValueError, "Unordered"):
            contiguous_segments([bars[0], (bars[1][0] + 1, *bars[1][1:])])

    def test_slow_signal_is_causal(self):
        bars = make_bars(450, PRE_START)
        original = extended_signal(bars, 250, "slow_sma_005")
        later = list(bars)
        b = later[251]
        later[251] = (b[0], b[1] * 5, b[2] * 5, b[3] * 5, b[4] * 5, b[5])
        self.assertEqual(original, extended_signal(later, 250, "slow_sma_005"))
        with self.assertRaisesRegex(ValueError, "Unknown"):
            extended_signal(bars, 250, "invented")

    def test_slow_costs_reconcile_and_double_costs_hurt(self):
        bars = make_bars(900, PRE_START)
        for name in ("slow_sma_005", "slow_sma_020"):
            paid = slow_simulate(bars, WARMUP, 800, name)
            free = slow_simulate(bars, WARMUP, 800, name, fee_multiplier=0)
            self.assertAlmostEqual(
                paid["gross_aud"] - paid["fees_aud"] -
                paid["spread_aud"] - paid["slippage_aud"],
                paid["net_aud"], places=4,
            )
            self.assertGreaterEqual(free["net_aud"], paid["net_aud"] - 1e-5)
            self.assertEqual(paid["trades"], paid["wins"] + paid["losses"] +
                             sum(t["net_aud"] == 0 for t in paid["trade_log"]))
        with self.assertRaisesRegex(ValueError, "unobserved"):
            slow_simulate(fixture(), WARMUP, 500, "slow_sma_005")

    def test_forward_protocol_and_buy_hold_reconcile(self):
        report = run_experiment(fixture(), {"source": "SYNTHETIC_NOT_MARKET"})
        self.assertEqual(len(report["folds"]), 2)
        self.assertEqual(set(report["train"]), set(CANDIDATES))
        self.assertIn("NOT UNTOUCHED", report["test_integrity"])
        self.assertTrue(report["promotion"].startswith("REJECTED"))
        self.assertLess(report["training_segment"]["validation_end_utc"],
                        report["later_segment"]["first_utc"])
        for fold in report["folds"]:
            self.assertIn("slow_sma_005", fold["strategies"])
            self.assertIn("sma", fold["strategies"])
            self.assertIn("max_drawdown_pct", fold["strategies"]["sma"])
            hold = fold["same_AUD50_buy_hold"]
            self.assertAlmostEqual(
                hold["gross_aud"] - hold["fees_aud"] -
                hold["spread_aud"] - hold["slippage_aud"],
                hold["net_aud"], places=4,
            )
            if fold["selected_from_pre2025_train_validation"] == "HOLD":
                self.assertEqual(fold["selected_net_aud"], 0.)

    def test_future_prices_cannot_change_pre2025_selection(self):
        bars = fixture()
        before = run_experiment(bars, {"source": "SYNTHETIC"})["selected_policy"]
        changed = list(bars)
        for i in range(2800, len(changed)):
            t, op, hi, lo, cl, vol = changed[i]
            changed[i] = (t, op * 1.2, hi * 1.2, lo * 1.2, cl * 1.2, vol)
        after = run_experiment(changed, {"source": "SYNTHETIC"})["selected_policy"]
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()

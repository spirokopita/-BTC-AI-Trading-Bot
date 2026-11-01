"""V27 deterministic sizing tests; fixtures are SYNTHETIC, not market results."""
import unittest

from research.forward_gap_experiment import (
    WARMUP, slow_simulate, run_experiment, same_stake_buy_hold,
)
from research.market_experiment import simulate
from tests.test_forward_gap_experiment import fixture, make_bars, PRE_START


class PositionSizingTest(unittest.TestCase):
    def test_aud100_is_allowed_and_larger_than_aud50(self):
        bars = make_bars(900, PRE_START)
        for name, fn in (("sma", simulate), ("slow_sma_005", slow_simulate)):
            old = fn(bars, WARMUP, 850, name, position_cap_aud=50.)
            new = fn(bars, WARMUP, 850, name, position_cap_aud=100.)
            self.assertEqual(old["trades"], new["trades"])
            self.assertAlmostEqual(new["gross_aud"], 2 * old["gross_aud"], delta=.10)
            self.assertAlmostEqual(new["fees_aud"], 2 * old["fees_aud"], delta=.10)
            self.assertAlmostEqual(new["spread_aud"], 2 * old["spread_aud"], delta=.10)
            self.assertAlmostEqual(new["slippage_aud"], 2 * old["slippage_aud"], delta=.10)
            self.assertAlmostEqual(
                new["gross_aud"] - new["fees_aud"] - new["spread_aud"] -
                new["slippage_aud"], new["net_aud"], places=4)

    def test_invalid_position_cap_rejected(self):
        bars = make_bars(900, PRE_START)
        for fn, name in ((simulate, "sma"), (slow_simulate, "slow_sma_005")):
            for invalid in (0., -1., 101., 1000.):
                with self.assertRaisesRegex(ValueError, "approved"):
                    fn(bars, WARMUP, 850, name, position_cap_aud=invalid)

    def test_chronological_selection_unchanged_by_later_future_prices(self):
        bars = fixture()
        original = run_experiment(bars, {"source": "SYNTHETIC"}, position_cap_aud=100.)
        changed = list(bars)
        for i in range(2800, len(changed)):
            t, op, hi, lo, cl, vol = changed[i]
            changed[i] = (t, op * 1.4, hi * 1.4, lo * 1.4, cl * 1.4, vol)
        modified = run_experiment(changed, {"source": "SYNTHETIC"}, position_cap_aud=100.)
        self.assertEqual(original["selected_policy"], modified["selected_policy"])
        self.assertEqual(original["train"], modified["train"])
        self.assertEqual(original["validation"], modified["validation"])
        self.assertEqual(original["folds"][0]["start_utc"], modified["folds"][0]["start_utc"])

    def test_benchmark_uses_same_position_cap(self):
        bars = make_bars(900, PRE_START)
        a = same_stake_buy_hold(bars, WARMUP, 850, 50.)
        b = same_stake_buy_hold(bars, WARMUP, 850, 100.)
        self.assertAlmostEqual(b["net_aud"], 2 * a["net_aud"], delta=.0001)
        with self.assertRaisesRegex(ValueError, "approved"):
            same_stake_buy_hold(bars, WARMUP, 850, 200.)


if __name__ == "__main__":
    unittest.main()

import math
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace

from research.v44_fx_volatility_gate import (
    CANDIDATES, calibration_thresholds, fx_volatility_at,
    make_entry_veto, percentile,
)

STEP = 14400
START = int(datetime(2023, 1, 1, tzinfo=timezone.utc).timestamp())


def fx_fixture(days=420, daily_vol=0.001):
    times = [START - 30*86400 + i*86400 for i in range(days)]
    rates = [0.75 * math.exp(daily_vol * math.sin(i*1.7) + 0.0001*i)
             for i in range(days)]
    return SimpleNamespace(times=times, rates=rates,
                           days=[datetime.fromtimestamp(t, timezone.utc).date().isoformat()
                                 for t in times])


def bar_fixture(n=1600):
    rows = []
    for i in range(n):
        p = 30000 * math.exp(0.00012*i + 0.0008*math.sin(i/13))
        rows.append([START + i*STEP, p, p*1.003, p*0.997, p, 10.0, 100])
    return rows


class V44FXVolatilityTests(unittest.TestCase):
    def test_asof_uses_only_available_daily_fx_observations(self):
        fx = fx_fixture()
        decision = START + 100*86400
        feature = fx_volatility_at(fx, decision)
        self.assertIsNotNone(feature)
        self.assertLessEqual(feature["latest_observation_available_at"], decision)
        self.assertEqual(feature["observations"], 21)

    def test_future_fx_append_does_not_change_past_feature(self):
        fx = fx_fixture()
        decision = START + 100*86400
        before = fx_volatility_at(fx, decision)
        fx.times.append(decision + 10)
        fx.rates.append(9.9)
        fx.days.append("2099-01-01")
        self.assertEqual(before, fx_volatility_at(fx, decision))

    def test_seven_day_placebo_uses_older_fx(self):
        fx = fx_fixture()
        decision = START + 100*86400
        actual = fx_volatility_at(fx, decision)
        placebo = fx_volatility_at(fx, decision, delay_days=7)
        self.assertLess(placebo["latest_observation_available_at"],
                        actual["latest_observation_available_at"])
        with self.assertRaises(ValueError):
            fx_volatility_at(fx, decision, delay_days=2)

    def test_stale_or_missing_fx_fails_closed(self):
        fx = fx_fixture(days=40)
        stale_decision = fx.times[-1] + 11*86400
        self.assertIsNone(fx_volatility_at(fx, stale_decision))
        self.assertIsNone(fx_volatility_at(
            SimpleNamespace(times=[START], rates=[0.75]), START + 30*86400))

    def test_bad_fx_rates_rejected(self):
        fx = SimpleNamespace(times=[START + i*86400 for i in range(30)],
                             rates=[0.75]*20 + [0.0]*10)
        with self.assertRaises(ValueError):
            fx_volatility_at(fx, START + 29*86400)

    def test_percentile_is_deterministic_and_bounded(self):
        self.assertEqual(percentile(list(range(1, 101)), 0.75), 75)
        self.assertEqual(percentile(list(range(1, 101)), 0.90), 90)
        self.assertIsNone(percentile([1.0]*29, 0.75))
        with self.assertRaises(ValueError):
            percentile([1.0]*40, 0.4)

    def test_calibration_uses_only_early_training_window(self):
        bars = bar_fixture()
        fx = fx_fixture(days=600)
        base = calibration_thresholds(bars, fx, train_end=900)
        calibration_last_ts = bars[base["calibration_end_index_exclusive"]-1][0]
        # Mutating observations that occur after the calibration cutoff cannot
        # alter the threshold used for validation/test.
        for j, t in enumerate(fx.times):
            if t > calibration_last_ts:
                fx.rates[j] *= 1.8
        changed = calibration_thresholds(bars, fx, train_end=900)
        self.assertEqual(base["q75"], changed["q75"])
        self.assertEqual(base["q90"], changed["q90"])
        self.assertGreaterEqual(base["coverage_fraction"], 0.75)

    def test_entry_gate_fails_closed_and_base_is_untouched(self):
        bars = bar_fixture(800)
        fx = fx_fixture(days=600)
        self.assertIsNone(make_entry_veto(bars, fx, "h80_base", {}))
        veto = make_entry_veto(bars, fx, "h80_fxvol_q75", {"q75": 1e-9})
        self.assertTrue(veto(bars[500][0]))
        missing = make_entry_veto(bars, fx, "h80_fxvol_q90", {"q90": None})
        self.assertTrue(missing(bars[500][0]))
        with self.assertRaises(ValueError):
            make_entry_veto(bars, fx, "invented", {})

    def test_candidate_menu_is_frozen(self):
        self.assertEqual(CANDIDATES, (
            "h80_base", "h80_fxvol_q75", "h80_fxvol_q90",
            "h80_fxvol_q75_placebo7d",
        ))


if __name__ == "__main__":
    unittest.main()

"""V44 cross-rate exit tests: past-only inputs, costs, and selector safety."""
import math
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from research.v31_hysteresis import replay as base_replay
from research.v44_fx_exit import (
    CANDIDATES, make_exit_veto, replay_variant, select,
)

STEP = 14400
START = int(datetime(2023, 1, 1, tzinfo=timezone.utc).timestamp())


def bars_fixture(n=1000):
    rows = []
    for i in range(n):
        price = 100.0
        rows.append((START + i * STEP, price, price + 1,
                     price - 1, price, 100.0))
    return rows


class V44FxExitTests(unittest.TestCase):
    def test_mask_exit_requires_positive_btc_aud_and_weak_implied_usd(self):
        bars = bars_fixture()
        idx = 500
        feature = {
            "btc_aud_log30": math.log(1.03),
            "implied_btc_usd_log30": -0.001,
        }
        fx = object()
        with patch("research.v44_fx_exit.decomposition",
                   return_value=feature) as mocked:
            veto, counts = make_exit_veto(bars, fx, "h80_fx_mask_exit_0")
            self.assertTrue(veto(bars[idx][0]))
            mocked.assert_called_once_with(bars, idx, fx, delay_days=0)
            self.assertEqual(counts["forced_exits"], 1)

    def test_mask_exit_rejects_weak_btc_aud_or_strong_usd_component(self):
        bars = bars_fixture()
        idx = 500
        cases = (
            {"btc_aud_log30": math.log(1.01),
             "implied_btc_usd_log30": -0.05},
            {"btc_aud_log30": math.log(1.03),
             "implied_btc_usd_log30": 0.01},
        )
        for feature in cases:
            with patch("research.v44_fx_exit.decomposition",
                       return_value=feature):
                veto, _ = make_exit_veto(
                    bars, None, "h80_fx_mask_exit_0")
                self.assertFalse(veto(bars[idx][0]))

    def test_strict_candidate_and_seven_day_placebo_thresholds(self):
        bars = bars_fixture()
        idx = 500
        feature = {"btc_aud_log30": math.log(1.03),
                   "implied_btc_usd_log30": math.log(0.995)}
        with patch("research.v44_fx_exit.decomposition",
                   return_value=feature) as mocked:
            strict, _ = make_exit_veto(
                bars, None, "h80_fx_mask_exit_m1")
            self.assertFalse(strict(bars[idx][0]))
            placebo, _ = make_exit_veto(
                bars, None, "h80_fx_mask_exit_placebo7d")
            self.assertTrue(placebo(bars[idx][0]))
            self.assertEqual(mocked.call_args_list[0].kwargs["delay_days"], 0)
            self.assertEqual(mocked.call_args_list[1].kwargs["delay_days"], 7)

    def test_missing_fx_does_not_force_exit(self):
        bars = bars_fixture()
        with patch("research.v44_fx_exit.decomposition", return_value=None):
            veto, counts = make_exit_veto(
                bars, None, "h80_fx_mask_exit_0")
            self.assertFalse(veto(bars[500][0]))
            self.assertEqual(counts["missing_fx"], 1)
            self.assertEqual(counts["forced_exits"], 0)

    def test_exit_callback_only_runs_while_holding_after_min_hold(self):
        bars = bars_fixture()
        start = 600
        bars[start + 7] = (
            bars[start + 7][0], 90.0, 91.0, 89.0, 90.0, 100.0,
        )
        calls = []

        def signal(rows, i, name, holding=False, held=0, events=()):
            if i == start and not holding:
                return "BUY"
            return "HOLD"

        def exit_veto(ts):
            calls.append(ts)
            return ts == bars[start + 7][0]

        with patch("research.v31_hysteresis.decision", side_effect=signal):
            result = base_replay(
                bars, start, start + 20, "h80_300",
                exit_veto=exit_veto, audit=True,
            )
        self.assertEqual(len(result["trade_audit"]), 1)
        self.assertEqual(result["trade_audit"][0]["exit_ts"],
                         bars[start + 7][0])
        self.assertEqual(calls, [bars[start + 6][0], bars[start + 7][0]])
        self.assertEqual(result["losses"], 1)

    def test_negative_trade_reconciles_costs_and_caps(self):
        bars = bars_fixture()
        start = 600
        bars[start + 7] = (
            bars[start + 7][0], 90.0, 91.0, 89.0, 90.0, 100.0,
        )

        def signal(rows, i, name, holding=False, held=0, events=()):
            return "BUY" if i == start and not holding else "HOLD"

        with patch("research.v31_hysteresis.decision", side_effect=signal):
            result = base_replay(
                bars, start, start + 20, "h80_300",
                exit_veto=lambda ts: ts == bars[start + 7][0],
                audit=True, max_entry_debit=100.0,
            )
        trade = result["trade_audit"][0]
        self.assertLessEqual(trade["entry_debit_aud"], 100.0 + 1e-8)
        self.assertLessEqual(trade["entry_debit_aud"],
                             0.10 * trade["cash_before_entry_aud"] + 1e-8)
        self.assertEqual(result["losses"], 1)
        self.assertAlmostEqual(
            result["gross_aud"] - result["fees_aud"]
            - result["spread_aud"] - result["slippage_aud"],
            result["net_aud"], places=5,
        )

    def test_selector_fails_closed_without_positive_train_and_validation(self):
        training = {name: {"trades": 2, "net_aud": 1.0}
                    for name in ("h80_base", "h80_fx_mask_exit_0",
                                 "h80_fx_mask_exit_m1", "h50_base")}
        validation = {name: {"trades": 2, "net_aud": 2.0}
                      for name in training}
        self.assertIn(select(training, validation), training)
        validation["h80_fx_mask_exit_0"]["net_aud"] = -1.0
        self.assertNotEqual(select(training, validation),
                            "h80_fx_mask_exit_0")
        for row in training.values():
            row["trades"] = 1
        self.assertEqual(select(training, validation), "HOLD")

    def test_candidate_menu_and_base_have_no_exit_override(self):
        bars = bars_fixture()
        self.assertEqual(len(CANDIDATES), 5)
        callback, counts = make_exit_veto(bars, None, "h80_base")
        self.assertIsNone(callback)
        self.assertEqual(counts["forced_exits"], 0)


if __name__ == "__main__":
    unittest.main()

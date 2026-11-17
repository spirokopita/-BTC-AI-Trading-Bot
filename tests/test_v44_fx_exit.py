"""V44 cross-rate exit tests: past-only inputs, costs, and selector safety."""
import math
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from research.v31_hysteresis import replay as base_replay
from research.v44_fx_exit import (
    CANDIDATES, buyhold_detail, make_exit_veto, make_news_entry_veto,
    replay_variant, select,
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
                                 "h80_fx_mask_exit_m1",
                                 "h80_news_negative_veto", "h50_base")}
        validation = {name: {"trades": 2, "net_aud": 2.0}
                      for name in training}
        self.assertIn(select(training, validation), training)
        validation["h80_fx_mask_exit_0"]["net_aud"] = -1.0
        self.assertNotEqual(select(training, validation),
                            "h80_fx_mask_exit_0")
        for row in training.values():
            row["trades"] = 1
        self.assertEqual(select(training, validation), "HOLD")

    def test_news_veto_requires_strict_v48_availability_and_negative_sentiment(self):
        events = [{"id": "verified-negative", "sentiment": -1}]
        with patch("research.v48_news_proof_gate.classify",
                   return_value={"eligible": True,
                                 "available_at_utc": START + 10}) as mocked:
            veto, counts = make_news_entry_veto(
                events, "h80_news_negative_veto")
            self.assertTrue(veto(START + 100))
            self.assertEqual(counts["vetoed_candidate_bars"], 1)
            mocked.assert_called_once_with(
                events[0], START + 100, latency_seconds=3600)

    def test_news_veto_audit_records_decision_bar_for_missed_opportunity(self):
        bars = bars_fixture()
        events = [{"id": "verified-negative", "sentiment": -1}]
        audit = []
        with patch("research.v48_news_proof_gate.classify",
                   return_value={"eligible": True,
                                 "available_at_utc": START + 10}):
            veto, _ = make_news_entry_veto(
                events, "h80_news_negative_veto",
                bars=bars, audit_rows=audit)
            self.assertTrue(veto(bars[500][0]))
        self.assertEqual(audit[0]["decision_index"], 500)
        self.assertEqual(audit[0]["decision"], "VETOED_BUY")

    def test_news_veto_does_not_use_unavailable_or_unscored_news(self):
        with patch("research.v48_news_proof_gate.classify",
                   return_value={"eligible": False,
                                 "available_at_utc": START + 500}):
            veto, counts = make_news_entry_veto(
                [{"sentiment": -1}], "h80_news_negative_veto")
            self.assertFalse(veto(START + 100))
            self.assertEqual(counts["vetoed_candidate_bars"], 0)
        with patch("research.v48_news_proof_gate.classify",
                   return_value={"eligible": True,
                                 "available_at_utc": START + 10}):
            veto, counts = make_news_entry_veto(
                [{"sentiment": "unscored"}], "h80_news_negative_veto")
            self.assertFalse(veto(START + 100))
            self.assertEqual(counts["vetoed_candidate_bars"], 0)

    def test_seven_day_news_placebo_shifts_decision_cutoff_backwards(self):
        with patch("research.v48_news_proof_gate.classify",
                   return_value={"eligible": False,
                                 "available_at_utc": START - 1}) as mocked:
            veto, _ = make_news_entry_veto(
                [{"sentiment": -1}], "h80_news_negative_veto_placebo7d")
            self.assertFalse(veto(START + 9 * 86400))
            self.assertEqual(
                mocked.call_args.args[1], START + 2 * 86400)

    def test_buyhold_benchmark_reports_gross_costs_net_and_drawdown(self):
        bars = bars_fixture()
        for i in range(700, 720):
            price = 100.0 - (i - 700) * 0.2
            bars[i] = (bars[i][0], price, price + 1, price - 1,
                       price, 100.0)
        result = buyhold_detail(bars, 700, 720)
        self.assertEqual(result["trades"], 1)
        self.assertEqual(result["losses"], 1)
        self.assertLess(result["net_aud"], 0)
        self.assertAlmostEqual(
            result["gross_aud"] - result["fees_aud"]
            - result["spread_aud"] - result["slippage_aud"],
            result["net_aud"], places=5,
        )
        self.assertLessEqual(result["max_drawdown_pct"], 0.0)

    def test_candidate_menu_and_base_have_no_exit_override(self):
        bars = bars_fixture()
        self.assertEqual(len(CANDIDATES), 7)
        callback, counts = make_exit_veto(bars, None, "h80_base")
        self.assertIsNone(callback)
        self.assertEqual(counts["forced_exits"], 0)
        news_callback, _ = make_exit_veto(
            bars, None, "h80_news_negative_veto")
        self.assertIsNone(news_callback)


if __name__ == "__main__":
    unittest.main()

"""V43 past-only drawdown gate, cash cap and no-lookahead tests."""
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from research.v31_hysteresis import replay as replay_base
from research.v43_drawdown_cash_gate import (
    CANDIDATES, DRAWDOWN_LOOKBACK, PLACEBO_DELAY_BARS,
    drawdown_from_high, make_entry_veto, missed_after_veto,
    replay_candidate, select,
)

STEP = 14400
START = int(datetime(2023, 1, 1, tzinfo=timezone.utc).timestamp())


def fixture(n=900):
    rows = []
    for i in range(n):
        price = 100.0
        rows.append((
            START + i * STEP, price, price + 1.0,
            price - 1.0, price, 100.0,
        ))
    return rows


class V43DrawdownGateTests(unittest.TestCase):
    def test_drawdown_uses_only_completed_bars(self):
        bars = fixture()
        index = 700
        bars[index - 1] = (
            bars[index - 1][0], 85.0, 100.0, 84.0, 85.0, 100.0,
        )
        before = drawdown_from_high(bars, index)
        bars[index] = (
            bars[index][0], 999.0, 1000.0, 1.0, 2.0, 999999.0,
        )
        bars[index + 1] = (
            bars[index + 1][0], 888.0, 999.0, 1.0, 2.0, 999999.0,
        )
        self.assertEqual(before, drawdown_from_high(bars, index))
        self.assertLess(before, -0.15)
        self.assertGreater(before, -0.20)

    def test_delayed_placebo_is_stale_and_does_not_see_current_drawdown(self):
        bars = fixture()
        index = 700
        bars[index - 1] = (
            bars[index - 1][0], 85.0, 100.0, 84.0, 85.0, 100.0,
        )
        current = drawdown_from_high(bars, index)
        delayed = drawdown_from_high(
            bars, index, delay_bars=PLACEBO_DELAY_BARS,
        )
        self.assertLess(current, -0.15)
        self.assertGreater(delayed, -0.02)

    def test_threshold_menu_and_placebo_gate_are_deterministic(self):
        bars = fixture()
        index = 700
        bars[index - 1] = (
            bars[index - 1][0], 85.0, 100.0, 84.0, 85.0, 100.0,
        )
        ts = bars[index][0]
        self.assertTrue(make_entry_veto(bars, "h80_dd10")(ts))
        self.assertTrue(make_entry_veto(bars, "h80_dd15")(ts))
        self.assertFalse(make_entry_veto(bars, "h80_dd20")(ts))
        self.assertFalse(make_entry_veto(
            bars, "h80_dd15_placebo7d",
        )(ts))
        self.assertEqual(DRAWDOWN_LOOKBACK, 540)
        self.assertEqual(len(CANDIDATES), 5)

    def test_warmup_returns_none_and_bad_ohlc_fails_closed(self):
        bars = fixture()
        self.assertIsNone(drawdown_from_high(bars, 100))
        broken = list(bars[699])
        broken[2] = float("nan")
        bars[699] = tuple(broken)
        with self.assertRaisesRegex(ValueError, "historical high"):
            drawdown_from_high(bars, 700)

    def test_entry_gate_does_not_block_protective_sell(self):
        bars = fixture()
        start = 550
        # Entry sees no drawdown. At the later SELL decision, the preceding
        # completed candle is deeply down; the entry-only gate must not run.
        bars[start + 4] = (
            bars[start + 4][0], 80.0, 100.0, 79.0, 80.0, 100.0,
        )
        bars[start + 5] = (
            bars[start + 5][0], 90.0, 91.0, 89.0, 90.0, 100.0,
        )
        calls = []

        def signal(rows, i, name, holding=False, held=0, events=()):
            if i == start and not holding:
                return "BUY"
            if i == start + 5 and holding:
                return "SELL"
            return "HOLD"

        veto = make_entry_veto(bars, "h80_dd10")
        def counted(ts):
            calls.append(ts)
            return veto(ts)

        with patch("research.v31_hysteresis.decision", side_effect=signal):
            result = replay_base(
                bars, start, start + 20, "h80_300",
                entry_veto=counted, audit=True,
            )
        self.assertEqual(len(result["trade_audit"]), 1)
        self.assertEqual(result["trade_audit"][0]["exit_ts"], bars[start + 5][0])
        self.assertEqual(calls, [bars[start][0]])
        self.assertEqual(result["losses"], 1)

    def test_a50_a100_inclusive_debit_and_negative_trade_audit(self):
        bars = fixture()
        start = 550
        bars[start + 5] = (
            bars[start + 5][0], 90.0, 91.0, 89.0, 90.0, 100.0,
        )

        def signal(rows, i, name, holding=False, held=0, events=()):
            if i == start and not holding:
                return "BUY"
            if i == start + 5 and holding:
                return "SELL"
            return "HOLD"

        for cap in (50.0, 100.0):
            with patch("research.v31_hysteresis.decision", side_effect=signal):
                result = replay_candidate(
                    bars, start, start + 20, "h80_base",
                    max_entry_debit=cap, audit=True,
                )
            trade = result["trade_audit"][0]
            self.assertLessEqual(trade["entry_debit_aud"], cap + 1e-8)
            self.assertLessEqual(
                trade["entry_debit_aud"],
                0.10 * trade["cash_before_entry_aud"] + 1e-8,
            )
            self.assertEqual(result["losses"], 1)
            self.assertAlmostEqual(
                result["gross_aud"] - result["fees_aud"]
                - result["spread_aud"] - result["slippage_aud"],
                result["net_aud"], places=5,
            )

    def test_train_validation_selector_fails_closed(self):
        training = {
            name: {"trades": 2, "net_aud": 1.0}
            for name in CANDIDATES[:-1]
        }
        validation = {
            name: {"trades": 2, "net_aud": 2.0}
            for name in CANDIDATES[:-1]
        }
        self.assertIn(select(training, validation), CANDIDATES[:-1])
        validation["h80_dd15"]["net_aud"] = -1.0
        self.assertNotEqual(select(training, validation), "h80_dd15")
        for name in CANDIDATES[:-1]:
            training[name]["trades"] = 1
        self.assertEqual(select(training, validation), "HOLD")

    def test_veto_forward_outcomes_are_descriptive_only(self):
        bars = fixture()
        index = 550
        bars[index + 6] = (
            bars[index + 6][0], 110.0, 111.0, 109.0, 110.0, 100.0,
        )
        bars[index + 42] = (
            bars[index + 42][0], 90.0, 91.0, 89.0, 90.0, 100.0,
        )
        report = missed_after_veto(
            bars, [{"decision_index": index}], len(bars),
        )
        self.assertEqual(report["24h"]["positive"], 1)
        self.assertEqual(report["7d"]["non_positive"], 1)
        self.assertIsNone(report["24h"].get("net_pnl_aud"))

    def test_gap_fails_closed(self):
        bars = fixture()
        broken = list(bars[560])
        broken[0] += STEP
        bars[560] = tuple(broken)
        with self.assertRaisesRegex(ValueError, "Candle gap"):
            replay_candidate(bars, 550, 580, "h80_base")


if __name__ == "__main__":
    unittest.main()

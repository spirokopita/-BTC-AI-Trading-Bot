"""V42 completed-bar ATR/time-stop and paper-accounting regression tests."""
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from research.v42_volatility_exit import (
    ATR_LOOKBACK, CANDIDATES, EXIT_RULES, SELECTABLE, V42_EMBARGO_BARS,
    atr14, boundaries_v42, replay_exit, select,
)

STEP = 14400
START = int(datetime(2023, 1, 1, tzinfo=timezone.utc).timestamp())


def fixture(n=400):
    rows = []
    for i in range(n):
        price = 100.0
        rows.append((
            START + i * STEP, price, price + 1.0,
            price - 1.0, price, 100.0,
        ))
    return rows


class V42VolatilityExitTests(unittest.TestCase):
    def test_atr_uses_only_completed_candles(self):
        bars = fixture()
        value = atr14(bars, 320)
        bars[320] = (bars[320][0], 999.0, 1000.0, 1.0, 2.0, 999999.0)
        bars[321] = (bars[321][0], 888.0, 999.0, 1.0, 2.0, 999999.0)
        self.assertEqual(value, atr14(bars, 320))
        self.assertAlmostEqual(value, 2.0)
        self.assertIsNone(atr14(bars, ATR_LOOKBACK))

    def test_atr_stop_is_close_confirmed_and_fills_at_next_open(self):
        bars = fixture()
        start = 320
        bars[start] = (
            bars[start][0], 100.0, 101.0, 79.0, 80.0, 100.0,
        )
        bars[start + 1] = (
            bars[start + 1][0], 79.5, 82.0, 78.0, 80.0, 100.0,
        )

        def signal(rows, i, name, holding=False, held=0, events=()):
            return "BUY" if i == start and not holding else "HOLD"

        with patch("research.v42_volatility_exit.base_decision",
                   side_effect=signal):
            result = replay_exit(
                bars, start, start + 20, "h80_atr25", audit=True,
            )
        trade = result["trade_audit"][0]
        self.assertEqual(trade["exit_index"], start + 1)
        self.assertEqual(trade["exit_reason"], "entry_atr_stop_next_open")
        self.assertEqual(trade["exit_mid_aud"], 79.5)
        self.assertEqual(trade["held_bars"], 1)

    def test_current_bar_low_does_not_trigger_uncompleted_stop(self):
        bars = fixture()
        start = 320
        bars[start] = (
            bars[start][0], 100.0, 101.0, 70.0, 100.0, 100.0,
        )
        bars[start + 1] = (
            bars[start + 1][0], 100.0, 101.0, 60.0, 100.0, 100.0,
        )

        def signal(rows, i, name, holding=False, held=0, events=()):
            return "BUY" if i == start and not holding else "HOLD"

        with patch("research.v42_volatility_exit.base_decision",
                   side_effect=signal):
            result = replay_exit(
                bars, start, start + 20, "h80_atr25", audit=True,
            )
        self.assertEqual(
            result["trade_audit"][0]["exit_reason"], "terminal_liquidation",
        )

    def test_42_bar_time_stop_exits_at_next_open(self):
        bars = fixture()
        start = 320

        def signal(rows, i, name, holding=False, held=0, events=()):
            return "BUY" if i == start and not holding else "HOLD"

        with patch("research.v42_volatility_exit.base_decision",
                   side_effect=signal):
            result = replay_exit(
                bars, start, start + 60, "h80_time42", audit=True,
            )
        trade = result["trade_audit"][0]
        self.assertEqual(trade["exit_index"], start + 42)
        self.assertEqual(
            trade["exit_reason"], "maximum_holding_time_next_open",
        )

    def test_a50_and_a100_inclusive_entry_debit_caps(self):
        bars = fixture()
        start = 320

        def signal(rows, i, name, holding=False, held=0, events=()):
            if i == start and not holding:
                return "BUY"
            if i == start + 5 and holding:
                return "SELL"
            return "HOLD"

        for cap in (50.0, 100.0):
            with patch("research.v42_volatility_exit.base_decision",
                       side_effect=signal):
                result = replay_exit(
                    bars, start, start + 20, "h80_base",
                    max_entry_debit=cap, audit=True,
                )
            trade = result["trade_audit"][0]
            self.assertLessEqual(trade["entry_debit_aud"], cap + 1e-8)
            self.assertLessEqual(
                trade["entry_debit_aud"],
                0.10 * trade["cash_before_entry_aud"] + 1e-8,
            )
            self.assertLess(
                abs(result["gross_aud"] - result["fees_aud"]
                    - result["spread_aud"] - result["slippage_aud"]
                    - result["net_aud"]),
                2e-6,
            )
            self.assertEqual(result["losses"], 1)

    def test_gap_fails_closed(self):
        bars = fixture()
        broken = list(bars[330])
        broken[0] += STEP
        bars[330] = tuple(broken)
        with self.assertRaisesRegex(ValueError, "Candle gap"):
            replay_exit(bars, 320, 350, "h80_base")

    def test_selector_uses_train_validation_only_and_holds_without_edge(self):
        training = {
            name: {"trades": 2, "net_aud": 1.0}
            for name in SELECTABLE
        }
        validation = {
            name: {"trades": 2, "net_aud": 2.0}
            for name in SELECTABLE
        }
        self.assertEqual(select(training, validation), "h80_base")
        validation["h80_base"]["net_aud"] = -1.0
        self.assertNotEqual(select(training, validation), "h80_base")
        for name in SELECTABLE:
            training[name]["trades"] = 1
        self.assertEqual(select(training, validation), "HOLD")

    def test_84_bar_embargo_covers_longest_time_stop(self):
        train_end, validation_start, validation_end, test_start = boundaries_v42(2000)
        self.assertEqual(V42_EMBARGO_BARS, 84)
        self.assertEqual(validation_start - train_end, 84)
        self.assertEqual(test_start - validation_end, 84)
        self.assertEqual(max(hold or 0 for _, hold in EXIT_RULES.values()), 84)

    def test_candidate_menu_is_frozen_and_registered(self):
        self.assertEqual(len(CANDIDATES), 7)
        self.assertEqual(EXIT_RULES["h80_atr25"], (2.5, None))
        self.assertEqual(EXIT_RULES["h80_time42"], (None, 42))
        self.assertEqual(EXIT_RULES["h80_atr35_time42"], (3.5, 42))


if __name__ == "__main__":
    unittest.main()

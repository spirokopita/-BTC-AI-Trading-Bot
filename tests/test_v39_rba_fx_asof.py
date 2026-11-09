"""V39 RBA FX causal availability, licensing and PAPER risk tests."""
import math
import unittest
from datetime import date, timedelta, datetime, timezone
from research.v39_rba_fx_asof import (
    parse_csv, validate_rows, FXSeries, available_at, fx_gate,
    variant, choose, SELECTABLE, source_request, usd_column)
from research.v29_point_in_time import STEP

def sample_fx(start=date(2022, 1, 1), n=750, daily_growth=0.0):
    return FXSeries([((start + timedelta(days=i)).isoformat(),
                      .70 * (1 + daily_growth) ** i) for i in range(n)])

def bars(n=540):
    out = []
    start = int(datetime(2023, 1, 1, tzinfo=timezone.utc).timestamp())
    for i in range(n):
        p = 20000 * math.exp(.0008 * i) * (1 + .001 * math.sin(i*.2))
        out.append((start + i*STEP, p, p*1.002, p*.998, p, 1.))
    return out

class V39RbaTests(unittest.TestCase):
    def test_rba_mixed_preamble_and_quote_direction(self):
        raw = b"Title,FX\nSeries ID,FXRUSD,FXRJPY\n03-Jan-2023,0.68,89\n04-Jan-2023,0.69,90\n"
        self.assertEqual(parse_csv(raw),
                         [("2023-01-03", .68), ("2023-01-04", .69)])
        with self.assertRaises(ValueError):
            parse_csv(b"Date,USD/AUD\n2023-01-03,1.46\n")
        with self.assertRaises(ValueError):
            usd_column([["Date", "Euro"]])

    def test_no_conflicting_duplicate_or_wrong_rate(self):
        with self.assertRaises(ValueError):
            validate_rows([("2023-01-01", .7), ("2023-01-01", .71)])
        with self.assertRaises(ValueError):
            FXSeries([("2023-01-01", .7), ("2023-01-02", 2.5)])
        with self.assertRaises(ValueError):
            FXSeries([])

    def test_dst_aware_delayed_release(self):
        summer = datetime.fromtimestamp(available_at("2023-01-01"), timezone.utc)
        winter = datetime.fromtimestamp(available_at("2023-06-01"), timezone.utc)
        self.assertEqual(summer.isoformat(), "2023-01-02T06:00:00+00:00")
        self.assertEqual(winter.isoformat(), "2023-06-02T07:00:00+00:00")
        self.assertGreater(available_at("2023-01-01"),
                           int(datetime(2023,1,1,tzinfo=timezone.utc).timestamp()))

    def test_no_current_day_or_future_revision_leak(self):
        fx = sample_fx(daily_growth=.001)
        t = available_at("2023-01-15") - 1
        before = fx.state(t)
        self.assertLess(before["available_at"], t)
        self.assertLess(before["latest_day"], "2023-01-15")
        after = fx.state(t + 1)
        self.assertEqual(after["latest_day"], "2023-01-15")
        extended = FXSeries(list(zip(fx.days, fx.rates)) +
                            [("2024-12-31", 1.1)])
        self.assertEqual(before, extended.state(t))

    def test_placebo_uses_past_not_future(self):
        fx = sample_fx(daily_growth=.002)
        t = available_at("2023-04-10") + 1
        self.assertTrue(fx_gate(fx, t, "h80_fx_headwind"))
        self.assertTrue(fx_gate(fx, t, "h80_fx_placebo7d"))
        self.assertGreater(fx.state(t)["available_at"],
                           fx.state(t, shift_days=7)["available_at"])
        with self.assertRaises(ValueError):
            fx_gate(fx, t, "invalid")

    def test_missing_or_stale_fx_blocks_new_buy_only(self):
        fx = sample_fx(start=date(2022,1,1), n=10)
        t = int(datetime(2023, 3, 1, tzinfo=timezone.utc).timestamp())
        self.assertTrue(fx_gate(fx, t, "h80_fx_headwind"))
        self.assertFalse(fx_gate(fx, t, "h80_base"))
        self.assertIsNone(fx.state(t))

    def test_paper_risk_and_cost_reconciliation(self):
        fx = sample_fx(start=date(2022,1,1), n=750)
        b = bars()
        r = variant(b, 305, 520, "h80_fx_headwind", fx, audit=True)
        self.assertGreater(r["trades"], 0)
        for t in r["trade_audit"]:
            self.assertLessEqual(t["entry_debit_aud"], 100 + 1e-8)
            self.assertLessEqual(t["entry_debit_aud"],
                                 .1 * t["cash_before_entry_aud"] + 1e-8)
            self.assertAlmostEqual(t["net"], t["gross"] - t["fees"] -
                                   t["spread"] - t["slippage"])
        r50 = variant(b, 305, 520, "h80_fx_headwind", fx,
                      max_entry_debit=50, audit=True)
        self.assertEqual(r["trades"], r50["trades"])
        self.assertLessEqual(r50["trade_audit"][0]["entry_debit_aud"], 50+1e-8)
        with self.assertRaises(ValueError):
            variant(b, 305, 520, "h80_fx_headwind", fx, max_entry_debit=101)

    def test_gap_and_negative_trade_loss_audit(self):
        fx = sample_fx(start=date(2022,1,1), n=750)
        b = bars()
        b[400] = (b[400][0] + STEP, *b[400][1:])
        with self.assertRaises(ValueError):
            variant(b, 305, 520, "h80_base", fx)
        b = bars()
        for i in range(400, len(b)):
            p = b[i][1] * .4
            b[i] = (b[i][0], p, p*1.002, p*.998, p, 1.)
        r = variant(b, 305, 520, "h80_base", fx, audit=True)
        self.assertGreater(r["losses"], 0)
        self.assertTrue(any(t["net"] < 0 for t in r["trade_audit"]))

    def test_train_selector_cannot_see_test(self):
        good = {"trades": 3, "net_aud": 4.}
        bad = {"trades": 0, "net_aud": 0.}
        tr = {k: bad for k in SELECTABLE}
        val = {k: bad for k in SELECTABLE}
        self.assertEqual(choose(tr, val, {"train": 1, "validation": 1}), "HOLD")
        tr["h80_fx_headwind"] = good
        val["h80_fx_headwind"] = good
        self.assertEqual(choose(tr, val, {"train": 1, "validation": 1}),
                         "h80_fx_headwind")
        self.assertEqual(choose(tr, val, {"train": .5, "validation": 1}),
                         "HOLD")

    def test_unapproved_external_endpoint_rejected(self):
        with self.assertRaises(ValueError):
            source_request("https://example.com/forex.csv")

if __name__ == "__main__":
    unittest.main()

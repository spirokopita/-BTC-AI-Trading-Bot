"""Deterministic synthetic protocol fixtures; NOT actual market observations."""
import unittest

from verify_kraken_public import AuditError, INTERVAL, validate_snapshot

NOW = 1_800_000_000  # 4h aligned, synthetic clock
BASE = NOW - 23 * INTERVAL


def fixture():
    market = "XXBTZAUD"
    assetpairs = {"error": [], "result": {market: {
        "altname": "XBTAUD", "wsname": "XBT/AUD", "base": "XXBT", "quote": "ZAUD"}}}
    ticker = {"error": [], "result": {market: {"b": ["100.0"], "a": ["100.5"], "c": ["100.2"]}}}
    rows = [[BASE + i * INTERVAL, "100", "102", "99", "101", "100", "0.5", 2]
            for i in range(24)]
    ohlc = {"error": [], "result": {market: rows, "last": 123}}
    return assetpairs, ticker, ohlc


class PublicAuditTest(unittest.TestCase):
    def test_completed_bars_exclude_unfinished(self):
        assets, ticker, bars = fixture()
        result = validate_snapshot(assets, ticker, bars, NOW)
        self.assertEqual(result["excluded_forming_rows"], 1)
        self.assertEqual(result["completed_ohlc_rows"], 23)
        self.assertEqual(result["latest_completed_age_seconds"], 0)
        self.assertEqual(result["market"], "BTC/AUD")

    def test_721_rows_includes_current_forming_bar(self):
        assets, ticker, bars = fixture()
        bars["result"]["XXBTZAUD"] = [
            [NOW - (720 - i) * INTERVAL, "100", "102", "99", "101", "100", "0.5", 2]
            for i in range(721)
        ]
        result = validate_snapshot(assets, ticker, bars, NOW)
        self.assertEqual(720, result["completed_ohlc_rows"])
        self.assertEqual(1, result["excluded_forming_rows"])

    def test_mismatched_market_fails_closed(self):
        assets, ticker, bars = fixture()
        ticker["result"] = {"XXBTZUSD": ticker["result"]["XXBTZAUD"]}
        with self.assertRaisesRegex(AuditError, "Canonical"):
            validate_snapshot(assets, ticker, bars, NOW)

    def test_kraken_api_error_fails_closed(self):
        assets, ticker, bars = fixture()
        bars["error"] = ["EQuery:Unknown asset pair"]
        with self.assertRaisesRegex(AuditError, "Kraken API error"):
            validate_snapshot(assets, ticker, bars, NOW)

    def test_partial_bar_cannot_warm_21_bar_signal(self):
        assets, ticker, bars = fixture()
        bars["result"]["XXBTZAUD"] = bars["result"]["XXBTZAUD"][-21:]
        with self.assertRaisesRegex(AuditError, "fewer than 21 completed"):
            validate_snapshot(assets, ticker, bars, NOW)

    def test_missing_bar_in_tail_fails_closed(self):
        assets, ticker, bars = fixture()
        del bars["result"]["XXBTZAUD"][-10]
        with self.assertRaisesRegex(AuditError, "gap"):
            validate_snapshot(assets, ticker, bars, NOW)

    def test_bad_price_fails_closed(self):
        assets, ticker, bars = fixture()
        bars["result"]["XXBTZAUD"][2][2] = "98"
        with self.assertRaisesRegex(AuditError, "price range"):
            validate_snapshot(assets, ticker, bars, NOW)

    def test_stale_bars_fail_closed(self):
        assets, ticker, bars = fixture()
        with self.assertRaisesRegex(AuditError, "stale"):
            validate_snapshot(assets, ticker, bars, NOW + 16 * 3600)

    def test_crossed_quote_fails_closed(self):
        assets, ticker, bars = fixture()
        ticker["result"]["XXBTZAUD"]["b"] = ["101"]
        with self.assertRaisesRegex(AuditError, "crossed"):
            validate_snapshot(assets, ticker, bars, NOW)

    def test_wrong_asset_pair_fails_closed(self):
        assets, ticker, bars = fixture()
        assets["result"]["XXBTZAUD"]["quote"] = "ZUSD"
        with self.assertRaisesRegex(AuditError, "base/quote mismatch"):
            validate_snapshot(assets, ticker, bars, NOW)


if __name__ == "__main__":
    unittest.main()

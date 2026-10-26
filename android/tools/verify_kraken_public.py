#!/usr/bin/env python3
"""Read-only, fail-closed provenance audit for Kraken public BTC/AUD 4h data.

This is CI evidence, not an Android trading client, history importer, backtest,
or assertion of profitability. No credentials or private endpoints are used.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import sys
import time
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

BASE = "https://api.kraken.com/0/public/"
PAIR = "XBTAUD"
INTERVAL = 240 * 60
MAX_BYTES = 2_000_000
MAX_AGE_SECONDS = 8 * 60 * 60


class AuditError(ValueError):
    pass


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise AuditError(f"HTTP redirect refused ({code})")


def utc(ts: int) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).isoformat().replace("+00:00", "Z")


def positive(value, field: str, allow_zero: bool = False) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise AuditError(f"{field} not numeric") from exc
    if not result.is_finite() or (result < 0 if allow_zero else result <= 0):
        raise AuditError(f"{field} invalid")
    return result


def unpack(response: dict, endpoint: str) -> dict:
    if not isinstance(response, dict) or not isinstance(response.get("error"), list):
        raise AuditError(f"{endpoint}: invalid Kraken envelope")
    if response["error"]:
        raise AuditError(f"{endpoint}: Kraken API error: {str(response['error'])[:160]}")
    result = response.get("result")
    if not isinstance(result, dict):
        raise AuditError(f"{endpoint}: missing result")
    return result


def one_pair(result: dict, endpoint: str, *, ignore_last: bool = False):
    keys = [key for key in result if key != "last"] if ignore_last else list(result)
    if len(keys) != 1:
        raise AuditError(f"{endpoint}: expected exactly one market, got {len(keys)}")
    return keys[0], result[keys[0]]


def validate_snapshot(assetpairs: dict, ticker: dict, ohlc: dict, now_s: int) -> dict:
    """Validate independent responses without trusting their market key names."""
    ap_key, ap = one_pair(unpack(assetpairs, "AssetPairs"), "AssetPairs")
    if not isinstance(ap, dict) or ap.get("altname") != PAIR or ap.get("wsname") not in ("XBT/AUD", "BTC/AUD"):
        raise AuditError("AssetPairs: response does not identify BTC/AUD")
    if ap.get("base") not in ("XXBT", "XBT", "BTC") or ap.get("quote") not in ("ZAUD", "AUD"):
        raise AuditError("AssetPairs: base/quote mismatch")

    tick_key, tick = one_pair(unpack(ticker, "Ticker"), "Ticker")
    bars_key, rows = one_pair(unpack(ohlc, "OHLC"), "OHLC", ignore_last=True)
    if ap_key != tick_key or ap_key != bars_key:
        raise AuditError("Canonical market keys differ between endpoints")
    if not isinstance(tick, dict):
        raise AuditError("Ticker: invalid data")
    try:
        bid = positive(tick["b"][0], "bid")
        ask = positive(tick["a"][0], "ask")
        last = positive(tick["c"][0], "last")
    except (KeyError, IndexError, TypeError) as exc:
        raise AuditError("Ticker: missing bid/ask/last") from exc
    if bid > ask:
        raise AuditError("Ticker: crossed bid/ask")
    if not isinstance(rows, list) or len(rows) < 21 or len(rows) > 720:
        raise AuditError(f"OHLC: insufficient or implausible row count ({len(rows) if isinstance(rows, list) else 'not-list'})")

    seen = set()
    completed = []
    previous = -1
    for row in rows:
        if not isinstance(row, list) or len(row) < 8:
            raise AuditError("OHLC: malformed row")
        try:
            start = int(row[0])
            count = int(row[7])
        except (ValueError, TypeError) as exc:
            raise AuditError("OHLC: invalid timestamp/count") from exc
        if start <= previous or start % INTERVAL != 0 or start > now_s or count < 0:
            raise AuditError("OHLC: unordered, unaligned, future or invalid bar")
        previous = start
        if start in seen:
            raise AuditError("OHLC: duplicate bar")
        seen.add(start)
        op = positive(row[1], "open")
        hi = positive(row[2], "high")
        lo = positive(row[3], "low")
        cl = positive(row[4], "close")
        positive(row[5], "vwap")
        positive(row[6], "volume", allow_zero=True)
        if lo > min(op, cl) or hi < max(op, cl) or lo > hi:
            raise AuditError("OHLC: invalid price range")
        # Kraken includes an unfinished last bar. Never count it as completed.
        if start + INTERVAL <= now_s:
            completed.append(start)
    if len(completed) < 21:
        raise AuditError("OHLC: fewer than 21 completed bars")
    tail = completed[-21:]
    if any(b - a != INTERVAL for a, b in zip(tail, tail[1:])):
        raise AuditError("OHLC: gap in last 21 completed bars")
    age = now_s - (completed[-1] + INTERVAL)
    if age < 0 or age > MAX_AGE_SECONDS:
        raise AuditError(f"OHLC: latest completed bar stale by {age}s")
    return {
        "market": "BTC/AUD", "kraken_market_key": ap_key,
        "ticker_bid_aud": str(bid), "ticker_ask_aud": str(ask),
        "ticker_last_aud": str(last),
        "ticker_timestamp_note": "Kraken REST Ticker has no per-quote timestamp; fetched_at is observation time",
        "ohlc_interval_minutes": 240, "raw_ohlc_rows": len(rows),
        "completed_ohlc_rows": len(completed), "excluded_forming_rows": len(rows) - len(completed),
        "latest_completed_bar_start_utc": utc(completed[-1]),
        "latest_completed_bar_end_utc": utc(completed[-1] + INTERVAL),
        "latest_completed_age_seconds": age,
        "last_21_completed_bars_contiguous": True,
    }


def fetch(endpoint: str, params: dict) -> tuple[dict, dict]:
    url = BASE + endpoint + "?" + urlencode(params)
    if urlsplit(url).hostname != "api.kraken.com":
        raise AuditError("Unexpected host")
    req = Request(url, headers={"Accept": "application/json", "User-Agent": "BTC-Paper-ReadOnly-Audit/1.0"})
    with build_opener(NoRedirects()).open(req, timeout=20) as response:
        if response.status != 200:
            raise AuditError(f"{endpoint}: HTTP {response.status}")
        raw = response.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise AuditError(f"{endpoint}: oversized response")
        metadata = {"endpoint": endpoint, "url": url,
                    "response_sha256": hashlib.sha256(raw).hexdigest(),
                    "http_date": response.headers.get("Date")}
    try:
        return json.loads(raw), metadata
    except (ValueError, UnicodeDecodeError) as exc:
        raise AuditError(f"{endpoint}: invalid JSON") from exc


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="kraken-public-audit.json")
    args = parser.parse_args(argv)
    output = Path(args.output)
    observed = int(time.time())
    report = {"checked_at_utc": utc(observed), "source": "Kraken public REST HTTPS",
              "read_only": True, "paper_only": True,
              "trading_or_net_performance": "NOT MEASURED", "status": "UNVERIFIED"}
    try:
        assets, a = fetch("AssetPairs", {"pair": PAIR})
        ticker, b = fetch("Ticker", {"pair": PAIR})
        bars, c = fetch("OHLC", {"pair": PAIR, "interval": 240})
        report["response_evidence"] = [a, b, c]
        raw_result = unpack(bars, "OHLC")
        _, raw_rows = one_pair(raw_result, "OHLC", ignore_last=True)
        report["observed_raw_ohlc_row_count"] = len(raw_rows) if isinstance(raw_rows, list) else None
        report.update(validate_snapshot(assets, ticker, bars, int(time.time())))
        report["status"] = "VERIFIED_PUBLIC_ENDPOINTS"
        exit_code = 0
    except Exception as exc:
        # CI should preserve evidence even when the network or exchange fails.
        report["error"] = f"{type(exc).__name__}: {str(exc)[:250]}"
        exit_code = 2
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Kraken BTC/AUD public audit: {report['status']} ({output})")
    if exit_code:
        print(report["error"], file=sys.stderr)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())

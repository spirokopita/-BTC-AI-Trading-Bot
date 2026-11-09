"""V39: official RBA AUD/USD historical snapshot + low-turnover FX ablations.

PAPER ONLY. A historical RBA CSV/XLS downloaded today is NOT a historical
first-observed or immutable vintage. Conservative 17:00 Sydney +24h release
assumption prevents same-day use but does NOT prove revision-free availability.
No Android strategy may be promoted from these already-inspected market periods.
Raw WM/Reuters-sourced RBA USD values are not committed or redistributed.
"""
from __future__ import annotations

import argparse
import bisect
import csv
import hashlib
import io
import json
import math
import re
import urllib.request
from datetime import datetime, date, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from research.v31_hysteresis import WARMUP, replay
from research.v33_cross_regime import archive, boundaries
from research.v32_segments import segments
from research.v29_point_in_time import simulate, buyhold, CAP, CASH

CSV_URL = "https://www.rba.gov.au/statistics/tables/csv/f11.1-data.csv"
XLS_URL = "https://www.rba.gov.au/statistics/tables/xls-hist/2018-2022.xls"
MAX_BYTES = 5_000_000
UTC = timezone.utc
SYDNEY = ZoneInfo("Australia/Sydney")
# RBA reports daily FX around 17:00 Sydney. PLUS 24 hours conservative delay.
# This is an ASSUMPTION, not an attested historical first-seen timestamp.
RELEASE_HOUR = 17
ASSUMED_EXTRA_LATENCY = timedelta(hours=24)
MAX_STALENESS = 10 * 86400
SPECS = {
    "h80_base": ("h80_300", "base"),
    "h80_fx_headwind": ("h80_300", "headwind"),
    "h80_fx_tailwind": ("h80_300", "tailwind"),
    "h80_fx_jump": ("h80_300", "jump"),
    "h80_fx_placebo7d": ("h80_300", "placebo"),
    "h50_fx_headwind": ("h50_200", "headwind"),
}
SELECTABLE = ("h80_fx_headwind", "h80_fx_tailwind",
              "h80_fx_jump", "h50_fx_headwind")
COSTS_BPS = {"taker_each_side": 80, "half_spread_each_side": 5,
             "slippage_each_side": 5}

def source_request(url):
    if url not in (CSV_URL, XLS_URL):
        raise ValueError("Unapproved FX host or endpoint")
    req = urllib.request.Request(url, headers={
        "User-Agent": "BTC-AUD-PAPER-research/39 (contact via GitHub repository)",
        "Accept": "text/csv,application/vnd.ms-excel,*/*"})
    with urllib.request.urlopen(req, timeout=35) as response:
        data = response.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError("RBA response exceeded byte limit")
    if len(data) < 500:
        raise ValueError("RBA response suspiciously small")
    return data

def date_cell(value):
    if isinstance(value, (datetime, date)):
        return value.date() if isinstance(value, datetime) else value
    if not isinstance(value, str):
        return None
    s = value.strip()
    for fmt in ("%d-%b-%Y", "%d-%b-%y", "%Y-%m-%d",
                "%d/%m/%Y", "%d/%m/%y", "%d %b %Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None

def rate_cell(value):
    try:
        x = float(str(value).strip().replace(",", ""))
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) and .30 < x < 1.5 else None

def usd_column(rows):
    # RBA mixed-format tables identify columns in a label or series-ID row.
    for i, row in enumerate(rows[:35]):
        for j, v in enumerate(row):
            s = re.sub(r"\\s+", "", str(v)).upper()
            if s in ("A$1=USD", "FXRUSD", "A$1=USDOLLAR",
                     "AUD/USD", "USD/AUD") or s.startswith("A$1=USD("):
                if s == "USD/AUD":
                    raise ValueError("Wrong FX quote direction")
                return i, j
    raise ValueError("RBA USD-per-AUD series column not found; fail closed")

def parse_csv(raw):
    text = raw.decode("utf-8-sig")
    rows = list(csv.reader(io.StringIO(text)))
    header, usd = usd_column(rows)
    result = []
    for row in rows[header + 1:]:
        if usd >= len(row):
            continue
        d = next((x for x in (date_cell(c) for c in row[:3]) if x), None)
        v = rate_cell(row[usd])
        if d and v:
            result.append((d.isoformat(), v))
    return validate_rows(result)

def parse_xls(raw):
    try:
        import xlrd
    except ImportError as e:
        raise RuntimeError("xlrd==2.0.1 required for official RBA 2018-22 XLS") from e
    wb = xlrd.open_workbook(file_contents=raw)
    combined = []
    for sheet in wb.sheets():
        rows = [[sheet.cell_value(i, j) for j in range(sheet.ncols)]
                for i in range(sheet.nrows)]
        try:
            header, usd = usd_column(rows)
        except ValueError:
            continue
        for i in range(header + 1, len(rows)):
            row = rows[i]
            if usd >= len(row):
                continue
            d = None
            for j in range(min(3, len(row))):
                cell = sheet.cell(i, j)
                if cell.ctype == xlrd.XL_CELL_DATE:
                    d = xlrd.xldate_as_datetime(cell.value, wb.datemode).date()
                elif cell.ctype == xlrd.XL_CELL_NUMBER and 40000 < cell.value < 50000:
                    d = xlrd.xldate_as_datetime(cell.value, wb.datemode).date()
                else:
                    d = date_cell(cell.value)
                if d:
                    break
            v = rate_cell(row[usd])
            if d and v:
                combined.append((d.isoformat(), v))
    return validate_rows(combined)

def validate_rows(rows):
    dedup = {}
    for d, v in rows:
        if not 2018 <= int(d[:4]) <= 2027:
            raise ValueError("RBA date outside study range")
        if not isinstance(v, (int, float)) or not math.isfinite(v) or not .30 < v < 1.5:
            raise ValueError("Invalid USD per AUD rate")
        if d in dedup and abs(dedup[d] - v) > 1e-10:
            raise ValueError("Conflicting duplicate FX date")
        dedup[d] = v
    return sorted(dedup.items())

def available_at(day):
    d = date.fromisoformat(day)
    local = datetime(d.year, d.month, d.day, RELEASE_HOUR,
                     tzinfo=SYDNEY) + ASSUMED_EXTRA_LATENCY
    return int(local.astimezone(UTC).timestamp())

class FXSeries:
    def __init__(self, rows):
        clean = validate_rows(rows)
        if not clean:
            raise ValueError("No valid RBA FX observations")
        self.days = [d for d, _ in clean]
        self.rates = [r for _, r in clean]
        self.times = [available_at(d) for d in self.days]
        if any(b <= a for a, b in zip(self.times, self.times[1:])):
            raise ValueError("Nonmonotonic FX availability")

    def state(self, at, shift_days=0):
        if shift_days not in (0, 7):
            raise ValueError("Unregistered delayed placebo")
        cutoff = at - shift_days * 86400
        k = bisect.bisect_right(self.times, cutoff) - 1
        if k < 5 or cutoff - self.times[k] > MAX_STALENESS:
            return None
        last = self.rates[k]
        return {"latest_day": self.days[k], "available_at": self.times[k],
                "five_observation_return": last / self.rates[k - 5] - 1,
                "one_observation_return": last / self.rates[k - 1] - 1}

def fx_gate(fx, at, name):
    if name not in SPECS:
        raise ValueError("Unknown FX candidate")
    kind = SPECS[name][1]
    if kind == "base":
        return False
    s = fx.state(at, shift_days=7 if kind == "placebo" else 0)
    if s is None:
        return True  # unavailable/stale FX -> NO NEW ENTRY, never a SELL veto
    if kind in ("headwind", "placebo"):
        return s["five_observation_return"] >= .005
    if kind == "tailwind":
        return s["five_observation_return"] <= -.005
    if kind == "jump":
        return abs(s["one_observation_return"]) >= .012
    raise AssertionError("Unhandled FX rule")

def variant(bars, start, end, name, fx, cost_mult=1.,
            max_entry_debit=CAP, audit=False):
    if name not in SPECS:
        raise ValueError("Unknown FX strategy")
    r = replay(bars, start, end, SPECS[name][0], events=(),
               cost_mult=cost_mult, max_entry_debit=max_entry_debit,
               entry_veto=lambda at: fx_gate(fx, at, name), audit=audit)
    r["strategy"] = name
    if audit:
        for t in r["trade_audit"]:
            if t["entry_debit_aud"] > min(max_entry_debit,
                    .1 * t["cash_before_entry_aud"]) + 1e-8:
                raise AssertionError("PAPER inclusive debit cap")
            if not math.isclose(t["net"], t["gross"] - t["fees"] -
                                t["spread"] - t["slippage"], abs_tol=1e-7):
                raise AssertionError("Gross-cost-NET mismatch")
    return r

def choose(train, val, coverage):
    eligible = [k for k in SELECTABLE
                if coverage["train"] >= .75 and coverage["validation"] >= .75
                and train[k]["trades"] >= 2 and val[k]["trades"] >= 2
                and train[k]["net_aud"] > 0 and val[k]["net_aud"] > 0]
    return max(eligible, key=lambda k: min(train[k]["net_aud"],
                                           val[k]["net_aud"])) if eligible else "HOLD"

def coverage(fx, bars, start, end):
    if end <= start:
        return 0.
    return round(sum(fx.state(bars[i][0]) is not None
                     for i in range(start, end)) / (end - start), 6)

def one_segment(bars, fx):
    n = len(bars)
    train_end, val_start, val_end, test_start = boundaries(n)
    cov = {"train": coverage(fx, bars, WARMUP, train_end),
           "validation": coverage(fx, bars, val_start, val_end),
           "test": coverage(fx, bars, test_start, n)}
    train = {k: variant(bars, WARMUP, train_end, k, fx) for k in SELECTABLE}
    val = {k: variant(bars, val_start, val_end, k, fx) for k in SELECTABLE}
    selected = choose(train, val, cov)
    test = {k: variant(bars, test_start, n, k, fx, audit=True) for k in SPECS}
    for r in test.values():
        r.pop("decision_audit", None)
    baseline = {k: simulate(bars, test_start, n, k) for k in
                ("sma", "momentum", "rsi", "breakout", "regime", "trend_breakout")}
    return {
        "segment_bars": n, "fx_coverage_fraction": cov,
        "test_start_utc": datetime.fromtimestamp(bars[test_start][0], UTC).isoformat(),
        "test_end_utc": datetime.fromtimestamp(bars[-1][0], UTC).isoformat(),
        "train": train, "validation": val,
        "selected_using_train_validation_only": selected,
        "selected_test_net_aud": test[selected]["net_aud"] if selected != "HOLD" else 0.,
        "test": test, "baseline": baseline,
        "buyhold_net_aud": buyhold(bars, test_start, n),
        "sensitivity": {
            "A50": variant(bars, test_start, n, "h80_fx_headwind", fx,
                           max_entry_debit=50.)["net_aud"],
            "A100": test["h80_fx_headwind"]["net_aud"],
            "half_cost": variant(bars, test_start, n, "h80_fx_headwind", fx,
                                 cost_mult=.5)["net_aud"],
            "double_cost": variant(bars, test_start, n, "h80_fx_headwind", fx,
                                   cost_mult=2.)["net_aud"],
        },
    }

def evaluate(bars, fx, market_provenance, fx_provenance):
    folds = [one_segment(bars[a:b], fx) for a, b in segments(bars, 1000)]
    fields = ("trades", "wins", "losses", "gross_aud", "fees_aud",
              "spread_aud", "slippage_aud", "net_aud")
    totals = {k: {f: round(sum(x["test"][k][f] for x in folds), 6)
                  for f in fields} for k in SPECS}
    return {
        "mode": "V39_EXPLORATORY_PRIOR_INSPECTED_PAPER_ONLY",
        "market": market_provenance, "fx": fx_provenance,
        "fx_release_clock": "ASSUMED 17:00 Australia/Sydney plus 24h, DST-aware",
        "fx_historical_first_observed_verified": False,
        "fx_historical_revisions_verified": False,
        "folds": folds, "aggregate_independent_reset_accounts": totals,
        "selected_test_net_aud": round(sum(x["selected_test_net_aud"] for x in folds), 6),
        "buyhold_net_aud": round(sum(x["buyhold_net_aud"] for x in folds), 6),
        "worst_fold_drawdown_pct": {
            k: min(x["test"][k]["max_drawdown_pct"] for x in folds) for k in SPECS},
        "baseline_net_aud": {
            k: round(sum(x["baseline"][k]["net_aud"] for x in folds), 6)
            for k in folds[0]["baseline"]},
        "cost_bps_each_side": COSTS_BPS, "starting_cash_aud": CASH,
        "max_inclusive_entry_aud": CAP, "paper_policy": "HOLD",
        "promotion": "REJECTED_NO_UNTOUCHED_OOS_OR_VERIFIED_FX_VINTAGE",
        "limitations": [
            "RBA snapshot is retrospective, not historical first-observed FX vintage",
            "Current 80bps taker fee imposed on historical prices",
            "Prior-inspected BTC/AUD data, NOT untouched out-of-sample",
            "No observed order-book fills, depth, partial fills or real slippage",
            "Independent A$1000 wallet resets per segment; NET not compounded",
            "Assumed 24h delay is conservative but not historical release proof",
        ],
    }

def fetch_fx():
    successes, failures, rows = {}, {}, []
    for label, url, parser in (
        ("rba_f11_1_csv_2023_current", CSV_URL, parse_csv),
        ("rba_f11_xls_2018_2022", XLS_URL, parse_xls),
    ):
        try:
            raw = source_request(url)
            subset = parser(raw)
            if not subset:
                raise ValueError("No valid USD per AUD observations")
            successes[label] = {"url": url, "sha256": hashlib.sha256(raw).hexdigest(),
                "rows": len(subset), "first": subset[0][0], "last": subset[-1][0],
                "retrieved_at_utc": datetime.now(UTC).isoformat(),
                "license": "RBA financial data / WM-Reuters upstream rights; no raw redistribution"}
            rows.extend(subset)
        except Exception as exc:
            failures[label] = f"{type(exc).__name__}: {str(exc)[:250]}"
    if not rows:
        raise RuntimeError("Both official RBA sources failed: " + json.dumps(failures))
    return FXSeries(rows), {"successful_sources": successes, "failed_sources": failures,
        "deduplicated_days": len(validate_rows(rows)),
        "first_day": min(d for d, _ in rows), "last_day": max(d for d, _ in rows),
        "availability": "retrospective_17_sydney_plus_24h_assumed_NOT_FIRST_OBSERVED"}

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output", default="audit/v39-rba-fx-walkforward.json")
    args = p.parse_args()
    fx, fx_prov = fetch_fx()
    bars, market_prov = archive()
    report = evaluate(bars, fx, market_prov, fx_prov)
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(report, indent=2, allow_nan=False) + "\n").encode()
    path.write_bytes(raw)
    print(json.dumps({
        "report_sha256": hashlib.sha256(raw).hexdigest(),
        "fx": fx_prov,
        "fold_coverage": [f["fx_coverage_fraction"] for f in report["folds"]],
        "aggregate_net": {k: v["net_aud"] for k, v in
                          report["aggregate_independent_reset_accounts"].items()},
        "selected_test_net": report["selected_test_net_aud"],
        "buyhold_net": report["buyhold_net_aud"], "paper_policy": "HOLD"}))

if __name__ == "__main__":
    main()

"""V43 PAPER ONLY: predeclared 90-day drawdown cash-entry gate.

The gate suppresses new H80/300 BUY decisions when the completed close is
below a fixed threshold from the preceding 540-bar high. Existing positions
can always SELL. A 42-bar delayed gate is a negative control. The three Kraken
archive segments were previously inspected: exploratory, not untouched OOS.
No news signal, Android promotion, or live execution is permitted.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

from research.v29_point_in_time import CASH, CAP, FEE, SPREAD, SLIPPAGE, simulate
from research.v31_hysteresis import replay as replay_base, WARMUP
from research.v32_segments import segments
from research.v33_cross_regime import archive
from research.v41_volume_confirmation import (
    buyhold_audit, load_verified_news, market_diagnostics,
)
from research.v42_volatility_exit import boundaries_v42
from research.v48_news_proof_gate import classify as classify_news

DRAWDOWN_LOOKBACK = 540  # 90 days of completed 4h candles
PLACEBO_DELAY_BARS = 42  # 7 days, deliberately stale negative control
THRESHOLDS = (0.10, 0.15, 0.20)
CANDIDATES = (
    "h80_base",
    "h80_dd10",
    "h80_dd15",
    "h80_dd20",
    "h80_dd15_placebo7d",
)
SELECTABLE = CANDIDATES[:-1]
THRESHOLD_BY_NAME = {
    "h80_dd10": 0.10,
    "h80_dd15": 0.15,
    "h80_dd20": 0.20,
    "h80_dd15_placebo7d": 0.15,
}
MIN_TRADE_COUNT = 2
EMBARGO_BARS = 84
REPLAY_START = DRAWDOWN_LOOKBACK + 1
FIELDS = (
    "trades", "wins", "losses", "gross_aud", "fees_aud",
    "spread_aud", "slippage_aud", "net_aud",
)


def drawdown_from_high(bars, decision_index, lookback=DRAWDOWN_LOOKBACK,
                       delay_bars=0):
    """Drawdown at OPEN i using only completed bars before i.

    The current bar's OHLCV is never inspected. A delayed value is an
    intentionally stale placebo, not a tradable signal.
    """
    if lookback < 2 or delay_bars < 0:
        raise ValueError("Invalid drawdown window")
    end = decision_index - delay_bars
    if end < lookback or end > len(bars):
        return None
    window = bars[end - lookback:end]
    close = float(bars[end - 1][4])
    highs = [float(row[2]) for row in window]
    if not math.isfinite(close) or close <= 0:
        raise ValueError("Invalid completed close")
    if any(not math.isfinite(high) or high <= 0 for high in highs):
        raise ValueError("Invalid historical high")
    peak = max(highs)
    if peak < close:
        # A close above all highs is possible only with inconsistent OHLC.
        if close > float(window[-1][2]) + 1e-9:
            raise ValueError("Close exceeds completed candle high")
        peak = max(peak, close)
    return close / peak - 1.0


def make_entry_veto(bars, candidate, audit_rows=None):
    """Build a strictly past-only gate; callback receives decision bar epoch."""
    if candidate not in CANDIDATES:
        raise ValueError("Unknown V43 candidate")
    if candidate == "h80_base":
        return None
    threshold = THRESHOLD_BY_NAME[candidate]
    delay = PLACEBO_DELAY_BARS if candidate.endswith("placebo7d") else 0
    index_by_ts = {int(row[0]): i for i, row in enumerate(bars)}

    def veto(decision_ts):
        index = index_by_ts.get(int(decision_ts))
        if index is None:
            raise ValueError("Decision timestamp is absent from market bars")
        value = drawdown_from_high(
            bars, index, DRAWDOWN_LOOKBACK, delay_bars=delay,
        )
        if value is None or value > -threshold:
            return False
        if audit_rows is not None:
            audit_rows.append({
                "decision_index": index,
                "decision_ts": int(decision_ts),
                "drawdown_pct": round(value * 100, 6),
                "threshold_pct": round(threshold * 100, 6),
                "delay_bars": delay,
                "decision": "BUY_VETOED",
            })
        return True

    return veto


def replay_candidate(bars, start, end, candidate, *, cost_mult=1.0,
                     max_entry_debit=CAP, audit=False):
    if candidate not in CANDIDATES:
        raise ValueError("Unknown V43 candidate")
    if start < REPLAY_START or end > len(bars) or end - start < 3:
        raise ValueError("Invalid V43 chronological replay interval")
    if not 0.5 <= cost_mult <= 2.0:
        raise ValueError("Cost multiplier outside registered sensitivity")
    if not 0 < max_entry_debit <= CAP:
        raise ValueError("Paper entry cap must be in (0, A$100]")
    veto_rows = []
    veto = make_entry_veto(
        bars, candidate, audit_rows=veto_rows if audit else None,
    )
    result = replay_base(
        bars, start, end, "h80_300", events=(), cost_mult=cost_mult,
        audit=audit, entry_veto=veto, max_entry_debit=max_entry_debit,
    )
    result["candidate"] = candidate
    result["gate_veto_count"] = len(veto_rows)
    result["gate_veto_audit"] = veto_rows if audit else []
    if audit:
        # The V31 engine records every decision; the gate audit above records
        # only BUYs actually suppressed. Keep trade-level accounting, discard
        # redundant HOLD decision rows.
        result.pop("decision_audit", None)
        result["missed_opportunities_after_veto"] = missed_after_veto(
            bars, veto_rows, end,
        )
    return result


def missed_after_veto(bars, veto_rows, end):
    """Descriptive forward outcomes after vetoed entries; not net P&L."""
    report = {}
    for horizon, label in ((6, "24h"), (42, "7d")):
        values = [
            float(bars[row["decision_index"] + horizon][4])
            / float(bars[row["decision_index"]][1]) - 1.0
            for row in veto_rows
            if row["decision_index"] + horizon < end
        ]
        report[label] = {
            "observations": len(values),
            "positive": sum(value > 0 for value in values),
            "non_positive": sum(value <= 0 for value in values),
            "mean_forward_return_pct": (
                round(sum(values) / len(values) * 100, 6)
                if values else None
            ),
        }
    return report


def select(training, validation):
    """Train/validation-only selection; insufficient evidence means HOLD."""
    eligible = [
        name for name in SELECTABLE
        if training[name]["trades"] >= MIN_TRADE_COUNT
        and validation[name]["trades"] >= MIN_TRADE_COUNT
        and training[name]["net_aud"] > 0
        and validation[name]["net_aud"] > 0
    ]
    if not eligible:
        return "HOLD"
    return max(eligible, key=lambda name: min(
        training[name]["net_aud"], validation[name]["net_aud"],
    ))


def aggregate(results):
    totals = {
        field: round(sum(row[field] for row in results), 6)
        for field in FIELDS
    }
    totals["return_pct"] = round(
        totals["net_aud"] / (CASH * len(results)) * 100, 6,
    )
    totals["worst_fold_drawdown_pct"] = min(
        row["max_drawdown_pct"] for row in results
    )
    totals["gate_veto_count"] = sum(
        row.get("gate_veto_count", 0) for row in results
    )
    return totals


def evaluate(bars, market_provenance, news_path="data/historical_news_sample_v38.jsonl"):
    market = market_diagnostics(bars, market_provenance)
    news_events, news_sha, news_counts = load_verified_news(news_path)
    folds = []
    eligible_segments = segments(bars, 1000)

    for left, right in eligible_segments:
        local = bars[left:right]
        n = len(local)
        train_end, val_start, val_end, test_start = boundaries_v42(n)
        if train_end <= REPLAY_START:
            raise ValueError("Segment lacks 90-day completed-bar warm-up")
        training = {
            name: replay_candidate(local, REPLAY_START, train_end, name)
            for name in SELECTABLE
        }
        validation = {
            name: replay_candidate(local, val_start, val_end, name)
            for name in SELECTABLE
        }
        chosen = select(training, validation)
        tests = {
            name: replay_candidate(local, test_start, n, name, audit=True)
            for name in CANDIDATES
        }
        baselines = {
            name: simulate(local, test_start, n, name)
            for name in ("sma", "momentum", "rsi", "breakout",
                         "regime", "trend_breakout")
        }
        sensitivity = {
            name: {
                "A50_current_cost": replay_candidate(
                    local, test_start, n, name, max_entry_debit=50.0,
                )["net_aud"],
                "A100_half_cost": replay_candidate(
                    local, test_start, n, name, cost_mult=0.5,
                )["net_aud"],
                "A100_current_cost": tests[name]["net_aud"],
                "A100_double_cost": replay_candidate(
                    local, test_start, n, name, cost_mult=2.0,
                )["net_aud"],
            }
            for name in CANDIDATES
        }
        test_start_ts = int(local[test_start][0])
        test_end_ts = int(local[-1][0])
        strict_news_test = 0
        for event in news_events:
            proof = classify_news(event, test_end_ts, latency_seconds=3600)
            if (proof["eligible"] and
                    test_start_ts <= proof["available_at_utc"] <= test_end_ts):
                strict_news_test += 1
        folds.append({
            "segment_bars": n,
            "first_utc": datetime.fromtimestamp(
                local[0][0], timezone.utc,
            ).isoformat(),
            "last_utc": datetime.fromtimestamp(
                local[-1][0], timezone.utc,
            ).isoformat(),
            "train_end_utc": datetime.fromtimestamp(
                local[train_end - 1][0], timezone.utc,
            ).isoformat(),
            "validation_start_utc": datetime.fromtimestamp(
                local[val_start][0], timezone.utc,
            ).isoformat(),
            "validation_end_utc": datetime.fromtimestamp(
                local[val_end - 1][0], timezone.utc,
            ).isoformat(),
            "test_start_utc": datetime.fromtimestamp(
                test_start_ts, timezone.utc,
            ).isoformat(),
            "test_end_utc": datetime.fromtimestamp(
                test_end_ts, timezone.utc,
            ).isoformat(),
            "embargo_bars": EMBARGO_BARS,
            "training": training,
            "validation": validation,
            "selected_using_train_validation_only": chosen,
            "selected_test_net_aud": (
                tests[chosen]["net_aud"] if chosen != "HOLD" else 0.0
            ),
            "test": tests,
            "price_baselines": baselines,
            "buyhold_aud100": buyhold_audit(
                local, test_start, n, max_entry_debit=100.0,
            ),
            "sensitivity": sensitivity,
            "strict_verified_news_available_in_test": strict_news_test,
        })

    aggregates = {
        name: aggregate([fold["test"][name] for fold in folds])
        for name in CANDIDATES
    }
    baseline_aggregates = {
        name: aggregate([fold["price_baselines"][name] for fold in folds])
        for name in folds[0]["price_baselines"]
    }
    buyhold = aggregate([fold["buyhold_aud100"] for fold in folds])
    return {
        "schema": "v43_drawdown_cash_gate_1",
        "mode": "V43_PAPER_ONLY_PRIOR_INSPECTED_EXPLORATORY",
        "market": market,
        "news": {
            "corpus_sha256": news_sha,
            "verified_capture_rows": len(news_events),
            "classification_counts_by_reason": news_counts,
            "strict_asof_events_in_test_windows": sum(
                fold["strict_verified_news_available_in_test"]
                for fold in folds
            ),
            "used_for_strategy_selection": False,
            "reason": "Price-only drawdown gate; no sentiment or retrospective publication-time feature used",
        },
        "parameters_predeclared": {
            "base": "H80/300",
            "lookback_completed_4h_bars": DRAWDOWN_LOOKBACK,
            "thresholds": list(THRESHOLDS),
            "placebo_delay_bars": PLACEBO_DELAY_BARS,
            "placebo_delay_hours": 168,
            "entry_only_gate": True,
            "protective_sells_never_vetoed": True,
            "selection": "train/validation only; >=2 trades and positive NET in both; otherwise HOLD",
            "embargo_bars": EMBARGO_BARS,
            "purge_rule": "84-bar embargo; independent A$1,000 wallets; terminal liquidation; no cross-partition positions",
        },
        "fees_each_side_bps": {
            "taker": 80, "half_spread": 5, "slippage": 5,
        },
        "starting_cash_aud": CASH,
        "max_inclusive_entry_debit_aud": CAP,
        "cash_fraction_cap": 0.10,
        "folds": folds,
        "aggregate_independent_reset_accounts": aggregates,
        "aggregate_price_baselines": baseline_aggregates,
        "aggregate_buyhold_aud100": buyhold,
        "aggregate_selected_test_net_aud": round(
            sum(fold["selected_test_net_aud"] for fold in folds), 6,
        ),
        "research_policy": "HOLD",
        "android_policy": "HOLD",
        "promotion": "REJECTED: previously inspected history; no untouched positive NET edge or Android parity",
        "limitations": [
            "All official Kraken archive periods were previously inspected; not untouched OOS",
            "Three independent A$1,000 wallets are summed, not compounded",
            "Historical fills use current 80bps taker plus modeled spread/slippage",
            "The gate is price-only; strict as-of news count is reported but not traded",
            "Forward returns after vetoed signals are descriptive missed opportunities, not net executable P&L",
            "The 42-bar placebo is deliberately delayed and is not a candidate for deployment",
            "No real order book, partial fills, latency or market impact is modeled",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="audit/v43-drawdown-cash-gate.json")
    parser.add_argument("--news", default="data/historical_news_sample_v38.jsonl")
    parser.add_argument("--bars-json", default=None)
    parser.add_argument("--bars-json-output", default=None)
    args = parser.parse_args(argv)
    if args.bars_json:
        source = json.loads(Path(args.bars_json).read_text(encoding="utf-8"))
        if source.get("schema") != "v41_kraken_ohlcvt_1":
            raise ValueError("Unknown official Kraken market-bar artifact schema")
        bars = source["bars"]
        provenance = source["market_provenance"]
    else:
        bars, provenance = archive()
    report = evaluate(bars, provenance, args.news)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(report, indent=2, allow_nan=False) + "\n").encode()
    output.write_bytes(raw)
    if args.bars_json_output:
        path = Path(args.bars_json_output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(json.dumps({
            "schema": "v41_kraken_ohlcvt_1",
            "market_provenance": report["market"],
            "bars": bars,
        }, separators=(",", ":"), allow_nan=False).encode() + b"\n")
    print(json.dumps({
        "output": str(output),
        "mode": report["mode"],
        "selected": [fold["selected_using_train_validation_only"]
                     for fold in report["folds"]],
        "aggregate": report["aggregate_independent_reset_accounts"],
        "selected_test_net_aud": report["aggregate_selected_test_net_aud"],
        "buyhold_net_aud": report["aggregate_buyhold_aud100"]["net_aud"],
        "promotion": report["promotion"],
    }, indent=2))


if __name__ == "__main__":
    main()

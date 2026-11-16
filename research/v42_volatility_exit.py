"""V42 PAPER ONLY: volatility-normalized exit and time-stop ablation.

Signals use the prior completed 4h candle; ATR stops are close-confirmed and
filled at the next bar OPEN. Historical Kraken periods are previously inspected
and exploratory, never untouched OOS. No Android promotion or live execution.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

from research.v29_point_in_time import (
    CAP, CASH, FEE, SPREAD, SLIPPAGE, STEP, execution, simulate,
)
from research.v31_hysteresis import (
    COOLDOWN, WARMUP, decision as base_decision,
)
from research.v32_segments import segments
from research.v33_cross_regime import archive
from research.v41_volume_confirmation import (
    buyhold_audit, load_verified_news, market_diagnostics,
)
from research.v48_news_proof_gate import classify as classify_news

ATR_LOOKBACK = 14
MIN_TRADE_COUNT = 2
CANDIDATES = (
    "h80_base",
    "h80_atr25",
    "h80_atr35",
    "h80_time42",
    "h80_atr25_time84",
    "h80_atr35_time42",
    "h50_base",
)
SELECTABLE = CANDIDATES
V42_EMBARGO_BARS = 84
BASE_STRATEGY = {
    "h80_base": "h80_300",
    "h80_atr25": "h80_300",
    "h80_atr35": "h80_300",
    "h80_time42": "h80_300",
    "h80_atr25_time84": "h80_300",
    "h80_atr35_time42": "h80_300",
    "h50_base": "h50_200",
}
EXIT_RULES = {
    "h80_base": (None, None),
    "h80_atr25": (2.5, None),
    "h80_atr35": (3.5, None),
    "h80_time42": (None, 42),
    "h80_atr25_time84": (2.5, 84),
    "h80_atr35_time42": (3.5, 42),
    "h50_base": (None, None),
}
FIELDS = (
    "trades", "wins", "losses", "gross_aud", "fees_aud",
    "spread_aud", "slippage_aud", "net_aud",
)


def atr14(bars, decision_index, lookback=ATR_LOOKBACK):
    """ATR of completed candles strictly before OPEN decision_index."""
    if lookback < 2 or decision_index < lookback + 1:
        return None
    true_ranges = []
    for k in range(decision_index - lookback, decision_index):
        high = float(bars[k][2])
        low = float(bars[k][3])
        previous_close = float(bars[k - 1][4])
        values = (high, low, previous_close)
        if not all(math.isfinite(x) and x > 0 for x in values) or high < low:
            raise ValueError("Invalid OHLC input for ATR")
        true_ranges.append(max(
            high - low,
            abs(high - previous_close),
            abs(low - previous_close),
        ))
    return sum(true_ranges) / len(true_ranges)


def select(training, validation):
    """Select only on past train/validation results; otherwise HOLD."""
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
        training[name]["net_aud"], validation[name]["net_aud"]
    ))



def boundaries_v42(n, embargo_bars=V42_EMBARGO_BARS):
    """50/20/30 chronological split with embargo matching the 84-bar max hold."""
    if embargo_bars < max(
            (hold or 0) for _, hold in EXIT_RULES.values()):
        raise ValueError("Embargo must cover the longest registered holding horizon")
    train_end = int(n * 0.50)
    validation_start = train_end + embargo_bars
    validation_end = int(n * 0.70) - embargo_bars
    test_start = int(n * 0.70)
    if (train_end <= WARMUP or validation_start >= validation_end
            or validation_end >= test_start or test_start >= n):
        raise ValueError("Segment too short for V42 84-bar embargo")
    return train_end, validation_start, validation_end, test_start


def replay_exit(
    bars, start, end, name, *, cost_mult=1.0,
    max_entry_debit=CAP, audit=False,
):
    """Hysteresis base plus fixed-entry-ATR stop and/or maximum holding time.

    ATR is frozen from the last completed candle at entry. A stop is evaluated
    only against a completed close, then filled at the next bar OPEN. No
    intrabar stop execution or current-bar high/low look-ahead is assumed.
    """
    if name not in CANDIDATES:
        raise ValueError("Unknown V42 candidate")
    if start < WARMUP or end > len(bars) or end - start < 3:
        raise ValueError("Invalid chronological replay segment")
    if not 0 < max_entry_debit <= CAP:
        raise ValueError("Paper entry cap must be in (0, A$100]")
    if not 0.5 <= cost_mult <= 2.0:
        raise ValueError("Cost multiplier outside registered sensitivity")
    if any(len(row) < 5 for row in bars):
        raise ValueError("OHLC fields missing")
    if any(bars[k][0] - bars[k - 1][0] != STEP
           for k in range(start - WARMUP + 1, end)):
        raise ValueError("Candle gap: fail closed")

    atr_multiple, max_hold_bars = EXIT_RULES[name]
    base_name = BASE_STRATEGY[name]
    cash = CASH
    qty = 0.0
    entry = None
    entry_mid = 0.0
    entry_atr = None
    entry_index = None
    entry_cash_before = None
    last_exit = -COOLDOWN
    trades = []
    equity = [cash]

    for i in range(start, end):
        mid = float(bars[i][1])
        held = i - entry_index if qty else 0
        exit_reason = None

        if i == end - 1:
            action = "SELL" if qty else "HOLD"
            if qty:
                exit_reason = "terminal_liquidation"
        else:
            action = base_decision(
                bars, i, base_name, bool(qty), held, events=(),
            )
            if qty:
                completed_close = float(bars[i - 1][4])
                if (atr_multiple is not None and entry_atr is not None
                        and held >= 1
                        and completed_close <= entry_mid - atr_multiple * entry_atr):
                    action = "SELL"
                    exit_reason = "entry_atr_stop_next_open"
                elif max_hold_bars is not None and held >= max_hold_bars:
                    action = "SELL"
                    exit_reason = "maximum_holding_time_next_open"
                elif action == "SELL":
                    exit_reason = "hysteresis_exit"

        if not qty and i < last_exit + COOLDOWN:
            action = "HOLD"

        if action == "BUY" and not qty:
            current_atr = atr14(bars, i)
            if current_atr is None or current_atr <= 0:
                action = "HOLD"
            else:
                budget = min(max_entry_debit, 0.10 * cash)
                qty = budget / (
                    mid * (1 + (SPREAD + SLIPPAGE) * cost_mult)
                    * (1 + FEE * cost_mult)
                )
                entry = execution(mid, qty, "buy", cost_mult)
                debit = entry["notional"] + entry["fee"]
                if debit > budget + 1e-8 or debit > max_entry_debit + 1e-8:
                    raise AssertionError("Inclusive A$100/10% paper debit cap")
                entry_cash_before = cash
                cash -= debit
                entry_mid = mid
                entry_atr = current_atr
                entry_index = i

        elif action == "SELL" and qty:
            out = execution(mid, qty, "sell", cost_mult)
            cash += out["notional"] - out["fee"]
            gross = qty * (mid - entry_mid)
            fees = entry["fee"] + out["fee"]
            spread = entry["spread"] + out["spread"]
            slippage = entry["slippage"] + out["slippage"]
            net = gross - fees - spread - slippage
            realised = (
                out["notional"] - out["fee"]
                - entry["notional"] - entry["fee"]
            )
            if not math.isclose(net, realised, abs_tol=1e-8):
                raise AssertionError("Gross/cost/NET accounting mismatch")
            if entry["notional"] + entry["fee"] > min(
                    max_entry_debit, 0.10 * entry_cash_before) + 1e-8:
                raise AssertionError("Entry debit exceeds inclusive risk cap")
            trades.append({
                "entry_index": entry_index,
                "exit_index": i,
                "entry_ts": bars[entry_index][0],
                "exit_ts": bars[i][0],
                "entry_mid_aud": entry_mid,
                "exit_mid_aud": mid,
                "entry_debit_aud": entry["notional"] + entry["fee"],
                "cash_before_entry_aud": entry_cash_before,
                "entry_atr14_aud": entry_atr,
                "atr_stop_multiple": atr_multiple,
                "max_hold_bars": max_hold_bars,
                "held_bars": i - entry_index,
                "exit_reason": exit_reason or "unspecified",
                "gross": gross,
                "fees": fees,
                "spread": spread,
                "slippage": slippage,
                "net": net,
            })
            qty = 0.0
            entry = None
            entry_atr = None
            entry_index = None
            entry_cash_before = None
            last_exit = i

        marked = cash
        if qty:
            mark_exit = execution(mid, qty, "sell", cost_mult)
            marked += mark_exit["notional"] - mark_exit["fee"]
        equity.append(marked)

    if qty or not math.isclose(
            cash - CASH, sum(t["net"] for t in trades), abs_tol=1e-7):
        raise AssertionError("Paper wallet does not reconcile")

    peak = equity[0]
    max_drawdown = 0.0
    for value in equity:
        peak = max(peak, value)
        if peak > 0:
            max_drawdown = min(max_drawdown, value / peak - 1.0)

    missed = {}
    for horizon, label in ((6, "24h"), (42, "7d")):
        observations = [
            float(bars[t["exit_index"] + horizon][4]) / t["exit_mid_aud"] - 1.0
            for t in trades if t["exit_index"] + horizon < end
        ]
        missed[label] = {
            "observations": len(observations),
            "positive_count": sum(x > 0 for x in observations),
            "negative_count": sum(x <= 0 for x in observations),
            "mean_forward_return_pct": (
                round(sum(observations) / len(observations) * 100, 6)
                if observations else None
            ),
        }

    totals = {field: sum(t[field] for t in trades)
              for field in ("gross", "fees", "spread", "slippage", "net")}
    result = {
        "strategy": name,
        "trades": len(trades),
        "wins": sum(t["net"] > 0 for t in trades),
        "losses": sum(t["net"] <= 0 for t in trades),
        "gross_aud": round(totals["gross"], 6),
        "fees_aud": round(totals["fees"], 6),
        "spread_aud": round(totals["spread"], 6),
        "slippage_aud": round(totals["slippage"], 6),
        "net_aud": round(totals["net"], 6),
        "return_pct": round(totals["net"] / CASH * 100, 6),
        "max_drawdown_pct": round(max_drawdown * 100, 6),
        "missed_opportunities_after_exit": missed,
        "cost_multiplier": cost_mult,
        "max_entry_debit_aud": max_entry_debit,
    }
    if audit:
        result["trade_audit"] = trades
    return result


def evaluate(bars, market_provenance, news_events, news_sha256,
             news_classification_counts=None):
    market = market_diagnostics(bars, market_provenance)
    folds = []
    for left, right in segments(bars, 1000):
        local = bars[left:right]
        n = len(local)
        train_end, val_start, val_end, test_start = boundaries_v42(n)
        training = {
            name: replay_exit(local, WARMUP, train_end, name)
            for name in SELECTABLE
        }
        validation = {
            name: replay_exit(local, val_start, val_end, name)
            for name in SELECTABLE
        }
        chosen = select(training, validation)
        tests = {
            name: replay_exit(local, test_start, n, name, audit=True)
            for name in CANDIDATES
        }
        baselines = {
            name: simulate(local, test_start, n, name)
            for name in ("sma", "momentum", "rsi", "breakout",
                         "regime", "trend_breakout")
        }
        sensitivity = {}
        for name in CANDIDATES:
            sensitivity[name] = {
                "A50_current_cost": replay_exit(
                    local, test_start, n, name, max_entry_debit=50.0
                )["net_aud"],
                "A100_half_cost": replay_exit(
                    local, test_start, n, name, cost_mult=0.5
                )["net_aud"],
                "A100_current_cost": tests[name]["net_aud"],
                "A100_double_cost": replay_exit(
                    local, test_start, n, name, cost_mult=2.0
                )["net_aud"],
            }
        selected_test = tests[chosen]["net_aud"] if chosen != "HOLD" else 0.0
        buyhold_50 = buyhold_audit(
            local, test_start, n, max_entry_debit=50.0
        )
        buyhold_100 = buyhold_audit(
            local, test_start, n, max_entry_debit=100.0
        )
        test_start_ts = local[test_start][0]
        test_end_ts = local[-1][0]
        strict_news_test = 0
        for event in news_events:
            proof = classify_news(
                event, test_end_ts, latency_seconds=3600
            )
            if (proof["eligible"] and
                    test_start_ts <= proof["available_at_utc"] <= test_end_ts):
                strict_news_test += 1
        folds.append({
            "segment_bars": n,
            "first_utc": datetime.fromtimestamp(
                local[0][0], timezone.utc
            ).isoformat(),
            "last_utc": datetime.fromtimestamp(
                local[-1][0], timezone.utc
            ).isoformat(),
            "train_end_utc": datetime.fromtimestamp(
                local[train_end - 1][0], timezone.utc
            ).isoformat(),
            "validation_start_utc": datetime.fromtimestamp(
                local[val_start][0], timezone.utc
            ).isoformat(),
            "validation_end_utc": datetime.fromtimestamp(
                local[val_end - 1][0], timezone.utc
            ).isoformat(),
            "test_start_utc": datetime.fromtimestamp(
                test_start_ts, timezone.utc
            ).isoformat(),
            "test_end_utc": datetime.fromtimestamp(
                test_end_ts, timezone.utc
            ).isoformat(),
            "embargo_bars": V42_EMBARGO_BARS,
            "training": training,
            "validation": validation,
            "selected_using_train_validation_only": chosen,
            "selected_test_net_aud": round(selected_test, 6),
            "test": tests,
            "price_baselines": baselines,
            "sensitivity": sensitivity,
            "buyhold_aud50": buyhold_50,
            "buyhold_aud100": buyhold_100,
            "strict_verified_news_available_in_test": strict_news_test,
        })

    aggregate = {}
    for name in CANDIDATES:
        aggregate[name] = {
            field: round(sum(f["test"][name][field] for f in folds), 6)
            for field in FIELDS
        }
        aggregate[name]["return_pct"] = round(
            aggregate[name]["net_aud"] / (CASH * len(folds)) * 100, 6
        )
        aggregate[name]["worst_fold_drawdown_pct"] = min(
            f["test"][name]["max_drawdown_pct"] for f in folds
        )
    baseline_aggregate = {}
    for name in folds[0]["price_baselines"]:
        baseline_aggregate[name] = {
            field: round(sum(f["price_baselines"][name][field]
                             for f in folds), 6)
            for field in FIELDS
        }
        baseline_aggregate[name]["return_pct"] = round(
            baseline_aggregate[name]["net_aud"] /
            (CASH * len(folds)) * 100, 6
        )
        baseline_aggregate[name]["worst_fold_drawdown_pct"] = min(
            f["price_baselines"][name]["max_drawdown_pct"]
            for f in folds
        )
    buyhold_aggregate = {}
    for cap, key in ((50, "buyhold_aud50"), (100, "buyhold_aud100")):
        buyhold_aggregate[str(cap)] = {
            field: round(sum(f[key][field] for f in folds), 6)
            for field in FIELDS
        }
        buyhold_aggregate[str(cap)]["return_pct"] = round(
            buyhold_aggregate[str(cap)]["net_aud"] /
            (CASH * len(folds)) * 100, 6
        )
        buyhold_aggregate[str(cap)]["worst_fold_drawdown_pct"] = min(
            f[key]["max_drawdown_pct"] for f in folds
        )

    return {
        "mode": "V42_PAPER_ONLY_PRIOR_INSPECTED_EXPLORATORY",
        "market": market,
        "news": {
            "corpus_sha256": news_sha256,
            "independently_verified_capture_rows": len(news_events),
            "classification_counts_by_reason": news_classification_counts or {},
            "strict_asof_events_in_test_windows": sum(
                f["strict_verified_news_available_in_test"] for f in folds
            ),
            "use_in_strategy": False,
            "reason": "This exit experiment is price-only; proof-gated news is reported separately and is not used as a trading feature",
            "sentiment": "NOT AVAILABLE / NOT INFERRED",
        },
        "parameters_predeclared": {
            "base_hysteresis": "H80/300",
            "atr_lookback_completed_bars": ATR_LOOKBACK,
            "atr_stop_multiples": [2.5, 3.5],
            "maximum_hold_bars": [42, 84],
            "minimum_hold_bars_for_ATR_stop": 1,
            "time_stop_clock": "completed 4h bars; fill next OPEN",
            "atr_stop_clock": "completed close breach; fill next OPEN",
            "candidate_count": len(CANDIDATES),
            "selection": "train/validation only; >=2 trades and positive NET in both; otherwise HOLD",
            "embargo_bars": 20,
        },
        "fees_each_side_bps": {
            "taker": 80, "half_spread": 5, "slippage": 5,
        },
        "starting_cash_aud": CASH,
        "max_inclusive_entry_debit_aud": CAP,
        "cash_fraction_cap": 0.10,
        "folds": folds,
        "aggregate_independent_reset_accounts": aggregate,
        "aggregate_price_baselines": baseline_aggregate,
        "aggregate_buyhold": buyhold_aggregate,
        "aggregate_selected_test_net_aud": round(
            sum(f["selected_test_net_aud"] for f in folds), 6
        ),
        "research_policy": "HOLD",
        "android_policy": "HOLD",
        "promotion": "REJECTED: prior-inspected historical data; no untouched OOS or verified Android execution parity",
        "limitations": [
            "All official archive periods were previously inspected; NOT untouched OOS",
            "Historical current fees are applied to old prices, not actual historic fills",
            "H80/H50 base variants have no fixed maximum holding period; forced terminal liquidation prevents cross-partition carry but truncates boundary trades",
            "ATR stop is close-confirmed and filled at next open; no intrabar stop or order-book execution",
            "All fills are hypothetical next-open taker fills with modeled spread/slippage",
            "News has no independently verified eligible test-window signal and is not used",
            "Each gap-free segment has an independent A$1,000 wallet; aggregates are not compounded",
            "Multiple candidate selection remains exploratory despite train/validation-only separation",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="audit/v42-volatility-exit.json")
    parser.add_argument("--news", default="data/historical_news_sample_v38.jsonl")
    parser.add_argument("--bars-json", default=None)
    parser.add_argument("--bars-json-output", default=None)
    args = parser.parse_args(argv)
    if args.bars_json:
        source_doc = json.loads(Path(args.bars_json).read_text(encoding="utf-8"))
        if source_doc.get("schema") != "v41_kraken_ohlcvt_1":
            raise ValueError("Unknown official Kraken market-bar artifact schema")
        bars = source_doc["bars"]
        provenance = source_doc["market_provenance"]
    else:
        bars, provenance = archive()
    events, news_sha, counts = load_verified_news(args.news)
    report = evaluate(bars, provenance, events, news_sha, counts)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(report, indent=2, allow_nan=False) + "\n").encode()
    output.write_bytes(raw)
    if args.bars_json_output:
        path = Path(args.bars_json_output)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema": "v41_kraken_ohlcvt_1",
            "market_provenance": report["market"],
            "bars": bars,
        }
        encoded = json.dumps(payload, separators=(",", ":"), allow_nan=False) + "\n"
        path.write_text(encoded, encoding="utf-8")
        readback = json.loads(path.read_text(encoding="utf-8"))
        if (len(readback["bars"]) != len(bars)
                or readback["market_provenance"].get("member_sha256")
                != report["market"].get("member_sha256")):
            raise AssertionError("V42 market artifact read-back mismatch")
    print(json.dumps({
        "report_sha256": hashlib.sha256(raw).hexdigest(),
        "segments": len(report["folds"]),
        "selected": [
            f["selected_using_train_validation_only"] for f in report["folds"]
        ],
        "selected_test_net_aud": report["aggregate_selected_test_net_aud"],
        "buyhold_a100_net_aud": report["aggregate_buyhold"]["100"]["net_aud"],
        "candidates": report["aggregate_independent_reset_accounts"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()

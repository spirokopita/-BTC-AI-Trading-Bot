"""V44 PAPER ONLY: AUD/USD realized-volatility entry filter.

Hypothesis: a high AUD/USD volatility regime can destabilize the AUD leg of
BTC/AUD and make long entries less reliable. The RBA FX snapshot is
retrospective; its 17:00 Sydney +24h availability is ASSUMED, not vintage
proof. Thresholds are calibrated on an early training-only window, frozen,
and tested later. Historical Kraken periods were already inspected.
"""
from __future__ import annotations

import argparse
import bisect
import hashlib
import json
import math
import statistics
from datetime import datetime, timezone
from pathlib import Path

from research.v29_point_in_time import CAP, CASH, simulate
from research.v31_hysteresis import WARMUP, replay
from research.v32_segments import segments
from research.v42_volatility_exit import boundaries_v42
from research.v39_rba_fx_asof import fetch_fx
from research.v41_volume_confirmation import buyhold_audit, load_verified_news

FX_WINDOW = 20
FX_STALENESS_SECONDS = 10 * 86400
CALIBRATION_FRACTION = 0.25
CALIBRATION_EMBARGO = 84
QUANTILES = {"h80_fxvol_q75": 0.75, "h80_fxvol_q90": 0.90,
             "h80_fxvol_q75_placebo7d": 0.75}
CANDIDATES = ("h80_base", *QUANTILES)
FIELDS = ("trades", "wins", "losses", "gross_aud", "fees_aud",
          "spread_aud", "slippage_aud", "net_aud")
COSTS = {"taker": 80, "half_spread": 5, "slippage": 5}


def fx_volatility_at(fx, decision_ts, *, delay_days=0, window=FX_WINDOW):
    """Annualized realized vol from the latest 20 FX observations available by cutoff."""
    if delay_days not in (0, 7) or window != FX_WINDOW:
        raise ValueError("Unregistered V44 window or placebo")
    cutoff = int(decision_ts) - delay_days * 86400
    k = bisect.bisect_right(fx.times, cutoff) - 1
    if k < window or cutoff - int(fx.times[k]) > FX_STALENESS_SECONDS:
        return None
    rates = [float(x) for x in fx.rates[k-window:k+1]]
    if any(not math.isfinite(x) or x <= 0 for x in rates):
        raise ValueError("Invalid AUD/USD observation")
    returns = [math.log(rates[j] / rates[j-1]) for j in range(1, len(rates))]
    if len(returns) != window:
        raise AssertionError("FX volatility window length mismatch")
    return {
        "annualized_volatility": statistics.pstdev(returns) * math.sqrt(252),
        "latest_observation_available_at": int(fx.times[k]),
        "latest_observation_day": fx.days[k] if hasattr(fx, "days") else None,
        "observations": window + 1,
        "delay_days": delay_days,
    }


def percentile(values, q):
    if not 0.5 <= q <= 0.99:
        raise ValueError("Quantile outside frozen range")
    clean = sorted(float(x) for x in values if math.isfinite(float(x)))
    if len(clean) < 30:
        return None
    index = max(0, min(len(clean)-1, math.ceil(q * len(clean)) - 1))
    return clean[index]


def calibration_thresholds(bars, fx, train_end):
    """Use only the first 25% of the pre-test training window to freeze thresholds."""
    if train_end <= WARMUP + 120:
        raise ValueError("Insufficient calibration history")
    calibration_end = WARMUP + max(120, int((train_end - WARMUP) * CALIBRATION_FRACTION))
    values = []
    for i in range(WARMUP, calibration_end):
        feature = fx_volatility_at(fx, bars[i][0])
        if feature is not None:
            values.append(feature["annualized_volatility"])
    coverage = len(values) / max(1, calibration_end - WARMUP)
    return {
        "calibration_start_index": WARMUP,
        "calibration_end_index_exclusive": calibration_end,
        "calibration_start_utc": datetime.fromtimestamp(bars[WARMUP][0], timezone.utc).isoformat(),
        "calibration_end_utc": datetime.fromtimestamp(bars[calibration_end-1][0], timezone.utc).isoformat(),
        "feature_observations": len(values),
        "coverage_fraction": round(coverage, 6),
        "q75": percentile(values, 0.75) if coverage >= 0.75 else None,
        "q90": percentile(values, 0.90) if coverage >= 0.75 else None,
    }


def make_entry_veto(bars, fx, name, thresholds, audit_rows=None):
    if name not in CANDIDATES:
        raise ValueError("Unknown V44 candidate")
    if name == "h80_base":
        return None
    qname = "h80_fxvol_q75" if name.endswith("placebo7d") else name
    threshold = thresholds.get("q75" if qname.endswith("q75") else "q90")
    delay = 7 if name.endswith("placebo7d") else 0
    index_by_ts = {int(row[0]): i for i, row in enumerate(bars)}

    def veto(decision_ts):
        index = index_by_ts.get(int(decision_ts))
        if index is None:
            raise ValueError("Decision timestamp missing from verified bars")
        feature = fx_volatility_at(fx, decision_ts, delay_days=delay)
        vol = None if feature is None else feature["annualized_volatility"]
        blocked = threshold is None or vol is None or vol >= threshold
        if blocked and audit_rows is not None:
            audit_rows.append({
                "decision_index": index,
                "decision_ts": int(decision_ts),
                "fx_vol_annualized": vol,
                "threshold": threshold,
                "delay_days": delay,
                "decision": "BUY_VETOED",
            })
        return blocked

    return veto


def replay_candidate(bars, start, end, fx, name, thresholds, *,
                     cost_mult=1.0, max_entry_debit=CAP, audit=False):
    if name not in CANDIDATES:
        raise ValueError("Unknown V44 candidate")
    if not 0.5 <= cost_mult <= 2.0:
        raise ValueError("Cost multiplier outside registered sensitivity")
    if not 0 < max_entry_debit <= CAP:
        raise ValueError("Paper entry debit must be <= A$100")
    veto_rows = []
    veto = make_entry_veto(bars, fx, name, thresholds,
                           veto_rows if audit else None)
    result = replay(
        bars, start, end, "h80_300", events=(), cost_mult=cost_mult,
        max_entry_debit=max_entry_debit, audit=audit, entry_veto=veto,
    )
    result["candidate"] = name
    result["gate_veto_count"] = len(veto_rows)
    if audit:
        result.pop("decision_audit", None)
        result["gate_veto_audit"] = veto_rows
        for trade in result["trade_audit"]:
            if trade["entry_debit_aud"] > min(max_entry_debit,
                    0.10 * trade["cash_before_entry_aud"]) + 1e-8:
                raise AssertionError("Inclusive A$100/10% cash cap violated")
            if not math.isclose(trade["net"], trade["gross"] - trade["fees"]
                    - trade["spread"] - trade["slippage"], abs_tol=1e-7):
                raise AssertionError("Gross-cost-NET mismatch")
    return result


def missed_opportunities(bars, veto_rows, end):
    report = {}
    for horizon, label in ((6, "24h"), (42, "7d")):
        values = [
            float(bars[row["decision_index"] + horizon][4])
            / float(bars[row["decision_index"]][1]) - 1.0
            for row in veto_rows if row["decision_index"] + horizon < end
        ]
        report[label] = {
            "observations": len(values),
            "positive": sum(x > 0 for x in values),
            "non_positive": sum(x <= 0 for x in values),
            "mean_forward_return_pct": round(statistics.mean(values) * 100, 6)
                if values else None,
            "note": "Descriptive missed-entry outcomes, not executable P&L",
        }
    return report


def select(training, validation):
    eligible = [
        name for name in CANDIDATES
        if training[name]["trades"] >= 2 and validation[name]["trades"] >= 2
        and training[name]["net_aud"] > 0 and validation[name]["net_aud"] > 0
    ]
    return max(eligible, key=lambda name: min(
        training[name]["net_aud"], validation[name]["net_aud"]
    )) if eligible else "HOLD"


def coverage(fx, bars, start, end, delay_days=0):
    if end <= start:
        return 0.0
    valid = sum(fx_volatility_at(fx, bars[i][0], delay_days=delay_days) is not None
                for i in range(start, end))
    return round(valid / (end - start), 6)


def aggregate(rows):
    totals = {field: round(sum(row[field] for row in rows), 6) for field in FIELDS}
    totals["return_pct_on_reset_wallets"] = round(
        totals["net_aud"] / (CASH * len(rows)) * 100, 6
    )
    totals["worst_fold_drawdown_pct"] = min(row["max_drawdown_pct"] for row in rows)
    totals["wins"] = int(totals["wins"])
    totals["losses"] = int(totals["losses"])
    return totals


def evaluate(bars, market_provenance, fx, fx_provenance, news_path):
    news_events, news_sha, news_counts = load_verified_news(news_path)
    folds = []
    for left, right in segments(bars, 1000):
        local = bars[left:right]
        n = len(local)
        train_end, val_start, val_end, test_start = boundaries_v42(n)
        thresholds = calibration_thresholds(local, fx, train_end)
        train_start = thresholds["calibration_end_index_exclusive"] + CALIBRATION_EMBARGO
        if train_start >= train_end:
            raise ValueError("Calibration plus embargo consumes training window")
        train = {
            name: replay_candidate(local, train_start, train_end, fx, name, thresholds)
            for name in CANDIDATES
        }
        validation = {
            name: replay_candidate(local, val_start, val_end, fx, name, thresholds)
            for name in CANDIDATES
        }
        selected = select(train, validation)
        tests = {
            name: replay_candidate(local, test_start, n, fx, name, thresholds, audit=True)
            for name in CANDIDATES
        }
        for result in tests.values():
            result["missed_opportunities_after_veto"] = missed_opportunities(
                local, result.get("gate_veto_audit", []), n
            )
        baselines = {
            name: simulate(local, test_start, n, name)
            for name in ("sma", "momentum", "rsi", "breakout", "regime", "trend_breakout")
        }
        sensitivity = {}
        for name in CANDIDATES:
            sensitivity[name] = {
                "A50_current_cost": replay_candidate(
                    local, test_start, n, fx, name, thresholds,
                    max_entry_debit=50.0
                )["net_aud"],
                "A100_half_cost": replay_candidate(
                    local, test_start, n, fx, name, thresholds, cost_mult=0.5
                )["net_aud"],
                "A100_current_cost": tests[name]["net_aud"],
                "A100_double_cost": replay_candidate(
                    local, test_start, n, fx, name, thresholds, cost_mult=2.0
                )["net_aud"],
            }
        folds.append({
            "segment_bars": n,
            "train_start_after_calibration_utc": datetime.fromtimestamp(
                local[train_start][0], timezone.utc).isoformat(),
            "train_end_utc": datetime.fromtimestamp(local[train_end-1][0], timezone.utc).isoformat(),
            "validation_start_utc": datetime.fromtimestamp(local[val_start][0], timezone.utc).isoformat(),
            "validation_end_utc": datetime.fromtimestamp(local[val_end-1][0], timezone.utc).isoformat(),
            "test_start_utc": datetime.fromtimestamp(local[test_start][0], timezone.utc).isoformat(),
            "test_end_utc": datetime.fromtimestamp(local[-1][0], timezone.utc).isoformat(),
            "embargo_bars": 84,
            "calibration": thresholds,
            "fx_coverage": {
                "train": coverage(fx, local, train_start, train_end),
                "validation": coverage(fx, local, val_start, val_end),
                "test": coverage(fx, local, test_start, n),
            },
            "train": train,
            "validation": validation,
            "selected_using_train_validation_only": selected,
            "selected_test_net_aud": 0.0 if selected == "HOLD" else tests[selected]["net_aud"],
            "test": tests,
            "price_only_baselines": baselines,
            "buyhold_aud100": buyhold_audit(local, test_start, n, max_entry_debit=100.0),
            "sensitivity": sensitivity,
        })
    if not folds:
        raise ValueError("No eligible gap-free Kraken segment")
    totals = {name: aggregate([fold["test"][name] for fold in folds])
              for name in CANDIDATES}
    baseline_totals = {name: aggregate([fold["price_only_baselines"][name]
                                        for fold in folds])
                       for name in folds[0]["price_only_baselines"]}
    buyhold_rows = [fold["buyhold_aud100"] for fold in folds]
    buyhold_total = aggregate(buyhold_rows)
    selected_net = round(sum(fold["selected_test_net_aud"] for fold in folds), 6)
    return {
        "mode": "V44_PAPER_ONLY_PRIOR_INSPECTED_EXPLORATORY",
        "hypothesis": "20-observation annualized AUD/USD realized-volatility gate on H80/300 BUYs",
        "market": market_provenance,
        "fx": fx_provenance,
        "fx_feature": {
            "source": "RBA F11.1 and 2018-2022 historical XLS",
            "quote": "USD per AUD; AUD/USD",
            "window_observations": FX_WINDOW,
            "annualization": "sqrt(252) from daily log-return population standard deviation",
            "availability": "17:00 Australia/Sydney +24h ASSUMED; no historical revision/crawl vintage",
            "staleness_limit_days": 10,
            "thresholds": "75th and 90th percentile calibrated on first 25% of training only, frozen thereafter",
            "negative_control": "same q75 threshold applied to FX volatility shifted 7 days older",
        },
        "fees_each_side_bps": COSTS,
        "starting_cash_aud": CASH,
        "max_inclusive_entry_debit_aud": CAP,
        "cash_fraction_cap": 0.10,
        "strict_asof_news": {
            "verified_capture_rows": len(news_events),
            "corpus_sha256": news_sha,
            "classification_counts": news_counts,
            "events_in_strategy_replay": 0,
            "reason": "No strict as-of news feature was injected; current corpus has no independently proven event available before these prior-inspected test decisions",
        },
        "folds": folds,
        "aggregate_test": totals,
        "aggregate_price_only_baselines": baseline_totals,
        "aggregate_buyhold_aud100": buyhold_total,
        "aggregate_selected_test_net_aud": selected_net,
        "selected_policy": "HOLD" if selected_net == 0 else "TRAIN_VALIDATION_SELECTED_CANDIDATE",
        "promotion": "REJECTED_PENDING_UNTOUCHED_OOS_AND_VERIFIED_FX_VINTAGES",
        "limitations": [
            "All historical Kraken segments were previously inspected; not untouched OOS",
            "RBA FX snapshot is retrospective; assumed availability is not proof of historical vintage",
            "Current official 80bps taker plus modeled 5bps half-spread and 5bps slippage per side",
            "Hypothetical next-open fills; no order-book queue, depth, partial-fill or latency model",
            "Three independently reset A$1000 wallets; summed AUD is not compounded",
            "No historical news event passed strict as-of proof for these test windows",
        ],
    }


def load_bars(path):
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    if doc.get("schema") != "v41_kraken_ohlcvt_1":
        raise ValueError("Unknown verified Kraken bar schema")
    bars = doc.get("bars")
    if not isinstance(bars, list) or not bars:
        raise ValueError("Missing Kraken bars")
    previous = None
    for row in bars:
        if not isinstance(row, list) or len(row) < 6:
            raise ValueError("Invalid OHLCVT row")
        ts = int(row[0])
        if previous is not None and ts <= previous:
            raise ValueError("Bars not strictly chronological")
        if any(not math.isfinite(float(x)) for x in row[1:6]):
            raise ValueError("Non-finite OHLCV field")
        if float(row[1]) <= 0 or float(row[4]) <= 0:
            raise ValueError("Non-positive OHLC price")
        previous = ts
    return bars, doc.get("market_provenance", {})


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--bars-json", default="audit/v41-market-bars.json")
    parser.add_argument("--news", default="data/historical_news_sample_v38.jsonl")
    parser.add_argument("--output", default="audit/v44-fx-volatility.json")
    args = parser.parse_args(argv)
    bars, market_provenance = load_bars(args.bars_json)
    fx, fx_provenance = fetch_fx()
    report = evaluate(bars, market_provenance, fx, fx_provenance, args.news)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(report, indent=2, allow_nan=False) + "\n").encode()
    out.write_bytes(raw)
    print(json.dumps({
        "sha256": hashlib.sha256(raw).hexdigest(),
        "segments": len(report["folds"]),
        "selected": [f["selected_using_train_validation_only"] for f in report["folds"]],
        "selected_net": report["aggregate_selected_test_net_aud"],
        "buyhold_net": report["aggregate_buyhold_aud100"]["net_aud"],
        "candidate_net": {k: v["net_aud"] for k, v in report["aggregate_test"].items()},
        "baseline_net": {k: v["net_aud"] for k, v in report["aggregate_price_only_baselines"].items()},
    }, sort_keys=True))


if __name__ == "__main__":
    main()

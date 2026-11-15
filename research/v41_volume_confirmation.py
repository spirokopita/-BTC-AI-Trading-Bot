"""V41 PAPER ONLY: completed-bar participation confirmation ablation.

A fixed, predeclared volume/close-location filter is tested on official Kraken
BTC/AUD OHLCVT. It sees only the prior completed candle and its trailing
20-bar reference. News controls use independently WARC-captured versions only.
All historical archive periods were previously inspected: EXPLORATORY, not
untouched OOS. No Android promotion or live execution.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import statistics
from datetime import datetime, timezone
from pathlib import Path

from research.v33_cross_regime import archive, boundaries
from research.v32_segments import segments
from research.v31_hysteresis import WARMUP, replay
from research.v29_point_in_time import simulate, buyhold
from research.v48_news_proof_gate import classify as classify_news

LOOKBACK = 20
PLACEBO_DELAY_BARS = 42
NEWS_WINDOW_SECONDS = 7 * 86400
VOLUME_THRESHOLD = 1.20
CLOSE_LOCATION_THRESHOLD = 0.65
CANDIDATES = (
    "h80_base",
    "h80_vol_confirm",
    "h80_volume_only",
    "h80_close_only",
    "h80_vol_placebo7d",
    "h50_vol_confirm",
    "h80_news_attention",
    "h80_news_delayed7d",
)
SELECTABLE = ("h80_base", "h80_vol_confirm", "h50_vol_confirm")
BASE_STRATEGY = {
    "h80_base": "h80_300",
    "h80_vol_confirm": "h80_300",
    "h80_volume_only": "h80_300",
    "h80_close_only": "h80_300",
    "h80_vol_placebo7d": "h80_300",
    "h50_vol_confirm": "h50_200",
    "h80_news_attention": "h80_300",
    "h80_news_delayed7d": "h80_300",
}
FIELDS = ("trades", "wins", "losses", "gross_aud", "fees_aud",
          "spread_aud", "slippage_aud", "net_aud")


def _epoch(value):
    if not isinstance(value, str) or not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Naive timestamp rejected")
    return parsed.astimezone(timezone.utc).timestamp()


def load_verified_news(path="data/historical_news_sample_v38.jsonl"):
    """Apply V48 exact-version proof; legacy WARC digests are not assumed SHA256."""
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError("Cumulative provenance corpus missing")
    raw = source.read_bytes()
    events = []
    rejected = collections.Counter()
    now = datetime.now(timezone.utc).timestamp()
    for line in raw.decode("utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        proof_row = dict(row)
        # A Common Crawl index digest is not silently re-labelled as article SHA256.
        if (row.get("availability_confidence") == "verified_crawl"
                and row.get("capture_source") == "common_crawl"
                and row.get("first_verified_capture_at_utc")):
            proof_row["capture_type"] = "independent_warc"
            proof_row["verified_capture_at_utc"] = row["first_verified_capture_at_utc"]
            proof_row["content_sha256"] = row.get("content_sha256")
            proof_row["version_capture_sha256"] = row.get("content_sha256")
            proof_row["retrieved_at_utc"] = row.get("retrieved_at_utc")
        proof = classify_news(proof_row, now, latency_seconds=3600)
        rejected[proof["reason"]] += 1
        if proof["eligible"]:
            events.append(proof_row)
    events.sort(key=lambda x: (
        x.get("verified_capture_at_utc", ""),
        x.get("url", x.get("canonical_url", "")),
        x.get("content_sha256", "")))
    return events, hashlib.sha256(raw).hexdigest(), dict(sorted(rejected.items()))

def volume_feature(bars, decision_index, lookback=LOOKBACK, delay_bars=0):
    """At OPEN i, inspect candle i-1-delay and only the lookback candles before it."""
    if lookback < 5 or delay_bars < 0 or decision_index < 1:
        raise ValueError("Invalid feature window")
    target = decision_index - 1 - delay_bars
    if target < lookback:
        return None
    candle = bars[target]
    if len(candle) < 6:
        raise ValueError("OHLCVT volume field missing")
    volumes = [float(bars[k][5]) for k in range(target - lookback, target)]
    values = volumes + [float(candle[5])]
    if not all(math.isfinite(x) and x >= 0 for x in values):
        raise ValueError("Invalid volume observation")
    median_volume = statistics.median(volumes)
    high, low, close = map(float, (candle[2], candle[3], candle[4]))
    if median_volume <= 0 or high <= low:
        return None
    return {
        "signal_candle_ts": candle[0],
        "reference_end_ts": bars[target - 1][0],
        "volume_ratio": float(candle[5]) / median_volume,
        "close_location": (close - low) / (high - low),
        "lookback": lookback,
        "delay_bars": delay_bars,
    }


def news_active(events, decision_ts, delay_seconds=0):
    if delay_seconds not in (0, 7 * 86400):
        raise ValueError("Unregistered news delay")
    cutoff = decision_ts - delay_seconds
    for event in events:
        proof = classify_news(event, cutoff, latency_seconds=3600)
        if (proof["eligible"]
                and 0 <= cutoff - proof["available_at_utc"] < NEWS_WINDOW_SECONDS):
            return True
    return False

def _volume_veto(feature, name):
    if name in ("h80_base", "h80_news_attention", "h80_news_delayed7d"):
        return False
    if feature is None:
        return True
    if name in ("h80_vol_confirm", "h50_vol_confirm", "h80_vol_placebo7d"):
        return (feature["volume_ratio"] < VOLUME_THRESHOLD
                or feature["close_location"] < CLOSE_LOCATION_THRESHOLD)
    if name == "h80_volume_only":
        return feature["volume_ratio"] < VOLUME_THRESHOLD
    if name == "h80_close_only":
        return feature["close_location"] < CLOSE_LOCATION_THRESHOLD
    raise ValueError("Unknown volume candidate")


def select(training, validation):
    """Only training and validation results may select a deployable research candidate."""
    eligible = [
        name for name in SELECTABLE
        if training[name]["trades"] >= 2
        and validation[name]["trades"] >= 2
        and training[name]["net_aud"] > 0
        and validation[name]["net_aud"] > 0
    ]
    return max(eligible, key=lambda name: min(
        training[name]["net_aud"], validation[name]["net_aud"])) if eligible else "HOLD"


def replay_variant(bars, start, end, name, events=(), *, cost_mult=1.0,
                   max_entry_debit=100.0, audit=False):
    if name not in CANDIDATES:
        raise ValueError("Unknown V41 candidate")
    if not 0 < max_entry_debit <= 100:
        raise ValueError("Paper entry cap must be in (0, A$100]")
    if any(len(row) < 6 for row in bars):
        raise ValueError("OHLCVT volume field missing")
    index = {row[0]: i for i, row in enumerate(bars)}
    if len(index) != len(bars):
        raise ValueError("Duplicate candle timestamps")
    counts = {"vetoed_candidate_bars": 0, "missing_feature_bars": 0,
              "news_vetoed_candidate_bars": 0}
    vetoed_indices = []

    def veto(timestamp):
        i = index[timestamp]
        rejected = False
        if name in ("h80_news_attention", "h80_news_delayed7d"):
            delay = 7 * 86400 if name == "h80_news_delayed7d" else 0
            rejected = news_active(events, timestamp, delay)
            if rejected:
                counts["news_vetoed_candidate_bars"] += 1
        elif name != "h80_base":
            delay = PLACEBO_DELAY_BARS if name == "h80_vol_placebo7d" else 0
            feature = volume_feature(bars, i, delay_bars=delay)
            if feature is None:
                counts["missing_feature_bars"] += 1
            rejected = _volume_veto(feature, name)
        if rejected:
            counts["vetoed_candidate_bars"] += 1
            vetoed_indices.append(i)
        return rejected

    result = replay(
        bars, start, end, BASE_STRATEGY[name], events=(),
        cost_mult=cost_mult, audit=audit,
        entry_veto=None if name == "h80_base" else veto,
        max_entry_debit=max_entry_debit,
    )
    result["strategy"] = name
    result.update(counts)
    # Ex-post missed-opportunity diagnostics; never fed back into decisions.
    forward = []
    for i in vetoed_indices:
        j = i + 6
        if j < end:
            forward.append(bars[j][4] / bars[i][1] - 1.0)
    result["vetoed_24h_observations"] = len(forward)
    result["vetoed_positive_24h_count"] = sum(x > 0 for x in forward)
    result["vetoed_negative_24h_count"] = sum(x <= 0 for x in forward)
    result["vetoed_mean_24h_return_pct"] = (
        round(statistics.mean(forward) * 100, 6) if forward else None)
    if audit:
        for trade in result["trade_audit"]:
            if trade["entry_debit_aud"] > min(
                    max_entry_debit, .1 * trade["cash_before_entry_aud"]) + 1e-8:
                raise AssertionError("Inclusive A$100/10% paper debit cap")
            if not math.isclose(
                    trade["net"], trade["gross"] - trade["fees"]
                    - trade["spread"] - trade["slippage"], abs_tol=1e-7):
                raise AssertionError("Gross/cost/NET mismatch")
        result.pop("decision_audit", None)
    return result


def evaluate(bars, market_provenance, news_events, news_sha256, news_rejections=None):
    slices = segments(bars, 1000)
    folds = []
    for left, right in slices:
        local = bars[left:right]
        n = len(local)
        train_end, val_start, val_end, test_start = boundaries(n)
        training = {name: replay_variant(local, WARMUP, train_end, name)
                    for name in SELECTABLE}
        validation = {name: replay_variant(local, val_start, val_end, name)
                      for name in SELECTABLE}
        chosen = select(training, validation)
        tests = {name: replay_variant(local, test_start, n, name,
                    news_events, audit=True) for name in CANDIDATES}
        baselines = {name: simulate(local, test_start, n, name)
                     for name in ("sma", "momentum", "rsi", "breakout",
                                  "regime", "trend_breakout")}
        sensitivity = {}
        for name in ("h80_base", "h80_vol_confirm"):
            sensitivity[name] = {
                "A50": replay_variant(local, test_start, n, name,
                    news_events, max_entry_debit=50.0)["net_aud"],
                "A100": tests[name]["net_aud"],
                "half_cost": replay_variant(local, test_start, n, name,
                    news_events, cost_mult=.5)["net_aud"],
                "current_cost": tests[name]["net_aud"],
                "double_cost": replay_variant(local, test_start, n, name,
                    news_events, cost_mult=2.0)["net_aud"],
            }
        selected_net = tests[chosen]["net_aud"] if chosen != "HOLD" else 0.0
        folds.append({
            "segment_bars": n,
            "first_utc": datetime.fromtimestamp(local[0][0], timezone.utc).isoformat(),
            "last_utc": datetime.fromtimestamp(local[-1][0], timezone.utc).isoformat(),
            "train_end_utc": datetime.fromtimestamp(local[train_end-1][0], timezone.utc).isoformat(),
            "validation_start_utc": datetime.fromtimestamp(local[val_start][0], timezone.utc).isoformat(),
            "validation_end_utc": datetime.fromtimestamp(local[val_end-1][0], timezone.utc).isoformat(),
            "test_start_utc": datetime.fromtimestamp(local[test_start][0], timezone.utc).isoformat(),
            "test_end_utc": datetime.fromtimestamp(local[-1][0], timezone.utc).isoformat(),
            "embargo_bars": 20,
            "training": training,
            "validation": validation,
            "selected_using_train_validation_only": chosen,
            "selected_test_net_aud": round(selected_net, 6),
            "test": tests,
            "price_baselines": baselines,
            "buyhold_aud100_net": buyhold(local, test_start, n),
            "sensitivity": sensitivity,
            "strict_news_available_in_test": sum(
                1 for e in news_events
                if (lambda p: p["eligible"] and
                    local[test_start][0] <= p["available_at_utc"] <= local[-1][0])(
                        classify_news(e, local[-1][0], latency_seconds=3600))),
        })
    totals = {
        name: {field: round(sum(f["test"][name][field] for f in folds), 6)
               for field in FIELDS}
        for name in CANDIDATES
    }
    return {
        "mode": "V41_PAPER_ONLY_PRIOR_INSPECTED_EXPLORATORY",
        "market": market_provenance,
        "strict_verified_news": {
            "corpus_sha256": news_sha256,
            "verified_capture_rows": len(news_events),
            "availability_basis": "V48 exact content SHA256 must match the independently captured version; 1h conservative latency",
            "rejected_by_reason": news_rejections or {},
            "historically_eligible_events_in_test_windows": sum(
                f["strict_news_available_in_test"] for f in folds),
            "sentiment": "NOT AVAILABLE / NOT INFERRED FROM TITLES",
        },
        "parameters_predeclared": {
            "lookback_bars": LOOKBACK,
            "volume_ratio_min": VOLUME_THRESHOLD,
            "close_location_min": CLOSE_LOCATION_THRESHOLD,
            "placebo_delay_bars": PLACEBO_DELAY_BARS,
            "news_window_seconds": NEWS_WINDOW_SECONDS,
        },
        "fees_each_side_bps": {"taker": 80, "half_spread": 5, "slippage": 5},
        "starting_cash_aud": 1000.0,
        "max_inclusive_entry_debit_aud": 100.0,
        "cash_fraction_cap": 0.10,
        "folds": folds,
        "aggregate_independent_reset_accounts": totals,
        "aggregate_price_baselines_net_aud": {
            name: round(sum(f["price_baselines"][name]["net_aud"] for f in folds), 6)
            for name in folds[0]["price_baselines"]
        },
        "aggregate_selected_test_net_aud": round(
            sum(f["selected_test_net_aud"] for f in folds), 6),
        "aggregate_buyhold_aud100_net": round(
            sum(f["buyhold_aud100_net"] for f in folds), 6),
        "worst_fold_drawdown_pct": {
            name: min(f["test"][name]["max_drawdown_pct"] for f in folds)
            for name in CANDIDATES
        },
        "research_policy": "HOLD",
        "android_policy": "HOLD",
        "promotion": "REJECTED: previously inspected history, no untouched OOS and no verified execution parity",
        "limitations": [
            "All Kraken archive periods were previously inspected; NOT untouched OOS",
            "Current 80bps taker and modeled spread/slippage applied to historical prices",
            "OHLCVT next-open fills are hypothetical; no order-book queue or intrabar fill model",
            "News corpus has no verified sentiment labels; only WARC-captured attention veto tested",
            "One capture row or zero eligible events cannot establish news predictiveness",
            "Independent A$1000 reset accounts per gap-free segment; aggregates are not compounded",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="audit/v41-volume-confirmation.json")
    parser.add_argument("--bars-json-output", default="audit/v41-market-bars.json")
    parser.add_argument("--news", default="data/historical_news_sample_v38.jsonl")
    args = parser.parse_args(argv)
    bars, provenance = archive()
    events, news_sha, news_rejections = load_verified_news(args.news)
    report = evaluate(bars, provenance, events, news_sha, news_rejections)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(report, indent=2, allow_nan=False) + "\n").encode()
    out.write_bytes(raw)
    bars_doc = {
        "schema": "v41_kraken_ohlcvt_1",
        "market_provenance": provenance,
        "bars": bars,
    }
    bars_path = Path(args.bars_json_output)
    bars_path.parent.mkdir(parents=True, exist_ok=True)
    bars_path.write_text(json.dumps(bars_doc, separators=(",", ":"), allow_nan=False) + "\n")
    print(json.dumps({
        "report_sha256": hashlib.sha256(raw).hexdigest(),
        "segments": len(report["folds"]),
        "strict_news_rows": len(events),
        "selected": [f["selected_using_train_validation_only"] for f in report["folds"]],
        "selected_test_net_aud": report["aggregate_selected_test_net_aud"],
        "buyhold_net_aud": report["aggregate_buyhold_aud100_net"],
        "candidates": report["aggregate_independent_reset_accounts"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()

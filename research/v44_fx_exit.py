"""V44 PAPER ONLY: AUD/USD decomposition as a trend-masking exit diagnostic.

A forced exit is tested only when the BTC/AUD 30-day return remains positive
while the implied BTC/USD component is weak. RBA FX is a retrospective
snapshot with assumed 17:00 Sydney +24h availability, not a verified vintage.
All Kraken periods have been inspected before; results are exploratory only.
Historical news variants use only V48 exact-version proof and a seven-day
shifted placebo. The new V44 RBA/CoinDesk snapshots are prospective only and
are not fed into this historical replay. No Android promotion is allowed.
Live execution remains disabled.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

from research.v29_point_in_time import (
    CASH, CAP, FEE, SPREAD, SLIPPAGE, execution, simulate, buyhold,
)
from research.v31_hysteresis import WARMUP, replay
from research.v32_segments import segments
from research.v33_cross_regime import archive, boundaries
from research.v39_rba_fx_asof import fetch_fx
from research.v40_fx_decomposition import decomposition
from research.v42_volatility_exit import boundaries_v42

CANDIDATES = (
    "h80_base",
    "h80_fx_mask_exit_0",
    "h80_fx_mask_exit_m1",
    "h80_fx_mask_exit_placebo7d",
    "h80_news_negative_veto",
    "h80_news_negative_veto_placebo7d",
    "h50_base",
)
SELECTABLE = (
    "h80_base",
    "h80_fx_mask_exit_0",
    "h80_fx_mask_exit_m1",
    "h80_news_negative_veto",
    "h50_base",
)
BASE_STRATEGY = {
    "h80_base": "h80_300",
    "h80_fx_mask_exit_0": "h80_300",
    "h80_fx_mask_exit_m1": "h80_300",
    "h80_fx_mask_exit_placebo7d": "h80_300",
    "h80_news_negative_veto": "h80_300",
    "h80_news_negative_veto_placebo7d": "h80_300",
    "h50_base": "h50_200",
}
WEAK_USD_THRESHOLD = {
    "h80_fx_mask_exit_0": 0.0,
    "h80_fx_mask_exit_m1": math.log(0.99),
    "h80_fx_mask_exit_placebo7d": 0.0,
}
BTC_AUD_MIN_RETURN = math.log(1.02)
NEWS_WINDOW_SECONDS = 7 * 86400
NEWS_DELAY_SECONDS = 7 * 86400
COSTS_BPS_EACH_SIDE = {"taker": 80, "half_spread": 5, "slippage": 5}
FIELDS = ("trades", "wins", "losses", "gross_aud", "fees_aud",
          "spread_aud", "slippage_aud", "net_aud")


def make_exit_veto(bars, fx, candidate, audit_rows=None):
    """Return a HOLD-to-SELL callback using only prior completed candles.

    The feature is the V40 30-day log decomposition. A position is exited
    only if BTC/AUD is still up at least 2% while the implied BTC/USD leg is
    flat/negative (or <= -1% for the stricter candidate). The placebo shifts
    both market and FX inputs seven days backward. Missing/stale FX never
    forces an exit.
    """
    if candidate not in CANDIDATES:
        raise ValueError("Unknown V44 candidate")
    if candidate not in WEAK_USD_THRESHOLD:
        return None, {"feature_observations": 0, "missing_fx": 0,
                      "forced_exits": 0}
    threshold = WEAK_USD_THRESHOLD[candidate]
    delay = 7 if candidate.endswith("placebo7d") else 0
    index_by_ts = {int(row[0]): i for i, row in enumerate(bars)}
    if len(index_by_ts) != len(bars):
        raise ValueError("Duplicate BTC/AUD candle timestamp")
    counts = {"feature_observations": 0, "missing_fx": 0,
              "forced_exits": 0}

    def veto(decision_ts):
        index = index_by_ts.get(int(decision_ts))
        if index is None:
            raise ValueError("Exit decision timestamp absent from market bars")
        feature = decomposition(bars, index, fx, delay_days=delay)
        if feature is None:
            counts["missing_fx"] += 1
            return False
        counts["feature_observations"] += 1
        triggered = (
            feature["btc_aud_log30"] >= BTC_AUD_MIN_RETURN
            and feature["implied_btc_usd_log30"] <= threshold
        )
        if triggered:
            counts["forced_exits"] += 1
            if audit_rows is not None:
                audit_rows.append({
                    "decision_index": index,
                    "decision_ts": int(decision_ts),
                    "latest_completed_candle_ts": feature["latest_completed_candle_ts"],
                    "btc_aud_log30": round(feature["btc_aud_log30"], 9),
                    "aud_usd_log30": round(feature["aud_usd_log30"], 9),
                    "implied_btc_usd_log30": round(
                        feature["implied_btc_usd_log30"], 9),
                    "latest_fx_assumed_available_ts":
                        feature["latest_fx_assumed_available_ts"],
                    "prior_fx_assumed_available_ts":
                        feature["prior_fx_assumed_available_ts"],
                    "delay_days": delay,
                    "decision": "FORCED_SELL_NEXT_OPEN",
                })
        return triggered

    return veto, counts


def make_news_entry_veto(events, candidate, bars=None, audit_rows=None):
    """Strict V48 negative-news entry veto and a seven-day shifted placebo."""
    if candidate not in (
            "h80_news_negative_veto",
            "h80_news_negative_veto_placebo7d"):
        return None, {"verified_event_rows": 0, "vetoed_candidate_bars": 0}
    from research.v48_news_proof_gate import classify as classify_news
    delay = (NEWS_DELAY_SECONDS
             if candidate.endswith("placebo7d") else 0)
    counts = {"verified_event_rows": len(events),
              "vetoed_candidate_bars": 0}
    index_by_ts = ({int(row[0]): i for i, row in enumerate(bars)}
                   if bars is not None else {})

    def veto(decision_ts):
        cutoff = float(decision_ts) - delay
        for event in events:
            proof = classify_news(event, cutoff, latency_seconds=3600)
            if not proof["eligible"]:
                continue
            try:
                negative = float(event.get("sentiment", 0)) < 0
            except (TypeError, ValueError):
                negative = False
            if (negative and proof["available_at_utc"] <= cutoff
                    and cutoff - proof["available_at_utc"] < NEWS_WINDOW_SECONDS):
                counts["vetoed_candidate_bars"] += 1
                if audit_rows is not None:
                    index = index_by_ts.get(int(decision_ts))
                    if index is None:
                        raise ValueError("News veto timestamp absent from bars")
                    audit_rows.append({
                        "decision_index": index,
                        "decision_ts": int(decision_ts),
                        "event_id": event.get("id") or event.get("url"),
                        "available_at_utc": proof["available_at_utc"],
                        "sentiment": event.get("sentiment"),
                        "decision": "VETOED_BUY",
                    })
                return True
        return False

    return veto, counts


def replay_variant(bars, start, end, candidate, fx, *, events=(),
                   cost_mult=1.0, max_entry_debit=CAP, audit=False):
    if candidate not in CANDIDATES:
        raise ValueError("Unknown V44 candidate")
    if not 0 < max_entry_debit <= CAP:
        raise ValueError("Paper entry debit must be in (0, A$100]")
    if not 0.5 <= cost_mult <= 2.0:
        raise ValueError("Cost multiplier outside registered sensitivity")
    if start < WARMUP or end > len(bars) or end - start < 3:
        raise ValueError("Invalid V44 chronological replay interval")
    forced_rows = [] if audit else None
    veto, counts = make_exit_veto(
        bars, fx, candidate, audit_rows=forced_rows,
    )
    news_rows = [] if audit else None
    entry_veto, news_counts = make_news_entry_veto(
        events, candidate, bars=bars, audit_rows=news_rows,
    )
    result = replay(
        bars, start, end, BASE_STRATEGY[candidate], events=(),
        cost_mult=cost_mult, audit=audit,
        max_entry_debit=max_entry_debit,
        entry_veto=entry_veto, exit_veto=veto,
    )
    result["candidate"] = candidate
    result["feature_counts"] = counts
    result["news_counts"] = news_counts
    result["news_veto_audit"] = news_rows or []
    result["forced_exit_audit"] = forced_rows or []
    if audit:
        result.pop("decision_audit", None)
        for trade in result["trade_audit"]:
            if trade["entry_debit_aud"] > min(
                    max_entry_debit,
                    0.10 * trade["cash_before_entry_aud"]) + 1e-8:
                raise AssertionError("Inclusive A$100/10% cash cap")
            if not math.isclose(
                    trade["net"],
                    trade["gross"] - trade["fees"]
                    - trade["spread"] - trade["slippage"],
                    abs_tol=1e-7):
                raise AssertionError("Gross-cost-NET mismatch")
    return result


def missed_opportunities(bars, forced_rows, end):
    """Forward prices after forced exits; descriptive only, never trade P&L."""
    report = {}
    for horizon, label in ((6, "24h"), (42, "7d")):
        values = [
            float(bars[row["decision_index"] + horizon][4])
            / float(bars[row["decision_index"]][1]) - 1.0
            for row in forced_rows
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
            "interpretation": "descriptive forward price only; not additive NET P&L",
        }
    return report


def select(training, validation):
    """Train/validation only; require >=2 trades and positive NET in both."""
    eligible = [
        name for name in SELECTABLE
        if training[name]["trades"] >= 2
        and validation[name]["trades"] >= 2
        and training[name]["net_aud"] > 0
        and validation[name]["net_aud"] > 0
    ]
    if not eligible:
        return "HOLD"
    return max(eligible, key=lambda name: min(
        training[name]["net_aud"], validation[name]["net_aud"]))


def aggregate(results):
    totals = {field: round(sum(row[field] for row in results), 6)
              for field in FIELDS}
    totals["return_pct"] = round(
        totals["net_aud"] / (CASH * len(results)) * 100, 6)
    totals["worst_fold_drawdown_pct"] = min(
        row["max_drawdown_pct"] for row in results)
    return totals


def buyhold_detail(bars, start, end):
    """A$100 buy-and-hold with the same per-side taker/spread/slippage model."""
    entry_mid = float(bars[start][1])
    exit_mid = float(bars[end - 1][1])
    quantity = CAP / (entry_mid * (1 + SPREAD + SLIPPAGE) * (1 + FEE))
    entry = execution(entry_mid, quantity, "buy", 1.0)
    exit_fill = execution(exit_mid, quantity, "sell", 1.0)
    gross = (exit_mid - entry_mid) * quantity
    fees = entry["fee"] + exit_fill["fee"]
    spread = entry["spread"] + exit_fill["spread"]
    slippage = entry["slippage"] + exit_fill["slippage"]
    net = gross - fees - spread - slippage
    if not math.isclose(net, buyhold(bars, start, end), abs_tol=1e-5):
        raise AssertionError("Detailed buy-and-hold does not reconcile to V29")
    cash_after_entry = CASH - entry["notional"] - entry["fee"]
    peak = CASH
    drawdown = 0.0
    for row in bars[start:end]:
        equity = cash_after_entry + quantity * float(row[4])
        peak = max(peak, equity)
        drawdown = min(drawdown, equity / peak - 1.0)
    return {
        "trades": 1,
        "wins": int(net > 0),
        "losses": int(net <= 0),
        "gross_aud": round(gross, 6),
        "fees_aud": round(fees, 6),
        "spread_aud": round(spread, 6),
        "slippage_aud": round(slippage, 6),
        "net_aud": round(net, 6),
        "return_pct": round(net / CASH * 100, 6),
        "max_drawdown_pct": round(drawdown * 100, 6),
        "drawdown_basis": "mark-to-market close; before hypothetical exit costs",
    }


def bars_from_json(path):
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    if doc.get("schema") != "v41_kraken_ohlcvt_1":
        raise ValueError("Unknown official Kraken bar schema")
    bars = doc.get("bars")
    if not isinstance(bars, list) or not bars:
        raise ValueError("Missing official Kraken BTC/AUD bars")
    return bars


def evaluate(bars, fx, market_provenance, fx_provenance,
            events=(), news_provenance=None):
    folds = []
    for left, right in segments(bars, 1000):
        local = bars[left:right]
        n = len(local)
        train_end, val_start, val_end, test_start = boundaries_v42(n)
        if train_end <= WARMUP:
            raise ValueError("Insufficient train history after warm-up")
        training = {
            name: replay_variant(local, WARMUP, train_end, name, fx,
                                  events=events)
            for name in SELECTABLE
        }
        validation = {
            name: replay_variant(local, val_start, val_end, name, fx,
                                  events=events)
            for name in SELECTABLE
        }
        chosen = select(training, validation)
        tests = {
            name: replay_variant(local, test_start, n, name, fx,
                                  events=events, audit=True)
            for name in CANDIDATES
        }
        baselines = {
            name: simulate(local, test_start, n, name)
            for name in ("sma", "momentum", "rsi", "breakout",
                         "regime", "trend_breakout")
        }
        sensitivity = {
            name: {
                "A50_current_cost": replay_variant(
                    local, test_start, n, name, fx, events=events,
                    max_entry_debit=50.0,
                )["net_aud"],
                "A100_half_cost": replay_variant(
                    local, test_start, n, name, fx, events=events,
                    cost_mult=0.5,
                )["net_aud"],
                "A100_current_cost": tests[name]["net_aud"],
                "A100_double_cost": replay_variant(
                    local, test_start, n, name, fx, events=events,
                    cost_mult=2.0,
                )["net_aud"],
            }
            for name in CANDIDATES
        }
        test_first = int(local[test_start][0])
        test_last = int(local[-1][0])
        folds.append({
            "segment_bars": n,
            "first_utc": datetime.fromtimestamp(
                local[0][0], timezone.utc).isoformat(),
            "last_utc": datetime.fromtimestamp(
                local[-1][0], timezone.utc).isoformat(),
            "train_end_utc": datetime.fromtimestamp(
                local[train_end - 1][0], timezone.utc).isoformat(),
            "validation_start_utc": datetime.fromtimestamp(
                local[val_start][0], timezone.utc).isoformat(),
            "validation_end_utc": datetime.fromtimestamp(
                local[val_end - 1][0], timezone.utc).isoformat(),
            "test_start_utc": datetime.fromtimestamp(
                test_first, timezone.utc).isoformat(),
            "test_end_utc": datetime.fromtimestamp(
                test_last, timezone.utc).isoformat(),
            "embargo_bars": 84,
            "training": training,
            "validation": validation,
            "selected_using_train_validation_only": chosen,
            "selected_test_net_aud": (
                tests[chosen]["net_aud"] if chosen != "HOLD" else 0.0),
            "test": tests,
            "price_baselines": baselines,
            "buyhold_aud100": buyhold_detail(local, test_start, n),
            "fee_sensitivity": sensitivity,
            "missed_opportunities": {
                name: {
                    "forced_exit": missed_opportunities(
                        local, tests[name]["forced_exit_audit"], n),
                    "news_veto": missed_opportunities(
                        local, tests[name]["news_veto_audit"], n),
                }
                for name in CANDIDATES
            },
        })
    if not folds:
        raise ValueError("No eligible gap-free >=1000-bar Kraken segment")
    totals = {
        name: aggregate([fold["test"][name] for fold in folds])
        for name in CANDIDATES
    }
    baseline_totals = {
        name: aggregate([fold["price_baselines"][name] for fold in folds])
        for name in folds[0]["price_baselines"]
    }
    buyhold_totals = aggregate([fold["buyhold_aud100"] for fold in folds])
    news_vetoed = sum(
        fold["test"]["h80_news_negative_veto"]["news_counts"]["vetoed_candidate_bars"]
        for fold in folds)
    news_placebo_vetoed = sum(
        fold["test"]["h80_news_negative_veto_placebo7d"]["news_counts"]["vetoed_candidate_bars"]
        for fold in folds)
    return {
        "mode": "V44_PAPER_ONLY_PRIOR_INSPECTED_EXPLORATORY",
        "market": market_provenance,
        "fx": fx_provenance,
        "news": news_provenance or {
            "strict_verified_event_rows": len(events),
            "signal": "negative sentiment veto with 1h V48 latency and 7d window",
            "placebo": "same rule shifted 7d earlier",
        },
        "fx_availability": (
            "RBA 17:00 Australia/Sydney +24h DST-aware ASSUMPTION; "
            "retrospective snapshot, not historical first-observed/vintage"),
        "fx_historical_first_observed_verified": False,
        "fx_historical_revisions_verified": False,
        "candidates": list(CANDIDATES),
        "selectable_candidates": list(SELECTABLE),
        "selection": (
            "50/20/30 chronological split, 84-bar embargo; >=2 trades and "
            "positive NET in train and validation, otherwise HOLD"),
        "folds": folds,
        "aggregate_independent_aud1000_reset_accounts": totals,
        "aggregate_price_baselines": baseline_totals,
        "aggregate_buyhold_aud100": buyhold_totals,
        "aggregate_buyhold_aud100_net": buyhold_totals["net_aud"],
        "aggregate_selected_test_net_aud": round(sum(
            fold["selected_test_net_aud"] for fold in folds), 6),
        "aggregate_news_vetoed_candidate_bars": news_vetoed,
        "aggregate_news_placebo_vetoed_candidate_bars": news_placebo_vetoed,
        "selected_by_fold": [
            fold["selected_using_train_validation_only"] for fold in folds],
        "worst_fold_drawdown_pct": {
            name: min(fold["test"][name]["max_drawdown_pct"]
                      for fold in folds)
            for name in CANDIDATES
        },
        "costs_bps_each_side": COSTS_BPS_EACH_SIDE,
        "starting_cash_aud": CASH,
        "max_inclusive_entry_debit_aud": CAP,
        "cash_fraction_cap": 0.10,
        "android_policy": "HOLD",
        "promotion": "REJECTED_NO_UNTOUCHED_OOS_OR_VERIFIED_FX_VINTAGE",
        "news_rows_evaluated": len(events),
        "news_used_for_trading": news_vetoed > 0,
        "limitations": [
            "All historical Kraken segments were previously inspected; not untouched OOS",
            "RBA FX data is a retrospective snapshot with assumed +24h availability",
            "Current 80bps taker fee and modeled spread/slippage applied to historical prices",
            "No observed order-book queue, partial fills, or actual execution",
            "News variants fail closed when V48 exact-version proof or numeric sentiment is absent",
            "V44 current RBA/CoinDesk captures are prospective only and excluded from this backtest",
            "Three independent A$1,000 reset wallets; summed returns are not compounded",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--bars-json", default=None)
    parser.add_argument("--market-report", default=None)
    parser.add_argument("--output", default="audit/v44-fx-exit.json")
    args = parser.parse_args(argv)
    if args.bars_json:
        bars = bars_from_json(args.bars_json)
        market_provenance = {}
        if args.market_report:
            market_doc = json.loads(Path(args.market_report).read_text())
            market_provenance = market_doc.get("market", market_doc)
    else:
        bars, market_provenance = archive()
    fx, fx_provenance = fetch_fx()
    from research.v41_volume_confirmation import load_verified_news
    events, news_sha256, news_counts = load_verified_news()
    news_provenance = {
        "strict_verified_event_rows": len(events),
        "historical_news_corpus_sha256": news_sha256,
        "proof_classification_counts": news_counts,
        "availability": "V48 exact-version proof only; 1h latency; no publication-time backdating",
        "signal": "negative-sentiment 7d entry veto; 7d shifted placebo; train-only selection",
        "current_v44_publisher_snapshots_used": False,
    }
    report = evaluate(
        bars, fx, market_provenance, fx_provenance,
        events=events, news_provenance=news_provenance,
    )
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(report, indent=2, allow_nan=False, sort_keys=True)
           + "\n").encode()
    target.write_bytes(raw)
    print(json.dumps({
        "sha256": hashlib.sha256(raw).hexdigest(),
        "folds": len(report["folds"]),
        "selected_by_fold": report["selected_by_fold"],
        "selected_net": report["aggregate_selected_test_net_aud"],
        "buyhold_net": report["aggregate_buyhold_aud100_net"],
        "candidate_net": {
            name: values["net_aud"]
            for name, values in report[
                "aggregate_independent_aud1000_reset_accounts"].items()
        },
        "baseline_net": {
            name: values["net_aud"]
            for name, values in report["aggregate_price_baselines"].items()
        },
        "promotion": report["promotion"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()

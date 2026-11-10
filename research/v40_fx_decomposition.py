"""V40 PAPER ONLY: BTC/AUD = BTC/USD / AUD/USD decomposition.
FX is an RBA retrospective snapshot with ASSUMED +24h release latency,
NOT historical first-observed/revision-vintage evidence. Previously inspected
Kraken periods are exploratory; no Android promotion or real execution.
At a 4h bar OPEN only prior completed BTC/AUD closes and assumed-available
FX rates can influence the entry gate. SELL is never vetoed.
"""
from __future__ import annotations
import argparse
import bisect
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

PERIOD = 180
FX_STALENESS = 10 * 86400
CANDIDATES = ("h80_base", "h80_fx_driven", "h80_usd_momentum",
              "h80_fx_placebo7d", "h50_fx_driven")
SELECTABLE = ("h80_base", "h80_fx_driven", "h80_usd_momentum", "h50_fx_driven")
PARAM = {"h80_base": "h80_300", "h80_fx_driven": "h80_300",
         "h80_usd_momentum": "h80_300", "h80_fx_placebo7d": "h80_300",
         "h50_fx_driven": "h50_200"}

def rate_asof(fx, cutoff):
    j = bisect.bisect_right(fx.times, cutoff) - 1
    if j < 0 or cutoff - fx.times[j] > FX_STALENESS:
        return None
    if not 0 < fx.rates[j] < 5:
        raise ValueError("Invalid AUD/USD quote")
    return fx.rates[j], fx.times[j]

def decomposition(bars, i, fx, delay_days=0):
    """Strict completed-candle 30d log-return identity, past-only placebo."""
    if delay_days not in (0, 7):
        raise ValueError("Unregistered placebo delay")
    if i < PERIOD + 1 or i >= len(bars):
        raise ValueError("Insufficient completed market history")
    if bars[i][0] - bars[i-1][0] != 14400:
        raise ValueError("Missing immediate completed candle")
    t = bars[i][0] - delay_days * 86400
    current = rate_asof(fx, t)
    prior = rate_asof(fx, t - PERIOD * 14400)
    if current is None or prior is None:
        return None
    aud_now, aud_then = bars[i-1][4], bars[i-1-PERIOD][4]
    if aud_now <= 0 or aud_then <= 0:
        raise ValueError("Invalid market close")
    aud_ret = math.log(aud_now / aud_then)
    fx_ret = math.log(current[0] / prior[0])
    usd_ret = aud_ret + fx_ret
    if not math.isclose(usd_ret - fx_ret, aud_ret, abs_tol=1e-12):
        raise AssertionError("FX decomposition identity")
    return {"btc_aud_log30": aud_ret, "aud_usd_log30": fx_ret,
            "implied_btc_usd_log30": usd_ret,
            "latest_fx_assumed_available_ts": current[1],
            "prior_fx_assumed_available_ts": prior[1],
            "latest_completed_candle_ts": bars[i-1][0],
            "decision_ts": bars[i][0], "fx_delay_days": delay_days}

def entry_veto(feature, name):
    if name == "h80_base":
        return False
    if feature is None:
        return True
    if name in ("h80_fx_driven", "h80_fx_placebo7d", "h50_fx_driven"):
        return (feature["btc_aud_log30"] >= math.log(1.02)
                and feature["implied_btc_usd_log30"] <= 0)
    if name == "h80_usd_momentum":
        return feature["implied_btc_usd_log30"] < math.log(1.02)
    raise ValueError("Unknown strategy")

def select(train, validation):
    """Fixed selector uses only earlier train/validation, never test."""
    eligible = [n for n in SELECTABLE if
                train[n]["trades"] >= 2 and validation[n]["trades"] >= 2
                and train[n]["net_aud"] > 0 and validation[n]["net_aud"] > 0]
    return max(eligible, key=lambda n: min(train[n]["net_aud"],
                                            validation[n]["net_aud"])) if eligible else "HOLD"

def replay_variant(bars, start, end, name, fx, *, cost_mult=1.,
                   max_entry_debit=100., audit=False):
    from research.v31_hysteresis import replay
    if name not in CANDIDATES:
        raise ValueError("Unknown strategy")
    index = {b[0]: i for i, b in enumerate(bars)}
    if len(index) != len(bars):
        raise ValueError("Duplicate bar timestamp")
    veto_counts = {"vetoed_candidate_bars": 0, "missing_fx_bars": 0}
    def veto(ts):
        i = index[ts]
        f = None if name == "h80_base" else decomposition(
            bars, i, fx, delay_days=7 if name == "h80_fx_placebo7d" else 0)
        if f is None and name != "h80_base":
            veto_counts["missing_fx_bars"] += 1
        rejected = entry_veto(f, name)
        if rejected:
            veto_counts["vetoed_candidate_bars"] += 1
        return rejected
    result = replay(bars, start, end, PARAM[name], entry_veto=veto,
                    cost_mult=cost_mult, max_entry_debit=max_entry_debit, audit=audit)
    result["strategy"] = name
    result.update(veto_counts)
    if audit:
        for t in result["trade_audit"]:
            assert t["entry_debit_aud"] <= min(max_entry_debit,
                .1 * t["cash_before_entry_aud"]) + 1e-8
            assert abs(t["gross"]-t["fees"]-t["spread"]-
                       t["slippage"]-t["net"]) < 1e-7
        result.pop("decision_audit", None)
    return result

def evaluate(bars, fx, market_provenance, fx_provenance):
    from research.v32_segments import segments
    from research.v33_cross_regime import boundaries
    from research.v31_hysteresis import WARMUP
    from research.v29_point_in_time import simulate, buyhold
    folds = []
    for a, b in segments(bars, 1000):
        local = bars[a:b]
        n = len(local)
        train_end, val_start, val_end, test_start = boundaries(n)
        train = {k: replay_variant(local, WARMUP, train_end, k, fx) for k in SELECTABLE}
        val = {k: replay_variant(local, val_start, val_end, k, fx) for k in SELECTABLE}
        chosen = select(train, val)
        test = {k: replay_variant(local, test_start, n, k, fx, audit=True)
                for k in CANDIDATES}
        baselines = {k: simulate(local, test_start, n, k) for k in
                     ("sma", "momentum", "rsi", "breakout", "regime", "trend_breakout")}
        sensitivity = {"A50": replay_variant(local, test_start, n,
                         "h80_fx_driven", fx, max_entry_debit=50.)["net_aud"],
                       "A100": test["h80_fx_driven"]["net_aud"],
                       "half_cost": replay_variant(local, test_start, n,
                           "h80_fx_driven", fx, cost_mult=.5)["net_aud"],
                       "double_cost": replay_variant(local, test_start, n,
                           "h80_fx_driven", fx, cost_mult=2.)["net_aud"]}
        folds.append({"segment_bars": n,
            "train_end_utc": datetime.fromtimestamp(local[train_end-1][0],timezone.utc).isoformat(),
            "validation_start_utc": datetime.fromtimestamp(local[val_start][0],timezone.utc).isoformat(),
            "test_start_utc": datetime.fromtimestamp(local[test_start][0],timezone.utc).isoformat(),
            "test_end_utc": datetime.fromtimestamp(local[-1][0],timezone.utc).isoformat(),
            "train": train, "validation": val,
            "selected_using_train_validation_only": chosen,
            "selected_test_net_aud": test[chosen]["net_aud"] if chosen != "HOLD" else 0.,
            "test": test, "baselines": baselines,
            "buyhold_aud100_net": buyhold(local,test_start,n),
            "sensitivity": sensitivity})
    if not folds:
        raise ValueError("No gap-free >=1000-bar segment")
    fields = ("trades","wins","losses","gross_aud","fees_aud","spread_aud","slippage_aud","net_aud")
    totals = {k: {f: round(sum(fold["test"][k][f] for fold in folds),6) for f in fields}
              for k in CANDIDATES}
    return {"mode": "V40_EXPLORATORY_PRIOR_INSPECTED_NO_VERIFIED_FX_VINTAGE",
        "market": market_provenance, "fx": fx_provenance,
        "market_segments": len(folds), "folds": folds,
        "totals_independent_aud1000_reset_accounts": totals,
        "selected_test_net_aud": round(sum(f["selected_test_net_aud"] for f in folds),6),
        "buyhold_aud100_net": round(sum(f["buyhold_aud100_net"] for f in folds),6),
        "baseline_net_aud": {k: round(sum(f["baselines"][k]["net_aud"] for f in folds),6)
                             for k in folds[0]["baselines"]},
        "worst_fold_drawdown_pct": {k: min(f["test"][k]["max_drawdown_pct"] for f in folds)
                                    for k in CANDIDATES},
        "fee_bps_each_side": {"taker":80,"half_spread":5,"slippage":5},
        "max_inclusive_paper_entry_aud": 100., "paper_starting_balance_aud": 1000.,
        "research_selected_policy": "HOLD",
        "promotion": "REJECTED_NO_UNTOUCHED_OOS_OR_VERIFIED_FX_VINTAGE",
        "fx_assumed_latency_not_verified": True,
        "news_signal_eligible": False,
        "limitations": ["FX is retrospective snapshot, no historical revision vintages",
                        "Previously inspected BTC/AUD history, NOT untouched OOS",
                        "Current 80bps fee applied to historical prices",
                        "No observed order-book fills or maker adverse selection",
                        "Independent A$1000 wallets per segment; returns not compounded"]}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", default="audit/v40-fx-decomposition.json")
    args = ap.parse_args()
    from research.v39_rba_fx_asof import fetch_fx
    from research.v33_cross_regime import archive
    fx, fx_prov = fetch_fx()
    bars, market_prov = archive()
    report = evaluate(bars, fx, market_prov, fx_prov)
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(report, indent=2, allow_nan=False) + "\n").encode()
    target.write_bytes(raw)
    print(json.dumps({"sha256": hashlib.sha256(raw).hexdigest(),
        "folds":len(report["folds"]),"aggregate":report["totals_independent_aud1000_reset_accounts"],
        "selectors":[f["selected_using_train_validation_only"] for f in report["folds"]],
        "selected_net":report["selected_test_net_aud"],"buyhold":report["buyhold_aud100_net"]}))

if __name__ == "__main__":
    main()

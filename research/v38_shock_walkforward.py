"""V38 price-shock event-conditioned hysteresis: exploratory PAPER ONLY.

Predeclared completed-candle 4h negative shock gates; delayed placebo is a
negative control. Train/validation choose candidate or HOLD, never test.
No retrospective news metadata is promoted to historical first-observed.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from research.v31_hysteresis import replay, WARMUP
from research.v33_cross_regime import archive, boundaries
from research.v32_segments import segments
from research.v29_point_in_time import simulate, buyhold, CAP, CASH

# Negative 4h close-to-close shock; veto entries for 6 completed bars (24h).
# The 42-bar delay placebo is deliberately in the past, not future information.
SPECS = {
    "h80_base": ("h80_300", None, 0),
    "h80_down25": ("h80_300", .025, 0),
    "h80_down40": ("h80_300", .040, 0),
    "h80_down25_placebo7d": ("h80_300", .025, 42),
    "h50_down25": ("h50_200", .025, 0),
}
SELECTABLE = ("h80_down25", "h80_down40", "h50_down25")
COSTS_BPS = dict(taker=80, half_spread=5, slippage=5)

def shock_recent(bars, i, threshold, delay=0, lookback=6):
    """Decision at open i sees closes <=i-1, no current candle/future data."""
    if threshold not in (.025, .040) or delay not in (0, 42):
        raise ValueError("Unregistered threshold or placebo")
    end = i - delay
    if end < lookback + 2 or end > len(bars):
        raise ValueError("Insufficient completed history")
    return any((bars[j][4] / bars[j-1][4] - 1) <= -threshold
               for j in range(end-lookback, end))

def veto(bars, name):
    if name not in SPECS:
        raise ValueError("Unknown variant")
    base, threshold, delay = SPECS[name]
    lookup = {b[0]: i for i, b in enumerate(bars)}
    if len(lookup) != len(bars):
        raise ValueError("Duplicate timestamp")
    def check(at):
        if at not in lookup:
            raise ValueError("Unknown candle")
        i = lookup[at]
        return bool(threshold and shock_recent(bars, i, threshold, delay))
    return check

def run_variant(bars, start, end, name, cost_mult=1., max_entry_debit=CAP,
                audit=False):
    if name not in SPECS:
        raise ValueError("Unknown strategy")
    r = replay(bars, start, end, SPECS[name][0], events=(),
               cost_mult=cost_mult, max_entry_debit=max_entry_debit,
               entry_veto=veto(bars, name), audit=audit)
    if audit:
        for t in r["trade_audit"]:
            if t["entry_debit_aud"] > min(max_entry_debit,
                    .1*t["cash_before_entry_aud"]) + 1e-8:
                raise AssertionError("Paper debit cap")
            if not math.isclose(t["net"], t["gross"]-t["fees"]-
                                t["spread"]-t["slippage"], abs_tol=1e-7):
                raise AssertionError("NET mismatch")
    return r

def choose(train, val):
    eligible = [k for k in SELECTABLE if train[k]["trades"] >= 2
                and val[k]["trades"] >= 2
                and train[k]["net_aud"] > 0 and val[k]["net_aud"] > 0]
    return max(eligible, key=lambda k: min(train[k]["net_aud"],
                                            val[k]["net_aud"])) if eligible else "HOLD"

def one_segment(bars):
    n = len(bars)
    train_end, val_start, val_end, test_start = boundaries(n)
    train = {k: run_variant(bars, WARMUP, train_end, k) for k in SELECTABLE}
    val = {k: run_variant(bars, val_start, val_end, k) for k in SELECTABLE}
    selected = choose(train, val)
    tests = {k: run_variant(bars, test_start, n, k, audit=True) for k in SPECS}
    for v in tests.values():
        v.pop("decision_audit", None)
    baseline = {k: simulate(bars, test_start, n, k) for k in
                ("sma", "momentum", "rsi", "breakout", "regime", "trend_breakout")}
    sens = {str(c): run_variant(bars, test_start, n, "h80_down25",
                                max_entry_debit=c)["net_aud"] for c in (50., 100.)}
    costs = {str(m): run_variant(bars, test_start, n, "h80_down25",
                                cost_mult=m)["net_aud"] for m in (.5, 1., 2.)}
    shock_count = sum(shock_recent(bars, i, .025) for i in range(test_start, n))
    return dict(bars=n, embargo_bars=20,
        test_start_utc=datetime.fromtimestamp(bars[test_start][0],timezone.utc).isoformat(),
        test_end_utc=datetime.fromtimestamp(bars[-1][0],timezone.utc).isoformat(),
        train=train, validation=val, selected_from_past_only=selected,
        selected_test_net_aud=tests[selected]["net_aud"] if selected != "HOLD" else 0,
        test=tests, baseline=baseline, size_sensitivity=sens,
        cost_sensitivity=costs, shock_veto_candidate_bars=shock_count,
        buyhold_net_aud=buyhold(bars,test_start,n))

def evaluate(bars, provenance):
    folds = [one_segment(bars[a:b]) for a,b in segments(bars,1000)]
    fields = ("trades","wins","losses","gross_aud","fees_aud",
              "spread_aud","slippage_aud","net_aud")
    agg = {k:{f:round(sum(x["test"][k][f] for x in folds),6)
              for f in fields} for k in SPECS}
    return dict(mode="V38_PRIOR_INSPECTED_EXPLORATORY_PAPER_ONLY",
        provenance=provenance, folds=folds,
        aggregate_independent_reset_accounts=agg,
        selected_test_net_aud=round(sum(x["selected_test_net_aud"] for x in folds),6),
        buyhold_net_aud=round(sum(x["buyhold_net_aud"] for x in folds),6),
        worst_fold_drawdown_pct={k:min(x["test"][k]["max_drawdown_pct"]
                                      for x in folds) for k in SPECS},
        baseline_net_aud={k:round(sum(x["baseline"][k]["net_aud"]
                                     for x in folds),6) for k in folds[0]["baseline"]},
        fee_bps_each_side=COSTS_BPS, paper_starting_cash_aud=CASH,
        paper_max_inclusive_entry_aud=CAP, android_strategy="HOLD",
        promotion="REJECTED_UNTOUCHED_OOS_NOT_AVAILABLE",
        caveats=["Historical market previously inspected, not untouched OOS",
                 "Shock threshold predeclared but exploratory after prior studies",
                 "A$1000 reset per segment, no compounding",
                 "No observed bid/ask/queue or maker fills",
                 "No historical first-observed article corpus; no news edge claimed"])

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--output",default="audit/v38-shock-walkforward.json")
    a=p.parse_args()
    bars,prov=archive()
    result=evaluate(bars,prov)
    path=Path(a.output);path.parent.mkdir(parents=True,exist_ok=True)
    raw=(json.dumps(result,indent=2,allow_nan=False)+"\n").encode()
    path.write_bytes(raw)
    print(json.dumps({"sha256":hashlib.sha256(raw).hexdigest(),
        "folds":len(result["folds"]),
        "aggregate_net":{k:v["net_aud"] for k,v in
            result["aggregate_independent_reset_accounts"].items()},
        "selected_net":result["selected_test_net_aud"],
        "buyhold":result["buyhold_net_aud"],"policy":"HOLD"}))
if __name__=="__main__":main()

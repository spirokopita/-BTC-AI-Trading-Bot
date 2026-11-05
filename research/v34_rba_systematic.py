"""V34 PAPER-ONLY: outcome-independent RBA monetary-policy calendar, matched
event diagnostics and entry-only hysteresis ablations. NEVER first-observed news.
All Kraken historical price periods were previously inspected: EXPLORATORY ONLY.
"""
from __future__ import annotations
import argparse, bisect, hashlib, json, statistics
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from research.v31_hysteresis import WARMUP, PARAMS, replay, choose
from research.v33_cross_regime import archive, boundaries
from research.v32_segments import segments
from research.v29_point_in_time import buyhold, simulate
from research.v30_matched_news import matched_study

CALENDAR = "data/rba_policy_calendar_2020_2025.json"
LATENCY_HOURS = 24
VETO_HOURS = (24, 48)
PLACEBO_SHIFT_HOURS = 7*24
NAMES = ("h50_200", "h80_300")
SYDNEY = ZoneInfo("Australia/Sydney")

def load_calendar(path=CALENDAR):
    raw = Path(path).read_bytes()
    data = json.loads(raw)
    if data.get("dataset_type") != "RETROSPECTIVE_COMPLETE_RBA_POLICY_DECISION_DATE_INDEX_2020_2025_NOT_FIRST_OBSERVED":
        raise ValueError("Refuse unverified calendar provenance")
    if data.get("source_timezone") != "Australia/Sydney" or data.get("release_clock_local") != "14:30":
        raise ValueError("Unsupported release time or timezone")
    events = []
    for row in data["events"]:
        day = datetime.strptime(row["local_date"], "%Y-%m-%d")
        local = day.replace(hour=14, minute=30, tzinfo=SYDNEY)
        if row["id"] != "rba_"+row["local_date"] or row["sentiment"] != 0:
            raise ValueError("RBA calendar must be neutral and date-indexed")
        if row["source_index_url"] != (
            "https://www.rba.gov.au/monetary-policy/int-rate-decisions/"
            + row["local_date"][:4] + "/"
        ):
            raise ValueError("Unexpected RBA source URL")
        pub = int(local.timestamp())
        available = pub + LATENCY_HOURS*3600
        events.append(dict(id=row["id"], category=row["category"], sentiment=0,
            release_ts=pub, available_ts=available, source=row["source_index_url"]))
    events.sort(key=lambda e:e["available_ts"])
    if len(events)!=61 or len({e["id"] for e in events})!=61:
        raise ValueError("Expected 61 complete 2020-2025 RBA meeting dates")
    return events, dict(sha256=hashlib.sha256(raw).hexdigest(), events=len(events),
        source="RBA official annual policy-decision date indexes 2020-2025",
        availability="Scheduled 14:30 Sydney release + conservative assumed 24h delay",
        provenance="RETROSPECTIVE_DATE_INDEX_NOT_FIRST_OBSERVED_NO_REVISION_HISTORY",
        sentiment="NEUTRAL: release occurrence, not rate-surprise direction")

def veto_factory(events, hours=48, shift_hours=0):
    """As-of-only event entry veto; shift is a DELAYED placebo, never future news."""
    if hours not in VETO_HOURS or shift_hours not in (0, PLACEBO_SHIFT_HOURS):
        raise ValueError("Unregistered experiment")
    timestamps=sorted(e["available_ts"]+shift_hours*3600 for e in events)
    def blocked(now):
        i=bisect.bisect_right(timestamps,now)-1
        return i>=0 and 0<=now-timestamps[i]<hours*3600
    return blocked

def summary(rows):
    keys=("trades","wins","losses","gross_aud","fees_aud","spread_aud",
          "slippage_aud","net_aud")
    return {key:round(sum(r[key] for r in rows),6) for key in keys}

def fold(bars, events):
    n=len(bars)
    tr,vs,ve,te=boundaries(n)
    train={k:replay(bars,WARMUP,tr,k) for k in PARAMS}
    validation={k:replay(bars,vs,ve,k) for k in PARAMS}
    selected=choose(train,validation)
    outcomes={}
    for name in NAMES:
        outcomes[name]=replay(bars,te,n,name,audit=True)
        for hours in VETO_HOURS:
            key=f"{name}_rba_{hours}h"
            outcomes[key]=replay(bars,te,n,name,audit=True,
                entry_veto=veto_factory(events,hours))
        outcomes[f"{name}_rba_48h_delayed_placebo"]=replay(bars,te,n,name,
            audit=True,entry_veto=veto_factory(events,48,PLACEBO_SHIFT_HOURS))
    for value in outcomes.values():
        value.pop("decision_audit",None)
    study=matched_study(bars,events)
    study["summary"]=[{k:v for k,v in row.items() if k not in (
        "mean_direction_aligned_excess_pct","direction_aligned_positive",
        "descriptive_signflip_p")} for row in study["summary"]]
    # Neutral scheduled events have no sentiment-aligned trading direction.
    study["rows"]=[{k:v for k,v in row.items() if k!="direction_aligned_excess_pct"}
        for row in study["rows"]]
    eligible=[e for e in events if bars[te][0]<=e["available_ts"]<=bars[-1][0]]
    return dict(bars=n, test_start_utc=datetime.fromtimestamp(
        bars[te][0],timezone.utc).isoformat(),test_end_utc=datetime.fromtimestamp(
        bars[-1][0],timezone.utc).isoformat(),embargo_bars=20,
        train_validation_selected=selected, selected_test_net_aud=(
            outcomes[selected]["net_aud"] if selected in outcomes else 0),
        rba_events_in_test=len(eligible),event_study=study,
        strategies=outcomes,sma=simulate(bars,te,n,"sma"),
        momentum=simulate(bars,te,n,"momentum"),
        rsi=simulate(bars,te,n,"rsi"),
        breakout=simulate(bars,te,n,"breakout"),
        regime=simulate(bars,te,n,"regime"),
        trend_atr=simulate(bars,te,n,"trend_breakout"),
        buyhold_aud100_net=buyhold(bars,te,n),
        cost_sensitivity_h80_rba48={
            str(m):replay(bars,te,n,"h80_300",cost_mult=m,
                entry_veto=veto_factory(events,48))["net_aud"]
            for m in (.5,1.,2.)})

def evaluate(bars, market, events, provenance):
    slices=segments(bars,1000)
    folds=[fold(bars[a:b],events) for a,b in slices]
    names=list(folds[0]["strategies"]) if folds else []
    totals={name:summary([f["strategies"][name] for f in folds]) for name in names}
    ablations={name:round(totals[name]["net_aud"]-
        totals[name.split("_rba_")[0]]["net_aud"],6)
        for name in names if "_rba_" in name}
    changed={name:sum(f["strategies"][name]["trades"]!=
        f["strategies"][name.split("_rba_")[0]]["trades"] or
        f["strategies"][name]["trade_audit"]!=
        f["strategies"][name.split("_rba_")[0]]["trade_audit"]
        for f in folds) for name in ablations}
    return dict(mode="V34_PAPER_ONLY_PREVIOUSLY_INSPECTED_EXPLORATORY",
        market=market,calendar=provenance,eligible_segments=len(slices),
        segment_bar_counts=[b-a for a,b in slices],folds=folds,
        aggregate_independent_reset_accounts=totals,
        aggregate_ablation_delta_aud=ablations,
        folds_with_changed_trade_audit=changed,
        aggregate_same_stake_buyhold_net_aud=round(
            sum(f["buyhold_aud100_net"] for f in folds),6),
        aggregate_selected_test_net_aud=round(
            sum(f["selected_test_net_aud"] for f in folds),6),
        fee_bps_per_side={"taker":80,"half_spread":5,"slippage":5},
        cash_aud=1000,max_inclusive_entry_debit_aud=100,
        selected_android_policy="HOLD",android_promotion="REJECTED_NOT_UNTOUCHED_OOS",
        limitations=[
            "RBA date index is systematically sampled scheduled MACRO announcements, not comprehensive crypto/financial news.",
            "Release at 14:30 Sydney is indexed schedule; original revisions/actual first-observed times NOT verified. 24h delay assumed.",
            "Event sign NEUTRAL, not a known surprise or sentiment forecast; matched returns descriptive only.",
            "Prior inspected historical Kraken prices; no untouched OOS and no strategy promotion.",
            "No observed order book/fill queue; next-open taker fills and fixed spread/slippage are hypothetical.",
            "Each fold is independent A$1000 reset; totals are not a compounded account."])

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--csv",default=None)
    p.add_argument("--output",default="audit/v34-rba-systematic.json")
    args=p.parse_args()
    if args.csv:
        from research.kraken_archive import parse_csv
        raw=Path(args.csv).read_bytes()
        bars=parse_csv(raw);market={"source":"LOCAL_CSV_UNVERIFIED",
            "sha256":hashlib.sha256(raw).hexdigest()}
    else:
        bars,market=archive()
    events,provenance=load_calendar()
    report=evaluate(bars,market,events,provenance)
    out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,indent=2,allow_nan=False)+"\n")
    print(json.dumps({"output":str(out),"calendar_events":len(events),
        "segments":report["eligible_segments"],
        "ablation_net_aud":report["aggregate_ablation_delta_aud"],
        "policy":"HOLD"}))
if __name__=="__main__":main()

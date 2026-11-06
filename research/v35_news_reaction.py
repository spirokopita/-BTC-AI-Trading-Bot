"""V35 PAPER ONLY: retrospective article + scheduled macro event reaction experiment.
NO historical first-observed article versions, NO untouched OOS, NO Android promotion.
Every signal is decided after one completed four-hour reaction bar; next-open fill.
"""
from __future__ import annotations
import argparse, bisect, hashlib, json, math, statistics
from datetime import datetime, timezone
from pathlib import Path
from research.v29_point_in_time import (STEP, CASH, CAP, FEE, SPREAD, SLIPPAGE,
    execution, simulate, buyhold, ts)
from research.v31_hysteresis import replay as hysteresis_replay
from research.v33_cross_regime import archive, boundaries, historical_news
from research.v34_rba_systematic import load_calendar
from research.v32_segments import segments

NEWS_PATH="data/historical_news_supplement_v35.json"
KIND="RETROSPECTIVE_SEARCH_DISCOVERED_NONREPRESENTATIVE_NEWS_V35_NOT_FIRST_OBSERVED"
DELAY=24*3600
HOLD_BARS=6
THRESHOLDS=(0.005,0.01)
SHIFTS=(0,7*86400,28*86400)

def load_articles(path=NEWS_PATH):
    raw=Path(path).read_bytes()
    doc=json.loads(raw)
    if doc.get("dataset_type")!=KIND:
        raise ValueError("Refuse mislabelled retrospective news")
    seen=set(); events=[]; omitted=[]
    for row in doc["articles"]:
        if row["id"] in seen or row["url"] in seen:
            raise ValueError("Duplicate article")
        seen.update((row["id"],row["url"]))
        pub=ts(row["published_at_utc"])
        updated=ts(row.get("updated_at_utc",row["published_at_utc"]))
        if updated<pub or not row["url"].startswith("https://"):
            raise ValueError("Invalid news timestamp or URL")
        event=dict(id=row["id"],source_kind="ordinary_article",
            category=row["category"],market_following=bool(row["market_following"]),
            published_ts=pub,revision_ts=updated,
            available_ts=updated+DELAY,url=row["url"],
            historical_revision_provenance="LATEST_DISPLAYED_ONLY_NOT_ARCHIVED")
        if event["market_following"]:
            omitted.append(event["id"])
        else:
            events.append(event)
    events.sort(key=lambda x:x["available_ts"])
    return events,dict(sha256=hashlib.sha256(raw).hexdigest(),
        total_articles=len(doc["articles"]),usable_non_market_following=len(events),
        excluded_market_following=len(omitted),excluded_ids=omitted,
        source="Euronews/Reuters retrospectively search-discovered 2021-2025",
        warning="NONREPRESENTATIVE; revisions not archived; +24h is assumed availability, not first-observed")

def event_corpus(path=NEWS_PATH):
    fresh,prov=load_articles(path)
    prior,prior_prov=historical_news()
    rba,rba_prov=load_calendar()
    # Earlier V29/V31 headlines are NOT necessarily independent market events.
    # Preserve that provenance; no sentiment labels are used in this experiment.
    old=[dict(id=e["id"],available_ts=e["available_ts"],
        category=e["category"],source_kind="prior_curated_article",
        market_following=False,url=e.get("url",""),
        historical_revision_provenance="RETROSPECTIVE_CONVENIENCE_UNVERIFIED")
        for e in prior]
    macro=[dict(id=e["id"],available_ts=e["available_ts"],
        category="scheduled_rba",source_kind="scheduled_rba",
        market_following=False,url=e["source"],
        historical_revision_provenance="SCHEDULE_PLUS_ASSUMED_DELAY")
        for e in rba]
    seen=set(); all_events=[]
    for e in sorted(fresh+old+macro,key=lambda e:(e["available_ts"],e["id"])):
        key=(e["source_kind"],e["url"],e["available_ts"]//(24*3600))
        if key in seen: continue
        seen.add(key);all_events.append(e)
    return all_events,dict(new_articles=prov,prior_news=prior_prov,
        rba=rba_prov,total_events=len(all_events),
        by_kind={kind:sum(e["source_kind"]==kind for e in all_events)
                 for kind in ("ordinary_article","prior_curated_article","scheduled_rba")})

def candidate_indices(bars,start,end,events,shift=0):
    """Only an already-available event can initiate an entry after completed bar k."""
    if shift not in SHIFTS: raise ValueError("Unregistered negative control shift")
    if start<2 or end>len(bars) or start>=end:
        raise ValueError("Invalid replay boundaries")
    if any(bars[i][0]-bars[i-1][0]!=STEP for i in range(start-1,end)):
        raise ValueError("Candle gap: fail closed")
    times=[b[0] for b in bars]
    seen=set();rows=[]
    for e in sorted(events,key=lambda e:e["available_ts"]):
        k=bisect.bisect_left(times,e["available_ts"]+shift)
        # Reaction bar k must be wholly after availability; decision is open k+1.
        if k<start or k+HOLD_BARS+1>=end or k in seen: continue
        seen.add(k)
        rows.append((k,e["id"]))
    return sorted(rows)

def replay_events(bars,start,end,events,threshold=.005,shift=0,
                  cost_mult=1.,max_entry_debit=CAP,audit=False):
    if threshold not in THRESHOLDS or not .5<=cost_mult<=2:
        raise ValueError("Unregistered reaction threshold or cost multiplier")
    if not 0<max_entry_debit<=CAP:
        raise ValueError("Invalid paper position limit")
    candidates=candidate_indices(bars,start,end,events,shift)
    cash=CASH; trades=[]; decisions=[];next_free=start;equity=[cash]
    # Trades do not overlap; all exits occur at next-open after fixed 24h hold.
    for k,event_id in candidates:
        entry_i=k+1;exit_i=entry_i+HOLD_BARS
        if entry_i<next_free:
            decisions.append(dict(event_id=event_id,reason="overlap_skipped",decision_ts=bars[entry_i][0]))
            continue
        reaction=bars[k][4]/bars[k][1]-1
        # No future candle or future news enters the entry decision.
        if reaction<threshold:
            decisions.append(dict(event_id=event_id,reason="reaction_below_threshold",
                decision_ts=bars[entry_i][0],reaction_pct=100*reaction))
            continue
        budget=min(max_entry_debit,.1*cash)
        a=bars[entry_i][1];b=bars[exit_i][1]
        qty=budget/(a*(1+(SPREAD+SLIPPAGE)*cost_mult)*(1+FEE*cost_mult))
        buy=execution(a,qty,"buy",cost_mult)
        sell=execution(b,qty,"sell",cost_mult)
        debit=buy["notional"]+buy["fee"]
        if debit>budget+1e-8 or debit>max_entry_debit+1e-8 or debit>.1*cash+1e-8:
            raise AssertionError("Inclusive A$100/10% cap breached")
        gross=qty*(b-a)
        fees=buy["fee"]+sell["fee"]
        spread=buy["spread"]+sell["spread"]
        slippage=buy["slippage"]+sell["slippage"]
        net=gross-fees-spread-slippage
        realised=sell["notional"]-sell["fee"]-debit
        if not math.isclose(net,realised,abs_tol=1e-7):
            raise AssertionError("NET reconciliation failed")
        trades.append(dict(event_id=event_id,decision_ts=bars[entry_i][0],
            observed_reaction_open_ts=bars[k][0],entry_ts=bars[entry_i][0],
            exit_ts=bars[exit_i][0],entry_debit_aud=debit,
            cash_before_entry_aud=cash,quantity_btc=qty,
            reaction_pct=100*reaction,gross=gross,fees=fees,
            spread=spread,slippage=slippage,net=net))
        # Track intratrade marked-to-liquidation equity to capture drawdown.
        for j in range(entry_i,exit_i+1):
            m=bars[j][1]
            mark=execution(m,qty,"sell",cost_mult)
            value=cash-debit+mark["notional"]-mark["fee"]
            equity.append(value)
        cash+=realised
        next_free=exit_i+1
    if not math.isclose(cash-CASH,sum(t["net"] for t in trades),abs_tol=1e-7):
        raise AssertionError("Account reconciliation failed")
    equity.append(cash)
    peak=equity[0];dd=0.
    for x in equity:
        peak=max(peak,x);dd=min(dd,x/peak-1)
    totals={key:round(sum(t[key] for t in trades),6)
        for key in ("gross","fees","spread","slippage","net")}
    out=dict(trades=len(trades),wins=sum(t["net"]>0 for t in trades),
        losses=sum(t["net"]<0 for t in trades),events_eligible=len(candidates),
        events_below_threshold=sum(d["reason"]=="reaction_below_threshold" for d in decisions),
        events_overlap_skipped=sum(d["reason"]=="overlap_skipped" for d in decisions),
        gross_aud=totals["gross"],fees_aud=totals["fees"],
        spread_aud=totals["spread"],slippage_aud=totals["slippage"],
        net_aud=totals["net"],return_pct=round((cash/CASH-1)*100,6),
        max_drawdown_pct=round(dd*100,6),
        fee_bps_per_side=80,cost_multiplier=cost_mult)
    if audit: out["trade_audit"]=trades;out["decision_audit"]=decisions
    return out

def aggregate(rows):
    keys=("trades","wins","losses","events_eligible","events_below_threshold",
        "events_overlap_skipped","gross_aud","fees_aud","spread_aud",
        "slippage_aud","net_aud")
    return {key:round(sum(r[key] for r in rows),6) for key in keys}

def one_segment(bars,events):
    n=len(bars)
    tr,vs,ve,te=boundaries(n)
    kinds={
        "all":events,
        "ordinary":[e for e in events if e["source_kind"]=="ordinary_article"],
        "prior":[e for e in events if e["source_kind"]=="prior_curated_article"],
        "scheduled":[e for e in events if e["source_kind"]=="scheduled_rba"]}
    train={str(t):replay_events(bars,305,tr,events,t) for t in THRESHOLDS}
    val={str(t):replay_events(bars,vs,ve,events,t) for t in THRESHOLDS}
    # Predeclared conservative train+validation selector; no test leakage.
    eligible=[t for t in THRESHOLDS
        if train[str(t)]["trades"]>=3 and val[str(t)]["trades"]>=3
        and train[str(t)]["net_aud"]>0 and val[str(t)]["net_aud"]>0]
    selected=max(eligible,key=lambda t:min(train[str(t)]["net_aud"],val[str(t)]["net_aud"])) if eligible else None
    outcomes={}
    for t in THRESHOLDS:
        for label,ev in kinds.items():
            outcomes[f"{label}_{t}"]=replay_events(bars,te,n,ev,t,audit=True)
        for shift in SHIFTS[1:]:
            outcomes[f"all_{t}_shift_{shift//86400}d"]=replay_events(bars,te,n,events,t,shift=shift,audit=True)
    sensitivity={str(m):replay_events(bars,te,n,events,.005,cost_mult=m)
        for m in (.5,1.,2.)}
    sizing={str(cap):replay_events(bars,te,n,events,.005,max_entry_debit=cap)
        for cap in (50,100)}
    return dict(bars=n,first_utc=datetime.fromtimestamp(bars[0][0],timezone.utc).isoformat(),
        test_start_utc=datetime.fromtimestamp(bars[te][0],timezone.utc).isoformat(),
        test_end_utc=datetime.fromtimestamp(bars[-1][0],timezone.utc).isoformat(),
        embargo_bars=20,training=train,validation=val,
        train_validation_selected=("HOLD" if selected is None else f"all_{selected}"),
        selected_test_net_aud=(0 if selected is None else outcomes[f"all_{selected}"]["net_aud"]),
        test=outcomes,fee_sensitivity=sensitivity,sizing_sensitivity=sizing,
        price_only_sma=simulate(bars,te,n,"sma"),
        price_only_momentum=simulate(bars,te,n,"momentum"),
        price_only_rsi=simulate(bars,te,n,"rsi"),
        price_only_breakout=simulate(bars,te,n,"breakout"),
        price_only_regime=simulate(bars,te,n,"regime"),
        price_only_trend_atr=simulate(bars,te,n,"trend_breakout"),
        price_only_h80_300=hysteresis_replay(bars,te,n,"h80_300"),
        same_stake_buyhold_net_aud=buyhold(bars,te,n))

def evaluate(bars,market,events,news_provenance):
    parts=segments(bars,1000)
    folds=[one_segment(bars[a:b],events) for a,b in parts]
    names=list(folds[0]["test"]) if folds else []
    totals={name:aggregate([f["test"][name] for f in folds]) for name in names}
    return dict(mode="V35_PAPER_ONLY_EXPLORATORY_PRIOR_INSPECTED_NO_PROMOTION",
        market=market,news=news_provenance,eligible_segments=len(parts),
        segment_bar_counts=[b-a for a,b in parts],folds=folds,
        aggregate_independent_reset_accounts=totals,
        selected_test_net_aud=round(sum(f["selected_test_net_aud"] for f in folds),6),
        same_stake_buyhold_net_aud=round(sum(f["same_stake_buyhold_net_aud"] for f in folds),6),
        cost_assumptions_bps_per_side=dict(taker=80,half_spread=5,slippage=5),
        starting_paper_balance_aud=1000,max_inclusive_paper_debit_aud=100,
        android_policy="HOLD",android_changes="NONE",real_execution="DISABLED",
        promotion="REJECTED_PREVIOUSLY_INSPECTED_NOT_UNTOUCHED_OOS",
        limitations=["15 new retrospectively search-discovered articles are NOT representative",
        "Original historical article versions and actual first-observed times unavailable",
        "Market-following recaps excluded from new article subset; older curated events may be reactive",
        "24h news delay is assumed, not independently verified historical accessibility",
        "RBA events are scheduled neutral macro announcements; not directional surprises",
        "No historical order book, actual spread, queue, adverse selection or fill observation",
        "All BTC/AUD historical segments were previously inspected; results EXPLORATORY",
        "Each segment has independently reset A$1000 account; totals not compounded",
        "Event reaction thresholds are hypotheses, not optimised deployable parameters"])

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--csv",default=None)
    p.add_argument("--output",default="audit/v35-news-reaction.json")
    a=p.parse_args()
    if a.csv:
        from research.kraken_archive import parse_csv
        raw=Path(a.csv).read_bytes()
        bars=parse_csv(raw)
        market=dict(source="LOCAL_CSV_UNVERIFIED",sha256=hashlib.sha256(raw).hexdigest())
    else:
        bars,market=archive()
    events,prov=event_corpus()
    result=evaluate(bars,market,events,prov)
    out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,indent=2,allow_nan=False)+"\n")
    print(json.dumps(dict(output=str(out),events=len(events),segments=len(result["folds"]),
        aggregates={k:v["net_aud"] for k,v in result["aggregate_independent_reset_accounts"].items()},
        selected_net_aud=result["selected_test_net_aud"],policy="HOLD")))
if __name__=="__main__":main()

"""V31 PAPER ONLY: predeclared low-turnover hysteresis strategies, strictly as-of news
and train/validation-only walk-forward selection. Historical evaluation is EXPLORATORY,
NOT untouched OOS: these price periods have been examined in earlier versions.
"""
from __future__ import annotations
import argparse, json, math, statistics
from datetime import datetime, timezone
from pathlib import Path
from research.kraken_archive import load
from research.v29_point_in_time import (STEP, CAP, CASH, FEE, SPREAD, SLIPPAGE,
    execution, buyhold, simulate as baseline_simulate, news_load, asof)

# Parameters are deliberately few, predeclared before inspecting V31 results.
PARAMS = {
    "h50_200": (50, 200, .015, .010, .07, .070),
    "h30_120": (30, 120, .020, .010, .07, .060),
    "h80_300": (80, 300, .010, .015, .08, .065),
}
VARIANTS = tuple(PARAMS) + ("h50_200_news", "h50_200_placebo")
WARMUP = 305
EMBARGO = 20
MIN_HOLD = 6
COOLDOWN = 12

def spec(name):
    if name not in VARIANTS: raise ValueError("Unknown V31 strategy")
    return PARAMS["h50_200"] if name.endswith(("_news", "_placebo")) else PARAMS[name]

def features(bars, i, fast, slow):
    """Decision at open i sees completed candles only, ending i-1."""
    if i < max(WARMUP, slow+1): raise ValueError("Insufficient completed candles")
    close = bars[i-1][4]
    ma_fast = sum(b[4] for b in bars[i-fast:i])/fast
    ma_slow = sum(b[4] for b in bars[i-slow:i])/slow
    closes = [b[4] for b in bars[i-43:i]]
    returns = [math.log(closes[k]/closes[k-1]) for k in range(1, len(closes))]
    weekly_vol = statistics.pstdev(returns) * math.sqrt(42)
    return close, ma_fast, ma_slow, weekly_vol

def news_risk(events, at, name):
    if name not in ("h50_200_news", "h50_200_placebo"): return False
    shift = 7*86400 if name.endswith("_placebo") else 0
    return any(e["sentiment"] < 0 for e in asof(events, at, shift=shift, window=7*86400))

def decision(bars, i, name, holding=False, held=0, events=()):
    fast, slow, entry_band, exit_band, stop_band, max_vol = spec(name)
    close, f, s, vol = features(bars, i, fast, slow)
    if holding:
        # A completed-bar risk exit; not an intrabar exchange stop.
        return "SELL" if (held >= MIN_HOLD and
            (f < s*(1-exit_band) or close < s*(1-stop_band))) else "HOLD"
    if (f > s*(1+entry_band) and close > s*(1+entry_band)
        and vol <= max_vol and not news_risk(events, bars[i][0], name)):
        return "BUY"
    return "HOLD"

def replay(bars, start, end, name, events=(), cost_mult=1., audit=False, entry_veto=None, max_entry_debit=CAP, exit_veto=None):
    if name not in VARIANTS or start < WARMUP or end > len(bars) or end-start < 3:
        raise ValueError("Invalid replay segment")
    if not .5 <= cost_mult <= 2: raise ValueError("Invalid cost multiplier")
    if not 0 < max_entry_debit <= CAP: raise ValueError("Invalid paper entry cap")
    if any(bars[k][0]-bars[k-1][0] != STEP for k in range(start-WARMUP+1,end)):
        raise ValueError("Candle gap: fail closed")
    cash=CASH; qty=0.; entry=None; entry_mid=0.; entry_i=None; entry_cash_before=None
    last_exit=-COOLDOWN; rows=[]; equity=[cash]; actions=[]
    for i in range(start,end):
        mid=bars[i][1]
        action=("SELL" if qty else "HOLD") if i==end-1 else decision(
            bars,i,name,bool(qty),i-entry_i if qty else 0,events)
        if not qty and i < last_exit+COOLDOWN: action="HOLD"
        # Optional strictly-as-of event-risk gate: suppress BUY only; never block protective SELL.
        if action=="BUY" and entry_veto is not None and entry_veto(bars[i][0]):
            action="HOLD"
        # Optional completed-bar exit override. The callback is invoked only
        # while holding, after MIN_HOLD, and never on the terminal liquidation
        # bar. Its timestamp is the next bar OPEN; callback inputs must be
        # derived exclusively from candles completed before this timestamp.
        if (action=="HOLD" and qty and exit_veto is not None
                and i < end-1 and i-entry_i >= MIN_HOLD
                and exit_veto(bars[i][0])):
            action="SELL"
        if audit: actions.append((bars[i][0], bars[i-1][0], action))
        if action=="BUY" and not qty:
            budget=min(max_entry_debit,.1*cash)
            qty=budget/(mid*(1+(SPREAD+SLIPPAGE)*cost_mult)*(1+FEE*cost_mult))
            entry=execution(mid,qty,"buy",cost_mult)
            debit=entry["notional"]+entry["fee"]
            if debit>budget+1e-8 or debit>max_entry_debit+1e-8: raise AssertionError("Entry debit exceeds cap")
            entry_cash_before=cash
            cash-=debit; entry_mid=mid; entry_i=i
        elif action=="SELL" and qty:
            out=execution(mid,qty,"sell",cost_mult)
            cash+=out["notional"]-out["fee"]
            row=dict(entry_ts=bars[entry_i][0],exit_ts=bars[i][0],
                entry_debit_aud=entry["notional"]+entry["fee"],
                cash_before_entry_aud=entry_cash_before,
                gross=qty*(mid-entry_mid),fees=entry["fee"]+out["fee"],
                spread=entry["spread"]+out["spread"],
                slippage=entry["slippage"]+out["slippage"])
            row["net"]=row["gross"]-row["fees"]-row["spread"]-row["slippage"]
            if not math.isclose(row["net"],out["notional"]-out["fee"]-entry["notional"]-entry["fee"],abs_tol=1e-8):
                raise AssertionError("NET accounting mismatch")
            rows.append(row);qty=0.;entry=None;entry_i=None;entry_cash_before=None;last_exit=i
        marked=cash
        if qty:
            out=execution(mid,qty,"sell",cost_mult)
            marked+=out["notional"]-out["fee"]
        equity.append(marked)
    totals={key:sum(t[key] for t in rows) for key in ("gross","fees","spread","slippage","net")}
    if qty or not math.isclose(cash-CASH,totals["net"],abs_tol=1e-7):
        raise AssertionError("Wallet reconciliation")
    peak=equity[0]; dd=0.
    for value in equity:
        peak=max(peak,value);dd=min(dd,value/peak-1)
    result=dict(strategy=name,trades=len(rows),wins=sum(t["net"]>0 for t in rows),
        losses=sum(t["net"]<=0 for t in rows),
        gross_aud=round(totals["gross"],6),fees_aud=round(totals["fees"],6),
        spread_aud=round(totals["spread"],6),slippage_aud=round(totals["slippage"],6),
        net_aud=round(totals["net"],6),return_pct=round(totals["net"]/CASH*100,6),
        max_drawdown_pct=round(dd*100,6))
    if audit: result.update(trade_audit=rows,decision_audit=actions)
    return result

def choose(training, validation):
    """No test metrics can influence selection. Require >=2 trades and NET>0 in both."""
    eligible=[name for name in PARAMS if
        training[name]["trades"]>=2 and validation[name]["trades"]>=2 and
        training[name]["net_aud"]>0 and validation[name]["net_aud"]>0]
    return max(eligible,key=lambda name:validation[name]["net_aud"]) if eligible else "HOLD"

def run(bars, events, provenance, news_sha):
    n=len(bars)
    if n<2500: raise ValueError("Need >=2500 contiguous bars")
    # Three nonoverlapping chronological test periods. 20-bar train/val/test embargo.
    starts=[int(n*x) for x in (.55,.70,.85)]
    folds=[]
    for idx,test_start in enumerate(starts):
        test_end=starts[idx+1]-EMBARGO if idx+1<len(starts) else n
        val_end=test_start-EMBARGO
        val_start=val_end-500
        train_end=val_start-EMBARGO
        if train_end<=WARMUP+300: raise ValueError("Insufficient training history")
        training={name:replay(bars,WARMUP,train_end,name,events) for name in PARAMS}
        validation={name:replay(bars,val_start,val_end,name,events) for name in PARAMS}
        selected=choose(training,validation)
        tests={name:replay(bars,test_start,test_end,name,events) for name in VARIANTS}
        baseline=baseline_simulate(bars,test_start,test_end,"sma",events)
        trend=baseline_simulate(bars,test_start,test_end,"trend_breakout",events)
        sensitivity={name:{str(mult):replay(bars,test_start,test_end,name,events,mult)["net_aud"]
                    for mult in (.5,1.,2.)} for name in VARIANTS}
        folds.append(dict(train_end_utc=datetime.fromtimestamp(bars[train_end-1][0],timezone.utc).isoformat(),
            validation_start_utc=datetime.fromtimestamp(bars[val_start][0],timezone.utc).isoformat(),
            validation_end_utc=datetime.fromtimestamp(bars[val_end-1][0],timezone.utc).isoformat(),
            test_start_utc=datetime.fromtimestamp(bars[test_start][0],timezone.utc).isoformat(),
            test_end_utc=datetime.fromtimestamp(bars[test_end-1][0],timezone.utc).isoformat(),
            training=training,validation=validation,selected_using_past_only=selected,
            selected_test_net_aud=0 if selected=="HOLD" else tests[selected]["net_aud"],
            tests=tests,sma_baseline=baseline,trend_atr_baseline=trend,
            buyhold_aud100_net_aud=buyhold(bars,test_start,test_end),
            fee_sensitivity=sensitivity))
    totals={name:{key:round(sum(f["tests"][name][key] for f in folds),6)
                  for key in ("trades","gross_aud","fees_aud","spread_aud","slippage_aud","net_aud")}
            for name in VARIANTS}
    return dict(mode="PAPER_ONLY_V31_EXPLORATORY_PREVIOUSLY_INSPECTED_DATA",
        market=provenance,news_sha256=news_sha,news_count=len(events),
        news_type="RETROSPECTIVE_PUBLICATION_NOT_FIRST_OBSERVED",
        fee_bps_per_side=dict(taker=80,half_spread=5,slippage=5),
        paper_cap_aud=CAP,cash_aud=CASH,parameter_menu=PARAMS,
        folds=folds,aggregate_independent_reset_folds=totals,
        selected_policy="HOLD",promotion="REJECTED_NO_UNTOUCHED_POSITIVE_NET",
        limitations=["Price history already inspected; test periods are NOT untouched OOS",
          "Only ten manually selected retrospective news articles; news variant is exploratory",
          "Current published fees imposed on historical prices, not actual historic fills",
          "Next-open fills, completed-candle risk exits, no real order-book/latency model",
          "Three independently reset A$1000 accounts; aggregate NET is NOT compounded"])

def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument("--csv",default=None)
    p.add_argument("--news",default="data/historical_news_reconstructed.json")
    p.add_argument("--output",default="audit/v31-hysteresis.json")
    a=p.parse_args(argv)
    bars,prov=load(a.csv); events,sha=news_load(a.news)
    report=run(bars,events,prov,sha)
    out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,indent=2,allow_nan=False)+"\n")
    print(json.dumps(dict(output=str(out),folds=len(report["folds"]),
        aggregate=report["aggregate_independent_reset_folds"],
        selected=[f["selected_using_past_only"] for f in report["folds"]],
        promotion=report["promotion"]),indent=2))
if __name__=="__main__":main()

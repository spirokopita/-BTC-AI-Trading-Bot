"""PAPER ONLY: never-sell BTC/AUD Hoarder research. Previously inspected history is exploratory."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
from research.v29_point_in_time import STEP,CASH,CAP,FEE,SPREAD,SLIPPAGE
from research.v32_segments import segments
from research.v33_cross_regime import boundaries,archive
from research.kraken_archive import parse_csv

WARMUP=180
POLICIES=("hoard_5","hoard_10","hoard_20","hoard_tiered","dca_30d","buy_now")

def replay(bars,start,end,policy,cap=CAP,cost_mult=1.):
    if policy not in POLICIES or start<WARMUP or end>len(bars) or end-start<2 or not 0<cap<=CAP or not .5<=cost_mult<=2:
        raise ValueError("Invalid research parameters")
    if any(bars[i][0]-bars[i-1][0]!=STEP for i in range(start-WARMUP+1,end)):
        raise ValueError("Candle gap: fail closed")
    cash=CASH;btc=0.;orders=[];last_buy=-1000000;last_tier=0
    equity=[]
    for i in range(start,end):
        mid=bars[i][1]
        high=max(b[4] for b in bars[i-WARMUP:i])
        dip=1-bars[i-1][4]/high
        tier=sum(dip>=t for t in (.05,.10,.20,.30,.40))
        if policy=="buy_now": buy=i==start
        elif policy=="dca_30d": buy=i==start or i-last_buy>=180
        elif policy=="hoard_tiered": buy=tier>last_tier and i-last_buy>=6
        else: buy=dip>=dict(hoard_5=.05,hoard_10=.10,hoard_20=.20)[policy] and i-last_buy>=180
        if buy and cash>1:
            budget=min(cap,.1*cash)
            if budget>=1:
                quantity=budget/(mid*(1+(SPREAD+SLIPPAGE)*cost_mult)*(1+FEE*cost_mult))
                entry_mid=quantity*mid
                fee=entry_mid*(1+(SPREAD+SLIPPAGE)*cost_mult)*FEE*cost_mult
                spread=entry_mid*SPREAD*cost_mult
                slip=entry_mid*SLIPPAGE*cost_mult
                debit=entry_mid+spread+slip+fee
                if debit>cap+1e-8 or debit>.1*cash+1e-8: raise AssertionError("Paper risk limit")
                cash-=debit;btc+=quantity;last_buy=i
                if policy=="hoard_tiered": last_tier=tier
                orders.append(dict(ts=bars[i][0],btc=quantity,debit=debit,mid=mid,fee=fee,spread=spread,slippage=slip,cash_before=cash+debit))
        equity.append(cash+btc*mid*(1-(SPREAD+SLIPPAGE)*cost_mult)*(1-FEE*cost_mult))
    final=bars[end-1][1]
    gross=btc*final-sum(o["btc"]*o["mid"] for o in orders)
    fees=sum(o["fee"] for o in orders)+btc*final*(1-(SPREAD+SLIPPAGE)*cost_mult)*FEE*cost_mult
    spread=sum(o["spread"] for o in orders)+btc*final*SPREAD*cost_mult
    slippage=sum(o["slippage"] for o in orders)+btc*final*SLIPPAGE*cost_mult
    net=gross-fees-spread-slippage
    if abs(cash+btc*final*(1-(SPREAD+SLIPPAGE)*cost_mult)*(1-FEE*cost_mult)-CASH-net)>1e-7:
        raise AssertionError("Gross-cost-NET mismatch")
    peak=CASH;dd=0.
    for v in equity:
        peak=max(peak,v);dd=min(dd,v/peak-1)
    return dict(policy=policy,buys=len(orders),sells=0,btc=btc,cash_aud=cash,
        gross_aud=gross,fees_aud=fees,spread_aud=spread,slippage_aud=slippage,
        net_liquidation_aud=net,return_pct=100*net/CASH,max_drawdown_pct=100*dd,
        average_entry_mid_aud=sum(o["btc"]*o["mid"] for o in orders)/btc if btc else None,
        orders=orders)

def evaluate(bars):
    folds=[]
    for a,b in segments(bars,1000):
        local=bars[a:b];n=len(local);te,vs,ve,ts=boundaries(n)
        train={p:replay(local,WARMUP,te,p) for p in POLICIES}
        val={p:replay(local,vs,ve,p) for p in POLICIES}
        eligible=[p for p in POLICIES if train[p]["net_liquidation_aud"]>0 and val[p]["net_liquidation_aud"]>0]
        selected=max(eligible,key=lambda p:val[p]["net_liquidation_aud"]) if eligible else "HOLD"
        test={p:replay(local,ts,n,p) for p in POLICIES}
        folds.append(dict(bars=n,selected_using_train_validation=selected,
            selected_test_net=0 if selected=="HOLD" else test[selected]["net_liquidation_aud"],
            test={p:{k:v for k,v in x.items() if k!="orders"} for p,x in test.items()},
            tiered_cap50_net=replay(local,ts,n,"hoard_tiered",cap=50.)["net_liquidation_aud"],
            tiered_half_cost_net=replay(local,ts,n,"hoard_tiered",cost_mult=.5)["net_liquidation_aud"],
            tiered_double_cost_net=replay(local,ts,n,"hoard_tiered",cost_mult=2.)["net_liquidation_aud"]))
    return dict(mode="PAPER_ONLY_PRIOR_INSPECTED_EXPLORATORY",folds=folds,policies=POLICIES,
        fee_bps_each_side=80,half_spread_bps_each_side=5,slippage_bps_each_side=5,
        cash_start_aud=1000,maximum_inclusive_entry_aud=100,
        valuation="HYPOTHETICAL_LIQUIDATION_VALUE_ONLY_NO_SELL_EXECUTED",
        promotion="NOT_ELIGIBLE_UNTOUCHED_OOS_NOT_ESTABLISHED")

def main():
    p=argparse.ArgumentParser();p.add_argument("--csv");p.add_argument("--output",default="audit/v43-hoarder.json");args=p.parse_args()
    if args.csv:
        raw=Path(args.csv).read_bytes();bars=parse_csv(raw)
        source=dict(source="LOCAL_CSV_UNVERIFIED",sha256=hashlib.sha256(raw).hexdigest())
    else: bars,source=archive()
    report=evaluate(bars);report["source"]=source
    out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,indent=2,allow_nan=False)+"\n")
    print(json.dumps(dict(folds=len(report["folds"]),selected=[f["selected_using_train_validation"] for f in report["folds"]],output=str(out))))
if __name__=="__main__": main()

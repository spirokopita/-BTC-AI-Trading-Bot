"""V45 PAPER ONLY: lot-aware long-cycle bulk selling; no permanent-hoard sales."""
import json
from pathlib import Path
from research.v33_cross_regime import archive
from research.v32_segments import segments
from research.v44_hoarder_grid import BUY,SELL,LOOKBACK,features,FEE,FRICTION,CASH

MIN_LOT_AGE=180 # 4h bars = 30 days; 1095 bars = 182.5 days
MIN_LOT_AGE=1095
MIN_PROFIT=1.15

def replay(bars,feat,start,end,buy_threshold,sell_level,split=.7,enable_sells=True,minimum_age=MIN_LOT_AGE):
    cash=CASH;hoard=0.;lots=[];buys=0;sells=0;lastbuy=-100000
    entry_fees=0.;exit_fees=0.;realised=0.;equity=[];sale_audit=[]
    for i in range(start,end):
        p=bars[i][1];dip,location=feat[i]
        # Sell first; independent lot age and per-lot cost basis. Buying today cannot reset eligibility.
        if enable_sells and location>=sell_level:
            eligible=[]
            for lot in lots:
                if i-lot["i"]<minimum_age:continue
                proceeds=lot["qty"]*p*(1-FRICTION)*(1-FEE)
                if proceeds>=lot["basis"]*MIN_PROFIT:eligible.append((lot,proceeds))
            if eligible:
                proceeds=sum(x[1] for x in eligible)
                cost=sum(x[0]["basis"] for x in eligible)
                cash+=proceeds;realised+=proceeds-cost
                exit_fees+=sum(x[0]["qty"]*p*(1-FRICTION)*FEE for x in eligible)
                ids={id(x[0]) for x in eligible}
                lots=[lot for lot in lots if id(lot) not in ids]
                sells+=1
                sale_audit.append(dict(ts=bars[i][0],lots=len(eligible),proceeds_aud=proceeds,
                    cost_basis_aud=cost,realised_net_aud=proceeds-cost))
        if dip>=buy_threshold and i-lastbuy>=180 and cash>=10:
            debit=min(100.,.1*cash)
            qty=debit/(p*(1+FRICTION)*(1+FEE))
            hoard+=qty*split
            lots.append(dict(i=i,qty=qty*(1-split),basis=debit*(1-split)))
            cash-=debit;entry_fees+=debit*FEE/(1+FEE);buys+=1;lastbuy=i
        trade=sum(l["qty"] for l in lots)
        equity.append(cash+(hoard+trade)*p*(1-FRICTION)*(1-FEE))
    peak=CASH;dd=0.
    for value in equity:peak=max(peak,value);dd=min(dd,value/peak-1)
    return dict(value_aud=round(equity[-1],3),net_aud=round(equity[-1]-CASH,3),
        buys=buys,bulk_sales=sells,hoard_btc=hoard,trade_btc=sum(l["qty"] for l in lots),
        remaining_lots=len(lots),cash_aud=round(cash,3),
        realised_net_aud=round(realised,3),fees_paid_aud=round(entry_fees+exit_fees,3),
        max_drawdown_pct=round(dd*100,3),sales=sale_audit)

def run(bars,source):
    folds=[]
    for a,b in segments(bars,1800):
        local=bars[a:b];n=len(local);feat=features(local);start=max(LOOKBACK,int(n*.6))
        if n-start<300:continue
        results=[]
        for dip in BUY:
            for sell in SELL:
                for split in (.7,.5):
                    active=replay(local,feat,start,n,dip,sell,split)
                    hold=replay(local,feat,start,n,dip,sell,split,enable_sells=False)
                    results.append(dict(buy_dip_pct=round(dip*100,4),sell_range_percentile=sell,
                        permanent_fraction=split,
                        active={k:v for k,v in active.items() if k!="sales"},
                        same_buy_rules_no_sell={k:v for k,v in hold.items() if k!="sales"},
                        sale_audit=active["sales"]))
        folds.append(dict(bars=n,start_ts=local[start][0],end_ts=local[-1][0],results=results))
    return dict(mode="PAPER_ONLY_EXPLORATORY_PRIOR_INSPECTED_DATA",source=source,folds=folds,
        execution="next 4h open after completed bars, 80bps taker and 10bps price friction per side",
        rules="Permanent hoard never sold; trade lots individually eligible >=182.5 days after purchase, >=15% net gain per lot, sell all eligible lots together at 70/80/90/95% of trailing 180-day low-high range. Each buy <=A$100 and <=10% remaining cash.",
        promotion="NOT_ELIGIBLE_NOT_UNTOUCHED_OOS")
def main():
    bars,source=archive();report=run(bars,source)
    out=Path("audit/v45-lot-aware-cycle-grid.json");out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(dict(folds=len(report["folds"]),
        combinations=[len(f["results"]) for f in report["folds"]],
        combinations_with_sales=[sum(x["active"]["bulk_sales"]>0 for x in f["results"]) for f in report["folds"]])))
if __name__=="__main__":main()

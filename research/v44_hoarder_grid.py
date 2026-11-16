"""PAPER ONLY exploratory grid: 10 dip thresholds x 4 sell levels on Kraken BTC/AUD."""
import json,math
from pathlib import Path
from research.v33_cross_regime import archive
from research.v32_segments import segments
STEP=14400
FEE=.008;FRICTION=.001;CASH=1000.;LOOKBACK=1080
BUY=[.02+i*(.03/9) for i in range(10)]
SELL=[.70,.80,.90,.95]
def features(bars):
    out=[None]*len(bars)
    for i in range(LOOKBACK,len(bars)):
        past=[b[4] for b in bars[i-LOOKBACK:i]]
        lo=min(past);hi=max(past)
        out[i]=(1-bars[i-1][4]/hi if hi>0 else 0,
                (bars[i-1][4]-lo)/(hi-lo) if hi>lo else .5)
    return out
def simulate(bars,feat,start,end,buy_threshold,sell_level,split=.7):
    cash=CASH;hoard=0.;trade=0.;basis=0.;lastbuy=-100000;lastsell=-100000
    buys=sells=0;equity=[];fees=0.
    for i in range(start,end):
        p=bars[i][1];dip,location=feat[i]
        if dip>=buy_threshold and i-lastbuy>=180 and cash>=10:
            debit=min(100.,cash*.1)
            qty=debit/(p*(1+FRICTION)*(1+FEE))
            hoard+=qty*split;trade+=qty*(1-split);basis+=debit*(1-split)
            cash-=debit;fees+=debit*FEE/(1+FEE);buys+=1;lastbuy=i
        if trade>0 and location>=sell_level and i-lastbuy>=1080 and i-lastsell>=1080:
            proceeds=trade*p*(1-FRICTION)*(1-FEE)
            if proceeds>=basis*1.15:
                cash+=proceeds;fees+=trade*p*(1-FRICTION)*FEE
                trade=0.;basis=0.;sells+=1;lastsell=i
        equity.append(cash+(hoard+trade)*p*(1-FRICTION)*(1-FEE))
    peak=CASH;dd=0
    for v in equity:peak=max(peak,v);dd=min(dd,v/peak-1)
    return dict(net_aud=round(equity[-1]-CASH,3),value_aud=round(equity[-1],3),
        buys=buys,bulk_sells=sells,hoard_btc=hoard,trade_btc=trade,cash_aud=round(cash,3),
        fees_paid_aud=round(fees,3),max_drawdown_pct=round(dd*100,3))
def main():
    bars,source=archive();folds=[]
    for a,b in segments(bars,1800):
        local=bars[a:b];n=len(local);feat=features(local);start=max(LOOKBACK,int(n*.6))
        if n-start<300:continue
        rows=[]
        for threshold in BUY:
            for sell in SELL:
                for split in (.7,.5):
                    r=simulate(local,feat,start,n,threshold,sell,split)
                    rows.append(dict(buy_dip_pct=round(threshold*100,4),sell_range_percentile=sell,
                        permanent_fraction=split,**r))
        folds.append(dict(bars=n,start_ts=local[start][0],end_ts=local[-1][0],results=rows))
    report=dict(mode="PAPER_ONLY_EXPLORATORY_PREVIOUSLY_INSPECTED_DATA",source=source,
        methodology="180d completed-bar high for buy dip; 180d completed-bar low-high position for bulk sale; 180d cooldown; >=15% trade reserve cost basis profit; 80bps taker and 10bps execution friction each side; no forced sales; mark only",
        folds=folds,selection="NONE_GRID_EXPLORATORY_NO_OOS_PROMOTION")
    p=Path("audit/v44-hoarder-cycle-grid.json");p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps({"folds":len(folds),"rows":[len(f["results"]) for f in folds],
      "bulk_sale_rows":[sum(r["bulk_sells"]>0 for r in f["results"]) for f in folds]}))
if __name__=="__main__":main()

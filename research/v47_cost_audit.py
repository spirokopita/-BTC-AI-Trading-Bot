"""V47 reproducible historical lot-aware A50/A100 cost sensitivity, exploratory."""
import json
from pathlib import Path
from research.v33_cross_regime import archive
from research.v32_segments import segments
from research.v44_hoarder_grid import features,LOOKBACK
from research.v45_lot_aware_cycle import replay

def evaluate(bars,source):
    result=[]
    for a,b in segments(bars,1800):
        local=bars[a:b];n=len(local);start=max(LOOKBACK,int(n*.6))
        if n-start<300:continue
        feat=features(local)
        for cap in (50.,100.):
            for sell in (.7,.9):
                for fraction in (.5,.7):
                    active=replay(local,feat,start,n,.04,sell,fraction,max_entry_debit=cap)
                    hold=replay(local,feat,start,n,.04,sell,fraction,enable_sells=False,max_entry_debit=cap)
                    assert active["fees_paid_aud"]>=0 and active["spread_paid_aud"]>=0 and active["slippage_paid_aud"]>=0
                    assert active["hoard_btc"]>=0
                    result.append(dict(segment_bars=n,cap_aud=cap,sell_threshold=sell,
                        permanent_fraction=fraction,active=active,hold=hold,
                        delta_net_aud=round(active["net_aud"]-hold["net_aud"],3)))
    return dict(source=source,mode="PAPER_ONLY_PREVIOUSLY_INSPECTED_EXPLORATORY",selection="HOLD_NO_PROMOTION",
        note="Gross is not reconstructed: unrealised mark-to-market and entry/exit friction are separately recorded. Do not equate mark-to-market net with realised trading P&L.",results=result)
def main():
    bars,source=archive();r=evaluate(bars,source)
    p=Path("audit/v47-cost-audit.json");p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(r,indent=2)+"\n")
    print(json.dumps(dict(rows=len(r["results"]),bulk_sale_rows=sum(x["active"]["bulk_sales"]>0 for x in r["results"]))))
if __name__=="__main__":main()

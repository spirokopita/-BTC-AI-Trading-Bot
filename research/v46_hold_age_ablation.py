"""V46 exploratory hold-age ablation on official Kraken BTC/AUD, PAPER ONLY.

Frozen 2/3/4/5% dip entries, 70/90% trailing-range exit gates,
50/70% permanent reserves; compare 90/180/365-day trade-lot ages
against identical buy rules with no sales. Never promote from inspected data.
"""
import json
from pathlib import Path
from research.v33_cross_regime import archive
from research.v32_segments import segments
from research.v44_hoarder_grid import features,LOOKBACK
from research.v45_lot_aware_cycle import replay
DIPS=(.02,.03,.04,.05)
EXITS=(.70,.90)
SPLITS=(.5,.7)
AGES=(540,1080,2190) # 4h bars: 90, 180, 365 days
def study(bars,source):
    out=[]
    for a,b in segments(bars,1800):
        local=bars[a:b];n=len(local);start=max(LOOKBACK,int(n*.6))
        if n-start<300:continue
        f=features(local);rows=[]
        for dip in DIPS:
            for exit_level in EXITS:
                for split in SPLITS:
                    hold=replay(local,f,start,n,dip,exit_level,split,enable_sells=False)
                    for age in AGES:
                        trade=replay(local,f,start,n,dip,exit_level,split,minimum_age=age)
                        rows.append(dict(buy_dip_pct=dip*100,exit_level=exit_level,
                            permanent_fraction=split,minimum_age_days=age/6,
                            trades=trade["bulk_sales"],gross_proceeds_minus_basis_aud=trade["realised_net_aud"],
                            net_marked_value_aud=trade["value_aud"],
                            no_sell_marked_value_aud=hold["value_aud"],
                            incremental_net_aud=round(trade["value_aud"]-hold["value_aud"],3),
                            fees_paid_aud=trade["fees_paid_aud"],
                            max_drawdown_pct=trade["max_drawdown_pct"]))
        out.append(dict(bars=n,start_ts=local[start][0],end_ts=local[-1][0],rows=rows))
    return dict(mode="PAPER_ONLY_EXPLORATORY_NOT_UNTOUCHED",source=source,
        fee_model="80bps taker + 10bps execution friction per side; net marked liquidation",
        sizing="A$100 or 10% cash max inclusive per entry; A$1000 reset per fold",
        folds=out,policy="HOLD_NO_ANDROID_PROMOTION",
        limitations=["Retrospectively inspected archive; no untouched OOS",
                     "Only 40% of each segment evaluated; 365-day sales may be impossible",
                     "No historical news joined: no claim of news predictiveness",
                     "Open-price proxy, not verified fills; fees and spread approximate"])
def main():
    bars,source=archive();report=study(bars,source)
    p=Path("audit/v46-hold-age-ablation.json");p.parent.mkdir(exist_ok=True)
    p.write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(dict(folds=len(report["folds"]),rows=[len(f["rows"]) for f in report["folds"]],
        sale_configurations=[sum(r["trades"]>0 for r in f["rows"]) for f in report["folds"]],
        positive_vs_hold=[sum(r["incremental_net_aud"]>0 for r in f["rows"]) for f in report["folds"]])))
if __name__=="__main__":main()

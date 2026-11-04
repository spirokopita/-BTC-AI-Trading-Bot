"""V33: cross-regime train/validation/test, retrospective news ablations.
PAPER research only. Prior-inspected archive means NO untouched OOS or promotion.
"""
from __future__ import annotations
import argparse, hashlib, json, zipfile
from datetime import datetime, timezone
from pathlib import Path
from research.v32_segments import segments
from research.v31_hysteresis import WARMUP, PARAMS, VARIANTS, replay, choose
from research.v29_point_in_time import simulate, buyhold, news_load, ts
from research.kraken_archive import parse_csv, HttpParts, MultipartReader, member_name

EMBARGO=20
BASELINES=("sma","momentum","rsi","breakout","regime","trend_breakout")

def historical_news(base="data/historical_news_reconstructed.json",
                    supplement="data/historical_news_supplement_v31.json"):
    first,sha=news_load(base)
    raw=Path(supplement).read_bytes()
    doc=json.loads(raw)
    if doc.get("dataset_type")!="RETROSPECTIVE_CONVENIENCE_SAMPLE_NOT_FIRST_OBSERVED_NOT_REPRESENTATIVE":
        raise ValueError("Unverified news provenance")
    seen=set()
    extra=[]
    for row in doc["articles"]:
        if row["cluster"] in seen: continue
        seen.add(row["cluster"])
        published=ts(row["published_at_utc"])
        updated=ts(row.get("updated_at_utc",row["published_at_utc"]))
        if updated<published or not row["url"].startswith("https://"):
            raise ValueError("Invalid historical publication metadata")
        extra.append(dict(id=row["id"],category=row["category"],
            sentiment=row["polarity"],available_ts=updated+86400,
            cluster=row["cluster"],source=row["source"],url=row["url"]))
    # This is retrospective publication-time reconstruction, NEVER first-observed.
    return sorted(first+extra,key=lambda e:e["available_ts"]),dict(
        base_sha256=sha,supplement_sha256=hashlib.sha256(raw).hexdigest(),
        original_events=len(first),supplement_clusters=len(extra),
        availability="BASE latest revision +1h; SUPPLEMENT latest known revision +24h",
        provenance="RETROSPECTIVE_NOT_FIRST_OBSERVED_CONVENIENCE_SAMPLE")

def boundaries(n):
    if n<1000: raise ValueError("Need >=1000 continuous bars")
    train_end=n//2
    val_start=train_end+EMBARGO
    val_end=int(n*.70)-EMBARGO
    test_start=int(n*.70)
    if train_end-WARMUP<100 or val_end-val_start<100 or n-test_start<100:
        raise ValueError("Insufficient embargoed chronological history")
    return train_end,val_start,val_end,test_start

def one_segment(local,events):
    n=len(local)
    train_end,val_start,val_end,test_start=boundaries(n)
    train={k:replay(local,WARMUP,train_end,k,events) for k in PARAMS}
    val={k:replay(local,val_start,val_end,k,events) for k in PARAMS}
    selected=choose(train,val)
    tests={}
    for name in VARIANTS:
        raw=replay(local,test_start,n,name,events,audit=True)
        # Preserve each completed trade and its cost audit, not thousands of redundant HOLD rows.
        raw.pop("decision_audit",None)
        tests[name]=raw
    baseline={k:simulate(local,test_start,n,k,events) for k in BASELINES}
    sensitivity={k:{str(m):replay(local,test_start,n,k,events,cost_mult=m)["net_aud"]
                    for m in (.5,1.,2.)} for k in PARAMS}
    test_first=local[test_start][0]
    test_last=local[-1][0]
    return dict(bars=n,
        first_utc=datetime.fromtimestamp(local[0][0],timezone.utc).isoformat(),
        last_utc=datetime.fromtimestamp(local[-1][0],timezone.utc).isoformat(),
        train_end_utc=datetime.fromtimestamp(local[train_end-1][0],timezone.utc).isoformat(),
        validation_start_utc=datetime.fromtimestamp(local[val_start][0],timezone.utc).isoformat(),
        validation_end_utc=datetime.fromtimestamp(local[val_end-1][0],timezone.utc).isoformat(),
        test_start_utc=datetime.fromtimestamp(test_first,timezone.utc).isoformat(),
        test_end_utc=datetime.fromtimestamp(test_last,timezone.utc).isoformat(),
        embargo_bars=EMBARGO,training=train,validation=val,
        train_validation_selected=selected,
        selected_test_net_aud=tests[selected]["net_aud"] if selected!="HOLD" else 0,
        test=tests,price_baselines=baseline,fee_sensitivity=sensitivity,
        buyhold_aud100_net=buyhold(local,test_start,n),
        test_market_open_return_pct=round((local[-1][1]/local[test_start][1]-1)*100,6),
        news_events_available_during_test=sum(test_first<=e["available_ts"]<=test_last for e in events),
        news_ablation_delta_aud=round(tests["h50_200_news"]["net_aud"]-tests["h50_200"]["net_aud"],6),
        shifted_placebo_delta_aud=round(tests["h50_200_placebo"]["net_aud"]-tests["h50_200"]["net_aud"],6))

def evaluate(bars,provenance,events,news_provenance):
    slices=segments(bars,1000)
    folds=[one_segment(bars[a:b],events) for a,b in slices]
    names=VARIANTS
    aggregates={k:{field:round(sum(f["test"][k][field] for f in folds),6)
                   for field in ("trades","wins","losses","gross_aud","fees_aud",
                                 "spread_aud","slippage_aud","net_aud")}
                for k in names}
    return dict(mode="V33_PAPER_ONLY_EXPLORATORY_PRIOR_INSPECTED",
        source=provenance,news_provenance=news_provenance,
        historical_events=len(events),eligible_segments=len(slices),
        fee_bps_per_side=dict(taker=80,half_spread=5,slippage=5),
        starting_cash_aud=1000,max_entry_debit_aud=100,
        selection="TRAIN_AND_VALIDATION_ONLY_WITH_20_BAR_EMBARGO",
        folds=folds,aggregate_independently_reset_accounts=aggregates,
        aggregate_buyhold_net_aud=round(sum(f["buyhold_aud100_net"] for f in folds),6),
        selected_paper_policy="HOLD",android_promotion="REJECTED_NOT_UNTOUCHED_OOS",
        limitations=["Previously inspected prices; chronological replay is not untouched OOS",
                     "Retrospective manually selected headlines cannot prove historical availability",
                     "News controls may change zero trades; no news predictive claim",
                     "No intrabar stops, order book or observed execution fills",
                     "All segments have separate A$1000 starting accounts; sums not compounded"])

def archive():
    store=HttpParts()
    with zipfile.ZipFile(MultipartReader(store.lengths,store.read)) as z:
        name=member_name(z.namelist());info=z.getinfo(name)
        if info.file_size>30000000: raise ValueError("Archive member too large")
        with z.open(info) as f: raw=f.read(30000001)
        if len(raw)!=info.file_size: raise IOError("Archive member truncated")
    return parse_csv(raw),dict(source="OFFICIAL_KRAKEN_FULL_OHLCVT_ARCHIVE",
        member=name,member_crc32=f"{info.CRC:08x}",
        member_sha256=hashlib.sha256(raw).hexdigest(),
        full_archive_sha256_verified=False)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--csv",default=None)
    p.add_argument("--output",default="audit/v33-cross-regime.json")
    args=p.parse_args()
    if args.csv:
        raw=Path(args.csv).read_bytes()
        bars=parse_csv(raw)
        provenance=dict(source="LOCAL_CSV_UNVERIFIED",sha256=hashlib.sha256(raw).hexdigest())
    else:
        bars,provenance=archive()
    events,news_provenance=historical_news()
    report=evaluate(bars,provenance,events,news_provenance)
    out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,indent=2,allow_nan=False)+"\n")
    print(json.dumps(dict(output=str(out),segments=report["eligible_segments"],
                          news=report["historical_events"],policy="HOLD")))
if __name__=="__main__":main()

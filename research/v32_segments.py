"""V32: deterministic gap-isolated market-regime coverage; PAPER research only.
No performance-based segment selection. All outputs are exploratory, never promotion evidence.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from research.kraken_archive import load, STEP
from research.v31_hysteresis import replay, PARAMS, WARMUP
from research.v29_point_in_time import buyhold, simulate

def segments(bars, minimum=1000):
    if minimum < 1: raise ValueError("minimum must be positive")
    if any(bars[i][0] <= bars[i-1][0] for i in range(1,len(bars))):
        raise ValueError("timestamps must increase")
    cuts=[0]+[i for i in range(1,len(bars)) if bars[i][0]-bars[i-1][0]!=STEP]+[len(bars)]
    return [(a,b) for a,b in zip(cuts,cuts[1:]) if b-a>=minimum]

def evaluate(bars, provenance):
    chosen=segments(bars,1000)
    reports=[]
    for a,b in chosen:
        local=bars[a:b]
        # Fixed, chronological 70/30 partition; 305 completed-bar warmup.
        start=max(WARMUP,int(len(local)*.70))
        if len(local)-start<3: continue
        result={name:replay(local,start,len(local),name) for name in PARAMS}
        baseline=simulate(local,start,len(local),"trend_breakout")
        hold=buyhold(local,start,len(local))
        reports.append(dict(start_utc=datetime.fromtimestamp(local[0][0],timezone.utc).isoformat(),
            end_utc=datetime.fromtimestamp(local[-1][0],timezone.utc).isoformat(),
            bars=len(local),test_bars=len(local)-start,
            test_start_utc=datetime.fromtimestamp(local[start][0],timezone.utc).isoformat(),
            hysteresis=result,trend_breakout=baseline,buyhold_aud100_net=hold))
    return dict(mode="PAPER_ONLY_V32_EXPLORATORY_NOT_UNTOUCHED_OOS",
        source=provenance,segments_eligible=len(chosen),segments_evaluated=len(reports),
        segments=reports,selected_policy="HOLD",promotion="NOT_ELIGIBLE",
        notes=["No performance-based segment selection; excludes shorter runs and never bridges gaps",
        "Test partition is chronological but historical prices were previously inspected",
        "Each segment resets A$1000; never sum as a compounded account",
        "Current 80bps taker plus 5bps half-spread and 5bps slippage each side",
        "No new historical news signal evaluated; no claimed news edge"])

def main():
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("--csv")
    p.add_argument("--output",default="audit/v32-segment-coverage.json")
    args=p.parse_args()
    # load() intentionally returns longest segment; CSV fixture path is needed for all segments.
    # For official archive, use the full-member extraction API in a subsequent verified run.
    if not args.csv:
        raise SystemExit("Full archive segment access not yet exposed by kraken_archive.load; no partial run disguised as full coverage")
    from research.kraken_archive import parse_csv
    raw=Path(args.csv).read_bytes()
    import hashlib
    bars=parse_csv(raw)
    result=evaluate(bars,dict(source="LOCAL_CSV_UNVERIFIED",sha256=hashlib.sha256(raw).hexdigest()))
    out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(dict(segments=result["segments_evaluated"],output=str(out))))
if __name__=="__main__":main()

"""V48 historical-news proof gate: NO retrospective availability inference.
PAPER research only. An article's publication/update timestamp is not proof
that the exact content version was independently captured before a trade.
"""
from __future__ import annotations
import hashlib,json
from datetime import datetime,timezone
from pathlib import Path

def epoch(value):
    if isinstance(value,bool):raise ValueError("Boolean timestamp")
    if isinstance(value,(int,float)):
        if not 0<value<4102444800:raise ValueError("Timestamp outside supported range")
        return float(value)
    if not isinstance(value,str):raise ValueError("Timestamp missing")
    d=datetime.fromisoformat(value.replace("Z","+00:00"))
    if d.tzinfo is None:raise ValueError("Timezone required")
    return d.timestamp()

def classify(row,decision_ts,latency_seconds=3600):
    """Fail closed: version-specific independent capture AND release must precede decision."""
    decision=epoch(decision_ts)
    if latency_seconds<0:raise ValueError("Negative latency")
    result=dict(eligible=False,reason=None)
    if row.get("capture_type") not in ("independent_warc","first_observed_snapshot","official_original_release"):
        result["reason"]="NO_INDEPENDENT_CAPTURE_PROOF";return result
    if not row.get("content_sha256") or len(row["content_sha256"])!=64:
        result["reason"]="NO_VERSION_HASH";return result
    try:
        published=epoch(row["published_at_utc"])
        updated=epoch(row.get("updated_at_utc") or row["published_at_utc"])
        capture=epoch(row["verified_capture_at_utc"])
        retrieved=epoch(row["retrieved_at_utc"])
    except (ValueError,TypeError,KeyError):
        result["reason"]="INVALID_PROVENANCE_TIME";return result
    if updated<published or capture<published or retrieved<capture:
        result["reason"]="INCONSISTENT_CHRONOLOGY";return result
    # Capture must contain the exact hashed article version; future updates cannot leak.
    if max(updated,capture)+latency_seconds>decision:
        result["reason"]="VERSION_NOT_YET_AVAILABLE";return result
    if row.get("version_capture_sha256")!=row["content_sha256"]:
        result["reason"]="UNMATCHED_CAPTURE_VERSION";return result
    result.update(eligible=True,reason="VERIFIED_AS_OF",available_at_utc=max(updated,capture)+latency_seconds)
    return result

def join(records,bar_open_timestamps,latency_seconds=3600):
    """Sorted, gap-safe as-of eligibility; no price/return fields used for selection."""
    ts=[epoch(t) for t in bar_open_timestamps]
    if any(b<=a for a,b in zip(ts,ts[1:])):raise ValueError("Non-monotonic bars")
    output=[]
    for bar in ts:
        eligible=[]
        counts={}
        for row in records:
            proof=classify(row,bar,latency_seconds)
            counts[proof["reason"]]=counts.get(proof["reason"],0)+1
            if proof["eligible"]:eligible.append(row["url"])
        output.append(dict(decision_ts=bar,verified_urls=sorted(set(eligible)),rejection_counts=counts))
    return output

def main():
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("--records",required=True)
    p.add_argument("--bar-opens",required=True)
    p.add_argument("--output",default="audit/v48-news-proof-gate.json")
    a=p.parse_args()
    records=[json.loads(s) for s in Path(a.records).read_text().splitlines() if s.strip()]
    bars=json.loads(Path(a.bar_opens).read_text())
    joined=join(records,bars)
    result=dict(mode="PAPER_ONLY",provenance="INDEPENDENT_VERSION_CAPTURE_REQUIRED",
        record_count=len(records),bars=len(bars),eligible_bar_matches=sum(len(r["verified_urls"]) for r in joined),
        source_sha256=hashlib.sha256(Path(a.records).read_bytes()).hexdigest(),joins=joined)
    dest=Path(a.output);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps({k:result[k] for k in ("record_count","bars","eligible_bar_matches")}))
if __name__=="__main__":main()

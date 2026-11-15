"""V48 historical-news proof gate: NO retrospective availability inference.
PAPER research only. An article's publication/update timestamp is not proof
that the exact content version was independently captured before a trade.
"""
from __future__ import annotations
import hashlib,json,re
from urllib.parse import urlsplit
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
    """Fail-closed proof for SHA256 snapshots or Common Crawl CDX SHA1 captures."""
    result={"eligible":False,"reason":None,"available_at_utc":None,
            "hash_algorithm":None}
    try:
        decision=epoch(decision_ts)
    except Exception:
        result["reason"]="INVALID_DECISION_TIME";return result
    if not isinstance(latency_seconds,(int,float)) or latency_seconds<0:
        result["reason"]="INVALID_LATENCY";return result
    url=row.get("url")
    parsed=urlsplit(url) if isinstance(url,str) else None
    if parsed is None or parsed.scheme!="https" or not parsed.netloc:
        result["reason"]="INVALID_URL";return result
    capture_type=row.get("capture_type")

    if capture_type=="common_crawl_index_digest":
        digest=row.get("version_hash")
        if (row.get("capture_source")!="common_crawl"
                or row.get("version_hash_algorithm")!="sha1_base32"):
            result["reason"]="NO_INDEPENDENT_CAPTURE_PROOF";return result
        if not isinstance(digest,str) or not re.fullmatch(r"[A-Z2-7]{32}",digest):
            result["reason"]="NO_VERSION_HASH";return result
        reference=row.get("capture_reference")
        index_version=row.get("index_version")
        if (not isinstance(reference,str) or "/warc/" not in reference
                or not isinstance(index_version,str)
                or not index_version.startswith("CC-MAIN-")):
            result["reason"]="INVALID_CAPTURE_REFERENCE";return result
        published=epoch(row.get("published_at_utc"))
        updated=epoch(row.get("updated_at_utc"))
        capture=epoch(row.get("verified_capture_at_utc"))
        retrieved=epoch(row.get("retrieved_at_utc"))
        if capture is None or retrieved is None:
            result["reason"]="INVALID_PROVENANCE_TIME";return result
        if ((published is not None and capture<published)
                or (published is not None and updated is not None and updated<published)
                or (updated is not None and updated>retrieved)
                or retrieved<capture):
            result["reason"]="INCONSISTENT_CHRONOLOGY";return result
        available=max(capture,published or capture,updated or capture)+latency_seconds
        result["hash_algorithm"]="sha1_base32"
        result["version_hash"]=digest
    else:
        if capture_type not in ("independent_warc","first_observed_snapshot",
                                "official_original_release"):
            result["reason"]="NO_INDEPENDENT_CAPTURE_PROOF";return result
        digest=row.get("content_sha256")
        if not isinstance(digest,str) or not re.fullmatch(r"[0-9a-fA-F]{64}",digest):
            result["reason"]="NO_VERSION_HASH";return result
        captured_digest=row.get("version_capture_sha256")
        if (not isinstance(captured_digest,str)
                or not re.fullmatch(r"[0-9a-fA-F]{64}",captured_digest)
                or captured_digest.lower()!=digest.lower()):
            result["reason"]="UNMATCHED_CAPTURE_VERSION";return result
        published=epoch(row.get("published_at_utc"))
        updated=epoch(row.get("updated_at_utc") or row.get("published_at_utc"))
        capture=epoch(row.get("verified_capture_at_utc"))
        retrieved=epoch(row.get("retrieved_at_utc"))
        if None in (published,updated,capture,retrieved):
            result["reason"]="INVALID_PROVENANCE_TIME";return result
        if updated<published or capture<published or retrieved<capture:
            result["reason"]="INCONSISTENT_CHRONOLOGY";return result
        available=max(published,updated,capture)+latency_seconds
        result["hash_algorithm"]="sha256"
        result["version_hash"]=digest

    result["available_at_utc"]=available
    if available>decision:
        result["reason"]="VERSION_NOT_YET_AVAILABLE";return result
    result["eligible"]=True
    result["reason"]="OK_ASOF"
    return result

def join(records,bar_open_timestamps,latency_seconds=3600,expected_step_seconds=14400):
    """Strict 4h gap-safe as-of eligibility; no price/return fields used for selection."""
    if expected_step_seconds<=0:raise ValueError("Invalid expected bar step")
    ts=[epoch(t) for t in bar_open_timestamps]
    if any(b<=a for a,b in zip(ts,ts[1:])):raise ValueError("Non-monotonic bars")
    if any(b-a!=expected_step_seconds for a,b in zip(ts,ts[1:])):
        raise ValueError("Gap or irregular bar spacing")
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

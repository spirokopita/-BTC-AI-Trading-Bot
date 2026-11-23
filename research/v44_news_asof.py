"""Strict proof-gated point-in-time news version selector. PAPER research only."""
from datetime import datetime, timezone
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

def seconds(value):
    if not isinstance(value,str): raise ValueError("timestamp required")
    dt=datetime.fromisoformat(value.replace("Z","+00:00"))
    if dt.tzinfo is None: raise ValueError("timezone required")
    return dt.astimezone(timezone.utc).timestamp()

def canonical(url):
    p=urlsplit(url)
    if p.scheme.lower() not in ("http","https") or not p.hostname: raise ValueError("invalid URL")
    query=urlencode(sorted((k,v) for k,v in parse_qsl(p.query,keep_blank_values=True) if not k.lower().startswith("utm_")))
    return urlunsplit((p.scheme.lower(),p.hostname.lower()+((":"+str(p.port)) if p.port and p.port not in (80,443) else ""),p.path or "/",query,""))

def validate(row):
    keys=("url","published_at","capture_at","retrieved_at","captured_sha256","version_id")
    if any(not row.get(k) for k in keys): raise ValueError("missing capture evidence")
    h=row["captured_sha256"]
    if len(h)!=64 or any(c not in "0123456789abcdef" for c in h): raise ValueError("bad SHA256")
    pub,cap,ret=(seconds(row[k]) for k in ("published_at","capture_at","retrieved_at"))
    if cap<pub or ret<cap: raise ValueError("invalid chronology")
    if row.get("updated_at") and seconds(row["updated_at"])>cap: raise ValueError("future revision")
    return canonical(row["url"]),cap

def asof_versions(rows,decision_at,latency_seconds=0):
    if not isinstance(latency_seconds,(int,float)) or not 0 <= latency_seconds < float("inf"):
        raise ValueError("latency must be finite and nonnegative")
    cutoff=seconds(decision_at)-latency_seconds
    selected={}
    for row in rows:
        try: url,cap=validate(row)
        except (ValueError,TypeError,OverflowError,AttributeError): continue
        if cap>cutoff: continue
        key=(cap,str(row["version_id"]))
        if url not in selected or key>selected[url][0]: selected[url]=(key,row)
    return [selected[url][1] for url in sorted(selected)]

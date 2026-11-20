"""Research-only as-of eligibility audit; never infers first observation from publication."""
from collections import Counter
from .v44_news_asof import validate, seconds

def eligibility_audit(rows, decision_at, latency_seconds=0):
    """Count version-level eligibility and failures without exposing unavailable rows."""
    if not isinstance(latency_seconds,(int,float)) or not 0 <= latency_seconds < float("inf"):
        raise ValueError("latency must be finite and nonnegative")
    cutoff=seconds(decision_at)-latency_seconds
    counts=Counter()
    eligible=[]
    for row in rows:
        try:
            url, captured=validate(row)
        except (ValueError,TypeError,OverflowError,AttributeError):
            counts["invalid_or_unproven"]+=1
            continue
        if captured>cutoff:
            counts["future_capture"]+=1
            continue
        counts["eligible_versions"]+=1
        eligible.append((url,captured,str(row["version_id"])))
    counts["eligible_unique_urls"]=len({x[0] for x in eligible})
    counts["total_rows"]=len(rows)
    return dict(counts)

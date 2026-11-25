"""V41 deterministic monthly archive cursor. PAPER ONLY. No invented first-observed times."""
import json
from pathlib import Path
MONTHS=tuple(f"{y}-{m:02d}" for y in range(2020,2027) for m in range(1,13) if f"{y}-{m:02d}"<="2026-10")
QUARTERLY={f"{y}-{m:02d}" for y in range(2020,2027) for m in (1,4,7,10) if f"{y}-{m:02d}"<="2026-10"}
V40=tuple(f"{y}-{m:02d}" for m in (2,5) for y in range(2020,2027) if f"{y}-{m:02d}"<="2026-10")[:12]
def seed():
    return {"schema":"monthly_cursor_v1","months":{m:{"status":"complete","count":None,"provenance":"V39/V40 verified request; individual count not imported"} for m in sorted(QUARTERLY|set(V40))}}
def validate(state):
    if state.get("schema")!="monthly_cursor_v1": raise ValueError("schema")
    for m,v in state.get("months",{}).items():
        if m not in MONTHS or v.get("status") not in ("complete","empty","failed"): raise ValueError("month/status")
        if v.get("count") is not None and (not isinstance(v["count"],int) or v["count"]<0): raise ValueError("count")
    return state
def plan(state,limit=12,retry_failed=True):
    validate(state)
    if not 1<=limit<=12: raise ValueError("limit")
    return tuple(m for m in MONTHS if state["months"].get(m,{}).get("status") not in (("complete","empty") if retry_failed else ("complete","empty","failed")))[:limit]
def record(state,month,note,count,retrieved_at):
    validate(state)
    if month not in MONTHS or not isinstance(count,int) or count<0: raise ValueError("observation")
    if state["months"].get(month,{}).get("status") in ("complete","empty"): raise ValueError("already complete")
    from datetime import datetime
    if datetime.fromisoformat(retrieved_at.replace("Z","+00:00")).tzinfo is None: raise ValueError("naive timestamp")
    ok=note=="OK_DATE_FILTERS_VERIFIED"
    state["months"][month]={"status":("empty" if count==0 else "complete") if ok else "failed","count":count if ok else None,"source_status":note,"retrieved_at_utc":retrieved_at}
    return state
def main():
    import argparse
    p=argparse.ArgumentParser();p.add_argument("--state",default="data/monthly_sampling_cursor.json");a=p.parse_args()
    f=Path(a.state);state=validate(json.loads(f.read_text())) if f.exists() else seed()
    print(json.dumps({"next_months":plan(state),"completed":sum(v["status"] in ("complete","empty") for v in state["months"].values()),"total_months":len(MONTHS)}))
if __name__=="__main__": main()

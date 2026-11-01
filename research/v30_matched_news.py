"""PAPER ONLY: retrospective BTC/AUD news vs strictly prior matched controls.
Selected historical articles are NOT first-observed records or causal evidence.
"""
from __future__ import annotations
import argparse, bisect, itertools, json, math, statistics
from pathlib import Path
from research.v29_point_in_time import STEP, FEE, SPREAD, SLIPPAGE, news_load

LOOKBACK = 42  # 7 days of completed four-hour candles
EXCLUSION = 42  # exclude +/- 7 days around known news
MAX_BACK = 1080  # 180 days; strictly past, never future
HORIZONS = (1, 6, 12)

def pre_open_state(bars, i):
    """At open i, read only completed candles with index < i."""
    if i < LOOKBACK + 7: return None
    closes = [bars[j][4] for j in range(i-LOOKBACK-1, i)]
    if any(p <= 0 for p in closes): raise ValueError('Invalid price')
    returns = [math.log(closes[j]/closes[j-1]) for j in range(1,len(closes))]
    return dict(vol=statistics.pstdev(returns), prior_24h=closes[-1]/closes[-7]-1,
                prior_7d=closes[-1]/closes[0]-1)

def roundtrip_pct(bars, i, horizon):
    """Hypothetical long spot roundtrip with 80bps taker and separate execution costs."""
    a,b=bars[i][1],bars[i+horizon][1]
    return 100*((b/a)*(1-SPREAD-SLIPPAGE)*(1-FEE)/
                ((1+SPREAD+SLIPPAGE)*(1+FEE))-1)

def available_open_index(times, available_ts):
    return bisect.bisect_left(times,available_ts)

def select_controls(bars, event_i, excluded_indices, count=5):
    """Same UTC weekday/4h slot; prior 24h direction and prior 7d volatility.

    Matching uses ONLY data available at each candidate's open. All candidate
    control dates are earlier than the event. This is a descriptive control,
    not a deployable trade-selection algorithm.
    """
    if count < 1: raise ValueError('count must be positive')
    state=pre_open_state(bars,event_i)
    if state is None: return []
    options=[]
    for j in range(max(LOOKBACK+7,event_i-MAX_BACK),event_i-EXCLUSION):
        if (event_i-j)%LOOKBACK: continue
        if any(abs(j-k)<=EXCLUSION for k in excluded_indices): continue
        other=pre_open_state(bars,j)
        if other is None: continue
        same_sign=(state['prior_24h']>=0)==(other['prior_24h']>=0)
        distance=abs(math.log((other['vol']+1e-9)/(state['vol']+1e-9)))
        options.append(((not same_sign,distance,event_i-j),j))
    return [j for _,j in sorted(options)[:count]]

def signflip_pvalue(differences):
    """Descriptive exact two-sided sign-flip; NOT a causal significance test."""
    n=len(differences)
    if n==0 or n>18: return None
    observed=abs(sum(differences))
    total=extreme=0
    for signs in itertools.product((-1,1),repeat=n):
        total+=1
        if abs(sum(s*x for s,x in zip(signs,differences)))>=observed-1e-12:
            extreme+=1
    return round(extreme/total,6)

def matched_study(bars, events, count=5):
    times=[b[0] for b in bars]
    if any(times[j]-times[j-1]!=STEP for j in range(1,len(times))):
        raise ValueError('Gaps: do not interpolate market candles')
    if any(t%STEP for t in times): raise ValueError('Unaligned candles')
    eligible=[];excluded=[];omissions=[]
    for e in events:
        i=available_open_index(times,e['available_ts'])
        if i<LOOKBACK+7 or i+max(HORIZONS)>=len(bars):
            omissions.append(dict(id=e['id'],reason='Outside price coverage/warmup'))
            continue
        if times[i]<e['available_ts']: raise AssertionError('Publication leakage')
        eligible.append((e,i));excluded.append(i)
    rows=[]
    for e,i in eligible:
        matches=select_controls(bars,i,excluded,count)
        if not matches:
            omissions.append(dict(id=e['id'],reason='No prior matched controls'))
            continue
        for h in HORIZONS:
            actual=roundtrip_pct(bars,i,h)
            benchmark=statistics.mean(roundtrip_pct(bars,j,h) for j in matches)
            rows.append(dict(id=e['id'],category=e['category'],sentiment=e['sentiment'],
                available_ts=e['available_ts'],event_open_ts=times[i],
                horizon_bars=h,control_count=len(matches),
                control_open_ts=[times[j] for j in matches],
                event_net_pct=round(actual,6),control_mean_net_pct=round(benchmark,6),
                excess_net_pct=round(actual-benchmark,6),
                direction_aligned_excess_pct=round(e['sentiment']*(actual-benchmark),6)))
    summary=[]
    for h in HORIZONS:
        rr=[r for r in rows if r['horizon_bars']==h]
        if not rr: continue
        aligned=[r['direction_aligned_excess_pct'] for r in rr]
        summary.append(dict(horizon_bars=h,n_events=len(rr),
            mean_event_net_pct=round(statistics.mean(r['event_net_pct'] for r in rr),6),
            mean_control_net_pct=round(statistics.mean(r['control_mean_net_pct'] for r in rr),6),
            mean_excess_net_pct=round(statistics.mean(r['excess_net_pct'] for r in rr),6),
            mean_direction_aligned_excess_pct=round(statistics.mean(aligned),6),
            direction_aligned_positive=sum(x>0 for x in aligned),
            descriptive_signflip_p=signflip_pvalue(aligned)))
    return dict(rows=rows,summary=summary,omissions=omissions,
        news_events_input=len(events),news_events_matched=len({r['id'] for r in rows}),
        controls='STRICTLY_PRIOR_SAME_WEEKDAY_4H_SLOT_24H_DIRECTION_7D_VOLATILITY',
        limitations=['Manually selected famous headlines, not a representative news corpus',
        'Publication reconstruction, NOT true historical first-observed bot timestamps',
        'Matched controls are observational, not causal or independent OOS evidence',
        'Sign-flip ignores event selection, overlaps and macro-regime confounding',
        'Current 80bps taker fees applied to historical prices; hypothetical fills',
        'Small and dependent sample; no strategy promotion'])

def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument('--csv',default=None)
    p.add_argument('--news',default='data/historical_news_reconstructed.json')
    p.add_argument('--output',default='audit/v30-matched-news.json')
    args=p.parse_args(argv)
    from research.kraken_archive import load
    bars,market=load(args.csv)
    events,sha=news_load(args.news)
    report=matched_study(bars,events)
    report.update(mode='PAPER_ONLY_V30_RETROSPECTIVE_EXPLORATORY',
        market=market,news_sha256=sha,
        fees_bps_per_side={'taker':80,'half_spread':5,'slippage':5},
        max_entry_debit_aud=100,selection='HOLD',
        promotion='REJECTED_NO_INDEPENDENT_OOS_NET_BENEFIT')
    out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps(dict(output=str(out),matched=report['news_events_matched'],
        omitted=report['omissions'],summary=report['summary'],selection='HOLD'),indent=2))

if __name__=='__main__':main()

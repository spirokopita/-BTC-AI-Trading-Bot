"""PAPER ONLY: retrospective BTC/AUD point-in-time news/price diagnostics.
4h bar timestamp denotes OPEN. Signal at completed close i; fill next open i+1.
Historical articles are NOT first-observed evidence; never promote from this study.
"""
from __future__ import annotations
import argparse, bisect, hashlib, json, math, statistics
from datetime import datetime, timezone
from pathlib import Path
from research.kraken_archive import load

STEP=14400
LATENCY=3600
WINDOW=48*3600
CAP=100.
CASH=1000.
FEE=.008
SPREAD=.0005
SLIPPAGE=.0005
STRATEGIES=('sma','momentum','rsi','breakout','regime','trend_breakout','news_veto','news_veto_7d','news_delay','placebo_veto','news_positive_pulse','news_positive_placebo')

def ts(s):
    if not isinstance(s,str) or not s.endswith('Z'): raise ValueError('UTC Z required')
    return int(datetime.fromisoformat(s.replace('Z','+00:00')).timestamp())

def news_load(path):
    raw=Path(path).read_bytes()
    data=json.loads(raw)
    if data.get('dataset_type')!='RETROSPECTIVE_PUBLISHED_TIMESTAMP_RECONSTRUCTION_NOT_FIRST_OBSERVED':
        raise ValueError('Provenance must distinguish retrospective news from first-observed')
    out=[]
    for e in data['events']:
        pub=ts(e['published_at_utc'])
        updated=ts(e.get('updated_at_utc',e['published_at_utc']))
        if updated<pub or e['sentiment'] not in (-1,1) or not e['url'].startswith('https://'):
            raise ValueError('Invalid event')
        out.append(dict(e,available_ts=max(pub,updated)+LATENCY))
    if len(set(e['id'] for e in out))!=len(out): raise ValueError('Duplicate event ID')
    return sorted(out,key=lambda e:e['available_ts']),hashlib.sha256(raw).hexdigest()

def asof(events,cutoff,shift=0,window=WINDOW):
    """Only headlines whose publication AND known revision plus latency precede cutoff."""
    return [e for e in events if 0<=cutoff-(e['available_ts']+shift)<window]

def signal(bars,i,name,events=()):
    if i<202 or i+1>=len(bars): return False
    close=bars[i][4]
    closes=[b[4] for b in bars[i-201:i+1]]
    if name in ('news_positive_pulse','news_positive_placebo'):
        # Fixed 24h long-only event window; this is a retrospective post-hoc hypothesis.
        shift=7*86400 if name=='news_positive_placebo' else 0
        return any(e['sentiment']>0 for e in asof(events,bars[i][0]+STEP,shift,window=86400))
    if name=='sma': return statistics.mean(closes[-10:])>statistics.mean(closes[-20:])
    if name=='momentum': return close>closes[-13]*1.01
    if name=='rsi':
        delta=[closes[k]-closes[k-1] for k in range(len(closes)-14,len(closes))]
        up=sum(max(x,0) for x in delta); down=sum(max(-x,0) for x in delta)
        return (100 if down==0 else 100-100/(1+up/down))<35
    if name=='breakout': return close>max(b[2] for b in bars[i-20:i])
    if name=='regime':
        ret=[closes[k]/closes[k-1]-1 for k in range(len(closes)-19,len(closes))]
        return close>statistics.mean(closes[-100:]) and close>closes[-7] and statistics.pstdev(ret)<.035
    ma50=statistics.mean(closes[-50:]); ma200=statistics.mean(closes[-200:])
    atr=statistics.mean(max(bars[k][2]-bars[k][3],abs(bars[k][2]-bars[k-1][4]),
                            abs(bars[k][3]-bars[k-1][4])) for k in range(i-19,i+1))/close
    trend=ma50>ma200*1.005 and close>ma50
    breakout=close>max(b[2] for b in bars[i-24:i])
    base=trend and breakout and .01<=atr<=.07
    if name=='trend_breakout': return base
    if name in ('news_veto','news_veto_7d','news_delay','placebo_veto','news_positive_pulse','news_positive_placebo'):
        # placebo is a negative control only, NOT a deployable news feature.
        shift=7*86400 if name=='placebo_veto' else 0
        risk=any(e['sentiment']<0 for e in asof(events,bars[i][0]+STEP,shift,
             window=7*86400 if name=='news_veto_7d' else WINDOW))
        if name=='news_delay': return trend and close>ma50*1.01 and not risk
        return base and not risk
    raise ValueError('Unknown strategy')

def execution(mid,qty,side,mult):
    px=mid*(1+(SPREAD+SLIPPAGE)*mult*(1 if side=='buy' else -1))
    notional=qty*px
    return dict(notional=notional,fee=notional*FEE*mult,
                spread=qty*mid*SPREAD*mult,slippage=qty*mid*SLIPPAGE*mult)

def simulate(bars,start,end,name,events=(),mult=1.,audit=False):
    if not 204<=start<end<=len(bars) or end-start<3 or not .5<=mult<=2:
        raise ValueError('Invalid segment or cost multiplier')
    if any(bars[k][0]-bars[k-1][0]!=STEP for k in range(start-202,end)):
        raise ValueError('Candle gap: fail closed')
    cash=CASH; qty=0.; entry=None; mid=0.; entry_ts=None
    totals=dict(gross=0.,fees=0.,spread=0.,slippage=0.,net=0.)
    trades=[]; equity=[cash]; decisions=[]
    for j in range(start,end):
        price=bars[j][1]
        want=False if j==end-1 else signal(bars,j-1,name,events)
        if audit:
            decisions.append(dict(decision_ts=bars[j][0],
                observed_max_open_ts=bars[j-1][0],
                news_ids=[e['id'] for e in asof(events,bars[j][0])],
                action='BUY' if want and not qty else 'SELL' if not want and qty else 'HOLD'))
        if want and not qty:
            budget=min(CAP,.1*cash)
            qty=budget/(price*(1+(SPREAD+SLIPPAGE)*mult)*(1+FEE*mult))
            entry=execution(price,qty,'buy',mult)
            debit=entry['notional']+entry['fee']
            if debit>budget+1e-8 or debit>CAP+1e-8: raise AssertionError('Paper debit cap')
            cash-=debit;mid=price;entry_ts=bars[j][0]
        elif not want and qty:
            out=execution(price,qty,'sell',mult)
            cash+=out['notional']-out['fee']
            row=dict(entry_ts=entry_ts,exit_ts=bars[j][0],gross=qty*(price-mid),
                     fees=entry['fee']+out['fee'],
                     spread=entry['spread']+out['spread'],
                     slippage=entry['slippage']+out['slippage'])
            row['net']=row['gross']-row['fees']-row['spread']-row['slippage']
            realised=out['notional']-out['fee']-entry['notional']-entry['fee']
            if not math.isclose(row['net'],realised,abs_tol=1e-8):
                raise AssertionError('Gross-cost-NET mismatch')
            for k in totals: totals[k]+=row[k]
            trades.append(row)
            qty=0.;entry=None
        mark=cash
        if qty:
            out=execution(price,qty,'sell',mult)
            mark+=out['notional']-out['fee']
        equity.append(mark)
    if qty or not math.isclose(cash-CASH,totals['net'],abs_tol=1e-7):
        raise AssertionError('Account reconciliation')
    peak=equity[0];dd=0.
    for v in equity:
        peak=max(peak,v);dd=min(dd,v/peak-1)
    result=dict(strategy=name,trades=len(trades),
        wins=sum(t['net']>0 for t in trades),losses=sum(t['net']<0 for t in trades),
        gross_aud=round(totals['gross'],6),fees_aud=round(totals['fees'],6),
        spread_aud=round(totals['spread'],6),slippage_aud=round(totals['slippage'],6),
        net_aud=round(totals['net'],6),return_pct=round(totals['net']/CASH*100,6),
        max_drawdown_pct=round(dd*100,6))
    if audit: result['trade_audit']=trades;result['decision_audit']=decisions
    return result

def buyhold(bars,start,end):
    a=bars[start][1];b=bars[end-1][1]
    q=CAP/(a*(1+SPREAD+SLIPPAGE)*(1+FEE))
    x=execution(a,q,'buy',1);y=execution(b,q,'sell',1)
    return round(y['notional']-y['fee']-x['notional']-x['fee'],6)

def event_study(bars,events):
    times=[b[0] for b in bars];out=[]
    for e in events:
        i=bisect.bisect_left(times,e['available_ts'])
        if i==0 or i+12>=len(bars) or times[i]-times[i-1]!=STEP: continue
        for h in (1,6,12):
            if times[i+h]-times[i]!=h*STEP: continue
            a=bars[i][1];b=bars[i+h][1]
            gross=b/a-1
            net=(b*(1-SPREAD-SLIPPAGE)*(1-FEE))/(a*(1+SPREAD+SLIPPAGE)*(1+FEE))-1
            out.append(dict(id=e['id'],category=e['category'],sentiment=e['sentiment'],
                first_tradable_open_ts=times[i],available_ts=e['available_ts'],
                horizon_bars=h,gross_return_pct=round(gross*100,6),
                net_roundtrip_pct=round(net*100,6)))
    return out

def run(bars,events,provenance,news_sha):
    n=len(bars)
    if n<1200: raise ValueError('Need >=1200 contiguous historical bars')
    cuts=[222,n//3,n//2,n*2//3,n*5//6,n]  # add early 2021 fold so news coverage is not discarded
    folds=[]
    for a,b in zip(cuts[:-1],cuts[1:]):
        start=a+20
        results={s:simulate(bars,start,b,s,events) for s in STRATEGIES}
        for s in ('trend_breakout','news_veto','news_veto_7d','news_delay','placebo_veto','news_positive_pulse','news_positive_placebo'):
            results[s]['half_cost_net_aud']=simulate(bars,start,b,s,events,mult=.5)['net_aud']
            results[s]['double_cost_net_aud']=simulate(bars,start,b,s,events,mult=2)['net_aud']
        folds.append(dict(start_utc=datetime.fromtimestamp(bars[start][0],timezone.utc).isoformat(),
            end_utc=datetime.fromtimestamp(bars[b-1][0],timezone.utc).isoformat(),
            training_history_bars=a,embargo_bars=20,results=results,
            same_AUD100_buyhold_net_aud=buyhold(bars,start,b)))
    return dict(mode='PAPER_ONLY_RETROSPECTIVE_EXPLORATORY_V29',
        market=provenance,news_sha256=news_sha,news_count=len(events),
        news_data_kind='RETROSPECTIVE_PUBLICATION_RECONSTRUCTION_NOT_FIRST_OBSERVED',
        fees_per_side_bps=dict(taker=80,half_spread=5,slippage=5),
        news_latency_seconds=LATENCY,news_window_seconds=WINDOW,
        max_paper_entry_debit_aud=CAP,initial_cash_aud=CASH,
        fixed_parameters_predeclared=True,chronological_expanding_folds=folds,
        event_study=event_study(bars,events),
        ablations='48h/7d veto vs price-only; 24h positive news pulse vs +7d placebo; added post-hoc as EXPLORATORY after veto showed zero effect',
        selection='HOLD',promotion='REJECTED_NO_UNTOUCHED_PROSPECTIVE_NET_EDGE',
        limitations=['Previously inspected historical data; chronological replay is NOT untouched OOS',
        'Manually selected famous news stories and revised publication timestamps are NOT first-seen bot data',
        'Current 80bps fee applied to historical prices, not historical actual fee',
        'Next-open OHLC taker fills hypothetical; end-of-window forced liquidation'])

def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument('--news',default='data/historical_news_reconstructed.json')
    p.add_argument('--output',default='audit/v29-point-in-time.json')
    p.add_argument('--csv',default=None)
    args=p.parse_args(argv)
    bars,prov=load(args.csv)
    events,sha=news_load(args.news)
    report=run(bars,events,prov,sha)
    path=Path(args.output);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps(dict(output=str(path),folds=len(report['chronological_expanding_folds']),
        news_events=len(events),event_horizons=len(report['event_study']),
        news_sha256=sha,promotion=report['promotion']),indent=2))

if __name__=='__main__':main()

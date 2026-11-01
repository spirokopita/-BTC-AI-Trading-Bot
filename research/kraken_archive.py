"""PAPER-ONLY: sparse extraction of Kraken's official multi-part OHLCVT archive.

Only reads byte ranges needed for BTC/AUD 240m candles, not the full ~10GB ZIP.
Verifies member CRC and SHA256; DOES NOT verify Kraken's full-archive SHA256.
"""
from __future__ import annotations
import argparse, bisect, csv, hashlib, io, json, math, re, time, zipfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

BASE = 'https://assets.kraken.com/marketing/institutions/Kraken_OHLCVT_Full.zip.part'
STEP = 14400
def utc(ts): return datetime.fromtimestamp(ts,timezone.utc).isoformat()

class MultipartReader(io.RawIOBase):
    def __init__(self,lengths,reader):
        if not lengths or any(n<=0 for n in lengths): raise ValueError('Invalid part lengths')
        self.lengths,self.reader,self.ends,self.pos=lengths,reader,[],0
        for n in lengths: self.ends.append(n+(self.ends[-1] if self.ends else 0))
        self.size=self.ends[-1]
    def readable(self): return True
    def seekable(self): return True
    def tell(self): return self.pos
    def seek(self,offset,whence=0):
        target=offset if whence==0 else self.pos+offset if whence==1 else self.size+offset if whence==2 else None
        if target is None or target<0: raise ValueError('Invalid seek')
        self.pos=target
        return target
    def read(self,size=-1):
        remain=max(0,self.size-self.pos) if size is None or size<0 else min(size,max(0,self.size-self.pos))
        out=bytearray()
        while remain:
            part=bisect.bisect_right(self.ends,self.pos)
            base=self.ends[part-1] if part else 0
            n=min(remain,self.lengths[part]-(self.pos-base))
            data=self.reader(part,self.pos-base,n)
            if len(data)!=n: raise IOError('Truncated range')
            out.extend(data); self.pos+=n; remain-=n
        return bytes(out)

class HttpParts:
    def __init__(self,base=BASE,count=5,block=1048576):
        self.base,self.block,self.cache=base,block,{}
        self.lengths=[]
        for i in range(count):
            with urlopen(Request(self.url(i),method='HEAD',headers={'User-Agent':'BTCAUD-paper-research/2.0'}),timeout=30) as r:
                n=int(r.headers.get('Content-Length','0'))
            if n<=0: raise IOError('Missing Content-Length on archive part')
            self.lengths.append(n)
    def url(self,i): return self.base+f'{i:02d}'
    def get_block(self,i,b):
        key=i,b
        if key in self.cache: return self.cache[key]
        start=b*self.block; end=min(start+self.block,self.lengths[i])-1
        req=Request(self.url(i),headers={'Range':f'bytes={start}-{end}',
                    'Accept-Encoding':'identity','User-Agent':'BTCAUD-paper-research/2.0'})
        with urlopen(req,timeout=60) as r:
            status=getattr(r,'status',None); cr=r.headers.get('Content-Range','')
            if status!=206 or not cr.startswith(f'bytes {start}-{end}/'):
                raise IOError(f'Range unsupported/mismatch part={i} status={status} range={cr}')
            data=r.read(self.block+1)
        if len(data)!=end-start+1: raise IOError('Incorrect byte range length')
        if len(self.cache)>=8: self.cache.pop(next(iter(self.cache)))
        self.cache[key]=data
        return data
    def read(self,i,start,n):
        if start<0 or n<0 or start+n>self.lengths[i]: raise ValueError('Invalid range')
        out=bytearray()
        while n:
            b,off=divmod(start,self.block)
            data=self.get_block(i,b)[off:off+n]
            if not data: raise IOError('Empty range')
            out.extend(data); start+=len(data); n-=len(data)
        return bytes(out)

def member_name(names):
    hits=[n for n in names if re.fullmatch(
        r'(?:XXBTZAUD|XBTAUD|BTCAUD|XBT_AUD|BTC_AUD)[_-]240\.csv',
        n.rsplit('/',1)[-1],re.I)]
    if len(hits)!=1: raise ValueError(f'Expected one BTC/AUD 240m CSV, found {hits}; sample {names[:8]}')
    return hits[0]

def parse_csv(raw):
    bars=[]
    for line,row in enumerate(csv.reader(io.StringIO(raw.decode('utf-8-sig'))),1):
        if not row: continue
        if len(row)!=7: raise ValueError(f'Line {line}: not 7 OHLCVT fields')
        t=float(row[0]); o,h,l,c,v,tr=map(float,row[1:])
        if (not t.is_integer() or int(t)%STEP or
            not all(map(math.isfinite,(t,o,h,l,c,v,tr))) or
            min(o,h,l,c)<=0 or l>min(o,c) or h<max(o,c) or
            v<0 or tr<0 or not tr.is_integer()):
            raise ValueError(f'Line {line}: invalid candle')
        ts=int(t)
        if bars and ts<=bars[-1][0]: raise ValueError('Duplicate/nonascending timestamp')
        bars.append((ts,o,h,l,c,v))
    if len(bars)<1000: raise ValueError(f'Only {len(bars)} candles')
    return bars

def longest_contiguous(bars):
    starts=[0]; gaps=[]
    for i in range(1,len(bars)):
        if bars[i][0]-bars[i-1][0]!=STEP:
            gaps.append((utc(bars[i-1][0]),utc(bars[i][0])))
            starts.append(i)
    ends=starts[1:]+[len(bars)]
    # Predeclared data-quality rule: longest continuous interval by bar count ONLY.
    # Never select a segment using returns. Later segments are held for future validation.
    valid=[(a,b) for a,b in zip(starts,ends) if b-a>=1000]
    if not valid: raise ValueError(f'No >=1000-candle contiguous segment; gaps={len(gaps)}')
    a,b=max(valid,key=lambda pair:pair[1]-pair[0])
    return bars[a:b],gaps

def load(csv_path=None):
    if csv_path:
        raw=Path(csv_path).read_bytes()
        prov={'source':'LOCAL_FIXTURE_NOT_VERIFIED_MARKET','file_sha256':hashlib.sha256(raw).hexdigest()}
    else:
        store=HttpParts()
        with zipfile.ZipFile(MultipartReader(store.lengths,store.read)) as z:
            name=member_name(z.namelist())
            info=z.getinfo(name)
            if info.file_size>30000000: raise ValueError('BTC/AUD member unexpectedly large')
            with z.open(info) as f: raw=f.read(30000001)
            if len(raw)!=info.file_size: raise IOError('Uncompressed member size mismatch')
        prov={'source':'OFFICIAL_KRAKEN_FULL_OHLCVT_ARCHIVE','parts':store.lengths,
              'member':name,'member_crc32':f'{info.CRC:08x}',
              'member_sha256':hashlib.sha256(raw).hexdigest(),
              'whole_archive_sha256_verified':False,
              'integrity_note':'ZIP member CRC verified, NOT full archive published SHA256'}
    all_bars=parse_csv(raw)
    bars,gaps=longest_contiguous(all_bars)
    prov.update({'total_candles':len(all_bars),'gap_count':len(gaps),
                 'gap_examples':gaps[:10], 'archive_first_utc':utc(all_bars[0][0]),
                 'archive_last_utc':utc(all_bars[-1][0]), 'selected_contiguous_bars':len(bars),'selection_rule':'LONGEST_CONTIGUOUS_BY_BAR_COUNT_NOT_RETURNS',
                 'first_utc':utc(bars[0][0]),'last_utc':utc(bars[-1][0])})
    return bars,prov

def strip_log(row): return {k:v for k,v in row.items() if k!='trade_log'}

def run_experiment(bars,prov):
    """Predeclared 50/25/25 chronological split with 20-bar embargoes.
    Candidate selected on train + validation only. Test is NEVER tuned.
    """
    from research.market_experiment import STRATEGIES,simulate
    from trading_costs import FeeSettings,FeeTier,estimate_execution
    n=len(bars); train_end=n//2; val_start=train_end+20
    val_end=(n*3)//4-20; test_start=(n*3)//4
    if train_end<500 or val_end-val_start<150 or n-test_start<150:
        raise ValueError('Insufficient purged train/validation/test data')
    train={s:simulate(bars,102,train_end,s) for s in STRATEGIES}
    val={s:simulate(bars,val_start,val_end,s) for s in STRATEGIES}
    eligible=[s for s in STRATEGIES if train[s]['trades']>=5 and val[s]['trades']>=3
              and train[s]['net_aud']>0 and val[s]['net_aud']>0]
    selected=max(eligible,key=lambda s:val[s]['net_aud']) if eligible else 'HOLD'
    folds=[]
    for a,b in ((test_start,(test_start+n)//2),((test_start+n)//2,n)):
        results={s:simulate(bars,a,b,s) for s in STRATEGIES}
        first,last=bars[a][1],bars[b-1][1]
        fee=FeeSettings(tiers=(FeeTier(0,.0016,.0016),),spread_bps=10,
            base_slippage_bps=5,volatility_slippage_multiplier=0,
            size_slippage_bps=0,max_slippage_bps=5)
        probe=estimate_execution(first,50/first,'buy','taker',fee)
        q=50/(probe.execution_price*(1+probe.fee_rate))
        buy=estimate_execution(first,q,'buy','taker',fee)
        sell=estimate_execution(last,q,'sell','taker',fee)
        hold_net=sell.executed_notional_quote-sell.fee_quote-buy.executed_notional_quote-buy.fee_quote
        sens={s:{str(m):simulate(bars,a,b,s,fee_multiplier=m)['net_aud'] for m in (.5,1,2)}
              for s in set(('sma',selected))-{'HOLD'}}
        folds.append({'start_utc':utc(bars[a][0]),'end_utc':utc(bars[b-1][0]),
            'strategies':{s:strip_log(v) for s,v in results.items()},
            'selected':selected,'selected_net_aud':0 if selected=='HOLD' else results[selected]['net_aud'],
            'equal_AUD50_buy_hold_net_aud':round(hold_net,6),'fee_sensitivity':sens})
    return {'mode':'PAPER_ONLY_RESEARCH','provenance':prov,'bars':n,
            'train_end_utc':utc(bars[train_end-1][0]),
            'validation_start_utc':utc(bars[val_start][0]),
            'validation_end_utc':utc(bars[val_end-1][0]),
            'test_start_utc':utc(bars[test_start][0]),
            'selection_from_train_and_validation_only':selected,
            'train':{s:strip_log(v) for s,v in train.items()},
            'validation':{s:strip_log(v) for s,v in val.items()},
            'test_folds':folds,
            'news':'NOT_TESTED: no verified point-in-time first-observed historical news corpus',
            'promotion':'REJECTED: no Android parity and no independent prospective validation',
            'assumptions':'Long-only next-open, A$1000 reset per fold, max A$50, 16bps taker+5bps half spread+5bps slippage per side, hypothetical final-open exit'}

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--csv',help='Offline fixture; never label this verified market data')
    p.add_argument('--output',default='audit/kraken-archive-experiment.json')
    args=p.parse_args()
    bars,prov=load(args.csv)
    report=run_experiment(bars,prov)
    report['run_utc']=datetime.now(timezone.utc).isoformat()
    out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,indent=2,allow_nan=False),encoding='utf8')
    print(json.dumps({'report':str(out),'bars':len(bars),
        'selection':report['selection_from_train_and_validation_only'],
        'test_net':[f['selected_net_aud'] for f in report['test_folds']]}))

if __name__=='__main__':main()

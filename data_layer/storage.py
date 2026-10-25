"""Verified, append/upsert-only OHLCVT SQLite store (UTC Unix seconds).

Kraken archives omit candle intervals with zero trades. Gaps are reported, never
imputed. A repeated timestamp may be replaced by an authoritative later source,
except when a different exchange or symbol is supplied (separate primary key).
"""
from __future__ import annotations
import csv
import io
import json
import math
import sqlite3
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, TextIO

SUPPORTED = (1, 5, 15, 30, 60, 240, 720, 1440)
ALIASES = {"BTC/AUD": {"XBTAUD", "XXBTZAUD", "BTCAUD", "XBT_AUD", "BTC_AUD"}}


@dataclass(frozen=True)
class Candle:
    ts: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    trades: int | None = None

    @classmethod
    def from_kraken(cls, row):
        if len(row) < 8:
            raise ValueError("Invalid Kraken OHLC row")
        return cls(int(row[0]), float(row[1]), float(row[2]), float(row[3]),
                   float(row[4]), float(row[6]), int(row[7]))

    @classmethod
    def from_archive(cls, row):
        if len(row) < 6:
            raise ValueError("Archive row must contain timestamp, OHLC, volume")
        # Published OHLCVT CSVs contain trades as an optional seventh field.
        return cls(int(row[0]), *(float(x) for x in row[1:6]),
                   int(row[6]) if len(row)>6 and row[6] != '' else None)


def validate(c: Candle, interval: int):
    if interval not in SUPPORTED:
        raise ValueError(f"Unsupported Kraken OHLC interval: {interval}")
    if c.ts < 0 or c.ts % (interval * 60):
        raise ValueError(f"Invalid {interval}m aligned timestamp: {c.ts}")
    values=(c.open,c.high,c.low,c.close,c.volume)
    if not all(math.isfinite(v) for v in values):
        raise ValueError(f"Non-finite candle values at {c.ts}")
    if min(c.open,c.high,c.low,c.close) <= 0 or c.volume < 0:
        raise ValueError(f"Invalid price or volume at {c.ts}")
    if c.high < max(c.open,c.close,c.low) or c.low > min(c.open,c.close,c.high):
        raise ValueError(f"Invalid OHLC envelope at {c.ts}")
    if c.trades is not None and c.trades < 0:
        raise ValueError("Negative trade count")


class CandleStore:
    def __init__(self, path: str | Path):
        self.path=Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db=sqlite3.connect(str(self.path), timeout=20)
        self.db.row_factory=sqlite3.Row
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA busy_timeout=20000')
        self.db.executescript('''
          CREATE TABLE IF NOT EXISTS candles (
            exchange TEXT NOT NULL, pair TEXT NOT NULL, interval INTEGER NOT NULL,
            ts INTEGER NOT NULL, o REAL NOT NULL, h REAL NOT NULL, l REAL NOT NULL,
            c REAL NOT NULL, v REAL NOT NULL, trades INTEGER, source TEXT NOT NULL,
            ingested_at INTEGER NOT NULL,
            PRIMARY KEY(exchange,pair,interval,ts)
          );
          CREATE INDEX IF NOT EXISTS candle_coverage ON candles(exchange,pair,interval,ts);
          CREATE TABLE IF NOT EXISTS ingest_events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp INTEGER NOT NULL,
            exchange TEXT NOT NULL, pair TEXT NOT NULL, interval INTEGER NOT NULL,
            source TEXT NOT NULL, count_input INTEGER NOT NULL, count_written INTEGER NOT NULL,
            warning TEXT NOT NULL DEFAULT ''
          );
        ''')
        self.db.commit()

    def close(self): self.db.close()
    def __enter__(self): return self
    def __exit__(self,*_): self.close()

    def upsert(self, exchange:str, pair:str, interval:int,
               candles:Iterable[Candle], source:str, warning:str='') -> dict:
        if exchange != 'kraken':
            raise ValueError('V5 data module supports Kraken only; never relabel proxy data')
        if pair != 'BTC/AUD':
            raise ValueError('V5 scope restricted to BTC/AUD')
        if interval not in SUPPORTED: raise ValueError('Unsupported interval')
        arr=list(candles)
        if len({c.ts for c in arr}) != len(arr):
            raise ValueError('Duplicate timestamps in same ingestion batch')
        for c in arr: validate(c,interval)
        now=int(time.time())
        values=[(exchange,pair,interval,c.ts,c.open,c.high,c.low,c.close,c.volume,
                 c.trades,source,now) for c in arr]
        with self.db:
            before=self.db.total_changes
            self.db.executemany('''INSERT INTO candles
              (exchange,pair,interval,ts,o,h,l,c,v,trades,source,ingested_at)
              VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
              ON CONFLICT(exchange,pair,interval,ts) DO UPDATE SET
               o=excluded.o,h=excluded.h,l=excluded.l,c=excluded.c,v=excluded.v,
               trades=excluded.trades,source=excluded.source,ingested_at=excluded.ingested_at''', values)
            writes=self.db.total_changes-before
            self.db.execute('''INSERT INTO ingest_events
              (timestamp,exchange,pair,interval,source,count_input,count_written,warning)
              VALUES (?,?,?,?,?,?,?,?)''', (now,exchange,pair,interval,source,len(arr),writes,warning))
        return {'received':len(arr),'written':writes,'source':source,'warning':warning}

    def coverage(self, exchange='kraken',pair='BTC/AUD',interval=240):
        row=self.db.execute('''SELECT COUNT(*) n, MIN(ts) first, MAX(ts) last FROM candles
          WHERE exchange=? AND pair=? AND interval=?''',(exchange,pair,interval)).fetchone()
        return dict(row)

    def candles(self, exchange='kraken',pair='BTC/AUD',interval=240,start=None,end=None):
        sql='SELECT ts,o,h,l,c,v,trades,source FROM candles WHERE exchange=? AND pair=? AND interval=?'
        params=[exchange,pair,interval]
        if start is not None: sql+=' AND ts>=?';params.append(start)
        if end is not None: sql+=' AND ts<=?';params.append(end)
        sql+=' ORDER BY ts ASC'
        return self.db.execute(sql,params).fetchall()

    def gaps(self,exchange='kraken',pair='BTC/AUD',interval=240,start=None,end=None):
        stamps=[x['ts'] for x in self.candles(exchange,pair,interval,start,end)]
        step=interval*60
        result=[]
        for a,b in zip(stamps,stamps[1:]):
            if b-a>step:
                result.append({'missing_from':a+step,'missing_until':b-step,
                  'missing_intervals':int((b-a)//step-1),
                  'status':'UNKNOWN_GAP_OR_ZERO_TRADES'})
        return result

    def export_csv(self, path: str | Path,exchange='kraken',pair='BTC/AUD',interval=240):
        out=Path(path)
        out.parent.mkdir(parents=True,exist_ok=True)
        rows=self.candles(exchange,pair,interval)
        with out.open('w',newline='',encoding='utf-8') as f:
            w=csv.writer(f)
            w.writerow(['timestamp','open','high','low','close','volume','trades'])
            for r in rows: w.writerow([r[k] for k in ('ts','o','h','l','c','v','trades')])
        return len(rows)


def parse_ohlcvt_csv(stream:TextIO):
    reader=csv.reader(stream)
    for ln,row in enumerate(reader,1):
        if not row or all(not x.strip() for x in row): continue
        if ln==1 and row[0].strip().lower() in ('timestamp','time'): continue
        try: yield Candle.from_archive([v.strip() for v in row])
        except Exception as exc: raise ValueError(f'Bad archive CSV row {ln}: {exc}') from exc


def ingest_stream(store:CandleStore, stream:TextIO, interval:int, source:str,
                  pair='BTC/AUD', chunk_size:int=10000):
    """Bounded-memory archive import, safe to rerun after an interrupted import.

    Each chunk is committed separately for multi-GB archives. If a late row is
    corrupt, earlier chunks remain imported; fix data and rerun, then verify
    coverage and gap report. No silent synthetic backfill.
    """
    if chunk_size < 1: raise ValueError('chunk_size must be positive')
    batch=[];received=0;written=0
    for candle in parse_ohlcvt_csv(stream):
        batch.append(candle)
        if len(batch)>=chunk_size:
            z=store.upsert('kraken',pair,interval,batch,source)
            received+=z['received'];written+=z['written'];batch=[]
    if batch:
        z=store.upsert('kraken',pair,interval,batch,source)
        received+=z['received'];written+=z['written']
    return {'received':received,'written':written,'source':source}


def import_csv(store:CandleStore,path:Path,interval:int,pair='BTC/AUD'):
    if pair not in ALIASES or path.stem.upper() not in {f'{alias}_{interval}' for alias in ALIASES[pair]}:
        raise ValueError('CSV must be a properly named official BTC/AUD interval file; cannot infer pair safely')
    with path.open('r',encoding='utf-8-sig',newline='') as f:
        return ingest_stream(store,f,interval,source=f'kraken_csv:{path.name}',pair=pair)


def import_kraken_zip(store:CandleStore,path:Path,intervals:list[int],pair='BTC/AUD'):
    """Read matching Kraken pair files without extracting the complete archive."""
    if pair not in ALIASES:raise ValueError('Unsupported pair')
    intervals=set(intervals)
    if not intervals or not intervals.issubset(SUPPORTED):raise ValueError('Invalid intervals')
    found=[]
    with zipfile.ZipFile(path,'r') as z:
        for name in sorted(z.namelist()):
            if name.endswith('/'):continue
            stem=Path(name).stem.upper()
            matched=[v for v in intervals if stem in {f'{alias}_{v}' for alias in ALIASES[pair]}]
            if not matched:continue
            interval=matched[0]
            with z.open(name) as raw,io.TextIOWrapper(raw,encoding='utf-8-sig') as reader:
                result=ingest_stream(store,reader,interval,
                         source=f'kraken_zip:{path.name}/{name}',pair=pair)
            found.append({'member':name,'interval':interval,**result})
    if not found:raise ValueError('Archive has no matching BTC/AUD OHLCVT members; did not import anything')
    return found

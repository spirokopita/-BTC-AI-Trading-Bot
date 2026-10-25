"""Kraken public spot OHLC reader: bounded retries and closed-candle-only sync.

No API keys required. OHLC is limited to latest 720 candles: users must import
Kraken's official OHLCVT history for multi-year backtests. Historical gaps are
not invented, interpolated, or backfilled from unrelated exchanges.
"""
from __future__ import annotations
import time
from typing import Callable

import requests
from .storage import Candle,CandleStore,SUPPORTED

URL='https://api.kraken.com/0/public/OHLC'
TRANSIENT={'EAPI:Rate limit exceeded','EService:Unavailable','EService:Throttled'}


class KrakenError(RuntimeError): pass


class KrakenOHLC:
    def __init__(self, session=None, sleep:Callable=time.sleep,
                 clock:Callable=time.time, min_interval=1.3, retries=5):
        self.session=session if session is not None else requests.Session()
        self.sleep=sleep
        self.clock=clock
        self.min_interval=float(min_interval)
        self.retries=int(retries)
        self._last_request=None

    def _wait(self):
        if self._last_request is not None:
            delay=self.min_interval-(self.clock()-self._last_request)
            if delay>0:self.sleep(delay)
        self._last_request=self.clock()

    def fetch(self, interval:int, since:int|None=None, pair='XBTAUD'):
        if interval not in SUPPORTED:raise ValueError('Unsupported interval')
        params={'pair':pair,'interval':interval}
        if since is not None:params['since']=max(0,int(since))
        last_error=None
        for attempt in range(self.retries):
            self._wait()
            try:
                response=self.session.get(URL,params=params,timeout=(5,30))
                if response.status_code in (429,500,502,503,504):
                    last_error=f'HTTP {response.status_code}'
                    retry_after=response.headers.get('Retry-After','')
                    try:wait=float(retry_after)
                    except ValueError:wait=min(30,2**attempt)
                    if attempt+1<self.retries:self.sleep(max(0,wait))
                    continue
                response.raise_for_status()
                data=response.json()
                if not isinstance(data,dict) or 'error' not in data or 'result' not in data:
                    raise KrakenError('Unexpected Kraken response structure')
                errors=data['error']
                if errors:
                    last_error=';'.join(errors)
                    if any(e.startswith(('EAPI:Rate limit','EService:')) for e in errors):
                        if attempt+1<self.retries:self.sleep(min(30,2**attempt))
                        continue
                    raise KrakenError(f'Kraken API error: {last_error}')
                results=data['result']
                keys=[k for k,v in results.items() if k!='last' and isinstance(v,list)]
                if len(keys)!=1:raise KrakenError('Expected exactly one OHLC pair in result')
                raw=results[keys[0]]
                now=int(self.clock())
                cutoff=(now//(interval*60))*(interval*60)
                closed=[Candle.from_kraken(r) for r in raw if int(r[0])+interval*60 <= now]
                return {'closed':closed,'received':len(raw),'pair_key':keys[0],
                        'last':results.get('last'),'cutoff':cutoff,
                        'dropped_open':len(raw)-len(closed)}
            except (requests.Timeout,requests.ConnectionError) as exc:
                last_error=str(exc)
                if attempt+1<self.retries:self.sleep(min(30,2**attempt))
            except (requests.HTTPError,ValueError,TypeError) as exc:
                raise KrakenError(f'Invalid Kraken response: {exc}') from exc
        raise KrakenError(f'Kraken OHLC unavailable after {self.retries} tries: {last_error}')


def sync(store:CandleStore,api:KrakenOHLC,interval:int,pair='BTC/AUD'):
    if pair!='BTC/AUD':raise ValueError('Only BTC/AUD permitted in v5')
    if interval not in SUPPORTED:raise ValueError('Unsupported interval')
    previous=store.coverage(interval=interval)
    step=interval*60
    since=max(0,previous['last']-step) if previous['last'] is not None else None
    res=api.fetch(interval,since=since,pair='XBTAUD')
    closed=res['closed']
    warnings=[]
    if not closed: warnings.append('NO_CLOSED_CANDLES_FROM_API')
    if previous['last'] is None:
        warnings.append('API_LAST_720_ONLY_IMPORT_KRAKEN_ARCHIVE_FOR_LONG_HISTORY')
    elif closed and closed[0].ts > previous['last']+step:
        warnings.append('UNBRIDGED_API_HISTORY_GAP_IMPORT_ARCHIVE_OR_TRADES')
    if previous['last'] is not None and closed and closed[0].ts > since+step:
        warnings.append('API_COULD_NOT_RETURN_ALL_REQUESTED_HISTORY')
    written=store.upsert('kraken',pair,interval,closed,source='kraken_public_api',
                         warning=';'.join(warnings))
    return {**written,'interval':interval,'pair':pair,'previous_coverage':previous,
            'current_coverage':store.coverage(interval=interval),
            'dropped_open':res['dropped_open'],'warnings':warnings,
            'observed_internal_gaps':len(store.gaps(interval=interval))}

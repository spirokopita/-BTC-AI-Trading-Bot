#!/usr/bin/env python3
"""V4 research-only BTC spot breakout replay and weekly ML shadow/gated comparison.

Never sends exchange orders. Needs user-supplied REAL 4h OHLCV.
Runs technical control, ML-shadow (reports its forecasts), and gated replay.
Signals use completed candles and fill at next open. Guard and fee model are
conservative approximations, NOT Freqtrade order-by-order equivalence.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from trading_costs import (load_settings, FeeSettings, settle_trade, quantity_for_quote_budget,
                           minimum_break_even_move, ledger_to_log)
FEES = load_settings()
HORIZON = 120  # 20 days, for model, not an exit timer
RETRAIN = 42   # 7 days
TRAIN_BARS = 365 * 6 * 2
COOLDOWN = 12
CAP = 50.0
STOP = 0.10


def net_ratio(buy: float, sell: float, settings=None,
              volatility_frac: float = 0.) -> float:
    """Net proceeds / total quote cost; same assumptions as replay and AI labels."""
    settings = FEES if settings is None else settings
    q=quantity_for_quote_budget(buy,CAP,settings,volatility_frac=volatility_frac)
    led=settle_trade(buy,sell,q,settings,volatility_frac=volatility_frac)
    return 1+led.net_return_on_outlay


def label_train_end(signal_idx: int, horizon: int = HORIZON) -> int:
    """Exclusive end: every train label needs its entire future price path matured."""
    if signal_idx < horizon: raise ValueError('Insufficient history')
    return signal_idx - horizon


def load_data(path: str) -> pd.DataFrame:
    with Path(path).open(encoding='utf8') as handle:
        first = handle.readline().strip().lower()
    if first.startswith(('date', 'datetime', 'time', 'timestamp')):
        d = pd.read_csv(path)
        d.columns = [c.strip().lower() for c in d.columns]
        field = next((f for f in ['datetime','date','open_time','timestamp','time'] if f in d.columns),None)
        if not field: raise ValueError('Missing datetime')
        raw = d[field]
        if pd.api.types.is_numeric_dtype(raw):
            unit='ms' if float(raw.iloc[0]) > 1e12 else 's'
            d['date'] = pd.to_datetime(raw, unit=unit, utc=True)
        else: d['date'] = pd.to_datetime(raw, utc=True)
    else:
        d = pd.read_csv(path,header=None,names=['timestamp','open','high','low','close','volume','trades'])
        d['date'] = pd.to_datetime(d['timestamp'],unit='s',utc=True)
    for c in ['open','high','low','close','volume']:
        if c not in d: raise ValueError('Missing '+c)
        d[c] = pd.to_numeric(d[c],errors='raise')
    d = d.sort_values('date').reset_index(drop=True)
    if d['date'].duplicated().any(): raise ValueError('Duplicate candle')
    if not d['date'].diff().iloc[1:].eq(pd.Timedelta(hours=4)).all():
        raise ValueError('Candle gaps/non-four-hour periods: cannot fabricate OHLC')
    if not (d['date'].dt.hour % 4 == 0).all(): raise ValueError('Incorrect candle alignment')
    if (d[['open','high','low','close']] <= 0).any().any(): raise ValueError('Bad price')
    if (d['high'] < d[['open','close','low']].max(axis=1)).any(): raise ValueError('High < OHLC')
    if (d['low'] > d[['open','close','high']].min(axis=1)).any(): raise ValueError('Low > OHLC')
    return d


def add_indicators(d: pd.DataFrame):
    d=d.copy()
    c=d['close']
    d['ema50']=c.ewm(span=50,adjust=False,min_periods=50).mean()
    d['ema200']=c.ewm(span=200,adjust=False,min_periods=200).mean()
    d['prior20dayhigh']=d['high'].shift(1).rolling(120).max()
    d['prior10daylow']=d['low'].shift(1).rolling(60).min()
    d['entry']=(c>d['prior20dayhigh'])&(c>d['ema200'])&(d['ema50']>d['ema200'])&(d['volume']>0)
    d['exit']=(c<d['prior10daylow'])|(c<d['ema200'])
    for bars in [1,6,30,120]: d[f'r{bars}']=c.pct_change(bars)
    tr=pd.concat([d['high']-d['low'],(d['high']-c.shift()).abs(),(d['low']-c.shift()).abs()],axis=1).max(axis=1)
    d['atr']=tr.ewm(alpha=1/14,adjust=False,min_periods=14).mean()/c
    d['trend']=d['ema50']/d['ema200']-1
    d['dist']=c/d['prior20dayhigh']-1
    d['relvol']=d['volume']/d['volume'].rolling(20).mean()
    d['weekday']=d['date'].dt.dayofweek/7
    FEATURES=['r1','r6','r30','r120','atr','trend','dist','relvol','weekday']
    # Trained only on mature 20-day net close outcomes, independent of future path.
    # Actual trades follow their own Donchian/stop exits, so this is a regime forecast,
    # not the expected profit of the trade; ML stays shadow unless validated.
    # The supervised target calls the same fee model as paper fills and gate.
    # Signals at i use only the ATR fraction available at i (not future ATR).
    label=np.full(len(d),np.nan,dtype='float64')
    entry=d['open'].shift(-1).to_numpy(float)
    future=c.shift(-HORIZON).to_numpy(float)
    vola=d['atr'].to_numpy(float)
    for i in range(len(d)-HORIZON):
        if np.isfinite(entry[i]) and np.isfinite(future[i]) and entry[i]>0 and future[i]>0:
            label[i]=net_ratio(entry[i],future[i],volatility_frac=vola[i] if np.isfinite(vola[i]) else 0.)-1
    d['label']=label
    return d, FEATURES


def fit_model(x:np.ndarray, y:np.ndarray, idx:int, days=730):
    from lightgbm import LGBMRegressor
    last=label_train_end(idx)
    first=max(250,last-days*6)
    X=x[first:last]; Y=y[first:last]
    valid=np.isfinite(X).all(axis=1)&np.isfinite(Y)
    if valid.sum() < 1500: return None
    model=LGBMRegressor(n_estimators=120, learning_rate=.025, num_leaves=7,
        max_depth=4, min_child_samples=80, reg_lambda=20,
        verbosity=-1, random_state=42, n_jobs=2)
    model.fit(X[valid],Y[valid]);return model


def make_forecasts(d, features, start, end):
    x=d[features].to_numpy(dtype='float64'); y=d['label'].to_numpy(dtype='float64')
    pred=np.full(len(d),np.nan); model=None; last=-RETRAIN; fits=0
    for i in range(start,end+1):
        if i-last>=RETRAIN:
            model=fit_model(x,y,i)
            last=i;fits+=bool(model)
        if model is not None and np.isfinite(x[i]).all():
            pred[i]=float(model.predict(x[i:i+1])[0])
    return pred,fits


def replay(d,start,end,pred=None,gate=None,settings=None):
    """Paper-only replay; all costs and every per-trade log from ONE fee module."""
    settings=FEES if settings is None else settings
    o,h,l,c=(d[k].to_numpy(dtype='float64') for k in ('open','high','low','close'))
    atr_frac=d['atr'].to_numpy(float) if 'atr' in d else np.zeros(len(d))
    entries=d['entry'].to_numpy(bool);exits=d['exit'].to_numpy(bool)
    cash=1000.;qty=0.;entryprice=0.;entry_i=0;vol=0.;date_in=None;pos=False
    pending=None;cooldown_until=-1;trades=[];signals=0;approved=0;fcasts=[]
    peak=1000.;maxdd=0.;locked=False;day=None;daybase=1000.
    for i in range(start,end+1):
        today=str(d.iloc[i]['date'].date())
        if today!=day:
            day=today
            if pos:
                led=settle_trade(entryprice,o[i],qty,settings,volatility_frac=vol,
                                 holding_hours=(i-entry_i)*4)
                daybase=cash+led.exit_total_received_quote-led.funding_quote
            else:daybase=cash
        # Prior closed-candle signal; fill at current OPEN, never at signal close.
        if pending=='sell' and pos:
            led=settle_trade(entryprice,o[i],qty,settings,volatility_frac=vol,
                             holding_hours=(i-entry_i)*4)
            cash+=led.exit_total_received_quote-led.funding_quote
            trades.append({'in':date_in,'out':str(d.iloc[i]['date']),
                'net':round(led.net_pnl_quote,4),'net_pct':round(100*led.net_return_on_outlay,3),
                'exit':'signal', **ledger_to_log(led)})
            pos=False;qty=0.;cooldown_until=i+COOLDOWN
        elif pending=='buy' and not pos and not locked:
            budget=min(CAP,cash*.99,cash*.05)
            if budget>=10:
                vol=max(0.,float(atr_frac[i-1])) if np.isfinite(atr_frac[i-1]) else 0.
                qty=quantity_for_quote_budget(o[i],budget,settings,volatility_frac=vol)
                estimated=settle_trade(o[i],o[i],qty,settings,volatility_frac=vol)
                outlay=estimated.entry_total_outlay_quote
                cash-=outlay;entryprice=o[i];entry_i=i;date_in=str(d.iloc[i]['date']);pos=True
        pending=None
        if pos:
            stop=entryprice*(1-STOP)
            if o[i]<=stop or l[i]<=stop:
                px=o[i] if o[i]<=stop else stop
                led=settle_trade(entryprice,px,qty,settings,volatility_frac=vol,
                                 holding_hours=(i-entry_i)*4)
                cash+=led.exit_total_received_quote-led.funding_quote
                trades.append({'in':date_in,'out':str(d.iloc[i]['date']),
                    'net':round(led.net_pnl_quote,4),
                    'net_pct':round(100*led.net_return_on_outlay,3),
                    'exit':'stop', **ledger_to_log(led)})
                pos=False;qty=0.;cooldown_until=i+COOLDOWN
        if pos:
            mark=settle_trade(entryprice,c[i],qty,settings,volatility_frac=vol,
                              holding_hours=(i-entry_i)*4)
            equity=cash+mark.exit_total_received_quote-mark.funding_quote
        else:equity=cash
        peak=max(peak,equity);maxdd=min(maxdd,equity/peak-1)
        if equity<daybase*.98 or equity<peak*.95 or equity<900: locked=True
        if i==end or locked:continue
        if pos:
            if exits[i]:pending='sell'
        elif i>cooldown_until and entries[i]:
            signals+=1
            if pred is not None and np.isfinite(pred[i]):fcasts.append(float(pred[i]))
            if gate is not None and (pred is None or not np.isfinite(pred[i]) or pred[i]<gate):continue
            approved+=1;pending='buy'
    if pos:
        mark=settle_trade(entryprice,c[end],qty,settings,volatility_frac=vol,
                         holding_hours=(end-entry_i)*4)
        final=cash+mark.exit_total_received_quote-mark.funding_quote
    else:final=cash
    yearly={}
    for t in trades:
        yr=t['in'][:4]
        if yr not in yearly:yearly[yr]={'trades':0,'wins':0,'pnl':0.}
        yearly[yr]['trades']+=1;yearly[yr]['wins']+=t['net']>0;yearly[yr]['pnl']+=t['net']
    for z in yearly.values():z['pnl']=round(z['pnl'],2)
    return {'gate':gate,'signals':signals,'approved':approved,'trades':len(trades),
            'wins':sum(t['net']>0 for t in trades),'equity':round(final,2),
            'return_pct':round(100*(final/1000-1),3),
            'total_trading_fees_quote':round(sum(t['total_trading_fees_quote'] for t in trades),3),
            'total_slippage_quote':round(sum(t['slippage_quote'] for t in trades),3),
            'total_spread_quote':round(sum(t['spread_quote'] for t in trades),3),
            'drawdown_pct':round(100*maxdd,3),'locked':locked,'open_position':pos,
            'forecast_count':len(fcasts),'forecast_range':[
                round(min(fcasts),4),round(max(fcasts),4)] if fcasts else None,
            'years':yearly,'recent_trades':trades[-5:]}


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('csv',help='4h BTC/AUD OHLCV CSV, contiguous (or BTC/USDT proxy explicitly identified)')
    ap.add_argument('--start',default='2023-01-01')
    ap.add_argument('--end',default='2026-09-18')
    args=ap.parse_args()
    src=Path(args.csv)
    d,features=add_indicators(load_data(args.csv))
    selected=np.flatnonzero((d['date']>=pd.Timestamp(args.start,tz='UTC'))&
                          (d['date']<=pd.Timestamp(args.end,tz='UTC')))
    if not len(selected):raise ValueError('Empty period')
    if selected[0] < 200+HORIZON+1500:raise ValueError('Not enough prehistory for mature ML training')
    start,end=int(selected[0]),int(selected[-1]);p,fit_count=make_forecasts(d,features,start,end)
    results=[replay(d,start,end,gate=None),
        replay(d,start,end,pred=p,gate=0.0),
        replay(d,start,end,pred=p,gate=0.01)]
    zero_cost_baseline=replay(d,start,end,gate=None,settings=FeeSettings.zero())
    print(json.dumps({'source':str(src),'sha256':hashlib.sha256(src.read_bytes()).hexdigest(),
        'date_range':[str(d.iloc[start]['date']),str(d.iloc[end]['date'])],
        'notes':'Research proxy. AI is an unvalidated regime gate; do not enable for unattended live orders.',
        'weekly_model_retrainings':fit_count,
        'fee_profile':'config/fees.json',
        'no_fee_technical_baseline':zero_cost_baseline,
        'results':results},indent=2))
if __name__=='__main__':main()

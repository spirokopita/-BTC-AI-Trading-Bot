#!/usr/bin/env python3
"""Experimental chronological BTC/AUD 4h OHLC replay (research, not Freqtrade).

Usage: python research/walk_forward.py data/BTC_AUD_240.csv --start 2023-01-01
Accepts Kraken no-header `timestamp,open,high,low,close,volume,trades`
or named-column CSV `datetime,open,high,low,close,volume`.

NO profitable-trading claims. Uses FreqAI-like LightGBM model, retrained every
42 candles; actual Freqtrade/market orders may yield different results.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from trading_costs import load_settings, quantity_for_quote_budget, settle_trade, ledger_to_log
FEE_SETTINGS = load_settings()

STRATEGIES = Path(__file__).resolve().parents[1] / 'user_data' / 'strategies'
sys.path.insert(0, str(STRATEGIES))
from v3_outcomes import (future_net_trade_labels, net_return, HOLD_BARS,
                         STOP_FRACTION, TARGET_FRACTION)

WARMUP = 250
TRAIN_CANDLES = 365 * 6
REFIT_CANDLES = 42


def load(path):
    first = Path(path).open(encoding='utf-8').readline().strip()
    if first.lower().startswith(('date', 'time', 'datetime')):
        df = pd.read_csv(path)
        df.columns = [x.strip().lower() for x in df.columns]
        field = 'datetime' if 'datetime' in df else 'date' if 'date' in df else 'timestamp'
        df['date'] = pd.to_datetime(df[field], utc=True)
    else:
        df = pd.read_csv(path, header=None, names=['timestamp','open','high','low','close','volume','trades'])
        df['date'] = pd.to_datetime(df['timestamp'], unit='s', utc=True)
    df = df.sort_values('date').reset_index(drop=True)
    if df.duplicated('date').any():
        raise ValueError('Duplicate OHLC timestamps detected')
    if not df['date'].diff().dropna().eq(pd.Timedelta(hours=4)).all():
        raise ValueError('OHLC candles are not contiguous 4h data; resolve missing intervals without fabrication')
    if not (df['date'].dt.hour.mod(4) == 0).all():
        raise ValueError('Time stamps must align to 00,04,08,12,16,20 UTC')
    for x in ('open', 'high', 'low', 'close', 'volume'):
        df[x] = pd.to_numeric(df[x],errors='raise')
    if (df[['open','high','low','close']] <= 0).any().any():
        raise ValueError('Prices must be positive')
    return df


def wilder(x, n):
    return x.ewm(alpha=1/n, adjust=False, min_periods=n).mean()


def indicators(df):
    df=df.copy()
    c,h,l=df['close'],df['high'],df['low']
    for k in (20,50,200):
        df[f'ema{k}'] = c.ewm(span=k,adjust=False,min_periods=k).mean()
    change=c.diff()
    gain=wilder(change.clip(lower=0),14)
    loss=wilder(-change.clip(upper=0),14)
    df['rsi14']=100-100/(1+gain/loss.replace(0,np.nan))
    tr = pd.concat([h-l,(h-c.shift()).abs(),(l-c.shift()).abs()],axis=1).max(axis=1)
    df['atr14']=wilder(tr,14)
    up=h.diff();down=-l.diff()
    plus=pd.Series(np.where((up>down)&(up>0),up,0),index=df.index)
    minus=pd.Series(np.where((down>up)&(down>0),down,0),index=df.index)
    posdi=100*wilder(plus,14)/df['atr14']
    negdi=100*wilder(minus,14)/df['atr14']
    df['adx14']=wilder(100*(posdi-negdi).abs()/(posdi+negdi).replace(0,np.nan),14)
    df['volavg20']=df['volume'].rolling(20).mean()
    df['atr_frac']=df['atr14']/c
    pullback=df['low'].rolling(4).min()<=df['ema20']*1.005
    df['setup']=(
        (c>df['ema200'])&(df['ema50']>df['ema200'])&
        (df['ema200']>df['ema200'].shift(12))&(df['adx14']>=14)&
        (c>df['ema20'])&pullback&(c<=df['ema20']+1.25*df['atr14'])&
        df['rsi14'].between(40,68)&df['atr_frac'].between(.005,.07)&
        (df['volume']>=.5*df['volavg20'])&(df['volume']>0)
    ).fillna(False)
    for n in (1,3,6,12,42):
        df[f'r{n}']=c.pct_change(n)
    df['e20_dist']=c/df['ema20']-1
    df['e50_dist']=c/df['ema50']-1
    df['e200_dist']=c/df['ema200']-1
    df['rel_vol']=df['volume']/df['volavg20']
    df['weekday']=df['date'].dt.dayofweek/7
    df['hour']=df['date'].dt.hour/24
    features=['r1','r3','r6','r12','r42','e20_dist','e50_dist','e200_dist',
             'rsi14','adx14','atr_frac','rel_vol','weekday','hour']
    df['target']=future_net_trade_labels(df['open'],df['high'],df['low'],df['close'],
                                          volatility_fracs=df['atr_frac'].fillna(0))
    return df,features


def replay(df,features,start,end,with_ai=True):
    from lightgbm import LGBMRegressor
    test=np.flatnonzero((df['date']>=pd.Timestamp(start,tz='UTC'))&
                         (df['date']<=pd.Timestamp(end,tz='UTC')))
    if len(test)==0: raise ValueError('No candles in test window')
    if test[0] < WARMUP+TRAIN_CANDLES+HOLD_BARS:
        raise ValueError('Start date too early to form 365-day mature training labels')
    X=df[features].to_numpy(dtype='float64')
    y=df['target'].to_numpy(dtype='float64')
    setup=df['setup'].to_numpy(dtype=bool)
    o,h,l,c=(df[x].to_numpy(dtype='float64') for x in ('open','high','low','close'))
    cash=1000.0;stake=0.0;entry=0.0;entry_i=-1;last_exit=-1000
    qty=0.0;entry_cost=0.0;vol=0.0
    pending=False;pred_pending=np.nan;model=None;last_train=-REFIT_CANDLES
    trades=[];signals=0;accepted=0;peak=1000.;mdd=0.0;locked=False
    daily=1000.;old_day=None;forecast_count=0;predictions=[]
    for i in test:
        day=df.iloc[i]['date'].date()
        if day!=old_day:
            old_day=day
            daily=cash+(settle_trade(entry, o[i], qty, FEE_SETTINGS,
                   volatility_frac=vol).exit_total_received_quote if stake else 0)
        # Previous complete-candle decision becomes next candle open order.
        if pending and not stake and not locked:
            entry=float(o[i]);vol=max(0.0, float(df.iloc[i-1]['atr_frac'])) if np.isfinite(df.iloc[i-1]['atr_frac']) else 0.0
            budget=min(50.,.05*cash,cash*.99)
            if budget>0:
                qty=quantity_for_quote_budget(entry,budget,FEE_SETTINGS,volatility_frac=vol)
                ent=settle_trade(entry,entry,qty,FEE_SETTINGS,volatility_frac=vol)
                entry_cost=ent.entry_total_outlay_quote
                stake=entry_cost;cash-=entry_cost;entry_i=i
        pending=False
        if stake:
            stop=entry*(1-STOP_FRACTION);take=entry*(1+TARGET_FRACTION)
            px=None;why=None
            if o[i]<=stop: px=o[i];why='gap_stop'
            elif l[i]<=stop: px=stop;why='stop'
            elif o[i]>=take: px=o[i];why='gap_target'
            elif h[i]>=take: px=take;why='target'
            elif i-entry_i>=HOLD_BARS-1: px=c[i];why='timeout'
            if px is not None:
                led=settle_trade(entry,px,qty,FEE_SETTINGS,volatility_frac=vol,
                      holding_hours=(i-entry_i)*4)
                profit=led.net_pnl_quote
                trades.append({'entered':str(df.iloc[entry_i]['date']),
                               'exited':str(df.iloc[i]['date']), 'net':round(float(profit),4),
                               'cause':why, **ledger_to_log(led)})
                cash+=led.exit_total_received_quote;stake=0.;qty=0.;last_exit=i
        equity=cash+(settle_trade(entry,c[i],qty,FEE_SETTINGS,volatility_frac=vol,
                      holding_hours=(i-entry_i)*4).exit_total_received_quote if stake else 0)
        peak=max(peak,equity);mdd=min(mdd,equity/peak-1)
        if equity<daily*.98 or equity<peak*.95 or equity<900:
            locked=True
        if model is None or i-last_train>=REFIT_CANDLES:
            left=max(WARMUP,i-HOLD_BARS-TRAIN_CANDLES)
            right=i-HOLD_BARS # right is EXCLUSIVE; full future window matured
            good=np.isfinite(X[left:right]).all(axis=1)&np.isfinite(y[left:right])
            if good.sum()>=1100 and with_ai:
                model=LGBMRegressor(n_estimators=180,learning_rate=.035,
                    num_leaves=9,min_child_samples=60,reg_lambda=10.0,
                    colsample_bytree=.85,verbosity=-1,random_state=42)
                model.fit(X[left:right][good],y[left:right][good])
            last_train=i
        if i+1>=len(df) or i>=test[-1] or locked or stake or i-last_exit<=12:
            continue
        if setup[i]:
            signals+=1
            if with_ai:
                if model is None or not np.isfinite(X[i]).all(): continue
                expected=float(model.predict(X[i].reshape(1,-1))[0]);forecast_count+=1
                if len(predictions)<2000: predictions.append(expected)
                if not (.012<=expected<=.2):continue
            accepted+=1
            pending=True
    # Unclosed positions marked to market only, with projected exit friction
    final=cash+(settle_trade(entry,c[test[-1]],qty,FEE_SETTINGS,
             volatility_frac=vol, holding_hours=(test[-1]-entry_i)*4).exit_total_received_quote if stake else 0)
    return {'period':[str(df.iloc[test[0]]['date']),str(df.iloc[test[-1]]['date'])],
       'model':'LightGBM_net_return' if with_ai else 'technical_no_AI',
       'signals':signals,'approved_entries':accepted,'completed_trades':len(trades),
       'positive_trades':sum(t['net']>0 for t in trades),
       'end_equity':round(float(final),2),'net_account_return_pct':round((final/1000-1)*100,2),
       'max_candle_drawdown_pct':round(mdd*100,2),
       'risk_lock_active':locked,'forecast_count':forecast_count,
       'forecast_net_minmax':[round(min(predictions),4),round(max(predictions),4)] if predictions else None,
       'last_five':trades[-5:]}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('csv',help='4h Kraken BTC/AUD CSV; fully contiguous timestamps required')
    ap.add_argument('--start',default='2023-01-01')
    ap.add_argument('--end',default='2026-09-30')
    args=ap.parse_args()
    df,features=indicators(load(args.csv))
    results=[replay(df,features,args.start,args.end,with_ai=False),
             replay(df,features,args.start,args.end,with_ai=True)]
    print(json.dumps({'notes':'Indicative, NOT Freqtrade. 4h OHLC model ignores order-book fill uncertainties.',
                      'results':results},indent=2))

if __name__=='__main__':main()

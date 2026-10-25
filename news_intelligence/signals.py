"""Deterministic news tagging, fee-adjusted event study, and research signal gate.

Event-study associations are NOT proof that news caused market changes. No
model here can place orders. Candidate long biases must survive chronological
holdout assessment and have matured price labels before being emitted.
"""
from __future__ import annotations
from bisect import bisect_right, bisect_left
from datetime import datetime,timezone
import math
import re
from statistics import mean
from typing import Iterable
from data_layer.storage import Candle,validate
from trading_costs import (FeeSettings,load_settings,settle_trade,
                           quantity_for_quote_budget,minimum_break_even_move)

CATEGORY_PHRASES={
 'regulation':('sec','lawsuit','court','regulator','regulation','ban','licence','license','tax law'),
 'etf':('etf','exchange traded fund','fund inflow','fund outflow','spot fund'),
 'macro_rates':('fed','federal reserve','interest rate','inflation','cpi','central bank','jobs report','tariff'),
 'security':('hack','exploit','breach','stolen','ransomware','drained','vulnerability'),
 'exchange':('kraken','coinbase','binance','exchange collapse','exchange insolvency','withdrawals halted'),
 'institutional':('blackrock','vanguard','institutional','treasury','corporate bitcoin'),
 'onchain':('halving','miner','hashrate','mining difficulty','block reward','on chain','onchain'),
 'technology':('protocol','upgrade','lightning network','wallet update','layer 2'),
}
POS={'approve','approval','approved','adopt','adoption','gain','rally','surge','rise','rises','inflow','record high','recover','breakout','bullish','growth','buy'}
NEG={'reject','rejection','ban','lawsuit','hack','breach','stolen','crash','plunge','drop','falls','fall','outflow','liquidation','fraud','bearish','sell','exploit'}
NEGATION={'not','never','no','without','denies','deny','avoids'}


def classify(headline: str,summary: str='') -> dict:
    text=(headline+' '+summary).lower()
    categories=tuple(k for k,phrases in CATEGORY_PHRASES.items()
                     if any(re.search(r'(?<!\w)'+re.escape(phrase)+r'(?!\w)',text) for phrase in phrases))
    if not categories:categories=('general',)
    # Explicitly identify instrument exposure instead of treating all altcoin
    # news as Bitcoin predictors. Macro/whole-market news may affect BTC.
    assets=[]
    for name,aliases in {
        'BTC':('bitcoin','btc','xbt'),
        'ETH':('ethereum','ether','eth'),
        'SOL':('solana','sol'),
        'XRP':('ripple','xrp'),
        'MARKET':('crypto market','cryptocurrency','digital asset','crypto exchange',
                  'crypto industry','crypto prices','stablecoin'),
    }.items():
        if any(re.search(r'(?<!\w)'+re.escape(alias)+r'(?!\w)',text) for alias in aliases):
            assets.append(name)
    if 'macro_rates' in categories and not any(a in assets for a in ('BTC','ETH','SOL','XRP')):
        assets.append('MACRO')
    # Scoring headlines twice: media summaries are often excerpts/boilerplate.
    def score(s):
        words=re.findall(r'[a-z]+',s.lower());value=0
        phrases=POS|NEG
        for n,w in enumerate(words):
            if w not in phrases:continue
            polarity=1 if w in POS else -1
            if any(x in NEGATION for x in words[max(0,n-3):n]):polarity*=-1
            value+=polarity
        return value
    sentiment=max(-8,min(8,2*score(headline)+score(summary)))
    label='positive' if sentiment>0 else 'negative' if sentiment<0 else 'neutral'
    return {'categories':categories,'assets':tuple(assets),'polarity':sentiment,'label':label,
            'method':'transparent-headline-lexicon-v1-not-a-trained-model'}


def event_study(news: Iterable, candles: Iterable[Candle], *, interval: int=240,
                horizons_hours=(4,24,48), fee_settings:FeeSettings|None=None,
                quote_budget:float=50.,min_edge:float=.0025) -> dict:
    """Score outcomes using only completed candles.

    Pre-price is the last fully completed candle as of first-observed time;
    forward-price is the first candle closing at/after observed+horizon.
    No missing-bar fill or post-hoc same-candle high/low oracle.
    """
    settings=fee_settings or load_settings()
    bars=list(candles)
    if not bars:raise ValueError('Empty verified market candle series')
    if not 0<quote_budget or min_edge<0:raise ValueError('Bad study budget or edge')
    if any(h<=0 or h*60%interval for h in horizons_hours):
        raise ValueError('Horizons must be positive multiples of candle interval')
    step=interval*60
    for i,b in enumerate(bars):
        validate(b,interval)
        if i and b.ts-bars[i-1].ts!=step:raise ValueError('Gapped or unsorted OHLC; attribution blocked')
    close_stamps=[b.ts+step for b in bars]
    result=[];skipped={'before_candles':0,'after_candles':0,'unrelated_to_btc':0}
    for article in news:
        if not {'BTC','MACRO','MARKET'}.intersection(article.assets):
            skipped['unrelated_to_btc']+=1
            continue
        ts=article.available_ts
        prev=bisect_right(close_stamps,ts)-1
        if prev<0:skipped['before_candles']+=1;continue
        anchor=bars[prev]
        for horizon in horizons_hours:
            end_time=ts+horizon*3600
            next_idx=bisect_left(close_stamps,end_time)
            if next_idx>=len(bars):skipped['after_candles']+=1;continue
            later=bars[next_idx]
            if later.ts+step<=ts:raise ArithmeticError('Event study timing leakage')
            move=later.close/anchor.close-1
            qty=quantity_for_quote_budget(anchor.close,quote_budget,settings)
            ledger=settle_trade(anchor.close,later.close,qty,settings,holding_hours=horizon)
            cost_threshold=minimum_break_even_move(anchor.close,quote_budget,settings,
                holding_hours=horizon,min_net_edge=min_edge)
            result.append({'article_id':article.id,'source':article.source,'category_tags':article.categories,'asset_tags':article.assets,
                 'sentiment':article.polarity_label,'first_seen_ts':article.first_seen_ts,
                 'published_ts':article.published_ts,'available_ts':ts,
                 'baseline_last_known_close_ts':anchor.ts+step,
                 'future_close_ts':later.ts+step,'horizon_hours':horizon,
                 'pre_close':anchor.close,'post_close':later.close,
                 'gross_change_pct':100*move,'fee_adjusted_net_return_pct':100*ledger.net_return_on_outlay,
                 'fee_adjusted_net_pnl_quote':ledger.net_pnl_quote,
                 'trading_fees_quote':ledger.trading_fees_quote,
                 'spread_quote':ledger.spread_quote,'slippage_quote':ledger.slippage_quote,
                 'upside_after_fee_and_edge':move>cost_threshold,
                 'absolute_move_exceeds_break_even_plus_edge':abs(move)>cost_threshold,
                 'threshold_upward_move_pct':100*cost_threshold})
    return {'method':'retrospective event-price association, NOT causal prediction',
            'execution':'paper research only; no hypothetical short-selling',
            'interval_minutes':interval,'horizons_hours':list(horizons_hours),
            'results':result,'skipped':skipped}


def train_signal_quality(study:dict, *, horizon_hours:int=24,as_of_ts:int,
                         min_train:int=20,min_validation:int=10,
                         min_mean_net_pct:float=.25,min_win_fraction:float=.55) -> dict:
    """As-of chronological validation of event-tag signal candidacy.

    Each label must be *mature* (future close no later than as_of). Events
    on/after cutoff are excluded completely; never use an event being scored
    as part of its own model. Splits are chronological with purged horizon gap.
    """
    if min_train<1 or min_validation<1 or not 0<min_win_fraction<1:
        raise ValueError('Bad validation parameters')
    rows=[r for r in study['results'] if r['horizon_hours']==horizon_hours
          and r['future_close_ts']<=as_of_ts]
    group={}
    for row in rows:
        for category in row['category_tags']:
            group.setdefault(category,[]).append(row)
    findings=[]
    for cat,events in sorted(group.items()):
        events.sort(key=lambda e:(e['available_ts'],e['article_id']))
        # chronological last-third holdout; purge training rows whose label
        # matures at or beyond the first holdout publication timestamp.
        split=int(len(events)*.7)
        hold=events[split:]
        if not hold:train=[]
        else:train=[x for x in events[:split] if x['future_close_ts']<hold[0]['available_ts']]
        def metrics(part):
            return {'n':len(part),
                    'avg_net_pct':mean(r['fee_adjusted_net_return_pct'] for r in part) if part else None,
                    'positive_net_fraction':sum(r['fee_adjusted_net_return_pct']>0 for r in part)/len(part) if part else None}
        a,b=metrics(train),metrics(hold)
        qualified=(a['n']>=min_train and b['n']>=min_validation and
                   a['avg_net_pct']>=min_mean_net_pct and b['avg_net_pct']>=min_mean_net_pct and
                   a['positive_net_fraction']>=min_win_fraction and b['positive_net_fraction']>=min_win_fraction)
        findings.append({'category':cat,'train':a,'holdout':b,
                         'candidate_long_bias':qualified,'as_of_ts':as_of_ts,
                         'lookahead_from_scored_event_used':False,
                         'research_only_no_autotrade':True})
    return {'horizon_hours':horizon_hours,'as_of_ts':as_of_ts,
            'qualified_categories':[r['category'] for r in findings if r['candidate_long_bias']],
            'findings':findings,'warning':'Associations can reflect price trends and duplicate coverage; independent future validation is mandatory.'}


def event_signal_asof(article, quality:dict, *,decision_ts:int) -> dict:
    """A conservative downstream strategy interface; no executable order."""
    if article.available_ts>decision_ts or quality['as_of_ts']>=article.available_ts:
        return {'bias':'unavailable','reason':'event not yet observed or model not strictly earlier'}
    valid=set(quality['qualified_categories']).intersection(article.categories)
    if not valid:return {'bias':'hold','reason':'no independently qualified news tag'}
    return {'bias':'research_candidate_long','categories':sorted(valid),
            'research_only':True,'requires_price_signal_and_risk_gate':True}


def category_impact_summary(study:dict) -> list[dict]:
    """Associations by category/horizon; never interpreted as causal effect."""
    groups={}
    for row in study['results']:
        for category in row['category_tags']:
            groups.setdefault((category,row['horizon_hours']),[]).append(row)
    output=[]
    for (category,h),group in sorted(groups.items()):
        wins=[g for g in group if g['fee_adjusted_net_return_pct']>0]
        material=[g for g in group if g['absolute_move_exceeds_break_even_plus_edge']]
        output.append({'category':category,'horizon_hours':h,'observations':len(group),
            'material_movement_above_round_trip_costs':len(material),
            'material_movement_fraction':len(material)/len(group),
            'upside_net_positive_fraction':len(wins)/len(group),
            'mean_forward_net_return_pct':mean(g['fee_adjusted_net_return_pct'] for g in group),
            'mean_forward_gross_move_pct':mean(g['gross_change_pct'] for g in group),
            'warning':'Correlation not causation; repeated news waves can bias samples.'})
    return output

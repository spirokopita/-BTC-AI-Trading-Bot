"""V36: paper-only cost-hurdle and volatility-conditioned hysteresis with news ablations.
Prior-inspected Kraken archive and retrospectively reconstructed articles: EXPLORATORY.
Signals at open i see only completed bars through i-1 and news available by i.
No Android promotion, no real orders, no first-observed historical news claims.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import statistics
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from research.v29_point_in_time import STEP, CASH, CAP, buyhold, simulate
from research.v31_hysteresis import replay, features, WARMUP
from research.v33_cross_regime import archive, boundaries
from research.v32_segments import segments
from research.v35_news_reaction import event_corpus

WEEK = 7 * 86400
# Predeclared, never selected by test returns. The edge hurdle is a
# trend-strength proxy, NOT an estimated future return or guaranteed edge.
SPECS = {
    "h80_base": ("h80_300", None, None, None, 0),
    "h80_edge25": ("h80_300", .025, None, None, 0),
    "h80_vol15": ("h80_300", None, 1.5, None, 0),
    "h80_news7d": ("h80_300", None, None, WEEK, 0),
    "h80_edge25_vol15": ("h80_300", .025, 1.5, None, 0),
    "h80_edge25_vol15_news7d": ("h80_300", .025, 1.5, WEEK, 0),
    "h80_edge25_vol15_placebo7d": ("h80_300", .025, 1.5, WEEK, WEEK),
    "h50_edge25_vol15": ("h50_200", .025, 1.5, None, 0),
}
SELECTABLE = tuple(k for k in SPECS if "placebo" not in k)

def volatility_ratio(bars, i):
    """42-bar volatility / 126-bar volatility; strictly completed candles."""
    if i < 128 or i > len(bars):
        raise ValueError("Insufficient completed history")
    close = [b[4] for b in bars[i-127:i]]
    if any(not math.isfinite(x) or x <= 0 for x in close):
        raise ValueError("Invalid completed close")
    ret = [math.log(close[k] / close[k-1]) for k in range(1, len(close))]
    long = statistics.pstdev(ret)
    short = statistics.pstdev(ret[-42:])
    if long == 0:
        return math.inf if short > 0 else 1.
    return short / long

def available_article(events, at, window=WEEK, shift=0):
    """No future news, no RBA-as-sentiment; delayed control shifts later only."""
    if shift not in (0, WEEK) or window != WEEK:
        raise ValueError("Unregistered article window or placebo")
    return any(e["source_kind"] in ("ordinary_article", "prior_curated_article")
               and 0 <= at - (e["available_ts"] + shift) < window
               for e in events)

def make_veto(bars, events, name):
    if name not in SPECS:
        raise ValueError("Unregistered strategy")
    underlying, edge, vol_limit, news_window, shift = SPECS[name]
    fast, slow = (80, 300) if underlying == "h80_300" else (50, 200)
    lookup = {b[0]: i for i, b in enumerate(bars)}
    if len(lookup) != len(bars):
        raise ValueError("Duplicate candle timestamps")
    def veto(at):
        if at not in lookup:
            raise ValueError("Unknown candle timestamp")
        i = lookup[at]
        if i < WARMUP:
            raise ValueError("No warmup")
        if edge is not None:
            _, f, s, _ = features(bars, i, fast, slow)
            if f / s - 1 < edge:
                return True
        if vol_limit is not None and volatility_ratio(bars, i) > vol_limit:
            return True
        if news_window is not None and available_article(events, at, news_window, shift):
            return True
        return False
    return veto

def replay_variant(bars, start, end, events, name, cost_mult=1.,
                   max_entry_debit=CAP, audit=False):
    if name not in SPECS:
        raise ValueError("Unregistered variant")
    base = SPECS[name][0]
    result = replay(bars, start, end, base, events=(), cost_mult=cost_mult,
                    max_entry_debit=max_entry_debit, audit=audit,
                    entry_veto=make_veto(bars, events, name))
    result["variant"] = name
    if audit:
        for row in result["trade_audit"]:
            if row["entry_debit_aud"] > min(max_entry_debit, .1*row["cash_before_entry_aud"])+1e-8:
                raise AssertionError("A$100 and 10%-cash inclusive debit breach")
            if not math.isclose(row["net"], row["gross"]-row["fees"]-
                                row["spread"]-row["slippage"], abs_tol=1e-7):
                raise AssertionError("Negative P&L or cost reconciliation failure")
    return result

def choose(training, validation):
    eligible = [k for k in SELECTABLE if
                training[k]["trades"] >= 2 and validation[k]["trades"] >= 2
                and training[k]["net_aud"] > 0 and validation[k]["net_aud"] > 0]
    return max(eligible, key=lambda k: min(training[k]["net_aud"],
                                          validation[k]["net_aud"])) if eligible else "HOLD"

def coverage(events):
    """Availability dates, not publication or historical first-seen dates."""
    articles = [e for e in events if e["source_kind"] != "scheduled_rba"]
    years = range(2020, 2027)
    counts = Counter(datetime.fromtimestamp(e["available_ts"],timezone.utc).year
                     for e in articles)
    months = {(datetime.fromtimestamp(e["available_ts"],timezone.utc).year,
               datetime.fromtimestamp(e["available_ts"],timezone.utc).month)
              for e in articles}
    return dict(article_events=len(articles),
        scheduled_rba_events=sum(e["source_kind"]=="scheduled_rba" for e in events),
        article_counts_by_year={str(y):counts[y] for y in years},
        empty_article_months_2020_2026=sum((y,m) not in months
                                            for y in years for m in range(1,13)),
        total_months=84,
        first_observed_historical_versions=0,
        warning="Search-selected retrospective article availability ASSUMED, not historical first-seen; zero events in a month does not mean no news.")

def one_segment(bars, events):
    n = len(bars)
    train_end, val_start, val_end, test_start = boundaries(n)
    training = {k:replay_variant(bars,WARMUP,train_end,events,k) for k in SELECTABLE}
    validation = {k:replay_variant(bars,val_start,val_end,events,k) for k in SELECTABLE}
    selected = choose(training, validation)
    test = {k:replay_variant(bars,test_start,n,events,k,audit=True) for k in SPECS}
    sensitivity = {str(m):replay_variant(bars,test_start,n,events,
                        "h80_edge25_vol15",cost_mult=m)["net_aud"]
                   for m in (.5,1.,2.)}
    sizing = {str(c):replay_variant(bars,test_start,n,events,
                        "h80_edge25_vol15",max_entry_debit=c)["net_aud"]
              for c in (50.,100.)}
    baselines = {k:simulate(bars,test_start,n,k)
                 for k in ("sma","momentum","rsi","breakout","regime","trend_breakout")}
    return dict(bars=n,
        first_utc=datetime.fromtimestamp(bars[0][0],timezone.utc).isoformat(),
        test_start_utc=datetime.fromtimestamp(bars[test_start][0],timezone.utc).isoformat(),
        test_end_utc=datetime.fromtimestamp(bars[-1][0],timezone.utc).isoformat(),
        embargo_bars=20, training=training, validation=validation,
        train_validation_selected=selected,
        selected_test_net_aud=0 if selected=="HOLD" else test[selected]["net_aud"],
        test=test, baseline_regression=baselines, cost_sensitivity=sensitivity,
        size_sensitivity=sizing, same_stake_buyhold_aud=buyhold(bars,test_start,n))

def evaluate(bars,market,events,news):
    parts = segments(bars,1000)
    folds = [one_segment(bars[a:b],events) for a,b in parts]
    keys=("trades","wins","losses","gross_aud","fees_aud",
          "spread_aud","slippage_aud","net_aud")
    aggregate = {name:{k:round(sum(f["test"][name][k] for f in folds),6)
                       for k in keys} for name in SPECS}
    return dict(mode="V36_PAPER_ONLY_PRIOR_INSPECTED_EXPLORATORY",
        market=market,news_provenance=news,news_coverage=coverage(events),
        segment_counts=[b-a for a,b in parts],folds=folds,
        aggregate_independent_reset_accounts=aggregate,
        selected_test_net_aud=round(sum(f["selected_test_net_aud"] for f in folds),6),
        buyhold_aud=round(sum(f["same_stake_buyhold_aud"] for f in folds),6),
        worst_fold_drawdown_pct={name:min(f["test"][name]["max_drawdown_pct"]
                                          for f in folds) for name in SPECS},
        fee_bps_per_side=dict(taker=80,half_spread=5,slippage=5),
        starting_cash_aud=CASH,max_inclusive_entry_aud=CAP,
        research_selection="TRAIN_AND_VALIDATION_ONLY_20_BAR_EMBARGO",
        android_policy="HOLD",android_changes="NONE",real_execution="DISABLED",
        promotion="REJECTED_NO_UNTOUCHED_OOS_AND_NEWS_VERSION_PROVENANCE",
        limitations=["Previously inspected Kraken periods: not untouched OOS",
          "Article availability and revision versions not genuinely first observed",
          "No observed bid/ask, fill probability, maker queue or adverse selection",
          "Each gap-free segment resets A$1000; totals are not compounded",
          "Volatility and trend-strength thresholds are predeclared hypotheses",
          "Zero news veto changes would not prove that news lacks all predictive value"])

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--csv",default=None)
    p.add_argument("--output",default="audit/v36-volatility-news-gates.json")
    args=p.parse_args()
    if args.csv:
        from research.kraken_archive import parse_csv
        raw=Path(args.csv).read_bytes()
        bars=parse_csv(raw)
        market=dict(source="LOCAL_CSV_UNVERIFIED",sha256=hashlib.sha256(raw).hexdigest())
    else:
        bars,market=archive()
    events,news=event_corpus()
    result=evaluate(bars,market,events,news)
    out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,indent=2,allow_nan=False)+"\n")
    print(json.dumps(dict(output=str(out),segments=len(result["folds"]),
        news_coverage=result["news_coverage"],
        aggregate_net={k:v["net_aud"] for k,v in result["aggregate_independent_reset_accounts"].items()},
        selected_net=result["selected_test_net_aud"],buyhold_net=result["buyhold_aud"],
        policy="HOLD")))
if __name__=="__main__":
    main()

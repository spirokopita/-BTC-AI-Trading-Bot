"""V41 retrospective publication-time event study; PAPER ONLY.

Uses only a frozen convenience sample of timestamped current-run articles/releases.
Publication time + conservative latency is explicitly NOT first-observed evidence.
Matched controls are selected using pre-event return/volatility only.
"""
from __future__ import annotations

import argparse
import bisect
import json
import math
import statistics
from datetime import datetime, timezone
from pathlib import Path

from research.v28_recent_bridge import bridge_window
from research.v29_point_in_time import (
    CASH, FEE, SPREAD, SLIPPAGE, execution,
)

HORIZONS = {"4h": 1, "24h": 6, "48h": 12}
STEP = 14400
MAX_ENTRY_DEBIT = 100.0
CONTROL_COUNT = 3
CONTROL_LOOKBACK_BARS = 540
EVENT_EXCLUSION_BARS = 42


def epoch(value):
    if not isinstance(value, str) or not value:
        raise ValueError("Missing explicit UTC timestamp")
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None or dt.utcoffset().total_seconds() != 0:
        raise ValueError("Event timestamp must be timezone-aware UTC")
    return dt.timestamp()


def load_market(path):
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    if doc.get("schema") != "v28_recent_ohlc_1":
        raise ValueError("Unknown recent-market artifact schema")
    bars = doc.get("bars")
    if not isinstance(bars, list) or len(bars) < 300:
        raise ValueError("Insufficient observed Kraken OHLC bars")
    if any(len(row) < 6 for row in bars):
        raise ValueError("Incomplete OHLCV row")
    if any(b[0] - a[0] != STEP for a, b in zip(bars, bars[1:])):
        raise ValueError("Recent market bars contain a gap or irregular interval")
    digest = doc.get("source_response_sha256")
    if not isinstance(digest, str) or len(digest) != 64:
        raise ValueError("Missing Kraken response digest")
    fetched = epoch(doc.get("fetched_at_utc"))
    if fetched < bars[-1][0] + STEP:
        raise ValueError("Fetch time predates final completed bar")
    return bars, {
        "source": doc["source"],
        "source_response_sha256": digest,
        "fetched_at_utc": doc["fetched_at_utc"],
        "all_completed_bars": len(bars),
        "all_first_utc": datetime.fromtimestamp(bars[0][0], timezone.utc).isoformat(),
        "all_last_open_utc": datetime.fromtimestamp(bars[-1][0], timezone.utc).isoformat(),
        "all_last_close_utc": datetime.fromtimestamp(bars[-1][0] + STEP, timezone.utc).isoformat(),
    }


def load_events(path):
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    if doc.get("schema") != "v41_recent_news_events_1":
        raise ValueError("Unknown event corpus schema")
    if not doc.get("retrieved_at_utc"):
        raise ValueError("Missing event retrieval timestamp")
    retrieved_ts = epoch(doc["retrieved_at_utc"])
    events = []
    seen = set()
    for row in doc.get("events", []):
        if row.get("event_id") in seen:
            raise ValueError("Duplicate event ID")
        seen.add(row.get("event_id"))
        if row.get("first_observed_at_utc") is not None:
            raise ValueError("Publication reconstruction cannot claim first observation")
        if not row.get("source_urls"):
            raise ValueError("Event lacks source URL")
        latency = row.get("latency_seconds")
        if not isinstance(latency, int) or latency < 0:
            raise ValueError("Invalid conservative latency")
        published = epoch(row.get("published_at_utc"))
        if published > retrieved_ts:
            raise ValueError("Future publication included in current event sample")
        if any(not isinstance(url, str) or not url.startswith("https://")
               for url in row["source_urls"]):
            raise ValueError("Invalid event source URL")
        events.append({**row, "_published_ts": published,
                       "_available_ts": published + latency})
    events.sort(key=lambda x: (x["_published_ts"], x["event_id"]))
    return events, doc


def entry_index(bars, start, end, available_ts):
    timestamps = [row[0] for row in bars]
    index = bisect.bisect_left(timestamps, available_ts, lo=start, hi=end)
    return index if index < end else None


def prior_features(bars, index):
    """Features at bar-open index use only closes through index-1."""
    if index < 43:
        return None
    last_close = float(bars[index-1][4])
    close_24h = float(bars[index-7][4])
    if last_close <= 0 or close_24h <= 0:
        return None
    returns = [
        math.log(float(bars[k][4]) / float(bars[k-1][4]))
        for k in range(index-41, index)
    ]
    if not all(math.isfinite(x) for x in returns):
        return None
    return {
        "prior_24h_return": last_close / close_24h - 1.0,
        "prior_7d_realized_vol": statistics.pstdev(returns),
    }


def net_trade(entry_mid, exit_mid, *, max_entry_debit=MAX_ENTRY_DEBIT):
    if entry_mid <= 0 or exit_mid <= 0:
        raise ValueError("Invalid BTC/AUD price")
    if not 0 < max_entry_debit <= 100:
        raise ValueError("Paper entry debit exceeds A$100")
    budget = min(max_entry_debit, 0.10 * CASH)
    qty = budget / (
        entry_mid * (1 + SPREAD + SLIPPAGE) * (1 + FEE))
    buy = execution(entry_mid, qty, "buy", 1.0)
    sell = execution(exit_mid, qty, "sell", 1.0)
    entry_debit = buy["notional"] + buy["fee"]
    if entry_debit > budget + 1e-8 or entry_debit > 100.0 + 1e-8:
        raise AssertionError("Inclusive A$100/10% cash cap")
    gross = qty * (exit_mid-entry_mid)
    fees = buy["fee"] + sell["fee"]
    spread = buy["spread"] + sell["spread"]
    slippage = buy["slippage"] + sell["slippage"]
    net = gross-fees-spread-slippage
    execution_net = sell["notional"] - sell["fee"] - buy["notional"] - buy["fee"]
    if not math.isclose(net, execution_net, abs_tol=1e-8):
        raise AssertionError("Event trade does not reconcile to execution cash flows")
    result = {
        "trades": 1,
        "wins": int(net > 0),
        "losses": int(net <= 0),
        "gross_aud": round(gross, 6),
        "fees_aud": round(fees, 6),
        "spread_aud": round(spread, 6),
        "slippage_aud": round(slippage, 6),
        "net_aud": round(net, 6),
        "return_pct_on_A1000_wallet": round(net/CASH*100, 6),
        "raw_price_return_pct": round((exit_mid/entry_mid-1)*100, 6),
        "entry_debit_aud": round(entry_debit, 6),
        "max_entry_debit_aud": budget,
        "taker_fee_each_side_bps": 80,
        "half_spread_each_side_bps": 5,
        "slippage_each_side_bps": 5,
    }
    return result


def match_controls(bars, event_index, all_event_indices, start, end,
                   count=CONTROL_COUNT):
    """Prior-only matching: same UTC weekday/hour and prior return sign; nearest 7d vol."""
    target = prior_features(bars, event_index)
    if target is None:
        return []
    event_dt = datetime.fromtimestamp(bars[event_index][0], timezone.utc)
    lower = max(start + 43, event_index - CONTROL_LOOKBACK_BARS)
    candidates = []
    target_sign = 0 if target["prior_24h_return"] == 0 else (
        1 if target["prior_24h_return"] > 0 else -1)
    for j in range(lower, min(event_index, end-12)):
        if any(abs(j-k) <= EVENT_EXCLUSION_BARS for k in all_event_indices):
            continue
        dt = datetime.fromtimestamp(bars[j][0], timezone.utc)
        if dt.weekday() != event_dt.weekday() or dt.hour != event_dt.hour:
            continue
        feature = prior_features(bars, j)
        if feature is None:
            continue
        sign = 0 if feature["prior_24h_return"] == 0 else (
            1 if feature["prior_24h_return"] > 0 else -1)
        if sign != target_sign:
            continue
        distance = abs(feature["prior_7d_realized_vol"]
                       - target["prior_7d_realized_vol"])
        candidates.append((distance, j, feature))
    candidates.sort(key=lambda x: (x[0], x[1]))
    return [{
        "bar_index": j,
        "bar_open_utc": datetime.fromtimestamp(
            bars[j][0], timezone.utc).isoformat(),
        "feature_distance": round(distance, 10),
        "prior_24h_return": feature["prior_24h_return"],
        "prior_7d_realized_vol": feature["prior_7d_realized_vol"],
    } for distance, j, feature in candidates[:count]]


def _outcomes(bars, index, end):
    result = {}
    for label, horizon in HORIZONS.items():
        exit_index = index + horizon
        if exit_index >= end:
            result[label] = None
            continue
        result[label] = net_trade(
            float(bars[index][1]), float(bars[exit_index][1]))
        result[label]["entry_bar_open_utc"] = datetime.fromtimestamp(
            bars[index][0], timezone.utc).isoformat()
        result[label]["exit_bar_open_utc"] = datetime.fromtimestamp(
            bars[exit_index][0], timezone.utc).isoformat()
        result[label]["horizon_bars"] = horizon
    return result


def run_event_study(bars, market, events, start, end):
    if end > len(bars) or start < 0 or end-start < 20:
        raise ValueError("Invalid recent event-study window")
    indexed = []
    for event in events:
        index = entry_index(bars, start, end, event["_available_ts"])
        indexed.append((event, index))
    event_indices = [index for _, index in indexed if index is not None]
    results = []
    aggregate = {}
    for event, index in indexed:
        item = {
            "event_id": event["event_id"],
            "cluster_id": event["cluster_id"],
            "event_type": event["event_type"],
            "causal_degree_hypothesis": event["causal_degree"],
            "published_at_utc": event["published_at_utc"],
            "reconstructed_available_at_utc": datetime.fromtimestamp(
                event["_available_ts"], timezone.utc).isoformat(),
            "latency_seconds": event["latency_seconds"],
            "first_observed_at_utc": None,
            "source_urls": event["source_urls"],
            "related_publications_not_counted_as_independent": event.get(
                "related_publications", []),
            "transmission_hypotheses": {
                "btc_usd": event["btc_usd_sign_hypothesis"],
                "aud_usd": event["aud_usd_sign_hypothesis"],
                "btc_aud": event["btc_aud_sign_hypothesis"],
            },
        }
        if index is None:
            item["status"] = "NO_LATER_COMPLETED_BAR"
            item["outcomes"] = {}
            item["matched_controls"] = {}
            results.append(item)
            continue
        item["status"] = "RECONSTRUCTED_PUBLICATION_TIME_ONLY"
        item["decision_bar_open_utc"] = datetime.fromtimestamp(
            bars[index][0], timezone.utc).isoformat()
        item["prior_features"] = prior_features(bars, index)
        item["outcomes"] = _outcomes(bars, index, end)
        controls = match_controls(bars, index, event_indices, start, end)
        item["matched_controls"] = {}
        for label, horizon in HORIZONS.items():
            matched = []
            for control in controls:
                j = control["bar_index"]
                if j+horizon >= end:
                    continue
                metrics = net_trade(
                    float(bars[j][1]), float(bars[j+horizon][1]))
                matched.append({
                    **control,
                    "outcome": metrics,
                })
            item["matched_controls"][label] = matched
        results.append(item)

    for label in HORIZONS:
        event_values = [
            item["outcomes"][label]["net_aud"] for item in results
            if item.get("outcomes", {}).get(label) is not None
        ]
        control_values = [
            control["outcome"]["net_aud"]
            for item in results
            for control in item.get("matched_controls", {}).get(label, [])
        ]
        aggregate[label] = {
            "event_count": len(event_values),
            "matched_control_count": len(control_values),
            "mean_event_net_aud": round(statistics.mean(event_values), 6)
                if event_values else None,
            "mean_control_net_aud": round(statistics.mean(control_values), 6)
                if control_values else None,
            "mean_event_minus_control_net_aud": round(
                statistics.mean(event_values)-statistics.mean(control_values), 6)
                if event_values and control_values else None,
            "positive_event_net_count": sum(x > 0 for x in event_values),
            "negative_or_zero_event_net_count": sum(x <= 0 for x in event_values),
        }

    overlaps = []
    for i, (left, li) in enumerate(indexed):
        if li is None:
            continue
        for right, ri in indexed[i+1:]:
            if ri is not None and abs(ri-li) <= EVENT_EXCLUSION_BARS:
                overlaps.append({
                    "event_a": left["event_id"], "event_b": right["event_id"],
                    "bar_distance": abs(ri-li),
                    "note": "Overlapping 7-day event windows; not independent observations",
                })
    return {
        "mode": "V41_RETROSPECTIVE_PUBLICATION_TIME_EVENT_STUDY",
        "market": market,
        "market_window": {
            "first_decision_eligible_bar_utc": datetime.fromtimestamp(
                bars[start][0], timezone.utc).isoformat(),
            "last_completed_bar_open_utc": datetime.fromtimestamp(
                bars[end-1][0], timezone.utc).isoformat(),
            "bars": end-start,
            "gap_count": 0,
        },
        "sample_design": "Convenience sample; not random and not outcome-independent",
        "availability_basis": "Publisher/official publication timestamp plus fixed latency; NOT first-observed time",
        "first_observed_at_utc": None,
        "event_count": len(events),
        "events": results,
        "overlap_pairs": overlaps,
        "aggregate": aggregate,
        "cost_model_each_side_bps": {"taker": 80, "half_spread": 5, "slippage": 5},
        "starting_cash_aud": CASH,
        "max_inclusive_entry_debit_aud": MAX_ENTRY_DEBIT,
        "cash_fraction_cap": 0.10,
        "sentiment": "NOT SCORED; no NLP label inferred",
        "strategy_selection": "NONE; descriptive event study only",
        "promotion": "REJECTED: retrospective timestamps, convenience sample, overlapping events and no independent OOS",
        "limitations": [
            "Historical publication-time reconstruction is not actual first-observed availability",
            "No revision timestamps were available for some article sources",
            "Event sample is small and convenience-selected; no causal inference",
            "Matched controls use only prior return direction and realized volatility",
            "No sentiment score is inferred from headlines",
            "Hypothetical next-bar-open fills; no order-book, queue or intrabar execution",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--bars-json", default="audit/v41-recent-bars.json")
    parser.add_argument("--events", default="data/v41_recent_news_events.json")
    parser.add_argument("--output", default="audit/v41-recent-news-event-study.json")
    args = parser.parse_args(argv)
    bars, market = load_market(args.bars_json)
    events, source_doc = load_events(args.events)
    start, end = bridge_window(bars)
    report = run_event_study(bars, market, events, start, end)
    report["event_corpus_retrieved_at_utc"] = source_doc["retrieved_at_utc"]
    report["scheduled_future_events_not_backtested"] = source_doc.get(
        "scheduled_future_events", [])
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(report, indent=2, ensure_ascii=False,
                      allow_nan=False) + "\n").encode()
    target.write_bytes(raw)
    print(json.dumps({
        "output_sha256": __import__("hashlib").sha256(raw).hexdigest(),
        "event_count": report["event_count"],
        "overlap_pairs": report["overlap_pairs"],
        "aggregate": report["aggregate"],
        "market": report["market"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()

"""V44 shared strict point-in-time join from captured news versions to Kraken 4h opens."""
from __future__ import annotations

import bisect
from datetime import datetime, timezone

from research.v48_news_proof_gate import classify

FAR_FUTURE_VALIDATION_TS = 4102444799.0


def _iso(epoch):
    return datetime.fromtimestamp(float(epoch), timezone.utc).replace(
        microsecond=0).isoformat().replace("+00:00", "Z")


def strict_asof_join(records, bars, market_provenance=None, latency_seconds=3600):
    """Find the first completed-market bar open at/after proven availability.

    Publication time alone never grants availability. V48 must validate the
    exact captured version; then the first BTC/AUD 4h open at or after the
    proof-derived availability is selected. Gaps are reported, not hidden.
    """
    if not bars:
        raise ValueError("No Kraken BTC/AUD bars supplied")
    times = [int(row[0]) for row in bars]
    if any(right <= left for left, right in zip(times, times[1:])):
        raise ValueError("Non-monotonic Kraken bar timestamps")
    gaps = [
        {"left_open_utc": _iso(left), "right_open_utc": _iso(right),
         "gap_seconds": right - left}
        for left, right in zip(times, times[1:])
        if right - left != 14400
    ]
    matches, pending, rejected = [], [], []
    for row in records:
        proof = classify(row, FAR_FUTURE_VALIDATION_TS,
                         latency_seconds=latency_seconds)
        if not proof["eligible"]:
            rejected.append({
                "url": row.get("url"),
                "reason": proof["reason"],
            })
            continue
        available = float(proof["available_at_utc"])
        index = bisect.bisect_left(times, available)
        if index >= len(times):
            pending.append({
                "url": row.get("url"),
                "available_at_utc": _iso(available),
                "reason": "AFTER_LAST_COMPLETED_BAR",
            })
            continue
        decision = classify(row, times[index], latency_seconds=latency_seconds)
        if not decision["eligible"]:
            rejected.append({
                "url": row.get("url"),
                "reason": decision["reason"],
            })
            continue
        matches.append({
            "url": row["url"],
            "available_at_utc": _iso(available),
            "first_tradable_bar_open_utc": _iso(times[index]),
            "first_tradable_bar_index": index,
            "gap_before_first_tradable_bar": (
                index > 0 and times[index] - times[index - 1] != 14400),
            "decision_proof": decision["reason"],
            "latency_seconds": latency_seconds,
        })
    return {
        "mode": "V44_STRICT_ASOF_KRAKEN_4H_JOIN",
        "bar_count": len(bars),
        "first_bar_open_utc": _iso(times[0]),
        "last_bar_open_utc": _iso(times[-1]),
        "gap_count": len(gaps),
        "gaps": gaps[:50],
        "strict_asof_eligible": len(matches),
        "pending_after_last_bar": len(pending),
        "proof_rejected": len(rejected),
        "matches": matches,
        "pending": pending,
        "rejected": rejected,
        "latency_seconds": latency_seconds,
        "market_provenance": market_provenance or {},
        "no_lookahead": all(
            row["first_tradable_bar_open_utc"] >= row["available_at_utc"]
            for row in matches),
    }

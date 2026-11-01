"""V26 PAPER-ONLY: gap-safe, later-period BTC/AUD strategy experiment.

Historical Kraken OHLCVT contains *trade-only* intervals. A missing 4h row
can mean no trades, not necessarily corrupted data. We NEVER synthesize bars,
carry positions across a gap, or calculate indicators through a gap.

The later 2025-26 period was previously inspected in V25 and is therefore
EXPLORATORY chronological forward evaluation, NOT an untouched holdout.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import statistics
import zipfile

from research.kraken_archive import (
    HttpParts, MultipartReader, member_name, parse_csv, longest_contiguous,
    STEP, utc,
)
from research.market_experiment import STRATEGIES, signal, simulate
from trading_costs import FeeSettings, FeeTier, estimate_execution

CUTOFF = int(datetime(2025, 1, 1, tzinfo=timezone.utc).timestamp())
WARMUP = 202
EMBARGO = 20
CANDIDATES = STRATEGIES + ("slow_sma_005", "slow_sma_020")


def contiguous_segments(bars):
    """Split on any unobserved 4h interval; reject nonascending input."""
    if not bars:
        return []
    result, start = [], 0
    for i in range(1, len(bars)):
        delta = bars[i][0] - bars[i - 1][0]
        if delta <= 0 or delta % STEP:
            raise ValueError("Unordered or unaligned candle timestamps")
        if delta != STEP:
            result.append(bars[start:i])
            start = i
    result.append(bars[start:])
    return result


def select_periods(all_bars):
    """Select periods using timestamps and segment length, never returns."""
    old = [b for b in all_bars if b[0] < CUTOFF]
    if not old:
        raise ValueError("No pre-2025 training history")
    reference, _ = longest_contiguous(old)
    later = []
    for segment in contiguous_segments(all_bars):
        tail = [b for b in segment if b[0] >= CUTOFF]
        if len(tail) >= WARMUP + 300:
            later.append(tail)
    if not later:
        raise ValueError("No sufficiently long gap-free 2025+ segment")
    # Latest sufficiently long interval, not best-performing interval.
    recent = max(later, key=lambda s: (s[-1][0], len(s)))
    if reference[-1][0] >= recent[0][0]:
        raise AssertionError("Training period overlaps forward period")
    return reference, recent


def load_archive_all():
    """Reuse V25 sparse byte-range ZIP reader; verify member CRC and SHA."""
    parts = HttpParts()
    with zipfile.ZipFile(MultipartReader(parts.lengths, parts.read)) as z:
        name = member_name(z.namelist())
        info = z.getinfo(name)
        if info.file_size > 30_000_000:
            raise ValueError("Unexpectedly large BTC/AUD member")
        with z.open(info) as handle:
            raw = handle.read(30_000_001)
        if len(raw) != info.file_size:
            raise IOError("Truncated archive member")
    bars = parse_csv(raw)
    gaps = len(contiguous_segments(bars)) - 1
    provenance = {
        "source": "OFFICIAL_KRAKEN_OHLCVT_SPARSE_MULTIPART_ARCHIVE",
        "member": name,
        "member_sha256": hashlib.sha256(raw).hexdigest(),
        "member_crc32": f"{info.CRC:08x}",
        "member_crc_verified_by_zipfile": True,
        "whole_archive_sha256_verified": False,
        "part_sizes_bytes": parts.lengths,
        "observed_bars": len(bars),
        "gap_boundaries": gaps,
        "gap_note": "20 counts gap boundaries, not missing candle count; Kraken documents missing OHLCVT rows when no trades occurred; no rows are imputed",
        "first_utc": utc(bars[0][0]),
        "last_utc": utc(bars[-1][0]),
    }
    return bars, provenance


def extended_signal(bars, i, name):
    """Completed candle i only. No future bars are visible."""
    if name in STRATEGIES:
        return signal(bars, i, name)
    if name not in ("slow_sma_005", "slow_sma_020"):
        raise ValueError("Unknown candidate")
    if i < 199:
        return False
    closes = [b[4] for b in bars[i - 199:i + 1]]
    margin = 1.005 if name == "slow_sma_005" else 1.02
    return statistics.mean(closes[-50:]) > margin * statistics.mean(closes)


def slow_simulate(bars, start, end, name, *, fee_multiplier=1.0, position_cap_aud=50.0, taker_fee_bps=16):
    """Same next-open execution/cost accounting as V24 for new slow signals."""
    if name not in ("slow_sma_005", "slow_sma_020"):
        raise ValueError("Not a slow candidate")
    if not (WARMUP <= start < end <= len(bars)) or end - start < 2:
        raise ValueError("Invalid backtest interval")
    if len(contiguous_segments(bars)) != 1:
        raise ValueError("Cannot simulate across an unobserved interval")
    if not (math.isfinite(fee_multiplier) and fee_multiplier >= 0):
        raise ValueError("Invalid cost multiplier")
    if position_cap_aud not in (50.0, 100.0):
        raise ValueError("Only approved paper research caps A$50/A$100")
    if taker_fee_bps not in (16, 80):
        raise ValueError("Only documented 16bps legacy or 80bps current taker scenarios")
    costs = FeeSettings(
        tiers=(FeeTier(0, taker_fee_bps/10_000 * fee_multiplier, taker_fee_bps/10_000 * fee_multiplier),),
        spread_bps=10 * fee_multiplier,
        base_slippage_bps=5 * fee_multiplier,
        volatility_slippage_multiplier=0,
        size_slippage_bps=0,
        max_slippage_bps=5 * fee_multiplier,
    )
    cash, qty, entry_mid, entry_fill = 1000., 0., 0., None
    equity = [cash]
    totals = dict(gross=0., fees=0., spread=0., slippage=0., net=0.)
    trades = []
    for j in range(start, end):
        price = bars[j][1]
        want = False if j == end - 1 else extended_signal(bars, j - 1, name)
        if want and not qty:
            stake = min(position_cap_aud, (position_cap_aud / 1000.) * cash)
            probe = estimate_execution(price, stake / price, "buy", "taker", costs)
            qty = stake / (probe.execution_price * (1 + probe.fee_rate))
            entry_fill = estimate_execution(price, qty, "buy", "taker", costs)
            entry_mid = price
            debit = entry_fill.executed_notional_quote + entry_fill.fee_quote
            if debit > stake + 1e-8:
                raise AssertionError("Entry exceeds cash fraction / position cap")
            cash -= debit
        elif not want and qty:
            exit_fill = estimate_execution(price, qty, "sell", "taker", costs)
            cash += exit_fill.executed_notional_quote - exit_fill.fee_quote
            gross = qty * (price - entry_mid)
            fees = entry_fill.fee_quote + exit_fill.fee_quote
            spread = entry_fill.spread_quote + exit_fill.spread_quote
            slippage = entry_fill.slippage_quote + exit_fill.slippage_quote
            net = gross - fees - spread - slippage
            if not math.isclose(net, exit_fill.executed_notional_quote - exit_fill.fee_quote -
                                entry_fill.executed_notional_quote - entry_fill.fee_quote,
                                abs_tol=1e-8):
                raise AssertionError("Gross/fees/spread/slippage/NET mismatch")
            for key, value in (("gross", gross), ("fees", fees), ("spread", spread),
                               ("slippage", slippage), ("net", net)):
                totals[key] += value
            trades.append({
                "exit_ts": bars[j][0], "gross_aud": gross, "fees_aud": fees,
                "spread_aud": spread, "slippage_aud": slippage, "net_aud": net,
            })
            qty, entry_fill = 0., None
        mark = cash
        if qty:
            sell = estimate_execution(price, qty, "sell", "taker", costs)
            mark += sell.executed_notional_quote - sell.fee_quote
        equity.append(mark)
    peak, drawdown = equity[0], 0.
    for value in equity:
        peak = max(peak, value)
        drawdown = min(drawdown, value / peak - 1)
    assert not qty and math.isclose(cash - 1000., totals["net"], abs_tol=1e-7)
    return {
        "strategy": name,
        "position_cap_aud": position_cap_aud,
        "taker_fee_bps": taker_fee_bps,
        "start_utc": utc(bars[start][0]),
        "end_utc": utc(bars[end - 1][0]),
        "trades": len(trades),
        "wins": sum(t["net_aud"] > 0 for t in trades),
        "losses": sum(t["net_aud"] < 0 for t in trades),
        "gross_aud": round(totals["gross"], 6),
        "fees_aud": round(totals["fees"], 6),
        "spread_aud": round(totals["spread"], 6),
        "slippage_aud": round(totals["slippage"], 6),
        "net_aud": round(totals["net"], 6),
        "net_return_pct": round((cash / 1000. - 1) * 100., 6),
        "max_drawdown_pct": round(drawdown * 100., 6),
        "trade_log": trades,
    }


def replay(bars, start, end, name, fee_multiplier=1.0, position_cap_aud=50.0, taker_fee_bps=16):
    if name in STRATEGIES:
        return simulate(bars, start, end, name, fee_multiplier=fee_multiplier,
                        position_cap_aud=position_cap_aud, taker_fee_bps=taker_fee_bps)
    return slow_simulate(bars, start, end, name, fee_multiplier=fee_multiplier,
                         position_cap_aud=position_cap_aud, taker_fee_bps=taker_fee_bps)


def same_stake_buy_hold(bars, start, end, position_cap_aud=50.0, taker_fee_bps=16):
    fee = FeeSettings(
        tiers=(FeeTier(0, taker_fee_bps/10_000, taker_fee_bps/10_000),), spread_bps=10,
        base_slippage_bps=5, volatility_slippage_multiplier=0,
        size_slippage_bps=0, max_slippage_bps=5,
    )
    first, last = bars[start][1], bars[end - 1][1]
    if position_cap_aud not in (50.0, 100.0):
        raise ValueError("Only approved paper research caps A$50/A$100")
    if taker_fee_bps not in (16, 80):
        raise ValueError("Only documented 16bps legacy or 80bps current taker scenarios")
    probe = estimate_execution(first, position_cap_aud / first, "buy", "taker", fee)
    qty = position_cap_aud / (probe.execution_price * (1 + probe.fee_rate))
    buy = estimate_execution(first, qty, "buy", "taker", fee)
    sell = estimate_execution(last, qty, "sell", "taker", fee)
    gross = qty * (last - first)
    fees = buy.fee_quote + sell.fee_quote
    spread = buy.spread_quote + sell.spread_quote
    slip = buy.slippage_quote + sell.slippage_quote
    return {
        "gross_aud": round(gross, 6),
        "fees_aud": round(fees, 6),
        "spread_aud": round(spread, 6),
        "slippage_aud": round(slip, 6),
        "net_aud": round(gross - fees - spread - slip, 6),
        "price_change_pct": round(100 * (last / first - 1), 6),
    }


def no_log(result):
    return {k: v for k, v in result.items() if k != "trade_log"}


def run_experiment(all_bars, provenance, *, position_cap_aud=50.0, taker_fee_bps=16):
    if position_cap_aud not in (50.0, 100.0):
        raise ValueError("Only approved paper research caps A$50/A$100")
    if taker_fee_bps not in (16, 80):
        raise ValueError("Only documented 16bps legacy or 80bps current taker scenarios")
    reference, recent = select_periods(all_bars)
    n = len(reference)
    train_end, val_start = n // 2, n // 2 + EMBARGO
    val_end = n * 3 // 4 - EMBARGO
    if train_end < WARMUP + 150 or val_end - val_start < 150:
        raise ValueError("Insufficient pre-2025 purged training/validation")
    train = {s: replay(reference, WARMUP, train_end, s, position_cap_aud=position_cap_aud, taker_fee_bps=taker_fee_bps) for s in CANDIDATES}
    validation = {s: replay(reference, val_start, val_end, s, position_cap_aud=position_cap_aud, taker_fee_bps=taker_fee_bps) for s in CANDIDATES}
    eligible = [
        s for s in CANDIDATES
        if train[s]["trades"] >= 5 and validation[s]["trades"] >= 3
        and train[s]["net_aud"] > 0 and validation[s]["net_aud"] > 0
    ]
    selected = max(eligible, key=lambda s: validation[s]["net_aud"]) if eligible else "HOLD"
    start = WARMUP
    midpoint = (start + len(recent)) // 2
    if midpoint - start < 150 or len(recent) - midpoint < 150:
        raise ValueError("Recent period too short for two test folds")
    folds = []
    for a, b in ((start, midpoint), (midpoint, len(recent))):
        results = {s: replay(recent, a, b, s, position_cap_aud=position_cap_aud, taker_fee_bps=taker_fee_bps) for s in CANDIDATES}
        sensitivity = {
            s: {
                "half_cost_net_aud": replay(recent, a, b, s, .5, position_cap_aud, taker_fee_bps)["net_aud"],
                "base_cost_net_aud": results[s]["net_aud"],
                "double_cost_net_aud": replay(recent, a, b, s, 2., position_cap_aud, taker_fee_bps)["net_aud"],
            }
            for s in CANDIDATES
        }
        folds.append({
            "start_utc": utc(recent[a][0]),
            "end_utc": utc(recent[b - 1][0]),
            "selected_from_pre2025_train_validation": selected,
            "selected_net_aud": 0. if selected == "HOLD" else results[selected]["net_aud"],
            "strategies": {s: no_log(v) for s, v in results.items()},
            f"same_AUD{int(position_cap_aud)}_buy_hold": same_stake_buy_hold(recent, a, b, position_cap_aud, taker_fee_bps),
            "fee_sensitivity": sensitivity,
        })
    return {
        "mode": "PAPER_ONLY_EXPLORATORY_LATER_PERIOD",
        "source": provenance,
        "position_cap_aud": position_cap_aud,
        "taker_fee_bps": taker_fee_bps,
        "max_cash_fraction": position_cap_aud / 1000.,
        "selection_rule": "pre-2025 training AND validation positive NET with min 5/3 trades; else HOLD",
        "candidates_predeclared": list(CANDIDATES),
        "training_segment": {
            "bars": len(reference), "first_utc": utc(reference[0][0]),
            "last_utc": utc(reference[-1][0]),
            "train_end_utc": utc(reference[train_end - 1][0]),
            "validation_start_utc": utc(reference[val_start][0]),
            "validation_end_utc": utc(reference[val_end - 1][0]),
        },
        "later_segment": {
            "bars": len(recent), "first_utc": utc(recent[0][0]),
            "last_utc": utc(recent[-1][0]), "warmup_bars": WARMUP,
            "selection": "latest sufficiently long contiguous segment ending 2025+; timestamp only",
        },
        "train": {s: no_log(v) for s, v in train.items()},
        "validation": {s: no_log(v) for s, v in validation.items()},
        "selected_policy": selected,
        "folds": folds,
        "test_integrity": "NOT UNTOUCHED: V25 already inspected a 2025-2026 contiguous segment. This is exploratory chronological evaluation, NOT independent confirmation.",
        "news_signal": "NOT TESTED: no verified historical first_observed_at event corpus",
        "promotion": "REJECTED_PENDING_INDEPENDENT_PROSPECTIVE_NET_AND_ANDROID_PARITY",
        "assumptions": f"A$1000 reset per fold, A${int(position_cap_aud)} cap, {int(position_cap_aud/10)}% cash fraction, next-open long-only, {taker_fee_bps}bps fee+5bps half spread+5bps slippage each side, terminal last-open liquidation; no real orders",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="audit/v26-forward-gap-experiment.json")
    args = parser.parse_args()
    bars, provenance = load_archive_all()
    result = run_experiment(bars, provenance)
    result["run_utc"] = datetime.now(timezone.utc).isoformat()
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf8")
    print(json.dumps({
        "report": str(target), "selected": result["selected_policy"],
        "later": result["later_segment"],
        "selected_test_net": [f["selected_net_aud"] for f in result["folds"]],
        "sma_test_net": [f["strategies"]["sma"]["net_aud"] for f in result["folds"]],
        "slow_sma_test_net": [f["strategies"]["slow_sma_005"]["net_aud"] for f in result["folds"]],
    }))


if __name__ == "__main__":
    main()

"""V28: verified Kraken public OHLC bridge past 2026-09-30, PAPER ONLY.

Uses frozen V27 candidates, no retuning. The 2026-10 period was inspected in
V24 and is therefore EXPLORATORY, not independent prospective evidence.
No news signals can be assigned to times before their first observation.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

STEP = 14400
CUTOFF = int(datetime(2026, 10, 1, tzinfo=timezone.utc).timestamp())
WARMUP = 202


def bridge_window(bars, *, cutoff=CUTOFF, warmup=WARMUP):
    """Require enough genuinely observed contiguous warmup before the cutoff.

    No synthetic rows, unclosed candles, gap bridging or future observations.
    Selection depends only on timestamps, never on performance.
    """
    if not bars:
        raise ValueError('No observed Kraken bars')
    for a, b in zip(bars, bars[1:]):
        if b[0] - a[0] != STEP:
            raise ValueError('Missing, duplicate or non-monotone Kraken 4h candles')
    start = next((i for i, b in enumerate(bars) if b[0] >= cutoff), None)
    if start is None:
        raise ValueError('No bars beyond frozen 2026-09-30 archive boundary')
    if start < warmup:
        raise ValueError(f'Only {start} pre-cutoff warmup bars; need {warmup}')
    if len(bars) - start < 3:
        raise ValueError('Insufficient post-cutoff bars to replay')
    return start, len(bars)


def run_recent(bars, digest, *, fetched_at_utc):
    from research.forward_gap_experiment import CANDIDATES, replay, same_stake_buy_hold
    start, end = bridge_window(bars)
    results = {}
    for name in CANDIDATES:
        base = replay(bars, start, end, name, position_cap_aud=100., taker_fee_bps=80)
        sensitivity = {}
        for factor in (.5, 2.):
            alt = replay(bars, start, end, name, fee_multiplier=factor,
                         position_cap_aud=100., taker_fee_bps=80)
            sensitivity[str(factor)] = alt['net_aud']
        results[name] = {k: v for k, v in base.items() if k != 'trade_log'}
        results[name]['cost_multiplier_sensitivity_net_aud'] = sensitivity
        results[name]['trade_audit'] = base['trade_log']
        if abs(base['gross_aud'] - base['fees_aud'] - base['spread_aud'] -
               base['slippage_aud'] - base['net_aud']) > .00001:
            raise AssertionError(f'Unreconciled costs for {name}')
    benchmark = same_stake_buy_hold(bars, start, end, position_cap_aud=100., taker_fee_bps=80)
    return {
        'mode': 'PAPER_ONLY_V28_FROZEN_RECENT_EXPLORATORY',
        'source': 'Kraken public OHLC 240-minute BTC/AUD API',
        'source_response_sha256': digest,
        'fetched_at_utc': fetched_at_utc,
        'all_completed_bars': len(bars),
        'all_first_utc': datetime.fromtimestamp(bars[0][0], timezone.utc).isoformat(),
        'all_last_utc': datetime.fromtimestamp(bars[-1][0], timezone.utc).isoformat(),
        'post_archive_start_utc': datetime.fromtimestamp(bars[start][0], timezone.utc).isoformat(),
        'post_archive_last_utc': datetime.fromtimestamp(bars[end-1][0], timezone.utc).isoformat(),
        'post_archive_bars': end-start,
        'precutoff_warmup_bars': start,
        'gap_count': 0,
        'position_cap_aud': 100,
        'initial_cash_aud': 1000,
        'costs_bps_per_side': {'taker_fee': 80, 'half_spread': 5, 'slippage': 5},
        'strategies': results,
        'same_AUD100_buy_hold': benchmark,
        'predeclared_policy': 'HOLD',
        'selected_policy_net_aud': 0.,
        'test_integrity': 'EXPLORATORY: October 2026 already inspected by V24; not untouched prospective OOS',
        'news_predictive_effect': 'NOT TESTED: first-seen November 1 observations cannot be used before observed',
        'limitations': 'Next-bar-open hypothetical taker fills; fixed half-spread/slippage; no order book, queue, maker fill or intrabar execution. Final-open forced liquidation.',
        'promotion': 'REJECTED: no independent positive OOS NET edge and no Android strategy parity',
    }


def main(argv=None):
    from research.market_experiment import fetch_public
    p = argparse.ArgumentParser()
    p.add_argument('--output', default='audit/v28-recent-bridge.json')
    p.add_argument('--bars-json-output', default=None)
    args = p.parse_args(argv)
    bars, digest = fetch_public()
    fetched_at = datetime.now(timezone.utc).isoformat()
    result = run_recent(bars, digest, fetched_at_utc=fetched_at)
    if args.bars_json_output:
        bars_path = Path(args.bars_json_output)
        bars_path.parent.mkdir(parents=True, exist_ok=True)
        bars_path.write_text(json.dumps({
            'schema': 'v28_recent_ohlc_1',
            'source': 'Kraken public OHLC 240-minute BTC/AUD API',
            'source_response_sha256': digest,
            'fetched_at_utc': fetched_at,
            'bars': bars,
        }, separators=(',', ':'), allow_nan=False) + '\n', encoding='utf-8')
        readback = json.loads(bars_path.read_text(encoding='utf-8'))
        if readback['source_response_sha256'] != digest or len(readback['bars']) != len(bars):
            raise AssertionError('Recent bar artifact read-back mismatch')
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2, allow_nan=False), encoding='utf-8')
    print(json.dumps({'output': str(target), 'bars': len(bars),
                      'post_archive_bars': result['post_archive_bars'],
                      'net_by_strategy': {k: {'trades':v['trades'], 'net_aud':v['net_aud']}
                                          for k,v in result['strategies'].items()},
                      'buy_hold_net_aud': result['same_AUD100_buy_hold']['net_aud'],
                      'selected': result['predeclared_policy'],
                      'integrity': result['test_integrity']}, indent=2))


if __name__ == '__main__':
    main()

# V43 CHECKPOINT — 2026-11-18

## Execution status
- **DONE:** V43 research implementation, 9 targeted tests, full repository regression, official Kraken archive replay, fresh Kraken OHLC bridge, recent event study, 12-month cryptocurrency.cv sample, bounded Common Crawl diagnostic, accounting and chronology verification.
- **DONE:** PR #33 merged; main push research and persistence jobs passed. Read-back verified 2,491 rows, 1,428 article versions, 1,399 outcome-independent monthly archive articles, cursor 64/64 and 18 months remaining.
- **BLOCKED:** Common Crawl exact-URL lookup: one ODaily URL, two post-publication indexes, both HTTP 404. This does not establish that the page was never crawled.
- **NOT ATTEMPTED:** Android engine changes or APK build; no research candidate passed train/validation, so no promotion was warranted.

## Reproducible implementation
- `research/v43_drawdown_cash_gate.py`
- `tests/test_v43_drawdown_cash_gate.py` (9 tests)
- `.github/workflows/v41-volume-confirmation.yml` (V43 CI step, bounded Common Crawl limit=1, concurrency cancellation, corrected persistence read-back command)
- PR #33: https://github.com/spirokopita/-BTC-AI-Trading-Bot/pull/33
- PR final head: `bfd890b500d6f8eeae213e6ac9815f8e222c167f` (V43 code/test CI ran on `f50bd8a176c876a338499cf2c5dae8c73605a47e`; subsequent commits were documentation-only)
- Main merge: `28cc61951a2a16879e7e04c935a74a80f239d5fd`; persistence commit `1aadc46d284b310895a1ee916d5f6a22922e3076`
- PR CI run 44190949880 PASSED 357 full regression tests + 9 V43 tests; main push run 44191923759 research and persistence jobs PASSED. Main artifact 14378080633, SHA256 `81cabf71f9b148a566fee73ad1135ada5d1f655408179646ca419d0b7ea05e68`.
- Test command: `python -m unittest discover -s tests -p 'test_v43_drawdown_cash_gate.py' -v`; full suite: `python -m unittest discover -s tests -v`.

## Data provenance
- Official Kraken archive member `XBTAUD_240.csv`: 13,763 completed 4h bars, first 2020-06-16 20:00 UTC, last open 2026-09-30 20:00 UTC, 20 gaps; member SHA256 `ed732a5cd906991b2d2b306b3266578dcea14b07c6f9b307cb4c3c3753eb296e`.
- Eligible gap-free segments: 6,863 bars (2020-12-02 to 2024-01-20), 3,398 bars (2024-04-14 to 2025-11-01), 1,999 bars (2025-11-01 to 2026-09-30). All were previously inspected: EXPLORATORY, not untouched OOS.
- Fresh Kraken public OHLC bridge: 720 completed 4h bars, 2026-07-20 20:00 to 2026-11-17 16:00 UTC; 287 post-archive bars from 2026-10-01; zero gaps; fetched 2026-11-17 22:27 UTC; response SHA256 `c802bf3681ddec609d9d03e726b6563649e0f6418d5e7ed8f15e8bc9a5c64554`; last completed close A$94,647.70 (bar close 2026-11-17 20:00 UTC).
- News archive sample: 265 article metadata rows across 12 outcome-independent months; 265 retrospective publication-time alignments, 0 first-observed snapshots, 0 strict as-of market joins. Existing main corpus before merge: 2,226 rows, 1,163 article versions, 52 completed months. Expected post-merge totals must be verified, not assumed.
- Common Crawl: 1 sampled URL, 2 CDX requests, 0 captures, 2 HTTP 404. No WARC body downloaded. Prior 12-URL/24-request probe had 23 failures and 0 captures.
- Existing proof-gated corpus: 2,225 records without independent capture proof, 1 verified capture row, 0 strict as-of events in the historical test windows.

## V43 experiment
Predeclared H80/300 base; 540 completed 4h bars (90d); drawdown thresholds 10/15/20%; 42-bar delayed placebo; BUY-only gate, SELL unaffected; 50/20/30 chronological split, 84-bar embargo; 3 independent A$1,000 wallets; A$100 inclusive debit and 10% cash cap; 80bps taker + 5bps half-spread + 5bps slippage each side. Train/validation selection requires at least two trades and positive NET in both; otherwise HOLD.

| Variant | Trades | Gross | Fees | Spread | Slippage | NET | Return | Worst DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| H80/300 base | 7 | +51.333281 | 11.448071 | 0.715531 | 0.715531 | +38.454151 | +1.281805% | -4.192577% |
| 10% gate | 7 | +32.180402 | 11.295001 | 0.705954 | 0.705954 | +19.473494 | +0.649116% | -4.192577% |
| 15% gate | 7 | +32.180402 | 11.295001 | 0.705954 | 0.705954 | +19.473494 | +0.649116% | -4.192577% |
| 20% gate | 7 | +51.333281 | 11.448071 | 0.715531 | 0.715531 | +38.454151 | +1.281805% | -4.192577% |
| 15% delayed placebo | 7 | +32.536538 | 11.298383 | 0.706165 | 0.706165 | +19.825825 | +0.660861% | -4.159425% |
| A$100 buy-and-hold | 3 | +135.859476 | 5.842937 | 0.365252 | 0.365252 | +129.286037 | +4.309535% | -2.790726% |

All train/validation selectors chose HOLD. Therefore selected test NET = A$0 by design. H80/300 is a diagnostic, not the selected policy. The 10/15% gates each vetoed 58 BUY attempts and lowered NET by A$18.980657 versus baseline; the 20% gate did nothing. The delayed placebo nearly matched the live gate. **Reject the feature.**

Price-only baselines on the same three test segments: SMA 118 trades NET -A$119.682481; momentum 242 NET -A$374.775403; RSI 158 NET -A$225.519567; ATR breakout 133 NET -A$197.561916; regime 267 NET -A$407.787388; trend+ATR 20 NET -A$27.686213.

A$50/A$100 sensitivity (H80/300): A$50 current friction NET +A$19.640152; A$100 half/current/double friction +A$45.178506 / +A$38.454151 / +A$25.215557. 10/15% gate: A$50 current +A$10.149824; A$100 half/current/double +A$26.026247 / +A$19.473494 / +A$6.573540.

## News/event context (not a predictive claim)
Five retrospective publication-time events and seven matched controls: mean event-minus-control NET +A$0.366381 at 4h, -A$0.657088 at 24h, -A$1.124280 at 48h; seven overlapping 7-day event windows. Convenience sample, no first-observed timestamps, not independent enough to establish predictiveness. RBA November minutes were actually published 17 Nov 11:30 AEDT (00:30 UTC); the checked-in event file still calls them scheduled/not yet released. The 17 Nov CoinDesk ETF-flow follow-up (published 06:36 EST / 11:36 UTC) is also not yet captured as first-observed. Do not use either retrospectively in the strategy until provenance is fixed.

## Next
1. Capture the RBA minutes released 17 Nov 11:30 AEDT and the 17 Nov CoinDesk ETF-flow follow-up with actual first-observed times; keep publication, update, capture and retrieval times separate.
2. Test BTC/USD–AUD/USD decomposition using the existing RBA F11.1 daily connector (2,224 rows, assumed 17:00 Sydney +24h availability); compare with price-only and degree-1 baselines. RBA source terms restrict redistribution; FRED DEXUSAL is a secondary daily cross-check, and bulk ALFRED vintages require authorized key access.
3. Diagnose Common Crawl with a different URL-key normalization and collection index; do not repeat the two exact 404 queries.
4. Sample the remaining 18 months toward the 10,000 outcome-independent monthly-article target (1,399/10,000, 13.99%).

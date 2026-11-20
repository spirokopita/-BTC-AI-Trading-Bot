# RUN SUMMARY (2026-11-21 V45 partial)
- GitHub main: V45 as-of eligibility audit and five synthetic tests committed; commit SHAs 9f1d3a01 and 74a9a5b3. Five tests passed locally on reconstructed dependencies, NOT GitHub CI.
- V44 strict selector remains unintegrated with historical backtests. No new verified news capture, market data, OOS trades, or strategy returns this run.
- Prior V43: 1,399 monthly archive articles, 18 months remaining; one verified historical capture, zero strict as-of test-window news. These are prior checkpoint figures, not refreshed V45 counts.
- PAPER ONLY HOLD, A$100 inclusive entry / 10% cash, 80bps per-side taker + separate spread/slippage; no Android changes/APK.
- NEXT: execute committed tests in CI, audit real corpus, capture WARC versions, run frozen chronological strategy/news ablations and report all NET components before any promotion.

# RUN SUMMARY (2026-11-20 V44 partial checkpoint)
- **DONE:** Added proof-gated version-specific historical news selector `research/v44_news_asof.py` and nine synthetic leakage tests `tests/test_v44_news_asof.py`; GitHub main read-back confirmed both files (commits 15436fa and b1e3555).
- **LOCAL TEST:** Equivalent nine-case standalone implementation passed 9/9 with `python -m unittest discover -s tests -p 'test_v44_news_asof.py' -v`; uploaded GitHub source has not yet been executed by CI. No historical article was newly proven available; no new market backtest or APK.
- **BLOCKED RESEARCH:** No new untouched OOS evidence; no algorithm promotion. Prior V43 benchmark H80/300 +A$38.454151 NET vs same-stake buy-and-hold +A$129.286037, all selectors HOLD. Do not interpret those as V44 results.
- **NEXT:** Execute committed tests in CI, integrate proof-gated selector into existing as-of joins, expand 18 unsampled archive months, verify original WARC captures, rerun chronological price/news ablations with 80bps per-side taker plus separate spread/slippage. Preserve PAPER ONLY, A$100 inclusive/10% cash and HOLD.

# RUN SUMMARY (2026-11-18 V43)
- Main: PR #33 merged 28cc619; persistence bot commit 1aadc46 verified; corpus 2,491 rows / 1,428 article versions / 1,399 outcome-independent monthly articles; cursor 64/64, 18 months remain.
- Android unchanged: native Kotlin/Compose/Room PAPER engine HOLD, A$100 inclusive / 10% cash, 80bps taker, stale/offline block, 15-minute WorkManager, purple notification and master controls; no APK or live orders.
- Market: official Kraken archive 13,763 completed 4h bars / 20 gaps / 3 eligible segments; fresh bridge 720 bars through 2026-11-17 16:00 UTC, 287 post-archive bars, zero gaps, last close A$94,647.70.
- Research/news: all selectors HOLD; H80/300 diagnostic NET +A$38.454 vs A$100 buy-and-hold +A$129.286; drawdown gate rejected; 265 rows persisted, 0 strict as-of; Common Crawl 1 URL / 2 HTTP 404; next snapshot RBA/ETF news and test BTC/USD–AUD/USD decomposition.

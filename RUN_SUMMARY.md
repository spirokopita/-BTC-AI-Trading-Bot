# V30 prior-time matched historical news research — 2026-11-02 AEDT

1. Android V27 remains PAPER-ONLY, max A$100 inclusive debit / 10% cash and 80bps taker; no new APK or promotion.
2. Official Kraken 13,763 BTC/AUD four-hour candles, 20 gaps, 6,863 contiguous 2020-12-02–2024-01-20 bars; archive member SHA256 verified, whole ZIP not verified.
3. Ten historical news events (retrospective publication times, NOT first-observed) compared with strictly earlier non-event matched controls at 4h/24h/48h, realistic 80bps taker plus execution costs.
4. 24h event mean NET -1.629283% vs prior matched-control -0.073195%, excess -1.556088%; sentiment-aligned mean +0.245267%, descriptive sign-flip p=0.884766; NO predictive edge.
5. V30 CI 41355350343 PASSED 22 deterministic tests, official Kraken matched study and 12-strategy baseline rerun; HOLD remains selected, no live trading.

**DONE:** Added `research/v30_matched_news.py`, `tests/test_v30_matched_news.py`, V30 Actions workflow. 10/10 events matched, no future control selection, 7-day exclusion around known headlines, cost-inclusive long roundtrips. CI artifact 13102518396 includes full per-event control dates and returns and V29 twelve-strategy re-evaluation with gross, fees, spread, slippage, NET, drawdown, benchmark and cost sensitivity.

**PARTIAL:** News is still 10 famous retrospectively chosen events; no new article collection. Controls and p-values are observational/descriptive, not causal, and historical prices were previously inspected. 80bps is a current Kraken fee scenario, not a historical executed fee.

**BLOCKED FOR PROMOTION:** No independently verified positive NET strategy; no representative point-in-time historical news corpus. No Android changes or APK. NEXT: systematically sample historical news including ordinary non-events, assess coverage and regime dependence, test low-turnover hysteresis strategies with train-only selection. HOLD and PAPER-ONLY remain in force.

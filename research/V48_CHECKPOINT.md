# V48 — 2026-11-15 — Independent news-version availability gate
**BLOCKER QUESTION:** Can historical original capture timestamps and matching content-version hashes be recovered for the 841 existing article versions? Without them, retrospective publication timestamps cannot be promoted to historical as-of news signals.

DONE: Added a fail-closed proof gate for independently captured WARC, actual first-observed snapshots, and original official release versions; exact content SHA256 and capture SHA256 must match. All timestamps timezone-aware; version updates, capture and one-hour latency must precede the trading decision. Negative controls cover retrospective-only, future updates, mismatched versions, and future capture.

PARTIAL: Existing historical news metadata has not been converted to independently proven article versions; no new historical article count claimed. Source manifest from V40: 1,900 metadata/version records, 841 article versions, one verified historical crawl, three original official release clocks. Do not equate those counts with 841 tradable as-of signals.

NOT ATTEMPTED: Fresh Kraken candles, new news collection, SMA/RSI/momentum/ATR walk-forward and NET comparison, Android changes/APK. Previous V40 algorithm comparison remains the most recent verified full baseline: selected strategy NET -A$14.351385, buyhold +A$129.286037, previously inspected exploratory data. HOLD retained; no promotion.

TEST: python -m unittest discover -s tests -p 'test_v48_news_proof_gate.py' -v
NEXT: Recover independently captured historical versions with hashes; run as-of joins on actual Kraken completed bars and frozen train-only-selected algorithms with shifted/randomized news placebo. Capture gross, fee, spread, slippage, NET and drawdown. Never infer historical availability from published_at alone.

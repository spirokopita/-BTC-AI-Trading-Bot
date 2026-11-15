# V41 verified checkpoint — 16 November 2026

## Main and CI
- PR #31 merged: 2a799d7d4f1f7e3bbd74bb1b1529c19f04a39e47.
- Persistence workflow fix: 2ee3e2e92b49c537c495b14c0f1b84f5f9b005db.
- Main research run: 43771050561 PASSED; persistence bot commit: 2636d9740b1dc121a0214e1925e3986d7ceec0b8.
- PR checks on head f20310b295a92a5ee166cbb3034fb3e376a8faa0: V41 43770654956, V48 43770654931, V40 43770654930, V28 43770654977 all PASSED. Targeted V41/V48 tests: 46; full repository regression ran 331 tests and passed.
- V41 artifact: 14184097918. Algorithm JSON SHA256: 9b6ec5ccce148bf37f122c957ac4e198003fc340bf4e11729417e30166860527. Monthly news JSON SHA256: 76cc17a2ba384a6d5dee78a3a0ad9e7e5a260101347f2c0c94a2438b72865125.

## Market
- Official Kraken XBTAUD_240 archive: 13,763 completed 4h bars, 20 gaps, gap-free segments 6,863 / 3,398 / 1,999. Archive member SHA256: ed732a5cd906991b2d2b306b3266578dcea14b07c6f9b307cb4c3c3753eb296e. All archive periods previously inspected.
- Fresh public OHLC: 720 completed bars, fetched 2026-11-15 22:42:32 UTC, 275 post-archive bars through 2026-11-15 16:00 UTC. Last completed 4h close: 2026-11-15 20:00 UTC, A$96,181.50. Response SHA256: 20d1f114d19a0883f9e39c2b576f45abd0fc8d7901dddfc20474ebde70f37a6c.
- Recent exploratory window: SMA -A$29.897604, momentum -A$40.611689, RSI -A$32.602995, breakout -A$11.968582, regime -A$14.495934, slow SMA 0.5% -A$4.359602, slow SMA 2% -A$4.142430, buy-and-hold -A$21.726512. October 2026 was previously inspected.

## Algorithm
- 3 gap-free segment tests, each A$1,000 reset wallet; 50/20/30 chronological split and 20-bar embargo; A$100 inclusive entry debit and 10% cash cap; 80bps taker +5bps half-spread +5bps slippage each side.
- H80/300 base: 7 trades, 3 wins/4 losses, gross +A$51.333281, fees 11.448071, spread 0.715531, slippage 0.715531, NET +A$38.454151, return +1.281805%, worst fold DD -4.192577%.
- H80/300 volume+close: 7 trades, 3/4, gross +A$49.330147, fees 11.429587, spread 0.714374, slippage 0.714374, NET +A$36.471813, return +1.215727%, worst DD -4.210041%; -A$1.982338 vs base.
- Volume-only NET +A$38.360130; close-only +A$37.785654; 42-bar/7-day placebo +A$41.202690; H50/200 volume+close +A$0.967253.
- Price-only baselines: SMA 118 trades NET -A$119.682481; momentum 242 NET -A$374.775403; RSI 158 NET -A$225.519567; ATR breakout 133 NET -A$197.561916; regime 267 NET -A$407.787388; trend+ATR 20 NET -A$27.686213.
- Buy-and-hold: 3 trades, gross +A$135.859476, fees 5.842937, spread 0.365252, slippage 0.365252, NET +A$129.286037, return +4.309535%, worst DD -2.790726%.
- Selector HOLD in all 3 folds. No promotion. A$50 same-period H80 base +A$19.640152; A$100 +A$38.454151. Volume confirmation A$50 +A$18.661217; A$100 +A$36.471813.
- Volume confirmation vetoed 28 candidate bars: 12 had positive subsequent 24h moves, 16 negative, weighted mean -0.468%; delayed placebo outperformed. Reject.
- News attention and delayed-news placebo did not change any trades: zero independently verified news events in test windows.

## News
- Incremental cryptocurrency.cv archive: 321 URL-deduplicated metadata rows from 12 previously unsampled months, all 12 populated; 30 months remain. 175 retrospective joins, 0 strict as-of eligible.
- Main manifest read-back: 2,221 metadata/version rows, 1,162 actual article versions total, of which 1,133 outcome-independent monthly-archive articles count toward the 10,000 target (11.33%); 29 GDELT topic-search rows are excluded, 1 Common Crawl capture proof, 3 official release clocks; SHA256 63597fc2437d9ca2953c1ac897d05fb3d71e87ca54df04aa3ef2cc22afb9fa70. Cursor 52 attempted/completed, no retry, 30 remaining.
- 2,220 canonical URLs among 2,221 records because one URL is represented once as a Common Crawl capture and once as a separate FOMC calendar event; it is not counted twice as an article version.
- V48 classifier: 1 proof passes; 1,899 lack independent capture proof; 0 eligible in V41 test windows. Historical first-observed timestamps remain null.
- First-observed RSS corpus: 249 unique URLs, 114 new this run, SHA256 fea579b57f3d6bf5f5f2273ceb961b91edc2d8630c6ead8dfc5fb8c874126bbc. V28 bot commit 0257d71c2232b1482f2609d7fc6c5553214419c8. Four feeds succeeded; Bloomberg Crypto RSS blocked by trusted-host redirect allowlist. No historic first-seen backfill.
- Five Nov 3–13 convenience events, seven prior matched controls, seven overlapping pairs. Event-minus-control mean NET per A$100: 4h +0.366381; 24h -0.657088; 48h -1.124280. Reconstructed publication times with assumed latency; first-observed null; descriptive only.
- RBA minutes scheduled 17 Nov 2026 11:30 AEDT; not released and not backtested.

## Pipeline fixes
- V48: Common Crawl index-digest rows accept optional publication/update fields without inventing timestamps; update-after-retrieval rejected; exact capture/retrieval chronology retained.
- V41: invalid URL counter bug fixed and covered by a regression test.
- Initial V41 persistence push lost a race with V28. Fixed by sharing V28's concurrency group and fetching/rebasing/retrying before push. Final main persistence/readback passed.
- No Android source/APK change. Android remains PAPER ONLY/HOLD; live execution disabled.

## Next
Test a predeclared volatility-normalized exit/time-stop or cash-gating overlay on H80/300 using train-only selection and genuinely new prospective bars. Expand the remaining 30 historical months and independently verified WARC captures. Do not repeat the volume filter.

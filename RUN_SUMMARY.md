# V41 volume-confirmation research and monthly news persistence — 2026-11-16 AEDT

1. Native Android remains PAPER ONLY/HOLD, default-disabled, A$1,000 wallet, A$100 inclusive entry/10% cash cap, 80bps taker +5bps half-spread +5bps slippage each side; no Android source changes, APK or live orders.
2. Official Kraken archive: 13,763 BTC/AUD 4h bars, 20 gaps, three gap-free segments (6,863/3,398/1,999); fresh public 720-bar bridge fetched 2026-11-15 22:42 UTC, 275 post-archive bars through 16:00 UTC, last completed close A$96,181.50 at 20:00 UTC.
3. V41 volume+close confirmation NET +A$36.471813 versus H80/300 base +A$38.454151 and 7-day placebo +A$41.202690; all three train/validation selectors chose HOLD; buy-and-hold +A$129.286037; volume hypothesis rejected.
4. Historical news main read-back: 2,221 metadata/version rows, 1,162 article versions, 1 independently verified capture, 3 official release clocks, 321 new monthly rows, 175 retrospective joins, 0 strict as-of joins; cursor 52/82 months, 30 remaining. First-observed corpus 249 unique URLs, 114 new, no backfill.
5. PR #31 merged; V41 main run 43771050561 and persistence commit 2636d974... passed read-back. DONE 8 / PARTIAL 2 / BLOCKED 1 / NOT ATTEMPTED 3; full repository regression: 331 tests passed. Next: volatility-normalized exit/time-stop hypothesis and independent WARC capture coverage; no strategy promotion.

# V40 FX decomposition and monthly historical news — 2026-11-11 AEDT

1. Android native PAPER ONLY remains default-disabled/HOLD, A$1,000 starting simulated wallet, A$100 inclusive entry/10% cash cap, 80bps taker +5bps half-spread +5bps slippage each side, no real execution/APK changes.
2. Official Kraken archive 13,763 BTC/AUD 4h bars/20 gaps/three >=1000-bar segments; fresh public 720 completed gap-free bars through 2026-11-10 16:00 UTC, 245 post-Sep30; frozen recent candidates all NET-negative.
3. New 30d BTC/AUD-implied BTC/USD/AUD/USD decomposition uses only completed bars and RBA FX with ASSUMED 17:00 Sydney +24h availability, NOT verified historical FX revision vintages; prior-inspected archive remains EXPLORATORY.
4. H80 FX-driven veto and 7d placebo identical to H80 base (7 trades gross +A$51.333281, fees 11.448071, spread .715531, slippage .715531, NET +38.454151); USD momentum NET +37.238819; train/validation-selected policy HOLD/H50/HOLD NET -14.351385 vs A$100 buyhold +129.286037; REJECT promotion.
5. PR #22 MERGED main 9de9a992c39df36f496aeee258bedaf868a2150d; main CI 42915872177 PASSED 59 tests, Kraken/RBA and persistence; +237 articles, cumulative 1,900 metadata rows/841 actual articles, SHA256 e59ad9941eb2688ecaf59a4a2d904533e875d5b6703ac400ee5f6afd14f5826b, 0 historical as-of eligible.

DONE: source, code, tests, market/news research and PR CI. PARTIAL: 10k article target, verified historical vintages and untouched OOS. BLOCKED: promotion. NOT ATTEMPTED: APK/live orders. NEXT: persistent monthly sampling cursor (avoid repeats), independent historical WARC/FX vintages and prospective frozen testing. PAPER ONLY HOLD.

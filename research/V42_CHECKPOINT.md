# V42 verified checkpoint — 2026-11-17

## Decision

**PAPER ONLY / HOLD. No strategy or Android promotion.** V42's predeclared volatility-normalized exit and maximum-holding-time variants did not improve H80/300 net performance. The train/validation-only selector chose HOLD in all three gap-free segments. The archive is previously inspected and is not untouched OOS.

## Repository and CI

- Repository: `spirokopita/-BTC-AI-Trading-Bot`; PR #32, branch `research/v42-volatility-exit-warc-20261117`, tested source head `a8769fbf37f9ddadb42fbc71772fae9e651fcb9c`.
- GitHub Actions run `43972653807` PASSED. Full repository regression: **348 tests**. Targeted suites: V42 volatility exits 9 tests; V42 Common Crawl capture/as-of 8 tests; existing V41/V48/V40/V38/V27 regression suites also passed.
- Artifact `14280272081`, `v41-paper-research.zip`, SHA256 `fd7703c3b09ef574661c7b689d0c4c9bf877ebfc5fb7cc716a4514d445f5baec`.
- V42 algorithm report SHA256 `c2079dd26f4bd13ba207256a76621129d55a92f8872bc71b5e3c98034d5bc2af`; enriched news audit SHA256 `b9e36bfbab174f6585aa7ef9f6b866fe8c935ee7a37393b0839f2574b04b7d41`.
- Source files: `research/v42_volatility_exit.py`, `research/v42_warc_capture_probe.py`, `tests/test_v42_volatility_exit.py`, `tests/test_v42_warc_capture_probe.py`, `research/v37_source_topic_registry.json`, `.github/workflows/v41-volume-confirmation.yml`.
- Reproduction: `python -m unittest discover -s tests -p 'test_v42_volatility_exit.py' -v`; `python -m unittest discover -s tests -p 'test_v42_warc_capture_probe.py' -v`; `python -m unittest discover -s tests -q`; `python -m research.v41_volume_confirmation --output audit/v41-volume-confirmation.json --bars-json-output audit/v41-market-bars.json`; `python -m research.v42_volatility_exit --bars-json audit/v41-market-bars.json --output audit/v42-volatility-exit.json --bars-json-output audit/v42-market-bars.json`; `python -m research.v41_monthly_news --bars-json audit/v42-market-bars.json --output audit/v42-monthly-news.json`; `python -m research.v42_warc_capture_probe --audit audit/v42-monthly-news.json --bars-json audit/v42-market-bars.json --output audit/v42-monthly-news-enriched.json`.
- PR #32 merged to main as e1b983f36941d986924433966f38ebb4fa2a2488. Main push workflow 43974285006 is re-running research and the cumulative persistence/read-back job is pending. No algorithm source changed after the passing PR CI.

## Market data

- Official Kraken full OHLCVT archive member `XBTAUD_240.csv`: 13,763 completed 4h bars, 20 gaps; member SHA256 `ed732a5cd906991b2d2b306b3266578dcea14b07c6f9b307cb4c3c3753eb296e`. Three eligible gap-free segments: 6,863 bars (2020-12-02 20:00 UTC to 2024-01-20 12:00 UTC), 3,398 (2024-04-14 08:00 UTC to 2025-11-01 12:00 UTC), and 1,999 (2025-11-01 20:00 UTC to 2026-09-30 20:00 UTC). Retrieved 2026-11-16 22:44 UTC. Full archive ZIP hash was not verified; the member hash was.
- Fresh Kraken public BTC/AUD 4h bridge: 720 completed, gap-free bars from 2026-07-19 20:00 UTC through 2026-11-16 16:00 UTC; 281 bars after the archive cutoff, 2026-10-01 00:00 through 2026-11-16 16:00 UTC. Last completed bar closed 2026-11-16 20:00 UTC at **A$96,088.40/BTC**. Fetch 2026-11-16 22:44:34 UTC; response SHA256 `c8dce30d2c5c657ca383b5f995a37af8d7992f7ff329feb68e77e601a6111e55`.
- The post-archive recent-window candidates (exploratory; October was previously inspected) were all NET-negative at A$100: SMA -29.897604 (11 trades), momentum -40.611689 (16), RSI -34.937428 (17), breakout -11.968582 (6), regime -14.495934 (5), slow SMA 0.5% -4.359602 (1), slow SMA 2% -4.142430 (1); same-stake buy-and-hold -22.035194. These are not untouched OOS.

## V42 algorithm experiment

- Predeclared 7 candidates around H80/300 and H50/200. ATR(14) uses only completed bars before entry; stop distance is frozen at entry; a completed-close breach exits at the next bar open. Time stops use 42 or 84 completed 4h bars and also fill at the next open. Three independent A$1,000 reset wallets; 50/20/30 chronological train/validation/test, 84-bar embargo on both boundaries; train/validation-only selection, at least two trades and positive NET in both partitions or HOLD.
- Costs: Kraken Pro standard taker **80bps per side**, half-spread 5bps and slippage 5bps per side. A$100 maximum inclusive entry debit and 10% of pre-entry cash, whichever is smaller. Gross less both-side fees, spread and slippage reconciles to NET for every trade.

| Candidate | Trades (wins/losses) | Gross A$ | Fees A$ | Spread A$ | Slippage A$ | NET A$ | Return | Worst fold DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| H80/300 base | 7 (3/4) | 51.333281 | 11.448071 | 0.715531 | 0.715531 | **+38.454151** | +1.281805% | -4.192577% |
| H80 ATR 2.5x | 16 (2/14) | 14.941552 | 25.189608 | 1.574358 | 1.574358 | -13.396773 | -0.446559% | -4.710642% |
| H80 ATR 3.5x | 13 (2/11) | 8.000425 | 20.472618 | 1.279542 | 1.279542 | -15.031278 | -0.501043% | -4.637510% |
| H80 42-bar time stop | 38 (12/26) | 17.232776 | 59.944547 | 3.746543 | 3.746543 | -50.204856 | -1.673495% | -3.856194% |
| H80 ATR 2.5x + 84-bar stop | 33 (10/23) | 33.031476 | 52.319573 | 3.269989 | 3.269989 | -25.828077 | -0.860936% | -3.347621% |
| H80 ATR 3.5x + 42-bar stop | 43 (13/30) | 10.601610 | 67.814553 | 4.238414 | 4.238414 | -65.689772 | -2.189659% | -4.569391% |
| H50/200 base | 10 (3/7) | 25.705656 | 15.941756 | 0.996373 | 0.996373 | +7.771157 | +0.259039% | -3.469220% |

- Same-stake A$100 buy-and-hold: 3 independent positions, gross +135.859476, fees 5.842937, spread 0.365252, slippage 0.365252, NET **+129.286037**, return +4.309535%, worst fold DD -2.790726%.
- Price baselines on the same three test partitions: SMA 118 trades NET -119.682481; momentum 242 / -374.775403; RSI 158 / -225.519567; breakout 133 / -197.561916; regime 267 / -407.787388; trend+ATR 20 / -27.686213.
- All three train/validation selectors chose **HOLD**; selected test NET A$0 against buy-and-hold +A$129.286037. H80/300's positive aggregate is a hindsight candidate result, not a promoted strategy.
- A$50/current-cost vs A$100/current-cost NET: H80 base +19.640152 vs +38.454151; H50 base +4.442762 vs +7.771157. Half/current/double total friction at A$100: H80 base +45.178506 / +38.454151 / +25.215557; H50 base +16.941450 / +7.771157 / -10.221027. All seven candidates' sensitivity is retained in the JSON artifact.
- The ATR and time-stop hypotheses are **rejected**: all added exits increased turnover and fee drag, and none beat H80 base or buy-and-hold. No Android strategy promotion.

## News, event study and graph

- V42 added **265** outcome-independent cryptocurrency.cv historical article metadata/version rows across 12 previously unsampled months: 2022-03, 2022-06, 2022-08, 2022-09, 2022-11, 2022-12, 2023-03, 2023-06, 2023-08, 2023-09, 2023-11, 2023-12. All 12 requests passed source date-filter checks. 18 predeclared archive months remain. These are retrospective publication-time metadata, not first-observed snapshots. 265 retrospective article timestamps aligned to the historical Kraken segment; **0 strict as-of eligible**. The cumulative main corpus before this PR remained 2,221 metadata/version rows, 1,162 actual article versions (1,133 monthly-archive articles counted toward the 10,000 target), 1 verified capture, and 0 historical strict as-of eligible events. PR data is not yet persisted to main.
- Common Crawl collinfo was retrieved and UTC-normalized for naive `from`/`to` values. 12 deterministic article URLs, 24 URL-specific CDX index queries across the first two post-publication indexes per URL: **0 successful index queries, 0 capture versions**; 24 failures (HTTP 404, 400 and 504). No WARC body was downloaded. The 404s do not prove an article is absent from all Common Crawl indexes; the probe is explicitly non-exhaustive. One pre-existing independent capture remains in the main corpus; V42 added none.
- The source/topic registry contains 31 source records and 56 proposed degree-1/2/3 transmission hypotheses. All graph links remain untested hypotheses with proposed signs, lags, channels and confounders; no causal claim. Key/paid/license-restricted sources remain disabled; no subscription or spend.
- Recent event study remains a five-event convenience sample with seven prior matched controls; seven event pairs overlap. Mean event-minus-control NET: 4h +A$0.366381, 24h -A$0.657088, 48h -A$1.124280. Publication-time reconstructions only; first-observed timestamps null; not independent causal evidence. The RBA November minutes were scheduled for 2026-11-17 11:30 AEDT (00:30 UTC) and were not yet released at the V42 fetch time; do not include them before actual release/capture.

## Status and next action

- **DONE:** V42 source, 17 targeted V42 tests, 348 full regression tests, official archive walk-forward, fresh Kraken bridge, 265-row monthly increment, 24 bounded Common Crawl probes, report artifacts and provenance audit.
- **PARTIAL:** 10,000 article target (pre-PR main 1,133 qualifying articles); first-observed historical versions, representative ordinary/non-event coverage, and true untouched OOS.
- **BLOCKED:** strategy promotion and historical news predictive use; no candidate selected above HOLD; zero strict as-of eligible events.
- **NOT ATTEMPTED:** Android APK rebuild or live execution. Native Android source/risk configuration remains unchanged; paper-only safeguards remain.
- **NEXT:** verify conflict-safe cumulative metadata/cursor persistence and read-back; diagnose CDX URL/index misses with alternate representative URLs; continue the remaining 18 monthly archive samples; develop a new low-turnover risk/cash-gating hypothesis with predeclared train-only selection and independent prospective validation. Keep PAPER ONLY/HOLD.


## Main persistence failure and correction

- Main run `43974285006` research job PASSED; persistence failed because `git rebase origin/main` conflicted in the cumulative JSONL and manifest after a concurrent writer updated main.
- Workspace-only verified result: 2,486 rows, 1,427 article versions, 64/64 months completed, 18 remaining; SHA256 `f452b0ef5c21e12520b3c758087ae220010768e364189ec4d91fd1f7ed7d6ad0`. Not committed.
- Authoritative main read-back after failure: 2,226 rows, 1,163 article versions, 52 completed months, 30 remaining.
- Conflict-safe correction committed as `c47ef37891aea530eaae351263e469573f0f19c1`: fetch/reset to latest main, rerun idempotent merge and cursor scripts, test/read-back, then push; repeat from latest main on race.
- Follow-up run `43975610213` is in progress. Do not mark the 265-row increment DONE until main read-back confirms it.


## Fold diagnostics, missed opportunities and source audit

### Fold-level NET and post-exit diagnostics
- H80/300 base test NET by segment: **+A$18.208983 / −A$7.361149 / +A$27.606317**. Same-stake A$100 buy-and-hold: **+A$97.488848 / +A$2.464909 / +A$29.332280**. H80 beat buy-and-hold in none of the three segments.
- H50/200 base: +A$16.320851 / −A$14.351385 / +A$5.801691. H80 ATR2.5x: +A$12.716815 / −A$26.692014 / +A$0.578426. All three train/validation selectors chose HOLD.
- Missed-opportunity diagnostic is a forward-return observation after exit, not an executable counterfactual P&L: in segment 1, H80 ATR2.5x had 7 post-exit observations and all 7 were followed by a positive 7-day return (mean +6.992303%); the tight stop often exited before a rebound. H80 base's 3 segment-1 post-exit observations had mean +9.271928% over 7 days. Other segments were mixed. This supports rejecting the tighter stop, not claiming recoverable profit.

### Twelve requested news sources — access and run status
| Source | Access class | Latest verified result | Status |
|---|---|---|---|
| INFINI-NEWS | FREE/PUBLIC dataset | 0 usable rows; preview incomplete | PARTIAL |
| GDELT 2.0 | FREE/PUBLIC | 0 new rows in latest audit; HTTP 429; 29 earlier topic-search rows remain in cumulative metadata | BLOCKED |
| Media Cloud | KEY REQUIRED / restricted | No authorized API key; 0 rows | NOT ATTEMPTED |
| Common Crawl CDX | FREE/PUBLIC metadata | 12 URLs / 24 requests; 1 successful empty query, 23 failed/rejected; 0 new captures and no WARC body; 1 older verified capture remains in corpus | PARTIAL |
| NewsData.io archive | PAID / KEY REQUIRED | No authorized key or paid plan; 0 rows | NOT ATTEMPTED |
| cryptocurrency.cv | FREE/PUBLIC metadata | V42: 265 rows across 12 verified month-filtered requests; V38's separate 575-row sample overlaps and is not additive | DONE |
| CryptoPanic | KEY REQUIRED / plan | No authorized key/plan; 0 rows | NOT ATTEMPTED |
| Crypto News API | KEY REQUIRED / paid limits | No authorized key/plan; 0 rows | NOT ATTEMPTED |
| Federal Reserve FOMC calendar | FREE/PUBLIC | 48 date-only calendar rows plus 3 official release-clock records; not first-observed | DONE |
| Federal Reserve press archive | FREE/PUBLIC | 1,015 official date-only release records; not intraday timestamps | DONE |
| FOMC statements mirror | FREE/PUBLIC mirror | Reachable, but no original release timing verified; 0 usable timed rows | PARTIAL |
| SANDL | KEY REQUIRED / access unverified | No authorized key; 0 rows | NOT ATTEMPTED |

**Exact source-status counts:** DONE **3/12**; PARTIAL **3/12**; BLOCKED **1/12**; NOT ATTEMPTED **5/12**. No paid subscription or credential was obtained. Fed date-only records are event metadata, not article versions and are excluded from the 10,000-article target.

### First-observed corpus limitation
- `data/first_observed_news.jsonl` read-back: **249** RSS observations. Its current fields are `first_seen_ts`, `published_ts`, headline, source, summary and URL; it does not preserve a per-version content hash, explicit capture source, retrieval timestamp or confidence. It remains useful as an RSS observation-time record but is not a complete immutable article-version proof. V42 added **0** new first-observed snapshots.
- The V42 265 rows are retrospective publication-time metadata; 265 aligned to Kraken bars, **0 strict as-of eligible**. The one pre-existing verified Common Crawl capture does not align to these 265 records.


## Follow-up execution guard
- Commit `0184ea21d94f5f5a827716666fa32b0e8f81b5cf` prevents persistence commits from recursively triggering another full V42 run by excluding cursor/workflow-only pushes and skipping bot actors.
- Rerun `43975610213`: 348-test regression and V41/V42 research, fresh bridge, event study and monthly sample passed; Common Crawl probe remains in progress; conflict-safe persistence/read-back is pending.


## Full price-baseline cost reconciliation (V41 report bundled in V42 main artifact)

All figures are summed across the same three independent A$1,000 test accounts, with A$100 inclusive entry cap, 10% cash cap, 80bps taker plus 5bps half-spread and 5bps slippage per side.

| Baseline | Trades | Gross A$ | Fees A$ | Spread A$ | Slippage A$ | NET A$ | Return | Worst fold DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| SMA | 118 | 86.793716 | 183.534320 | 11.470939 | 11.470939 | -119.682481 | -3.989416% | -7.631585% |
| Momentum | 242 | 24.061066 | 354.521285 | 22.157592 | 22.157592 | -374.775403 | -12.492513% | -19.713239% |
| RSI mean reversion | 158 | 43.488769 | 239.118482 | 14.944926 | 14.944926 | -225.519567 | -7.517319% | -13.666897% |
| ATR/volatility breakout | 133 | 30.799440 | 202.987846 | 12.686756 | 12.686756 | -197.561916 | -6.585397% | -9.369700% |
| Regime filter | 267 | 22.700181 | 382.655597 | 23.915986 | 23.915986 | -407.787388 | -13.592913% | -24.735182% |
| Trend + ATR | 20 | 7.746437 | 31.495682 | 1.968484 | 1.968484 | -27.686213 | -0.922874% | -2.153114% |

- V41 H80 volume-confirmation variant: 7 trades, gross +49.330147, fees 11.429587, spread .714374, slippage .714374, NET +36.471813, return +1.215727%, worst fold DD -4.210041%; worse than H80 base.
- Volume-only: 7 trades, NET +38.360130; close-only: 7, +37.785654; shifted 7-day volume placebo: 7, +41.202690. The placebo was higher than the real feature, so no volume-confirmation edge.
- News-attention and 7-day delayed-news variants were exactly identical to H80 base (7 trades, NET +38.454151) because **zero strict as-of news events** entered the replay. This is not evidence that news is neutral or predictive; it means the available news sample could not change a decision.
- Same-stake A$100 buy-and-hold: 3 positions, gross +135.859476, fees 5.842937, spread .365252, slippage .365252, NET +129.286037, return +4.309535%, worst fold DD -2.790726%. It beat every selected/price-only strategy in aggregate.

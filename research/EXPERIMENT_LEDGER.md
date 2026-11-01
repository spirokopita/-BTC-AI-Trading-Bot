# BTC/AUD Research Experiment Ledger

## V27 — 2026-11-01, approved A$100 paper cap and 2026 Kraken fee reality check

**Status:** DONE: paper sizing source, realistic fee model, four matched research scenarios, 11 deterministic research tests, official-market CI and new news snapshot. PARTIAL: Android build/emulator verification pending. BLOCKED: independent prospective NET edge and cumulative point-in-time news history. NOT ATTEMPTED: live orders.

**Verified official-market evidence:** GitHub Actions run [41297183117](https://github.com/spirokopita/-BTC-AI-Trading-Bot/actions/runs/41297183117) passed V26's six gap/causal tests plus five V27 risk/fee tests, ran `python3 -m research.v27_position_sizing --output audit/v27-position-sizing.json`, and saved full JSON + first-observed news SQLite. Same official Kraken `XBTAUD_240.csv` member SHA256 `ed732a5cd906991b2d2b306b3266578dcea14b07c6f9b307cb4c3c3753eb296e`, 13,763 observed candles and 20 gap boundaries. Two later 2025–2026 folds are exploratory (V25 inspected these years), not untouched. Independent A$1,000 wallet reset for each fold. **No promotion**: train+validation selection HOLD at both caps under current 80bps.

**Important corrected fee assumption:** Official Kraken Pro Australian spot fee page https://www.kraken.com/au/pro/fees, checked 2026-11-01, lists standard tier-1 spot **40bps maker and 80bps taker**. V24–V26's 16bps taker was too optimistic for a low-volume account under current schedule. V27 applies current 80bps per side as a scenario to past price history, not actual 2020–2024 exchange fees; actual user tier and discounted pair eligibility remain unverified. Retains 5bps half-spread + 5bps slippage each side. Approximate round-trip break-even price move (1.009/0.991 - 1) = **1.816%** before extra impact.

**Current standard tier-1 taker scenario (80bps per side), two reset diagnostic folds:**

| Strategy | Completed trades | A$50 NET | A$100 gross | A$100 fees | A$100 spread | A$100 slippage | **A$100 NET** | Worst A$100 fold DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| SMA | 51 | -48.897141 | -8.596029 | 78.407428 | 4.900460 | 4.900460 | **-96.804378** | -5.678372% |
| Momentum | 110 | -97.863777 | -5.177700 | 165.301403 | 10.331335 | 10.331335 | **-191.141773** | -9.914884% |
| RSI | 82 | -69.391597 | +4.170229 | 125.043992 | 7.815252 | 7.815252 | **-136.504266** | -7.336663% |
| Breakout | 54 | -48.127962 | -1.210979 | 83.506287 | 5.219142 | 5.219142 | **-95.155551** | -4.938759% |
| Volatility regime | 108 | -92.735012 | +1.759229 | 162.737643 | 10.171103 | 10.171103 | **-181.320621** | -9.993421% |
| Slow SMA 50/200 +0.5% | 6 | -0.786221 | +9.106192 | 9.540331 | 0.596275 | 0.596275 | **-1.626688** | -1.574483% |
| Slow SMA 50/200 +2% | 8 | -9.603848 | -5.028210 | 12.579334 | 0.786205 | 0.786205 | **-19.179955** | -1.644612% |

**Legacy 16bps sensitivity:** A$100 slow SMA +0.5% diagnostic NET **+A$6.086363** (six trades) vs **−A$1.626688** at current 80bps; legacy A$50 +A$3.069562, current A$50 −A$0.786221. Pre-2025 A$100 slow SMA 0.5% training +A$41.988147, validation **−A$17.936265** under current fees. No training/validation eligibility; HOLD earns A$0 by avoiding trades. Same-stake A$100 buy/hold current-fee benchmark: gross −A$12.638522, fees A$3.070425, spread A$0.191895, slippage A$0.191895, **NET −A$16.092737**. Results are sums across independent reset accounts, not a single compounded history.

**News and leakage:** Latest V27 run observed 114 articles at actual first-seen time 2026-11-01 10:22:41 UTC (CoinDesk 25, Cointelegraph 30, Decrypt 39, The Block 20). The V26 prior snapshot had 134 articles, demonstrating publisher feed variability; do not treat lower V27 count as deletion from V26 artifact. News snapshots remain separate CI artifacts rather than a durable merged corpus. No post-observation return labels mature yet, so news predictive effect NOT TESTED; historical published dates are not substituted for first-seen times.

**Android and safety:** `PaperDecisionEngine` now min(A$100, 10% of cash) inclusive of actual rounded entry friction, 80bps paper taker fee; Kotlin unit assertions cover limit across cash/price combinations. Native source remains PAPER-ONLY, one long position, no live order route, stale/offline entry blocking. Android CI [41297183119](https://github.com/spirokopita/-BTC-AI-Trading-Bot/actions/runs/41297183119) pending at time of this ledger entry. Research strategy proxies are not exact Android SMA10/20 crossover/stop parity.

**NEXT EXECUTABLE ACTION:** Read Android build/emulator CI; if failed, fix and rerun. Persist first-observed news snapshots across runs, gather genuinely new BTC/AUD candles after 2026-11-01 observation, then evaluate frozen lower-turnover candidates with conservative 80bps taker fees and observed market costs. No strategy promotion without independent positive NET evidence.

---


## V26 — 2026-11-01, gap-safe later-period algorithm research and prospective news capture

**Status:** DONE: official-market forward evaluation, 6/6 deterministic tests, real-market CI, point-in-time news snapshot. PARTIAL: future event-study corpus (only first observation so far). BLOCKED: independently untouched prospective market evidence, historical first-observed news for earlier years and Android parity. NOT ATTEMPTED: Android APK, real trading.

**Verified evidence:** GitHub Actions run [41296254494](https://github.com/spirokopita/-BTC-AI-Trading-Bot/actions/runs/41296254494) passed the 6 deterministic causal/gap/fee/future-isolation tests, Kraken archive experiment, and prospective news RSS snapshot. Earlier run 41296212862 independently produced the same market results and 114 first-observed articles; the later final run captured 134 articles, read back from its SQLite artifact. Artifact [V26-BTC-AUD-Gap-Safe-Research](https://github.com/spirokopita/-BTC-AI-Trading-Bot/actions/runs/41296254494) contains JSON + news SQLite. Official Kraken `XBTAUD_240.csv` SHA256 `ed732a5cd906991b2d2b306b3266578dcea14b07c6f9b307cb4c3c3753eb296e`, ZIP member CRC `61c06c60` checked; whole multipart ZIP SHA not checked. 13,763 observed bars, 20 gap boundaries (NOT 20 missing candles). Kraken documents that OHLCVT omits intervals with no trades. No missing rows were fabricated.

**Protocol:** Pre-2025 reference segment selected by contiguous bar count only: 6,863 observed 4h bars, 2020-12-02–2024-01-20 UTC. 50% training / 25% validation with 20-bar embargo, 202-bar indicator warmup, seven fixed candidates: five V24 baselines and two 50/200 slow SMA thresholds (0.5% and 2%). Require >=5 training trades, >=3 validation trades, and positive NET in both, else HOLD. Later segment selected by latest timestamp and sufficient gap-free length: 1,999 bars, 2025-11-01–2026-09-30 UTC. First 202 bars used only for warmup; two non-overlapping reset-A$1,000 folds 2025-12-05–2026-05-04 and 2026-05-04–2026-09-30. Long-only next-open hypothetical fills, A$50 cap, taker fee 16bps + half-spread 5bps + slippage 5bps PER SIDE; last-open liquidation. **V25 already inspected a 2025–2026 segment: V26 is exploratory chronological later-period evaluation, NOT a genuinely untouched holdout.**

**Pre-2025 training/validation:** SMA training 92 trades NET −A$29.431310; validation 53 trades NET +A$8.946109. Slow SMA 0.5% training 7 trades NET +A$25.816029; validation 7 trades NET **−A$4.568657**. Slow SMA 2% training 7 trades NET +A$12.009348; validation 8 trades NET −A$18.195043. Other four baselines negative in both training and validation. **Predeclared selected policy HOLD; zero trades, A$0 NET in both later folds.** Do NOT promote the diagnostic slow SMA based on later-period gains.

**Later-period exploratory diagnostics (two independent reset wallets; not compounded):**

| Candidate | Trades | Gross A$ | Fees A$ | Spread A$ | Slippage A$ | NET A$ |
|---|---:|---:|---:|---:|---:|---:|
| SMA baseline | 51 | −4.076202 | 8.072684 | 2.522711 | 2.522711 | **−17.194309** |
| Momentum | 110 | −2.260472 | 17.379036 | 5.430948 | 5.430948 | **−30.501404** |
| RSI | 82 | +2.528952 | 12.997426 | 4.061697 | 4.061697 | **−18.591867** |
| Breakout | 54 | −0.545995 | 8.579689 | 2.681152 | 2.681152 | **−14.487988** |
| Volatility regime | 108 | +1.350038 | 17.089953 | 5.340611 | 5.340611 | **−26.421136** |
| Slow SMA 50/200, +0.5% | 6 | +4.634684 | 0.963150 | 0.300987 | 0.300987 | **+3.069562** |
| Slow SMA 50/200, +2% | 8 | −2.523621 | 1.270500 | 0.397029 | 0.397029 | **−4.588182** |

Slow SMA 0.5% returned +A$0.159711 (3 trades, max full-account drawdown −0.680733%) in fold 1 and +A$2.909851 (3 trades, max drawdown −0.454882%) in fold 2; total +A$3.069562. Same-A$50 fee-adjusted buy/hold returned −A$10.657851 and +A$3.796086 respectively, aggregate **−A$6.861765**. SMA baseline returned −A$13.182139 and −A$4.012170; aggregate −A$17.194309. Slow SMA 0.5% half-cost fold NET +A$0.550700/+A$3.308706; double-cost −A$0.618924/+A$2.115556. Tiny six-trade sample and negative validation make these gains insufficient for strategy promotion. No risk-free or consistently profitable edge established.

**News — actual prospective first-seen, NOT historical predictive proof:** At **2026-11-01 10:10:09 UTC**, final CI `news_intelligence.cli sync` saved 134 distinct articles in a SQLite artifact with immutable `first_seen_ts` and `available_ts >= first_seen_ts` (read-back verified). Counts: CoinDesk 25, Cointelegraph 30, Decrypt 59, The Block 20. Bloomberg Crypto feed failed closed after a cross-host redirect; 4/5 feeds succeeded. Sources included reports about Binance's breach and recovery, but historical publication timestamps are not equivalent to the bot's first observation. These articles became available to this research pipeline on Nov 1 and **cannot be used as signals for the earlier 2025–2026 candles**. No matured future price outcomes are yet available for these observations; NEWS PREDICTIVE VALUE = NOT TESTED. The workflow captures an independent snapshot per run, not a continuously maintained central news database.

**Failure cases / missed opportunities:** High-turnover baseline losses after costs; +2% slow threshold lost money; validation rejected both slow variants; no news causal evaluation; hypothetical open-price fills omit queue/depth and intra-bar execution. The selected HOLD policy missed the diagnostic +A$3.07 later gain, but did not incur the other candidates' losses; that opportunity is hindsight-only and cannot justify deployment.

**Verified commands:** `python3 -m unittest discover -s tests -p 'test_forward_gap_experiment.py' -v` (6/6 passed), `python3 -m research.forward_gap_experiment --output audit/v26-forward-gap-experiment.json` (official Kraken), `python3 -m news_intelligence.cli --news-db audit/v26-news-observed.sqlite sync` (134 articles in final first-observed snapshot). Verified outputs in Actions artifact; no Android APK or real orders.

**NEXT:** Begin immutable multi-run first-seen news collection and join only events available before candle decisions after a sufficient observation horizon; run later prospective paper performance monitoring with frozen 50/200 parameters and an actual Android execution parity test before any promotion. Independently source additional fresh market data and cost/spread evidence. Keep real trading OFF.

---

## V25 — 2026-11-01, official Kraken multi-year sparse-archive BTC/AUD experiment

**Status: DONE (data extraction, 6 tests, real-market experiment); PARTIAL (multi-year coverage and news study); NOT ATTEMPTED (Android strategy promotion, real orders).** PR #9 merged into main as squash commit 2361354a41067511f45b2272f86006c1b13b864c; latest pre-merge CI run 41294998715 passed all 6 tests and live archive research, and main-branch ledger read-back succeeded. First attempt used the most recent contiguous segment (1,999 bars, Nov 2025–Sep 2026) and returned train/validation all NET-negative, selected HOLD. A follow-up data-quality correction selected the longest contiguous segment by BAR COUNT ONLY, not by returns, to obtain a multi-year retrospective study; one transient CI failure occurred because code and test rename commits raced. The subsequent complete commit passed all six deterministic tests and official archive research in GitHub Actions run **41294883216**.

**Official source:** Kraken OHLCVT full ZIP (five parts), fetched with HTTP Range HEAD/206 from assets.kraken.com. The ZIP member is `XBTAUD_240.csv`, SHA-256 `ed732a5cd906991b2d2b306b3266578dcea14b07c6f9b307cb4c3c3753eb296e`, CRC32 `61c06c60`. Source contains **13,763 actual BTC/AUD 4h candles** and **20 gaps** (not filled). Five part sizes: 2,097,152,000 bytes each for parts 00–03, 1,157,945,626 bytes for part 04. The full 10GB ZIP SHA was NOT verified; only member CRC and extracted SHA were checked. The published support page describes a full archive through June 2026, but observed member data extends into September 2026; do not infer that the documentation cutoff exactly describes the current archive.

**Predeclared analysis segment:** Longest gap-free stretch **6,863 bars, UTC 2020-12-02 20:00 through 2024-01-20 12:00**. The remaining archive history is not silently zero-filled or used to tune this segment. 50% train / 25% validation / 25% test with 20-bar chronological embargoes. Train ends 2022-06-27; validation 2022-07-01 through 2023-04-06; two test folds 2023-04-09–08-30 and 2023-08-30–2024-01-20. Five frozen V24 research candidates, next-candle OPEN fills, spot long-only, A$1,000 reset per test fold, A$50 maximum position, 16bps taker fee + 5bps half-spread + 5bps slippage PER SIDE; hypothetical fills and terminal liquidation. These are NOT parity-verified with the Android paper engine.

**Training/validation selection:** All five strategies lost NET during training (SMA −A$21.065211, momentum −A$69.983804, RSI −A$19.558916, breakout −A$43.836674, regime −A$39.481583). Although SMA gained A$8.946109 NET on validation, it failed the positive-training requirement. **Selected policy: HOLD, 0 paper trades and A$0 NET across the two test folds.** Do not retrospectively select SMA using the test outcomes.

**Exploratory out-of-sample strategy diagnostics, not the selected policy:**

| Test fold | SMA trades | SMA gross A$ | SMA fees A$ | SMA spread A$ | SMA slippage A$ | SMA NET A$ | Same-A$50 buy/hold NET A$ |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2023 Apr–Aug | 30 | +4.601008 | 4.792387 | 1.497623 | 1.497623 | **−3.186626** | +0.300933 |
| 2023 Aug–2024 Jan | 26 | +21.415450 | 4.180905 | 1.306544 | 1.306544 | **+14.621458** | +24.970585 |

Across the two reset test wallets, diagnostic SMA gross +A$26.016458, fees A$8.973292, spread A$2.804167, slippage A$2.804167, NET **+A$11.434832**, versus equal-stake buy/hold **+A$25.271518**. This does NOT establish SMA as deployable: it failed predeclared train/validation eligibility and lagged buy/hold. Other test NET aggregates: momentum −A$16.597643, RSI −A$14.586487, breakout −A$0.155196, regime −A$25.957521. Costs and regime dependence remain material. Fee sensitivity for diagnostic SMA: first fold NET +A$0.717295 at half costs, −A$3.186626 at base costs, −A$10.911715 at double costs; second fold +A$18.056357, +A$14.621458, +A$7.783360 respectively.

**News watch, NOT a predictive backtest:** Reuters published 2026-11-01 05:49 UTC on Binance withdrawal restoration after the reported hack (source: https://www.reuters.com/legal/government/binance-resumes-bitcoin-withdrawals-after-covering-bulk-stolen-63-billion-2026-11-01/). ASIC has published CP392 on digital asset platform licensing (source: https://www.asic.gov.au/about-asic/news-centre/find-a-media-release/2026-releases/26-245mr-asic-consults-on-implementation-of-new-digital-asset-laws). These are contextual observations discovered on 2026-11-01, NOT reconstructed historical first-observed signals. Do not backfill them as if the bot knew them at publication time.

**Verified commands:** `python3 -m unittest discover -s tests -p 'test_kraken_archive.py' -v` (6 passed); `python3 -m research.kraken_archive --output audit/kraken-archive-experiment.json` (real official archive, 6,863 bars). CI run 41294883216, artifact ID 13078523908. A subsequent provenance-label-only code update is awaiting CI read-back. Report in GitHub Actions artifact; no real trades, no Android APK built.

**Next executable action:** Keep 2025–2026 as a separate strictly chronological future-period evaluation after training on pre-2025 history, with 102-bar post-gap warmup and no position spanning a missing candle. Test fewer-turnover controls and fee sensitivity on this separate, not-yet-promoted period. Build point-in-time first-observed news capture and a timestamped matched-control event study; until then NEWS PREDICTIVE VALUE = NOT TESTED. No strategy promotion without positive robust OOS NET and Android execution parity.


## V24 — 2026-11-01, verified public Kraken 4h OHLC, exploratory 3-fold walk-forward

**Status:** Research runner and 6 deterministic tests passed GitHub Actions run 41293127006. PAPER ONLY. No Android strategy promotion, no real orders, no AI-training claim.

**Source:** Public Kraken `/0/public/OHLC?pair=XBTAUD&interval=240`, directly fetched by GitHub-hosted runner. 720 completed four-hour BTC/AUD bars, UTC 2026-07-04 08:00 through 2026-11-01 04:00; API response SHA-256 `c313552d04160e13b50182886ae6da85b1655c27ecfe36156480a2b4f6f4a6cc`. Checked pair, chronology, gaps, duplicates, OHLC envelopes, finite values and excluded unfinished candle. Kraken public OHLC API provides only a short recent window; multi-year archive remains required.

**Execution assumptions:** Spot long-only; starting cash A$1,000 per independent fold; maximum entry A$50 and 5% cash; next candle OPEN after prior completed bar; taker fee 16 bps + half spread 5 bps + slippage 5 bps per side, using the repository's `trading_costs.estimate_execution`. One position at a time, no leverage. At each test boundary, liquidate hypothetically at the final test candle OPEN. No intra-bar stop, no real order book, no guaranteed fills. This is a research approximation, **not parity** with Android's SMA crossover and polling-based stops.

**Selection protocol:** Five fixed candidates: SMA trend-state proxy, 12-bar momentum, 14-bar RSI oversold, 20-bar high breakout, 100-bar trend/volatility regime. Train-only ranking requires at least 3 closed trades and positive NET; otherwise HOLD. Three non-overlapping test folds: 2026-09-05 to 09-25 (120 bars), 09-25 to 10-15 (120), 10-15 to 11-01 (100); training ends 20 bars before each test. Indicator warmup sees past embargo bars, never future bars. The same test periods must not be retuned in later runs and represented as untouched.

### Out-of-sample NET results — selected train-only SMA proxy

| Fold | Closed trades | Gross AUD | Fees AUD | Spread AUD | Slippage AUD | NET AUD | Max DD | Equal-A$50 buy/hold NET AUD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Sep 5–25 | 3 | +4.786721 | 0.486201 | 0.151940 | 0.151940 | **+3.996640** | -0.2364% | +4.064618 |
| Sep 25–Oct 15 | 4 | -0.987580 | 0.636145 | 0.198795 | 0.198795 | **-2.021314** | -0.2613% | -1.179425 |
| Oct 15–Nov 1 | 5 | -2.555495 | 0.793430 | 0.247946 | 0.247946 | **-3.844817** | -0.4007% | -3.778457 |

**Aggregate of three separate, reset A$1,000 test wallets:** SMA 12 trades, gross **+A$1.243646**, fees **A$1.915776**, spread **A$0.598681**, slippage **A$0.598681**, NET **−A$1.869491**. Fees/friction turned positive gross P&L into a loss. Equal-A$50 buy-and-hold across the same three independent windows: **−A$0.893264 NET**.

### Candidate aggregate NET over the same 3 disjoint OOS windows

| Strategy | Closed trades | Gross AUD | Costs AUD | NET AUD |
|---|---:|---:|---:|---:|
| SMA trend-state proxy | 12 | +1.243646 | 3.113138 | **-1.869491** |
| Momentum | 19 | -1.989264 | 4.916702 | **-6.905968** |
| RSI oversold | 19 | +1.975379 | 4.930304 | **-2.954924** |
| Breakout | 7 | +0.393187 | 1.816063 | **-1.422878** |
| Regime | 15 | +0.809689 | 3.889087 | **-3.079396** |

All five candidate strategies LOST money NET across these exploratory OOS folds. The breakout candidate lost the least, but selecting it based on these holdout outcomes would be hindsight tuning. **No promotion.** The last fold included a sharp negative market period; same-stake buy-and-hold also lost. Maximum drawdown is calculated on the full A$1,000 paper wallet, not on the A$50 position alone.

### News evidence and leakage firewall

Observed during this 2026-11-01 research run: The Guardian published a 2026-10-29 report about the Binance breach; Reuters published 2026-11-01 reporting on Binance withdrawal resumption. Both are potentially material market events, but our research did **not** possess a trustworthy first-observed historical news corpus at the relevant times. They are **not** treated as backtest signals or proof of predictive news value. For future event studies, record `published_at`, `first_observed_at`, source and exact headline, use only information observable before each decision timestamp, and compare matched controls.

**Next highest-value hypothesis:** Do lower-turnover trend/volatility filters preserve gross edge after transaction costs on **multi-year** Kraken BTC/AUD OHLCVT? Obtain official exchange archive, establish a genuinely untouched future holdout, compare against buy/hold with equal exposure, and run fee/spread sensitivity. Do not optimize against the V24 holdouts again.

**Verification:** GitHub Actions run `41293127006`, artifact `BTC-AUD-Research-OOS-Report`; six offline tests passed and genuine public feed experiment completed. No Android build or physical Samsung test was performed in this research run.

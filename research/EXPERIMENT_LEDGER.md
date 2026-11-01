# BTC/AUD Research Experiment Ledger

## V25 — 2026-11-01, official Kraken multi-year sparse-archive BTC/AUD experiment

**Status: DONE (data extraction, 6 tests, real-market experiment); PARTIAL (multi-year coverage and news study); NOT ATTEMPTED (Android strategy promotion, real orders).** PR #9 is a DRAFT pending final CI and review. First attempt used the most recent contiguous segment (1,999 bars, Nov 2025–Sep 2026) and returned train/validation all NET-negative, selected HOLD. A follow-up data-quality correction selected the longest contiguous segment by BAR COUNT ONLY, not by returns, to obtain a multi-year retrospective study; one transient CI failure occurred because code and test rename commits raced. The subsequent complete commit passed all six deterministic tests and official archive research in GitHub Actions run **41294883216**.

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

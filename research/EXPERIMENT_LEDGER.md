# BTC/AUD Research Experiment Ledger

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

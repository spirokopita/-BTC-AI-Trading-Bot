# V16 — Android BTC/AUD paper strategy (source of truth)

**NO REAL CRYPTO ORDERS.** No wallets, exchange accounts, credentials, trade endpoints, withdrawal functionality, or autonomous capital are included. This is a paper-only experimental simulator.

## New in V16
- Deterministic SMA10/SMA20 crossover baseline on Kraken BTC/AUD completed 4h candles. **Not AI, not a verified profitable system.**
- Fetches a separate observed Kraken BTC/AUD last ticker price at the actual poll, used for simulated execution and portfolio valuation. Entries are permitted only for a new signal less than 1 hour past the candle close. No retroactive trades during warmup, imports, or after an old signal expires.
- V27 max PAPER entry debit min(10% of available simulated cash, A$100), including individually rounded entry costs. One long position at a time; no leverage or shorts.
- V27 assumed per-side PAPER trading costs: **80 bps tier-1 taker fee** (current standard Kraken Pro spot schedule as of 2026-11-01) + 5 bps half-spread + 5 bps slippage. Prior 16bps fee assumption was too optimistic for current low-volume tier. Actual account/pair fees and fills may differ.
- Observed-price polling stop at -3% and target at +6%, plus bearish SMA exit. Stops run **only when Android polls successfully**, not instant real orders. WorkManager's nominal 15-minute schedule may be delayed by Doze or battery limits.
- Existing local SQLite account upgraded additively v1→v2; positions, realised execution records, mark-to-liquidation equity estimates, decision explanations and last ticker date persist. A$1,000 paper prefill preserved across upgrades.
- Independent UI toggles for monitoring and paper strategy (OFF by default). REFILL adds funding rather than profit. RESET clears open positions and disarms trading but keeps historical transaction audits.
- Dark-mode UI and widgets report estimated net equity and recent simulated BUY/SELL actions.

## Build
From the `android/` directory with JDK 17, Android SDK 35 and Gradle 8.9:

```bash
gradle --no-daemon testDebugUnitTest
gradle --no-daemon assembleDebug
```

GitHub Actions `.github/workflows/build-android.yml` runs both commands and publishes the signed-with-debug-key APK artifact after success. Kotlin JUnit tests cover crossover, data gaps, price-based exits, risk sizing and net-cost accounting. Android instrumentation/database migration and live exchange connectivity still require device tests.

## News eye (observational only)\n- Hard-coded HTTPS RSS sources: CoinDesk, Decrypt and Cointelegraph. Content and request sizes are bounded, redirects restricted to the source domain, and XML DTD/entities rejected.\n- News collected roughly every 30 minutes when monitoring is on. First-seen timestamps are written once to SQLite; publication time is retained separately.\n- RSS outages do not block public ticker polling or the strategy engine. Headlines are categorised for display only; no unvalidated sentiment trade entries.\n\n## Research roadmap
Historical BTC/AUD data provenance and 1h/15m timeframes, walk-forward tests and realistic fill assumptions are needed before treating the strategy as day trading. Existing Python news collectors and backtests **are not connected to the Android strategy**. Future news signals must be timestamped by actual first observation and validated out of sample to avoid look-ahead bias. There is no verified profit claim.

## Causal historical replay
- The on-device REPLAY CACHED HISTORY button backtests the baseline against
  up to 800 locally cached completed BTC/AUD 4h candles. No replay writes to
  the real paper ledger or implies a profitable algorithm.
- Decisions see completed bars only; simulated fills are delayed to the
  following bar's OPEN. Stops conservatively win when both stop/target touch.
- Uses the current PAPER A$100 / 10%-cash risk budget and 80bps fee model; no strategy is promoted from V27 research diagnostics.
- Kraken's roughly 720-bar OHLC limit spans at most about 120 days; the lab explicitly warns this is too
  little history for credible AI training or selection. Multi-year archives
  and purged walk-forward validation remain required.

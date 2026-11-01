# V24 algorithm research — 2026-11-01 (PR #8, paper-only)

**NEXT DATA ACCESS QUESTION:** Can the official multi-year Kraken BTC/AUD OHLCVT archive (large multi-part download) be ingested into a persistent research cache, and can point-in-time FIRST-OBSERVED news history be sourced, so the next experiment has a genuinely untouched multi-year test set? Current short Kraken OHLC endpoint cannot establish robust profitability.

### Current state — exactly five lines
1. Android V23 remains the deployed-source baseline, paper-only, strategy OFF by default; no real order route.
2. V24 research pipeline retrieved and validated 720 public Kraken BTC/AUD completed 4h candles (2026-07-04 to 2026-11-01 UTC).
3. Five predefined algorithms evaluated with three disjoint chronological out-of-sample folds and 20-bar training purges.
4. GitHub Actions run 41293127006 passed 6 deterministic tests and real-market research; report artifact retained.
5. Real orders 0; selected SMA proxy aggregate gross +A$1.243646, costs A$3.113138, NET **−A$1.869491** across three independent paper windows.

### Done — one highest-value unfinished task: verifiable market-data strategy research
- Added `research/market_experiment.py`, six tests, and `.github/workflows/market-research.yml` to fetch genuine public Kraken data, hash the source response, reject gaps/duplicates/unfinished candles and run fee-aware next-open simulations.
- Evaluated SMA trend-state proxy, momentum, RSI oversold, breakout and trend/volatility regime using the V6 fee execution model with Android-matching 16bps fee, 5bps half-spread and 5bps slippage **per side**.
- Three train-only selected SMA proxy test folds returned +A$3.996640, −A$2.021314 and −A$3.844817 NET respectively. The last period was a loss. Aggregate 12 trades: gross +A$1.243646, fees A$1.915776, spread A$0.598681, slippage A$0.598681, NET **−A$1.869491**. The equal-A$50-exposure buy-and-hold comparator returned −A$0.893264 NET across those three reset windows.
- All five strategies were NET negative across the combined exploratory folds; none promoted. This SMA trend-state research proxy is NOT identical to the Android crossover and stop logic; parity remains to be verified.
- News: located dated 2026-10-29 Binance breach reporting and 2026-11-01 withdrawal resumption reporting. No trustworthy historical first-observed feed was available; no news-predictive trading signal was backtested or claimed.
- All findings and source/protocol details: `research/EXPERIMENT_LEDGER.md`. Detailed per-trade outcomes are in the GitHub Actions artifact `BTC-AUD-Research-OOS-Report` from run 41293127006. Kraken raw API response SHA-256 `c313552d04160e13b50182886ae6da85b1655c27ecfe36156480a2b4f6f4a6cc`.

### Broken / limitations / next
- The public Kraken API supplies only ~120 days of 4h history. Official multi-year OHLCVT archive must be downloaded and validated before credible model selection.
- Historical news first-observed timestamps unavailable for these test folds; publication-time backfilling would be leakage. News predictive value NOT TESTED.
- The experiment uses next-open hypothetical fills and forced final-open liquidation, without order-book depth, intra-bar stops, exchange queue position or Android strategy parity. Real performance and production profitability NOT ESTABLISHED.
- Next: import verified multi-year exchange archive; run purged walk-forward with a fresh, untouched holdout and fee sensitivity, and validate a lower-turnover candidate. No Android APK was built during V24; prior V23 remains unchanged.

---

# V23 engineering update — 2026-11-01

### Current state — exactly five lines
1. Native Android BTC/AUD app remains paper-only; paper strategy OFF by default, no real order route or exchange keys.
2. V22 SQLite v4 persists gross execution notional, modeled costs, signed NET cash flow and realised NET P&L.
3. V23 adds a populated V2-to-V4 migration regression covering funding, an open position, a realised loss, news-table creation and safe reopen.
4. V23 GitHub Actions Android 15 emulator executed 19/19 instrumentation tests with zero failures/errors/skips; JVM tests and APK build passed.
5. Real exchange orders: 0; genuine BTC/AUD strategy gross, costs and NET profitability: NOT MEASURED.

### Done — one highest-value unfinished task: V2 legacy wallet migration validation
- Added a full V2 SQLite fixture with A$3,000 cumulative funding, A$2,435.50 cash, a 0.05 BTC remaining paper position and two legacy fills.
- Asserts V2->V4 adds first-observed news schema and backfills execution gross/cost/NET without rewriting funding, cash, position basis, ticker, original candle, or realised NET.
- Synthetic partial close remains a **-A$59.50 realised NET loss** (SELL gross A$450.00, costs A$4.50, NET cash inflow A$445.50); BUY gross A$1,000.00, costs A$10.00, NET cash outflow -A$1,010.00. These are fabricated test fixtures, not real-market results.
- Reopens the same database and checks the upgraded rows are unchanged (no duplicate backfill). No real trading adapter, keys or service were added.
- Android versionCode 23 / versionName 0.23.0-paper; migration production code unchanged.

### Tests and deliverables
- Test source: `android/app/src/androidTest/java/com/btcaud/paper/data/PaperDatabaseInstrumentedTest.kt`.
- [V23 GitHub Actions run 41246248077](https://github.com/spirokopita/-BTC-AI-Trading-Bot/actions/runs/41246248077) completed successfully on 2026-11-01 AEDT: Kotlin JVM tests, instrumentation compilation, debug APK assembly and Android 15 emulator instrumentation passed.
- Independently inspected [V23 instrumentation XML/logcat artifact 13059474276](https://github.com/spirokopita/-BTC-AI-Trading-Bot/actions/runs/41246248077/artifacts/13059474276): **19 tests, 0 failures, 0 errors, 0 skips**; the new V2 migration/reopen test executed. Live public Kraken-to-SQLite smoke test logged `LIVE_KRAKEN_SQLITE_VERIFIED; paper trades=0; net cents=0`.
- [V23 debug APK artifact 13059647916](https://github.com/spirokopita/-BTC-AI-Trading-Bot/actions/runs/41246248077/artifacts/13059647916) extracted: 11,091,296 bytes, APK SHA-256 `af114cb4757718ba1e38b351b44d06f38de77932bf92b590061dce0265667d92`. Stable signing secrets remain absent.

### Broken / limitations / next
- Physical Samsung installation, Glance widget layout, notification interactions, Doze delays and stable APK signing remain unverified.
- Real-market after-fee performance remains unmeasured; the current SMA rule is not a trained AI.
- Next: verify physical Samsung behaviour and stable signing, then acquire independently sourced multi-year BTC/AUD data for untouched out-of-sample NET research.

### Observed NET results
- Genuine BTC/AUD strategy gross: **NOT MEASURED**; costs: **NOT MEASURED**; NET: **NOT MEASURED**.
- Real exchange orders: **0**. Synthetic fixture realised NET: **-A$59.50**, strictly a loss.

---

# V22 engineering update — 2026-10-31

### Current state — exactly five lines
1. Native Android BTC/AUD app remains paper-only, with no real order route or exchange keys; paper strategy defaults OFF.
2. V22 persists gross execution notional and signed NET cash flow separately from existing costs and realised NET P&L.
3. Additive SQLite v4 migration backfills V2/V3 audit fields using integer-only arithmetic; V1 upgrades create the v4 trade table directly.
4. GitHub Actions Android 15 emulator executed 18/18 instrumentation tests (0 failures/errors/skips), including V3 migration and losing round-trip accounting.
5. Real exchange orders: 0; genuine BTC/AUD strategy gross, trading costs and NET profitability: NOT MEASURED.

### Done — one highest-value unfinished task: complete paper trade audit
- Added `gross_cents` (execution notional, not profit) and `net_cash_flow_cents` (signed BUY debit / SELL credit) to every new persisted paper fill.
- Added additive SQLite database version 4 upgrade. For existing V2/V3 fills, backfill both columns without changing original price, quantity, costs, realised NET, account funding or historical audit rows. Legacy gross uses exact half-up integer rounding with BigInteger intermediate multiplication.
- Kept existing `realised_net_cents` semantics: only closed SELL fills have realised trading P&L. BUY net cash flow is not a loss; SELL net cash flow is not profit.
- Exposed gross notional, costs, signed NET cash flow and optional realised NET P&L in Android execution history; dashboard latest-fill summary includes the same distinction.
- Added instrumentation checks for negative realised NET on a losing synthetic round trip, fill accounting equality, idempotent re-polls, and V3-to-V4 legacy trade preservation. Existing V1 migration test retained.
- Bumped Android to versionCode 22 / versionName 0.22.0-paper.

### Build and test evidence
- [V22 GitHub Actions run 41140286354](https://github.com/spirokopita/-BTC-AI-Trading-Bot/actions/runs/41140286354) **succeeded** 2026-10-31 09:53 AEDT: Kotlin JVM tests, Android instrumentation compilation, APK build and Android 15 emulator all passed.
- Independently extracted [Android instrumentation XML and logcat artifact 13018179083](https://github.com/spirokopita/-BTC-AI-Trading-Bot/actions/runs/41140286354/artifacts/13018179083): 18 tests, **0 failures, 0 errors, 0 skips**. Both `v3TradesMigrateGrossAndNetWithoutRewritingRealisedLoss` and `paperExecutionIsPersistedAndIdempotent` executed. Live public Kraken-to-SQLite smoke logged `LIVE_KRAKEN_SQLITE_VERIFIED` (no real orders).
- Extracted [V22 debug APK artifact 13018488727](https://github.com/spirokopita/-BTC-AI-Trading-Bot/actions/runs/41140286354/artifacts/13018488727): 11,091,296 bytes; SHA-256 `a81ebdd794a373ab4bfd9a3334a82da354d28f804e35c8a7a29f68924dc01e1b`. Stable signing secrets absent.
- Samsung physical-device installation, widget layout, persistent signing, offline Doze recovery and live BTC/AUD after-fee performance remain unverified; emulator verification does not prove those.

### Broken / limitations / next
- Stable APK signing is absent; avoid uninstalling an existing installation without backing up the paper wallet.
- V3-to-V4 migration passed Android 15 emulator instrumentation; V2 upgrade path and real existing-phone databases are not independently validated.
- Next: validate Samsung widget/notification/offline behaviour and stable signing; independently source longer BTC/AUD history for untouched out-of-sample NET performance.

### Observed NET results
- Genuine BTC/AUD strategy gross: **NOT MEASURED**; costs: **NOT MEASURED**; NET: **NOT MEASURED**.
- Real exchange orders: **0**. Synthetic fixture expected realised NET loss is -A$119.00; it is a test assertion, not market evidence.

---

# V21 engineering update — 2026-10-30

### Current state — exactly five lines
1. V20 native Android BTC/AUD paper-only app persists validated public Kraken observations in SQLite; simulated trading defaults OFF.
2. V21 dashboard now displays estimated equity, funding-adjusted NET, ticker age, last paper trade, open BTC quantity, SMA decision and health.
3. Cached quotes and open-position valuation are labelled STALE when the feed is paused, suspended, old or errored; no cached quote is described as live.
4. V21 adds network-independent local status refresh; JVM tests passed and Android 15 emulator ran 17/17 tests (0 failures/skips).
5. Real exchange orders: 0; genuine BTC/AUD strategy gross, trading costs and NET profitability: NOT MEASURED.

### Done — one highest-value unfinished task: stale-safe Android dashboard
- Added pure, clock-injected DashboardWidgetPresentation and upgraded the 4×2 Glance dashboard to include BTC/AUD quote age, estimated equity, funding-adjusted NET after modelled costs, open paper position, last trade costs and realised NET, SMA/AI distinction, and RUNNING/PAUSED/STALE/SUSPENDED health.
- Explicit STALE quote and STALE MARK on open-position equity/P&L when an observation is old, missing, future-dated, paused or invalidated by a feed error. No exchange order routes or API credentials were added.
- Added a separate 15-minute WorkManager WidgetRefreshWorker with **no network constraint**. It updates local widgets and status notification even when the network-constrained market sync cannot run; Doze can still delay the refresh.
- Added eight deterministic JVM tests for no-data, fresh/old/paused/error/suspended/future timestamps, stale open-position marks and negative realised NET, plus one Android instrumentation test for unique local-refresh scheduling.
- Bumped Android versionCode to 21 and versionName to 0.21.0-paper; existing SQLite data schema unchanged.

### Build and test evidence
- [V21 pull request #5](https://github.com/spirokopita/-BTC-AI-Trading-Bot/pull/5) merged as squash commit `06efab3f8ea86c43f5b27bc1102112fbedea8f95`.
- [V21 Android 15 CI run 40962512737](https://github.com/spirokopita/-BTC-AI-Trading-Bot/actions/runs/40962512737) completed successfully on 2026-10-30 AEDT: Kotlin JVM tests passed, Android instrumentation compiled, debug APK assembled, emulator executed **17/17 tests, 0 failures, 0 errors, 0 skips**. One new Android scheduling test executed.
- [Android test XML and logcat evidence](https://github.com/spirokopita/-BTC-AI-Trading-Bot/actions/runs/40962512737/artifacts/12936723842) independently inspected: 17 tests, 0 failures/errors/skips; live Kraken HTTPS-to-SQLite log marker `LIVE_KRAKEN_SQLITE_VERIFIED; paper trades=0; net cents=0` present.
- [V21 debug APK artifact](https://github.com/spirokopita/-BTC-AI-Trading-Bot/actions/runs/40962512737/artifacts/12936583165) extracted and SHA-256 verified: `e50c70f6d8465c753f0158ad1fa25bedf522373ec2aaf83ac03282bc73ed07d9` (11,091,296 bytes). Stable signing is still absent.

### Broken / limitations / next
- Physical Samsung widget rendering, tap actions, notification permission, Doze timing and stable signing/update continuity remain unverified.
- Local periodic refresh is best-effort: Android can delay both market sync and offline widget redraw. No 24/7 uptime promise.
- Trade-event storage records price, quantity, modeled costs and realised NET, but does not persist a separate explicit gross field; gross/cost/NET trade-audit completeness is a future ledger task.
- Next: physical-device widget layout, offline/Doze redraw and notification tap validation; establish persistent APK signing and complete gross/cost/NET trade-audit fields, then run independently sourced long-horizon BTC/AUD out-of-sample NET research.

### Observed NET results
- Genuine BTC/AUD gross: **NOT MEASURED**; costs: **NOT MEASURED**; NET: **NOT MEASURED**.
- Real exchange orders: **0**. Any paper fixture losses remain losses, not profits.

---

# V20 engineering update — 2026-10-29

### Current state — exactly five lines
1. V19 native Android BTC/AUD app uses public Kraken HTTPS, validated completed 4h bars, and SQLite; simulated trading defaults OFF.
2. V20 implements a purple-accent notification showing last successful poll, observed BTC/AUD price and explicit STALE/NO DATA labels.
3. V20 keeps an ongoing Pause action while monitoring and a dismissible Resume action when paused; both route to idempotent AppControl.
4. GitHub Actions on Android 15 executed 16/16 instrumentation tests (including 4 new notification tests): 0 failures, 0 errors, 0 skips; APK built.
5. Real orders: 0; genuine BTC/AUD strategy gross, trading costs and NET profitability: NOT MEASURED.

### Done — one highest-value unfinished task: notification user control and freshness
- Replaced paused-state notification cancellation with a dismissible PAUSED notification offering a Resume action. Monitoring ON retains a low-priority ongoing notification with Pause.
- Notification now displays last successful poll time, observed BTC/AUD price, and a STALE marker when paused, overdue, suspended or otherwise unhealthy. Missing prices explicitly say NO DATA.
- Both broadcast actions call AppControl.setEnabled with fixed boolean values, rather than a race-prone toggle; receiver remains non-exported.
- Purple #7C3AED is only a notification accent; Android owns status-bar/chip colours. No unsupported foreground service, promoted Live Update or uptime guarantee is claimed.
- Added four Android 15 instrumentation assertions covering RUNNING, PAUSED, STALE/SUSPENDED and WAITING states, action labels and ongoing flags. These tests construct notifications without requiring notification permission or network.
- Bumped Android package version to 0.20.0-paper / versionCode 20. Existing local SQLite data and paper-only execution remain unchanged.

### Verified build and tests — 2026-10-29 AEDT
- [V20 GitHub Actions pull-request run 40782358174](https://github.com/spirokopita/-BTC-AI-Trading-Bot/actions/runs/40782358174) completed successfully. Kotlin unit tests, instrumentation compilation, debug APK assembly and Android 15 emulator instrumentation succeeded.
- Independently inspected the [device-test XML artifact from successful push run 40782310019](https://github.com/spirokopita/-BTC-AI-Trading-Bot/actions/runs/40782310019/artifacts/12857743926): **16 tests, 0 failures, 0 errors, 0 skips**. Four V20 notification tests executed, alongside the prior 12 tests.
- Live public Kraken -> Android SQLite smoke test logged `LIVE_KRAKEN_SQLITE_VERIFIED; paper trades=0; net cents=0`; this is source connectivity, not market profitability.
- [V20 APK artifact](https://github.com/spirokopita/-BTC-AI-Trading-Bot/actions/runs/40782310019/artifacts/12857517887) downloaded and unpacked to `BTCAUD_Paper_V20_EmulatorVerified_Debug.apk` (11,091,296 bytes; SHA-256 `3381e102f0ddddbe315b76106e1ff7c5874df4e6778643285427ec468a191cb4`).
- Debug signing remains ephemeral because persistent signing secrets are absent; upgrading an installation signed with a different certificate may fail.

### Broken / limitations / next
- A paused notification can be dismissed. On Android 13+ notification permission may be denied; widgets and in-app controls remain the fallback.
- Emulator notification construction tests do not prove Samsung notification rendering, real tap handling, Doze scheduling or persistent signing on a physical phone.
- Next: physical-device notification tap/widget/Doze checks and persistent signing; emulator construction tests do not establish Samsung UX behaviour.

### Observed NET results
- Genuine BTC/AUD strategy gross: **NOT MEASURED**; costs: **NOT MEASURED**; NET: **NOT MEASURED**.
- Real exchange orders: **0**. Notification tests cannot establish financial performance.

---

# V19 engineering update — 2026-10-28

### Current state — exactly five lines
1. V16 native Android BTC/AUD app remains paper-only with local SQLite, purple status UI and Glance widgets; strategy defaults OFF.
2. V18 verified Kraken public BTC/AUD AssetPairs/Ticker/4h OHLC from a GitHub runner, but not on an Android device.
3. V19 adds a shared, strict Android public-feed parser and production network-to-SQLite sync path.
4. V19 Android 15 emulator executed 12/12 tests, zero failures and zero skips, including real Kraken HTTPS-to-SQLite.
5. Real orders: 0; genuine strategy gross, costs and NET BTC/AUD returns: NOT MEASURED.

### Done — one highest-value task: Android network-to-SQLite integration
- Production MarketSyncWorker now calls KrakenPublicFeed.syncInto(db), the exact path exercised by the live Android instrumentation smoke test.
- The shared parser checks the BTC/AUD market key, positive OHLC/ticker values, bid <= ask, candle alignment/ordering, completed-only bars, a contiguous 21-bar tail and completed-bar freshness <= 8 hours. It accepts up to 721 Kraken rows, persists at most 720 completed rows, and refuses redirects and oversized HTTP responses.
- Added emulator fixture tests for 721 rows with a forming candle, duplicate persistence, wrong market, stale data, duplicate/gapped timestamps, crossed bid/ask, paused writes, zero paper trades and stale status on failure.
- Added a real HTTPS Kraken -> Android parser -> SQLite smoke test. Network IO failures produce an explicit JUnit skip, not a fabricated pass. This is not a profitability test.
- **Verified CI 2026-10-28 10:04 AEDT (2026-10-27 23:04 UTC):** [GitHub Actions run 40598355525](https://github.com/spirokopita/-BTC-AI-Trading-Bot/actions/runs/40598355525) passed JVM, instrumentation compilation, debug APK build, and Android 15 emulator **12/12 tests with 0 failures, 0 errors, 0 skips**. The live Android test logcat explicitly states `LIVE_KRAKEN_SQLITE_VERIFIED; paper trades=0; net cents=0`. Public-market-audit job also passed.
- Preserved [emulator XML/HTML/logcat evidence](https://github.com/spirokopita/-BTC-AI-Trading-Bot/actions/runs/40598355525/artifacts/12777354695), [V19 APK artifact](https://github.com/spirokopita/-BTC-AI-Trading-Bot/actions/runs/40598355525/artifacts/12777484530), and [public-source audit](https://github.com/spirokopita/-BTC-AI-Trading-Bot/actions/runs/40598355525/artifacts/12777063501). Android package version is now `0.19.0-paper` (versionCode 19).
- Debug APK SHA-256 (downloaded artifact): `a8f8e05357cb8965614552cd73599cbdcb15b1fbf135f89041b258fc19a9f090`.

### Broken / limitations / next
- The real Android emulator Kraken network smoke **passed, not skipped**, but a future offline run may skip this test explicitly. Emulator success does not verify a physical Samsung device.
- No multi-year independently sourced BTC/AUD history, untouched out-of-sample NET evaluation, real news edge, or stable APK signing continuity is established.
- Next: test physical-phone installation, widgets, notification permission, Doze behaviour and stable APK signing; then acquire long-horizon BTC/AUD history for out-of-sample NET validation.

### Observed NET results
- Genuine BTC/AUD strategy gross: **NOT MEASURED**; costs: **NOT MEASURED**; NET: **NOT MEASURED**.
- Real exchange orders: **0**. Synthetic Android tests assert zero trading P&L and zero trades; they are not market profits.

---

# V18 engineering update — 2026-10-27

### Current state — exactly five lines
1. V16 native Android BTC/AUD monitor and local paper-only SQLite ledger remain the product; simulated trading defaults OFF.
2. V18 verified real Kraken BTC/AUD public AssetPairs, Ticker and 4h OHLC HTTPS responses from a GitHub runner, not a handset.
3. Kraken returned 721 4h rows: 720 completed plus one forming; the source audit now correctly excludes the forming row.
4. V18 CI passed 10/10 synthetic protocol checks and the retained 9/9 Android 15 emulator instrumentation tests; debug APK built.
5. Real orders: 0; genuine strategy gross, trading costs and NET BTC/AUD returns: NOT MEASURED.

### Done — one highest-value task: verify the real BTC/AUD public source
- Merged V18 PR #2 on 2026-10-27: https://github.com/spirokopita/-BTC-AI-Trading-Bot/pull/2 (squash commit c495e42beebdd0b8f007117bdd124c7e258914de).
- Added android/tools/verify_kraken_public.py, a **read-only** HTTPS source audit that verifies AssetPairs canonical BTC/AUD identity, Ticker bid/ask/last, OHLC chronology, positive finite prices, candle alignment, 21-bar tail continuity, completed-candle freshness and exclusion of the unfinished bar. It never calls private/order endpoints and needs no keys.
- The first live probe detected **721** rows, exposing our initial incorrect 720-row maximum. Corrected the parser's accepted raw count to 721 and added a regression test for 720 completed + 1 forming; **10/10** deterministic protocol tests passed.
- **Verified GitHub Actions run:** https://github.com/spirokopita/-BTC-AI-Trading-Bot/actions/runs/40415827030 on 2026-10-26 22:54 UTC (2026-10-27 09:54 AEDT). Observed market key XBTAUD, 721 raw 4h rows, 720 completed, 1 forming, latest 21 contiguous, last completed candle ending 2026-10-26 20:00 UTC; ticker last A$113,920.20 at HTTP observation time. Kraken REST Ticker does not provide a per-quote timestamp; the observation is not a historical tick stream.
- Preserved SHA-256 response hashes, HTTP Date and exact checked-at time in JSON evidence: https://github.com/spirokopita/-BTC-AI-Trading-Bot/actions/runs/40415827030/artifacts/12696001110.
- Android CI on the same commit also compiled the APK, passed JVM tests and **9/9 Android 15 emulator instrumentation tests**. APK artifact: https://github.com/spirokopita/-BTC-AI-Trading-Bot/actions/runs/40415827030/artifacts/12695778197. Device-test evidence: https://github.com/spirokopita/-BTC-AI-Trading-Bot/actions/runs/40415827030/artifacts/12695662761.

### Broken / limitations / next
- Live endpoint verification occurred on a GitHub runner. **Android phone connectivity, parsing and SQLite persistence against this real feed remain unverified**; CI tests use synthetic market fixtures. No evidence yet of a working 24/7 Android monitor.
- Physical phone installation, widget rendering, notification permission, Doze recovery and stable signing/update continuity are still unverified. APK remains debug-signed without configured persistent signing secrets; installing over differently signed APKs may fail, and uninstalling loses local data.
- Multi-year historical BTC/AUD source provenance and untouched out-of-sample after-fee evaluation are still missing. Kraken's 720 completed 4h rows are insufficient for credible AI training.
- **Next highest-value task:** add an Android network-to-SQLite integration smoke test against real Kraken public responses, checking 721-row/unfinished-bar handling, fail-closed stale behaviour and safe idempotent cache updates; then verify physical-phone behaviour and stable signing.

### Observed NET results
- Genuine BTC/AUD strategy gross: **NOT MEASURED**; costs: **NOT MEASURED**; NET: **NOT MEASURED**.
- Real orders: **0**. Source verification is not a backtest, paper-profit observation or live execution result.

---

# V17 engineering update — 2026-10-26

### Current state in exactly five lines
1. V16 native Android app monitors public Kraken BTC/AUD and keeps all simulated funds, decisions and trades in local SQLite.
2. Paper strategy is a rule-based SMA crossover, OFF by default; no wallet, live orders, exchange keys or verified AI model.
3. WorkManager, purple-accent notification and two Glance widgets remain bounded by Android background restrictions.
4. V17 GitHub Actions now boots an Android 15 (API 35) emulator and **executed all 9 existing SQLite/paper instrumentation tests successfully**.
5. Android debug APK built; physical Samsung testing and genuine BTC/AUD gross/cost/NET results remain unverified.

### Done — one highest-value task: execute Android instrumentation in CI
- Updated `.github/workflows/build-android.yml` to grant runner KVM access, boot a Google APIs API 35 x86_64 emulator and run `gradle --no-daemon connectedDebugAndroidTest` as a required build gate.
- Kept JVM unit tests, instrumentation compilation and `assembleDebug`; added always-uploaded Android test XML/HTML evidence artifact.
- **Verified run:** [GitHub Actions run 40239464599](https://github.com/spirokopita/-BTC-AI-Trading-Bot/actions/runs/40239464599) completed successfully on 2026-10-26 AEDT. Runner output: `Starting 9 tests on emulator-5554`, `Finished 9 tests`, `BUILD SUCCESSFUL`.
- [Android emulator test evidence](https://github.com/spirokopita/-BTC-AI-Trading-Bot/actions/runs/40239464599/artifacts/12616836718) and [debug APK ZIP](https://github.com/spirokopita/-BTC-AI-Trading-Bot/actions/runs/40239464599/artifacts/12617001299) were published by the runner.
- Existing tests exercised paper account refill/reset, SQLite schema/migration, idempotent controls, paused writes, candle deduplication, paper entry/exit and news first-observed retention. No network-connected Kraken test or visual widget test was run.

### Broken / limitations / next
- Physical-device installation, widget rendering, notification permissions, Doze recovery and public Kraken/RSS reachability are **NOT TESTED**. Emulator instrumentation tests validate SQLite/paper logic, not the whole app UX.
- Signing secrets were absent in the verified CI run. The resulting ephemeral debug-signed APK cannot update an APK signed by a different certificate; uninstalling loses app data. Do not uninstall a prior build until its local data is preserved.
- Android 15+ background execution cannot guarantee 24/7 monitoring or immediate protective exits. The current rule-based strategy has no demonstrated after-fee edge.
- **Next highest-value task:** verify full phone smoke test and stable signing/update continuity; then collect source-audited BTC/AUD history and run out-of-sample NET evaluation.
- **Question for device-validation run:** Which Android phone/emulator can be used for manual widget/notification/Doze checks, and has a persistent signing keystore been configured in GitHub Actions secrets?

### Observed NET results
- Real orders: **0**. Genuine BTC/AUD gross, trading costs and NET returns: **NOT MEASURED**.
- Emulator tests: **9/9 passed**. These are functional tests, not performance or profitability measurements.

---

# V16 engineering update — 2026-10-25

### Current state in five lines
1. V16 native Android public-market monitor, optional local simulated BTC/AUD strategy and persistent fee-accounting SQLite ledger are committed.
2. Android observed ticker execution uses completed-bar signals, first-seen gating, 5%/A$50 long-only sizing; trading is OFF by default and is **not AI**.
3. Three bounded HTTPS RSS feeds now populate an observational, first-seen-timestamped news eye; no headline controls trades.
4. A causal offline replay lab executes following-candle fills and warns of short Kraken OHLC sample history; Python research suite passed 130 tests locally.
5. GitHub Actions has built V16 successfully and compiles JVM and Android instrumentation tests. Real-device behavior and net profitability remain unverified.

### Completed
- Preserved pre-existing installed app account with additive SQLite migrations v1 -> v3. Trades, equity and funding history are separated.
- Explicit paper control, execution audit, reset/refill separation, dark-mode improvements, and traceable decisions.
- Kotlin strategy, costs, guardrails, replay, news labels and instrumentation source tests.
- Expanded recent public Kraken OHLC retention; missing historical bars are not invented and gaps in signal lookback block new entries.
- Corrected fresh-install v3 database schema after review.
- Added a separate signing-secret path in Gradle/Actions; no private key is committed.

### Broken / limitations / next
- **Important:** Existing V15 APK cannot be replaced by these V16 debug builds because signer certificates differ. A stable keystore secret must be installed once for future upgrade continuity. Uninstalling old builds removes local app data.
- GitHub runner compilation does not execute Android instrumentation tests on a real device or prove RSS endpoints work on a Samsung phone.
- Android background jobs are inexact; protective exits can be delayed by Doze/network failure.
- The current app does not implement a trained AI, news-based edge estimation, 15m/1h streaming trading, or reliable verified annual profitability.
- Official live Kraken OHLC provides only roughly 720 4h bars; obtain multi-year properly sourced archives and run time-separated validation before promoting any learned model.
- Next: phone smoke test, stable signed updates, model-data provenance/audit, and forward paper performance tracking.

---

## Historical changelog (previous notes retained)

# Project changelog / next-run briefing

**OPEN BLOCKER (V15): Which GitHub repository should receive the Android project so GitHub Actions can actually compile and test the APK?** No repository was provided or modified in this run.

## 2026-10-25 — V15 CI build pipeline

### Current state in exactly five lines
1. V12 Python strategy/backtesting and paper engine retained; genuine BTC/AUD NET edge unverified.
2. V13 Android monitor, widgets, simulated funding and background scheduling remain source-only.
3. V14 Kotlin fee-aware single-position paper ledger retained; not integrated with UI or persistence.
4. V15 adds GitHub Actions SDK/Gradle debug APK build and JVM test workflow; remote run NOT executed.
5. Real orders: 0; real Kraken BTC/AUD NET return: NOT MEASURED; installable APK: NOT VERIFIED.

### Done
- Added `.github/workflows/android-paper-ci.yml` with least-privilege GitHub permissions, Android SDK setup, Java 17, Gradle 8.9, `assembleDebug`, `testDebugUnitTest`, artifact validation and debug APK upload.
- Added Android README instructions for manually triggering and retrieving the build.
- Local static YAML/workflow checks and retained host tests run as reported in RUN_SUMMARY.md.

### Broken / next
- This runtime cannot run Android SDK/Gradle; the workflow has not been executed on GitHub, and no APK/device result is claimed.
- **Next:** Run CI in a repository, inspect/fix actual compile errors, verify installation and widgets on device. Keep paper-only execution.

### Observed NET results
- Genuine market gross/cost/NET: NOT MEASURED. No new simulated strategy trades; no profit claimed.

---

# Project changelog / next-run briefing

**OPEN BLOCKER (V14):** Which Android SDK/Gradle-enabled build runner or GitHub Actions repository can compile and device-test the Android app? APK compilation and device verification remain unperformed.

## 2026-10-25 — Run 10 (V14 pure Kotlin fee-aware paper ledger)

### Current state in exactly five lines
1. V12 Python research and paper engine retained; historical net edge unproven.
2. V13 Android monitor, funding, notification and Glance widget sources retained.
3. V14 adds a pure Kotlin single-position paper fill/round-trip fee ledger.
4. V14 Kotlin host checks pass; Android APK/device and genuine Kraken validation remain untested.
5. Real orders: zero; real BTC/AUD NET results: NOT MEASURED.

### Done
- Added `android/app/src/main/java/com/btcaud/paper/core/PaperTradeLedger.kt` for integral-cent and satoshi paper-only accounting with fee/spread/slippage and gross/cost/NET reporting.
- Added `android/host_tests/PaperTradeLedgerHostTest.kt` for deterministic round-trip, accounting, and rejection tests.
- Compiled pure Kotlin sources with locally installed kotlinc and ran host test successfully.
- Existing app remains monitor-only; ledger is NOT wired to UI, database, trading signals or Android worker.

### Observed NET results
- Synthetic fixture only: gross +A$50.00; total modeled costs A$8.41; NET +A$41.59. This is a math fixture, NOT a real market result.
- Genuine Kraken BTC/AUD returns: NOT MEASURED. Real orders: 0.

### Broken / next
- Android SDK/Gradle missing; no APK compiled or on-device verification.
- Partial sells, exact Python V12 parity fixtures, DB persistence and strategy integration remain incomplete.
- **Next highest-value task:** Build Android APK in SDK-enabled CI, repair compile errors and execute instrumentation tests. Do not activate real orders.

---

# Project changelog / next-run briefing

**OPEN BUILD BLOCKER (Run 09 / V13):** This runtime has Kotlin JVM and Python, but **no Android SDK, Gradle or internet access for Android dependencies**. V13 Android source and 12 Kotlin host tests exist, but no APK or on-device/widget test is possible here. An Android Studio/SDK + Gradle 8.9 build runner is required. **No live wallet is required.**

## 2026-10-25 — Run 09 (V13 Android native paper monitor and refill)

### Current state in five lines
1. V12 Python trading research, fee engine, simulated wallet, news, restart-safe paper loop and read-only dashboard remain intact; 130/130 Python tests pass.
2. V13 adds `android/` native Kotlin/Compose project, local SQLite paper prefill A$1,000, auditable refill/reset and funding-adjusted NET P&L.
3. V13 implements WorkManager public Kraken 4h completed-candle polling, pause/resume, purple-accent notification and two Glance home-screen widgets.
4. Kotlin-only host tests **12/12** and Android source contract tests **5/5** pass; 5 Android instrumented tests are written but not executed.
5. **No Android APK built, no on-device test, no genuine Kraken candles imported, no AI orders, no real trades, no observed profit.**

### Done
- Native Android project: Compose control screen, SQLite paper account with prefilled A$1,000, REFILL +A$1,000, RESET, funding audit and explicit separation of deposits from profit. Default starts PAUSED.
- Local public market monitor: Kraken XBTAUD 240-minute OHLC request, integer-cent validation, reject partial/stale/gapped tails, SQLite timestamp deduplication. Offline/no network in build environment, so actual fetch remains unverified.
- Unique WorkManager periodic 15-minute job plus one-time sync on user activation; network required, safe cancellation and transactional enabled-state recheck after fetch. No foreground service or live order API.
- 2×1 one-tap ON/OFF Glance widget with idempotent fixed actions, 4×2 resizeable Glance dashboard widget with net equity/P&L, latest price, no trades, AI disabled and health state. Purple (#7C3AED) notification with Pause; system bar colour is not controllable by apps.
- Pure Kotlin model validates simulated refill/reset, overflow, stale status and completed candles; 12/12 JVM tests passed. Five Python static source/manifest contract tests passed. Five Android SQLite instrumentation tests authored, **not run**.
- V12 Python regression suite re-run: **130/130 passed**. Source-verified BTC/AUD history in bundled `data/market.sqlite`: **0 rows**.

### Broken / not verified
- No Android SDK/Gradle, so **no compiled APK**, no installation, no widget rendering test, no real notification/permission test, no Kraken network request in this environment.
- No Android paper trade/strategy engine yet; only public data monitoring and simulated funding. The V12 Python engine is a reference, not an Android runtime component.
- No evidence of a profitable trading edge; genuine market NET returns are **NOT MEASURED**. No real-money orders or wallet access.

### Next highest-value task
Build V13 with Android SDK + Gradle and run device/instrumentation tests, then fix actual compile/runtime issues before claiming an installable APK. After that, port the V12 fee-aware paper ledger with golden fixture parity tests and keep real trading disabled.

---

## Prior project changelog / next-run briefing

**OPEN BLOCKER (Run 08):** The deployment host and real Kraken BTC/AUD archive source are still unconfirmed. The current project SQLite candle cache has no genuine prices or contemporaneously collected RSS history. Which internet-connected Linux VPS will run the *paper-only* service and import source-verified history? No live trading is permitted.

## 2026-10-24 — Run 08 (V12 read-only dashboard)

### Current state in five lines
1. V5 Kraken OHLCV cache and validation are implemented; **no verified genuine BTC/AUD candles are stored** here.
2. V6 shared trading-cost engine and V7 persistent local paper wallet drive V8/V9 historical research.
3. V10 observed-time news intelligence and V11 restart-safe paper decision daemon exist but are **not deployed** and have no proven net trading edge.
4. V12 introduces a local, GET-only monitoring dashboard over the four SQLite databases with estimated NET accounting and explicit unknown-data states.
5. **130/130 unit/integration tests passed** (120 retained, 10 new), plus a clearly labeled synthetic accounting smoke example. **Real trades: zero.**

### Done
- `dashboard/snapshot.py`: opens only existing SQLite databases using `mode=ro` and connection-local `query_only`; does not create files or initiate trading. Consistent read transactions; journal/cash reconciliation errors report unavailable data instead of inventing returns.
- Portfolio accounting from V7: initial and remaining simulated cash, closed-trade gross/NET P&L, maker/taker fees on both sides, spread, slippage, win rate, last-candle estimated exit-liquidation equity, unrealized net mark-to-fee outlay and open stop/target risk. Closed-trade gross minus modeled costs is checked against NET.
- V5 market candle coverage (latest source label and recent 2,000-bar gap scan per timeframe), V10 observed-time news/feed attempts and V11 read-only decision/heartbeat journal integration. Synthetic provenance and stale observations flagged.
- `dashboard/server.py`: Python standard-library `ThreadingHTTPServer`, static local assets + `GET /api/status`; rejects POST/PUT/PATCH/DELETE, non-loopback binds, hostile Host headers and unknown paths; no third-party assets or real-exchange API calls. Security headers, `no-store`, Content-Security-Policy.
- `dashboard/static/`: responsive black-and-white presentation, 15-second auto-refresh, net equity SVG, fee breakdown, trade/market tables, simulated orders, headlines/decision evidence and diagnostic warnings. No clickable trade actions. Does not execute JavaScript from untrusted article names.
- Added 10 tests: DB absence/invalid file, cash/net/trade cost reconciliation, open-position liquidation parity, stale/lock warnings, source/time metadata, read-only file integrity, accounting corruption refusal, GET-only/Host header HTTP safety and remote-bind refusal. New demo runs on fabricated numbers in a temporary DB and is labeled SYNTHETIC.

### Results (NET of fees)
- **Actual historical BTC/AUD net performance: NOT MEASURED**. Genuine Kraken cache still has 0 candles; no live orders or real balances exist.
- Synthetic dashboard reconciliation-only demonstration: one closed simulated trade, gross +2.478619 quote units, fees 0.812975, spread 0.040649, slippage 0.022498, **NET +1.602497**. Not genuine price action, a prediction, or evidence of profitability.
- **130 tests passed** (120 retained V11 + 10 new dashboard tests). HTTP access returns JSON but does not allow any mutation.

### Broken / incomplete / risks
- No verified exchange archive/history, contemporaneous news history, or deployment machine. The dashboard can only display present local DBs; empty caches truthfully show UNKNOWN/NO DATA.
- Estimates use the same V6 cost model and last processed candle; not current bid/ask, actual fill depth or live profit. Maker-order probability, latency and partial fills are not established.
- Dashboard is localhost-only and unauthenticated; for use from a phone another device needs authenticated forwarding. Never expose the dashboard directly to the internet.
- Gap count on the dashboard covers latest 2,000 records per timeframe; full data history requires V5 audit.
- Strategy alpha is unproven; displaying attractive graphs must not be interpreted as proof of net profitability.

### Next single high-value task
**Deployment & real-data validation gate:** on an authorised network-connected Linux machine, ingest and verify authentic Kraken BTC/AUD historical bars and current public RSS feeds, validate candle gaps and fees, deploy the paper-only loop/dashboard under limited privileges, and then conduct an untouched forward paper run. Don't enable actual orders or assume any profits.

---

## 2026-10-24 — Run 07 (V11 resilient PAPER strategy daemon)

### Current state in five lines
1. V5 Kraken multi-interval SQLite OHLCV cache exists, but authentic Kraken BTC/AUD history has **not** been imported here.
2. V6 fees, spread and slippage drive V7 paper wallet and all V8/V9 fee-aware research components.
3. V9 hindsight/train-test analysis and V10 first-observed RSS event study remain research-only, not demonstrated profitable.
4. V11 adds fail-closed 24/7 PAPER-only strategy loop integrating Donchian trend breakouts with strictly earlier qualified news and minimum NET edge.
5. **120/120 regression tests pass**, zero real trades or historical trading P&L measured; Roadmap 8 dashboard is next.

### Done
- `strategy_loop/engine.py`: fresh completed Kraken BTC/AUD candles only, strict source/time/gap checks, complete warm-up with no retrospective entries, deterministic one-decision-per-bar journal, restart persistence via V7 SQLite wallet, EMA/Donchian buy/sell and protective exit handling.
- Entry gate: strictly recent actually-observed BTC/MARKET/MACRO-positive article; event evidence uses only *earlier* matured labels and purged chronological holdout. Requires >=20 training and >=10 validation events and positive NET outcome fractions/means; conservative train/holdout mean gross move then checked through the V6 fee-aware expected-net rule (at least +0.5% NET, not just positive gross). Without evidence, HOLD.
- Default passive maker-limit entry 10bps below last close and cancel if unfilled after 3 bars. The V7 paper engine's conservative strict-through OHLC fill behavior and protective stop-loss/take-profit stay in force. Fees include both sides plus spread and slippage; no unverified maker-fill assumption is credited as earned profit.
- `strategy_loop/cli.py`: `once`, unattended `serve` (public no-key Kraken/news sync, bounded polling/backoff, independent feed error handling), `status`, single-process Linux `fcntl` lock and heartbeat/error journal. Failed feeds block new buys but do not disable existing protective simulated sells.
- `deploy/crypto-paper-bot.service.example`: **uninstalled** secure service template requiring user-supplied non-root Linux setup, no trading credentials.
- `tests/test_strategy_loop.py`: 13 new tests for replay idempotency, news-availability timing, maker expiry/trade-through, full round-trip cost gate, stale/gapped/untrusted price refusal, simulated stop under feed outages, and Linux singleton lock.
- `examples/strategy_loop_demo.py`: fabricated 700-bar restart demo processed once, 2nd iteration processed zero bars, wallet validated. **No orders and no P&L**; only architecture test.

### Results (NET of fees)
- **Actual historical/live BTC/AUD P&L: NOT MEASURED**. No real OHLC feed, source-qualified events, profitable AI model or execution established.
- **Fabricated local test:** starting 1,000 simulated quote units; ending 1,000 units, **net 0**, no completed trades and no claimed earnings. Mocked-news unit tests exercise order plumbing only; they are NOT market results.
- Full regression suite **120 tests passed** including 107 retained V10 tests. CLI correctly refused to run with the empty market cache.
- **Live exchange orders placed: 0.** No live execution code was enabled or added.

### Broken / incomplete / risks
- No verified Kraken BTC/AUD candle backfill or live RSS first-observation data. Without sufficiently matured news-event evidence, V11 intentionally cannot open positions.
- Market provenance stored in SQLite is a source label, not independent verification; users must obtain actual data from the exchange. News correlations can be spurious; strict filters are not proof of predictive alpha or calibrated model estimates.
- Candle-only limit fill model cannot model queue position, partial orders, impact or real maker fill likelihood. Modeled slippage/spread also need comparison to genuine trade/order-book data.
- Networked host deployment, restart-on-boot and monitoring have not been performed here. Cron/systemd example provided only.
- Restarting after missing candles fails closed; open **paper** positions cannot be updated without a valid sequential candle feed. Any eventual live-grade counterpart needs tick-level protections and broker reconciliation.

### Next single roadmap item
**8. Read-only dashboard** for whole-account gross and net P&L, actual simulated entry/exit fee components, open risk, recent orders, validated news evidence and feed/loop health. Must display missing data and empty-account states truthfully and must not trigger orders.

## 2026-10-24 — Run 06 (V10 news intelligence, no trade execution)

### Current state in five lines
1. V5 Kraken multi-timeframe historical storage exists; **zero authentic Kraken BTC/AUD candles** are verified in this environment.
2. V6 provides the single configurable fee, spread and size/volatility slippage cost engine used in all offline examples.
3. V7 persistent paper wallet and V8 net-fee backtester are unchanged; risk locks and the absolute prohibition on live trading remain in place.
4. V9 adds fee-adjusted hindsight oracles and purged walk-forward validation; no profitable BTC/AUD edge has been established.
5. V10 adds observed-time-aware BTC-first RSS ingestion and fee-aware news/price event studies; **107/107 tests pass**, market/news empirical effectiveness unmeasured.

### Done
- New `news_intelligence/feeds.py`: bounded, HTTPS-allowlisted RSS/Atom collector for five public outlets with ETag/Last-Modified support, retries of transient errors, XML DOCTYPE/ENTITY rejection, timezone-aware publication dates, and per-feed failure isolation.
- New `news_intelligence/store.py`: persistent SQLite cache with unique canonical URL, title syndication deduplication, actual bot first-seen timestamps, category/asset tags and ingest state. Late historical article publication is **not** misrepresented as a tradable contemporaneous observation.
- New `news_intelligence/signals.py`: transparent rule-based sentiment/event tags, BTC vs altcoin scope, event return windows from LAST KNOWN completed candle to FIRST qualifying future closed candle. V6 fees, spread and slippage determine **net** outcomes and break-even threshold. Categories summarise material movement frequencies; associations explicitly do **not** demonstrate causation.
- The as-of study CLI strictly ignores not-yet-completed future candles and refuses to report from an empty, invalidly-sourced or gapped BTC/AUD price series.
- `train_signal_quality` uses chronological category-level training/holdout with purged label windows; `event_signal_asof` allows only research candidate annotations based on strictly earlier matured evidence. **No autonomous trading signal is installed into V7**; that is Roadmap 7.
- Added `news_intelligence/cli.py`, an explicitly SYNTHETIC demo and 12 new unit tests. Full regression suite **107 tests passed** with 95 retained tests; no real orders.

### Results (NET of fees)
- **Genuine news-conditional BTC/AUD net returns: NOT MEASURED.** First direct CoinDesk RSS access failed `URLError: Temporary failure in name resolution`. Existing Kraken candle cache still has zero verified genuine observations.
- **SYNTHETIC accounting example only:** a fabricated Bitcoin ETF headline accompanied by a 0.0993% future upward midpoint move yielded a **-1.6119% simulated entry-to-exit return after estimated fees/spread/slippage**. The example produces **zero qualified news signal categories** due to tiny sample size. The price and story are fabricated; this is a program validation, not an earned or historically missed trade.
- 107/107 local `unittest` tests passed. No investment recommendations or live trades were generated.

### Broken / incomplete / risks
- DNS/network access to public news and Kraken markets is unavailable here. No 24/7 collection daemon or real article archive was established, so don't claim that macro/ETF/news predicts BTC.
- Rules-based lexicon sentiment can misunderstand irony, negatives, entities and topic salience. Publisher timestamps, editorial publication delays and overlapping articles are imperfect; first-seen protects simulated signal timing but doesn't prove universal availability.
- Price moves around articles are **correlations**, not causal event impacts. No matched controls or adequate independent holdout sample exists. ATR- and orderbook-calibrated live slippage is still unverified.
- The event-study is descriptive and not integrated with execution; its research candidate does not authorise trades.

### Next single roadmap item
**7. Combine causal/available historical price indicators with only validated news candidate signals into a continuously running, restart-safe **PAPER-only** decision loop. Fail closed until real candles/news are ingested and fee-aware thresholds are met.**

## 2026-10-24 — Run 05 (V9 fee-adjusted hindsight + purged walk-forward)

### Current state in five lines
1. V5 multi-timeframe Kraken BTC/AUD cache and import logic exist, but zero verified real candles are stored here.
2. V6 fee/spread/slippage engine is shared across V7 wallet and V8 backtester and new V9 diagnostics.
3. V7 provides persistent SQLite-only simulated trades, risk locks and a reconciled ledger; no broker order calls.
4. V8 computes fee-on/off net returns, trade metrics, drawdown and Sharpe; strategy edge remains unproven.
5. V9 adds counterfactual net-fee oracle analysis and train-only purged walk-forward validation; automated tests pass and live trading stays disabled.

### Done
- New `hindsight/analysis.py`: scores completed V8 trades against the best possible **future open-to-open** exit within a 60-bar window, and separately the best hypothetical delayed entry/exit within six delayed openings. Uses **V6 unified fees, spread and size/volatility slippage**, and explicit matching of entry/exit timestamps to the candle series.
- Reports realized **NET P&L** alongside oracle net/gross/fees/spread/slippage, possible early/late exits, and differences. An oracle selects future opening prices with knowledge of the future; it **cannot be traded** and must never be combined with earned profit.
- Identifies unexecuted strategy buy signals, calculates their hindsight net opportunity after costs, and warns that overlaps, pending orders, opportunity capital and risk locks make them non-additive, non-executable what-ifs.
- New `hindsight/walkforward.py`: a predeclared, small parameter grid is selected on **training-only net backtest return**, with purged chronological, nonoverlapping tests. Each test uses a clean V7 wallet; prior bars are used for indicator warm-up without allowing trades. The future oracle is diagnostics only, never an input for parameter selection.
- `hindsight/cli.py`: offline real-market-store report, `--walk-forward` option, configurable bar horizons and timeframe, strict empty/gapped-candle rejection. Fixed a discovered CLI bug so the non-default `--interval` is also passed into the ordinary V8 backtest.
- Added synthetic-only hindsight and walk-forward examples plus unit/integration tests for identical ledger accounting, net fees, oracle limits, missing-data refusal, non-default timeframe and mutation-of-heldout-prices leakage regression.

### Results (NET of fees)
- **Genuine Kraken BTC/AUD returns: NOT MEASURED** — local candle cache contains zero observations. No real orders placed.
- **SYNTHETIC software example**, 700 fabricated 4h bars: one realized paper trade and **+0.329151% account return after costs** (same V8 smoke test), versus hypothetical best later-opening exit **+9.1424 quote units** on the trade and actual realized trade **+3.2915 quote units**. The **+5.8509 quote-unit difference is unattainable oracle hindsight**, NOT profit or a performance forecast. No result was tuned using actual market data.
- Synthetic example: 40 unmatched prior-close entry signals scored and 40 positive-oracle opportunities; these **must not** be summed as earnings. Separate synthetic walk-forward example scored 3 future folds; each **0.0% net**, **zero trades**. This merely checks temporal separation, not model quality.

### Broken / risks
- Genuine Kraken BTC/AUD archives/network fetch, actual spread/depth, exchange-minimum orders, real slippage and partial fills remain unverified.
- Oracle scans future opening prices and can ignore protective stops, available cash, overlapping positions and fill probability; it is a **research upper bound, not an achievable trade plan**.
- No trained ML was added in this task. The small train-only grid is a test of strategy-parameter separation, **not proof of out-of-sample predictive advantage**. Years already examined elsewhere may be contaminated by earlier researcher decisions.
- Current walk-forward test periods may have no actual trades; do not interpret 0.0% synthetic returns as evidence the strategy is safe or profitable.

### Next single roadmap item
**6. Timestamped crypto/macro news and sentiment module** with sources, event-before/after attribution and a strict publish-time firewall. Genuine market data provenance and first networked Kraken backfill remain prerequisites for credible live-like event studies.

## 2026-10-24 — Run 04 (V8 unified fee-aware backtester)

### Current state in five lines
1. V5 Kraken BTC/AUD historical-data cache remains empty; genuine market test data have not been ingested here.
2. V6 trading-cost model is still the single source of fees, spread, and size/volatility slippage.
3. V7 SQLite paper wallet is now reused unmodified for V8 historical replay and its reconciled fills/realized P&L.
4. V8 implemented paired cost-on/cost-off replays with net performance, win rate, net profit factor, drawdown, Sharpe and full ledgers.
5. **78/78 tests passed**, no real-data profits measured and real-money execution remains unavailable/disabled.

### Done
- `backtester/engine.py`: strict OHLC validation, causal Donchian 20-day breakout and 10-day low/EMA200 exits, prior-EMA trend filter, next-open order fills, previous-bar ATR-based cost inputs, 10% protective stop and enforced cooldown.
- Historical runs dispatch buys, sells, targets and stops exclusively via V7 `PaperEngine`, preserving its persistence, spread/slippage/fee charges and risk halts.
- Separate `costs_on.sqlite` and `costs_off.sqlite` outputs, immutable fresh wallets, full trade logs plus bar-close net liquidation equity series. Side-by-side returns include full fees-on/off comparison and audit.
- Metrics: net account P&L, gross and net completed trade totals, net win rate, net profit factor, fee/share-of-gross-positive-pnl, spread/slippage, max drawdown and annualized Sharpe; zero-divisor metrics are explicitly null rather than made up.
- CLI on V5 Kraken BTC/AUD storage, strict no-imputation gaps, honest provenance metadata. Synthetic demonstration isolated in `examples/backtest_demo.py`.
- 12 new backtester tests + 66 retained tests = **78 passing** without resource leaks.

### Results (NET of fees)
- Genuine BTC/AUD performance: **NOT MEASURED**; shipped candle cache contains zero rows.
- SYNTHETIC price-path smoke test: 700 generated 4h candles, one round-trip trade; fees ON net account return **+0.32915%** (end 1003.2915 from 1000) vs all execution friction OFF **+0.42509%**. Trading fees **0.8266**, spread **0.0413**, slippage **0.0540** quote units. NOT historical or predictive.
- Real orders placed: **0**.

### Broken / risks
- No real Kraken BTC/AUD archive or public API response on this host (DNS inaccessible); cannot claim strategy works on market data.
- Intrabar path, passive limit fill probability, order-book impact, exchange lot/tick minima and exact Freqtrade dry-run parity are not modeled or verified.
- The fee-off comparison removes *all* modeled friction; return differences may also reflect sizing/risk paths. Do not interpret as simply fees paid.
- Strategy is a fixed baseline without trained ML; historical proxy backtests elsewhere do not prove forward net returns.

### Next single roadmap item
**5. Hindsight net-of-fees trade opportunity analysis** with predeclared benchmark and lookahead-safe train/test and walk-forward validation. Obtain authentic market data first to make profit/loss measurements meaningful.

## 2026-10-24 — Run 03 (persistent paper wallet)

### Current state in five lines
1. V5 public Kraken BTC/AUD historical data layer exists; networked ingestion and multi-year historical coverage remain unverified.
2. V6 costs module remains the **single source of execution and fee estimates**; default retail Kraken spot tier is modeled, not confirmed from real fills.
3. **V7** adds a persistent, locally simulated BTC/AUD spot wallet, market/limit orders, fills, stop/target exits, a full NET-P&L ledger and restart recovery.
4. V3/V4 trading strategy profitability remains unproven. Real Kraken BTC/AUD trading results remain **unmeasured**; all new sample candles are synthetic.
5. Paper-only safety remains absolute: no exchange-order functionality is connected; the V7 engine processes only provided offline candle data.

### Done
- `paper_engine/engine.py`: atomic SQLite ledger for cash, equity snapshots, simulated open position, unique/client-idempotent market and limit orders, maker/taker fills, stop/target protective exits, audit journal and cancellation.
- All new trade executions and position budgets use `trading_costs` for entry and exit costs. Net P&L is calculated from **actual simulated cash flows** and separately reconciles to gross less maker/taker fees, spread and slippage.
- Persistent risk settings: default A$1,000 starting cash, A$50 maximum order, 5% maximum exposure, 2% daily loss lock, 5% high-water drawdown lock. The lock rejects new buys after a breach, survives restart, and permits existing position exits.
- Candle processor guards against time travel, duplicate processing and unacknowledged history gaps; stop beats target in ambiguous OHLC bars; gaps through stops exit at opening quote, not at an unachievable stop.
- Newly filled market orders activate stops in the opening bar; for limit fills with unknown intrabar ordering, the stop is assumed if crossed, and same-bar targets are not credited.
- `paper_engine/cli.py` supports initialization, place/cancel offline orders, candle playback, replay CSV, status, trades, orders and reconciliation checks.
- `examples/paper_demo.py` generates an explicitly synthetic two-trade accounting report; `tests/test_paper_engine.py` verifies cash/fees, fills, restart, risk, gaps, rollback, maker/taker and idempotency.

### Results (NET of fees)
- New real-market BTC/AUD test trades or profit: **none**. Zero real orders.
- Offline synthetic example on arbitrary candles: initial 1,000 quote units, ending **998.3694**, combined **NET −1.6306**, total entry+exit fees 1.5870, modeled spread 0.0793 and slippage 0.0439. Not a performance forecast or historical replay.
- **66/66 automated tests passed**. No genuine Kraken connectivity was required or tested.

### Broken / incomplete / risks
- The standalone paper engine is not an always-on collector; a worker reading completed price bars, outage recovery and remote monitoring remain pending later roadmap steps.
- Native Freqtrade dry-run is not reconciled with this wallet. No live-grade execution fidelity is claimed: partial fills, book queue positioning, minimum lots/ticks and real spread/impact are absent.
- The OHLC replay assumes next-bar opening fills after an order placed on a prior bar and pessimistic stops on ambiguous candles. Real-time paper trading needs a feed that can actually observe those executions.
- No proven profitable strategy exists yet; original V3/V4 reports remain research artifacts, not real investment returns.
- Multi-year Kraken BTC/AUD history and a real API ingestion run on a networked host are still pending.

### Next single roadmap item
**4. Fee-aware, unified backtester** using genuine Kraken BTC/AUD from V5 when available, the exact V7 wallet, independent fee-on/fee-off controls, net profit factor, Sharpe, drawdown, net win rate, and gross/fee/net trade breakdown. Do not optimise on test-set data.

## 2026-10-24 — Run 02 (unified fee model)

### Current state in five lines
1. V5 Kraken multi-timeframe candle cache persists; real Kraken API sync remains unverified on this host.
2. V3 trade-outcome labels and V4 breakout proxy research are unproven; past strategies lost money on BTC/USDT proxy tests.
3. V6 now has one configurable `trading_costs` engine shared by research labels, fills, and candidate-trade estimates.
4. Risk controls and dry-run-only setup remain; V3 Freqtrade entry now explicitly rejects `dry_run=false` rather than relying on an arming file.
5. **44/44 local tests pass**, and both legacy research engines passed a synthetic-data smoke replay; **zero genuine market results** were measured today.

### Done
- `trading_costs/model.py`: maker/taker execution fees on both sides, optional USD-denominated volume tiers, spread and volatility/order-size slippage, funding for simulated perpetuals, opt-in transfer/network charges, budget-aware sizing, expected-net decision gate, minimum break-even gain and fully reconciled per-trade ledger.
- `config/fees.json`: exchange-configurable retail Kraken spot fee assumptions 0.40% maker/0.80% taker at initial tier, with partial 30-day USD volume tiers; spread/slippage figures are adjustable **assumptions**.
- `trading_costs/cli.py`: offline fee-inclusive net P&L and break-even calculator.
- Changed V3 and V4 future-outcome labels and research executions to call the new module, replacing competing hardcoded percentage formulae. V4 CLI produces a no-fee reference for technical rules.
- Every completed V3/V4 research trade now carries a gross P&L, both fee line items, modeled spread, slippage, funding, total costs and **NET P&L** in its log.
- `docker-compose.yml` mounts read-only cost package/config for Freqtrade strategy target calculations; `BtcAudEdgeV3` rejects real execution if dry-run is false even if an old arming marker exists.
- 16 new/expanded integration/cost checks and 28 retained tests all passed (44 tests total). V3 and V4 research scripts also smoke-ran on labeled **synthetic candles**, not market evidence.

### Fee example (not an actual trade)
- Midpoint buy A$100,000/BTC, midpoint sell A$104,000/BTC, total budget A$50, assumed ATR ratio 2%, market/taker fills.
- Gross profit A$1.9813; trading fees A$0.8084 (entry A$0.3968, exit A$0.4115); modeled spread A$0.0404; modeled slippage A$0.1032; **net A$1.0293**, or +2.06% on A$50.
- Estimated break-even price move ~1.90%; numbers depend strongly on *assumed*, not observed, spread/slippage and tier.

### Results (NET of fees)
- **No new real-market or validated backtest returns**. Implementation and synthetic integration tests only, not a profit claim.
- Synthetic V4 smoke check (2022-10-01 to 2023-05-31, generated candles): technical replay with modeled fees -1.237%, same replay with all costs disabled -0.715%; six closed trades each. **DO NOT interpret as BTC history.**
- Synthetic V3 smoke check: one trade, modeled net account equity 996.89 from 1000 (generated candles only).
- No money placed at risk; **0 real trades**.

### Broken / incomplete / risks
- Freqtrade's built-in dry-run execution/accounting uses its own broker fill and fee handling. Actual native runtime P&L is **not yet reconciled** to `trading_costs` because the modular wallet doesn't exist. No claim that all platforms share identical fills.
- Kraken order-book spread/depth and actual slippage have not been sampled; input values are configuration estimates. Funding is a linear signed-rate approximation, not an exchange-specific funding settlement feed.
- Tier schedules can change; only the first five current example USD-volume tiers are listed, and other exchanges need their own profile.
- Multi-year Kraken BTC/AUD archive remains missing. Native strategy/Freqtrade/Docker end-to-end was not run (dependencies/exchange access unavailable).
- Synthetic data is **not valid for estimating strategy profitability**. Existing research may be overfit; preserve unseen data.
- No multi-order asynchronous paper wallet exists yet. Ensure fee ledger, risk lock and account balances reconcile exactly in Roadmap 3.

### Next single roadmap item
**3. Paper-only trading engine** with wallet, order lifecycle, position sizing, stop/target, full fee ledger, restart persistence and audit checks. Integrate strictly with `trading_costs`, with orders never reaching Kraken.

## 2026-10-24 — Run 01 (data layer)

### Current state in five lines
1. V3 paper-only FreqAI trade-outcome model exists but has no established trading edge.
2. V4 breakout research exists and showed a preliminary proxy backtest profit; it was not validated on genuine Kraken BTC/AUD.
3. Independent risk guard and dry-run Freqtrade configuration remain available; no exchange credentials are bundled.
4. **V5** added a Kraken BTC/AUD multi-timeframe historical-data layer with SQLite storage, backfill imports and explicit gap reports.
5. **28 automated tests PASS** for all retained components (11 data tests + 17 retained tests); no networked exchange integration test completed.

### Done
- `data_layer/storage.py`: schema, per-pair/per-interval candle primary keys, candle integrity checks, bulk upsert, source provenance, ingestion-event log, UTC CSV export, coverage summaries and nonfabricated gap reports.
- `data_layer/kraken.py`: free public Kraken OHLC requests for intervals `1,5,15,30,60,240,720,1440` min; bounded 429/5xx and transient API retries, `Retry-After`, request pacing, candle finalization, incremental update checkpoint, 720-bar history warnings.
- `data_layer/cli.py`: `sync`, `import-csv`, `import-zip`, `report`, `export`.
- Chunked official Kraken OHLCVT ZIP/CSV import (10k candles at a time); doesn't mix BTC/USD or BTC/USDT into BTC/AUD.
- Kept V4 breakout research alongside V3 dry-run framework. No live trade execution added or enabled.
- Offline tests passed: timestamp alignment, wrong OHLC rollback, duplicate/idempotent ingestion, zip pair matching, rate-limit recovery, closed-candle filtering, incomplete archive warnings, cross-pair safety, UTC export and retained V3/V4 regression tests.

### Results (net of fees)
- **No newly measured net trading return**: this run implemented infrastructure, not a new trading strategy/backtest. Historical research remains preliminary and is not presented as live performance.
- **Real Kraken BTC/AUD candles ingested in this environment: 0.** No genuine archive bundled; do not treat mock/API fixtures as real prices.
- **Live orders placed: 0.**

### Broken / incomplete / risks
- Outbound DNS/network access from this execution environment failed when requesting Kraken and Coinbase public APIs; therefore no end-to-end REST response verification or actual BTC/AUD historical download occurred.
- Multi-year genuine Kraken history needs the official full archive or the Kraken Trades endpoint, followed by recent API updates. The official archive is several gigabytes; V5 does not download all parts automatically.
- Strict 4-hour V4 backtester can reject Kraken no-trade gaps; gap policy should be explicit rather than quietly fabricating candles.
- No overlapping-job lock, monitoring or retryable daily scheduler is installed; `cron` is documented as an example only.
- 2025–2026 analysis has already been studied repeatedly, so future model tuning on these years risks overfitting. Preserve new truly out-of-sample periods.
- Live execution must remain DISABLED. Running existing Freqtrade config is paper-only; full end-to-end Freqtrade integration remains unverified.

### Next single roadmap item
**2. Configurable fee model** shared by paper wallet, signals, backtester and trade ledger. Separate maker/taker, per-side charges, volatility/order-size slippage, spread, optional perpetual funding and volume tiers; report gross and **NET** P&L for every trade. Test against fee-off baseline. Do not modify strategy parameters until this is done.

## Roadmap state
1. Data layer — **implemented & offline-tested**; pending first real Kraken sync and archive import on networked host.
2. Fee model — **implemented & locally tested**, external Freqtrade dry-run reconciliation pending.
3. Paper engine — **implemented and locally tested**, pending genuine market feed and Freqtrade reconciliation.
4. Backtester — **implemented, locally tested**; authentic BTC/AUD dataset still pending.
5. Hindsight/missed-moves — **implemented & tested on synthetic data**; historical validation blocked.
6. News module — **NEXT**.
7. Combined strategy loop — pending.
8. Dashboard — pending.

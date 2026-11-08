## V38 — 2026-11-09: historical archive provenance + downside-shock ablation (PR #20)

**TOP BLOCKER:** 818 initial metadata/version rows do not establish a tradable historical first-observed corpus; only 1 WARC-index-attested crawl, dated 2024-02-23 after the 2024-01-31 FOMC release. No untouched positive NET OOS candidate; PAPER ONLY HOLD.

**SOURCE AUDIT:** 137 cryptocurrency.cv historical archive rows (6 outcome-independent January months, 2020–2025; source-claimed archive 662,047 NOT verified), 603 official Fed press-release date-only links (2020, 2022, 2024, 2026), 48 FOMC statement links, 3 explicit official release clocks (2021-01-27/2023-02-01/2025-01-29 at 19:00 UTC), 1 Common Crawl WARC-index capture with digest and filename, 0 INFINI (HTTP 503), 29 deduplicated GDELT recent articles (30 raw, 1 URL duplicate; transient HTTP 429 on prior PR run), 0 mirror article rows (reachability only), 0 from 5 key/paid/disabled sources. Total 818 version records, 817 unique canonical URLs; first-verified crawl 1, strict-as-of historical tradable news 0. INFINI body publisher rights; metadata-only retention. Source classification registry 23 and hypothesis graph 19 edges, all effects UNPROVEN. Original Fed statement clock is official retrospective time, NOT independently first-seen. First retrieval by this pipeline is 2026-11-08 UTC; no backdating.

**MARKET:** Official Kraken archive XBTAUD_240.csv member SHA256 ed732a5cd906991b2d2b306b3266578dcea14b07c6f9b307cb4c3c3753eb296e, 13,763 4h bars, 20 gaps; eligible gap-free segments 6863/3398/1999. Historical prior-inspected exploratory. In 6863-bar segment, 65 retrospective publication-time links <=4h to next bar, 2 Fed official release-clock links, 0 strict as-of historical news. Older news before first bar explicitly rejected; no cross-gap price alignment.

**STRATEGY / REPRO:** Predeclared h80/300 base, h80 downside 2.5%, h80 downside 4%, h80 downside 2.5% +42-bar delayed placebo, h50 downside 2.5%. A negative 4h completed close-to-close shock vetoes BUY for 6 bars; SELL always available. 3 independent 50/20/30 chronological folds, 20-bar embargo, train/validation-only candidate selector HOLD/h50_down25/HOLD. A$100 inclusive or 10% cash (whichever smaller), A$1000 starting PAPER wallet per segment; 80bps taker +5bps half-spread +5bps slippage per side. 7 H80 trades gross +51.333281 fees 11.448071 spread .715531 slippage .715531 NET +38.454151, 3 wins/4 losses, worst DD -4.192577%. H80 shock gates and shifted placebo identical to price-only despite 144/24/12 candidate shock-bar counts in tests. H50 downside 10 trades gross +25.219918 fees 15.934943 spread .995947 slippage .995947 NET +7.293084, 3 wins/7 losses. Earlier-data selector test NET -14.351385; buyhold +129.286037. Price baselines SMA -119.682481 / momentum -374.775403 / RSI -225.519567 / breakout -197.561916 / regime -407.787388 / trend ATR -27.686213. H80 downside A$50 +19.640152 vs A$100 +38.454151; half/standard/double costs +45.178506/+38.454151/+25.215557. No trade changes, no evidence shock gate adds edge, REJECTED. Existing history NOT untouched.

**TESTS / FILES:** research/v38_archive_ingest.py, research/v38_shock_walkforward.py, research/v38_persist_sample.py, tests/test_v38_archive_ingest.py, tests/test_v38_shock_walkforward.py, tests/test_v38_persist_sample.py, research/v37_source_topic_registry.json, .github/workflows/v38-archive-ingestion.yml. Merged-main CI 42530218869 PASSED 50 deterministic/regression tests and official archive research; artifact 13636713722. Commands: python -m unittest discover -s tests -p 'test_v38_archive_ingest.py' -v ; python -m unittest discover -s tests -p 'test_v38_shock_walkforward.py' -v ; python -m unittest discover -s tests -p 'test_v38_persist_sample.py' -v ; python -m research.v38_shock_walkforward ; python -m research.v38_archive_ingest --with-kraken ; python -m research.v38_persist_sample. Main-only cumulative write/push VERIFIED: dbd15f25b413bc1fbfc2da549f3cbde31b0fea3f, 818 rows, SHA256 58b5fb461ba00ae0631195e2d19ab4db3eab74d682421d811905a5bed6954cf7.

**DONE:** Live metadata adapters and exact HTTP failures; real 818-row sample, 1 WARC capture, Fed clocks, market join; new shock hypothesis/negative control; 50 tests; CI artifact. **PARTIAL:** 10k goal, revision provenance, representative non-event coverage, maker adverse selection, fresh bars. **BLOCKED:** historical news predictive benefit and untouched NET OOS. **NOT ATTEMPTED:** Android APK or live trading. **NEXT:** Broaden months, retry INFINI 503 and seek GDELT historical bulk coverage with bounded backoff, integrate official vintage macro/FX and repeat purged causal ablations. PAPER ONLY HOLD.

---

## V36 — 2026-11-08: cost-hurdle/volatility gates and as-of article veto (PR #19)

**BLOCKER:** Earlier-data selector HOLD in all 3 segments. Historical prices previously inspected; article availability reconstructed, not genuine first observed; real fills absent. No Android promotion, PAPER ONLY HOLD.

**DATA:** Official Kraken XBTAUD_240.csv member SHA256 ed732a5cd906991b2d2b306b3266578dcea14b07c6f9b307cb4c3c3753eb296e; 13,763 4h candles/20 gaps, segments 6863/3398/1999. 38 retrospective article events, 61 scheduled RBA events; article events by 2020–2026 year 0/6/16/3/4/2/7, 57/84 months empty; 0 historical article versions independently first observed. News +1h/+24h assumed after displayed publication/revision; not evidence of actual historical availability. No fresh OHLC/new articles this run.

**ALGORITHM:** H80/300 or H50/200 hysteresis; predeclared 2.5% fast/slow MA hurdle, 42/126-bar completed-candle volatility ratio >1.5 veto, retrospective article-only 7d as-of entry veto, +7d shifted placebo. BUY veto only; SELL not blocked. Three chronological 50/20/30 train/validation/test partitions with 20-bar embargo, earlier-data-only selection; 3 independently reset A$1000 wallets, A$100 inclusive debit/10% cash; 80bps taker +5bps half-spread +5bps slippage per side. Test history exploratory NOT untouched.

**TEST NET A$:** H80 base 7 trades gross 51.333281 fees 11.448071 spread .715531 slippage .715531 NET +38.454151; H80 hurdle 7 trades gross 31.523430 fees 11.288391 spread .705540 slippage .705540 NET +18.823957; volatility-only and news-only H80 both identical to H80 base; hurdle+vol+article veto 7 trades gross 28.784422 fees 11.266501 spread .704171 slippage .704171 NET +16.109578; +7d placebo NET +18.823957; H50 hurdle+vol 9 trades NET +8.473316. News addition delta -2.714379, no predictive benefit. Selected HOLD/HOLD/HOLD test NET 0. A$100 buy/hold +129.286037. Worst H80 hurdle+vol fold DD -4.344621%, folds +16.274874/-6.076577/+8.625660. Half/standard/double costs aggregate +25.365534/+18.823957/+5.945753. A$50 same strategy +9.825531 vs A$100 +18.823957. SMA/momentum/RSI/breakout/regime/trend-ATR baselines -119.682481/-374.775403/-225.519567/-197.561916/-407.787388/-27.686213.

**TESTS/REPRODUCE:** PR CI 42420540363 and merged-main CI 42420645371 PASSED 10 V36 +8 V35 +5 V27 =23 deterministic tests and official Kraken archive study. Artifact 13593257881 (merged main); PR artifact 13592359512; report SHA256 a507fac67eb8434638abd42cb8523f8e57bf33ce9cdf3bbf88204a74aadfedf6. `python -m unittest discover -s tests -p 'test_v36_volatility_news_gates.py' -v`; `python -m research.v36_volatility_news_gates --output audit/v36-volatility-news-gates.json`.

**DONE** new cost-aware regime features, chronological ablations, negative control, news coverage audit, fees/caps and loss tests, CI. **PARTIAL** broad article provenance and representative sampling, untouched OOS, actual fills. **BLOCKED** Android promotion. **NOT ATTEMPTED** APK/live. **NEXT** consistent news archive with historical first-seen versions, broader non-headline sampling, independent forward data and robust maker adverse-selection simulation.

---

## V35 — 2026-11-07: retrospective news-reaction study, no Android promotion (PR #18)

**BLOCKER:** Need genuinely untouched positive-NET OOS with representative point-in-time article versions and realistic fills; unavailable. PAPER ONLY HOLD.

**DATA:** Official Kraken XBTAUD_240.csv SHA256 ed732a5cd906991b2d2b306b3266578dcea14b07c6f9b307cb4c3c3753eb296e, 13,763 4h bars/20 gaps, three eligible segments 6863/3398/1999. News: 23 new source-linked retrospective articles 2021–2026, 4 market-following excluded, 19 retained; plus 19 earlier curated and 61 RBA events = 99 event timestamps. Availability: new V35 articles +24h after latest displayed revision, V29 curated +1h, V31 curated +24h, scheduled RBA +24h after indexed release; all ASSUMED, historical first-observed and complete revision histories unverified. Search ranking means news coverage is NOT representative. 23 anchors eligible across test folds; 16 of those did not clear 0.5% reaction threshold, not necessarily missed profitable trades.

**ALGORITHM:** Fixed 0.5%/1% post-availability 4h reaction thresholds, next-open hypothetical BUY, 24h fixed hold then next-open SELL; independent reset A$1000 accounts, <=A$100 inclusive and <=10% cash, taker 80bps plus 5bps half-spread +5bps slippage per side. 50/20/30 train/validation/test, 20-bar embargo; train+validation-only selector required >=3 trades and positive NET in both; selected HOLD/HOLD/HOLD. Delayed placebo 7d and 28d, ordinary-only/prior-only/scheduled-only ablations. No future information in decision; historical dataset was previously inspected.

**TEST NET:** 0.5% combined 7 trades gross +11.486189 fees 11.182399 spread .698905 slippage .698905 NET **-1.094021**; 1% 2 trades NET **+1.352762** insufficient. Ordinary-only 4 trades NET -1.384531; prior curated 1 trade +1.438152; scheduled RBA 2 trades -1.147642. 7d delayed placebo 10 trades -2.106931; 28d delayed 2 trades -2.682510. Same-stake buy/hold +129.286037; H80/300 hindsight +38.454151. Selector NET 0 because HOLD all folds. Worst 0.5% fold DD -0.472732%. Half/standard/double costs +5.227226/-1.094021/-13.532048; A$50 -0.543419 vs A$100 -1.094021.

**BASELINE REGRESSION:** SMA 118 trades -119.682481; momentum 242 -374.775403; RSI 158 -225.519567; breakout 133 -197.561916; volatility regime 267 -407.787388; trend ATR 20 -27.686213. All A$ NET across three independent test accounts.

**TESTS/ARTIFACT:** GitHub Actions 42306385487 PASSED 8 V35 +7 V34 +5 V27 =20 deterministic tests and official archive study. Artifact 13546711827, JSON SHA256 c5dd96b5a34794b4f3b7331f3fd2e612023dd5fdb9ac3e1b039fede4dd2c62ca. `python -m unittest discover -s tests -p 'test_v35_news_reaction.py' -v`; `python -m research.v35_news_reaction --output audit/v35-news-reaction.json`.

**DONE** research source, dataset, safety tests, workflow, real archive evaluation. **PARTIAL** representative article coverage, revision archives, order-book fills, untouched OOS. **BLOCKED** promotion. **NOT ATTEMPTED** APK/live. **NEXT** independent archival news feed with historical first-seen snapshots, preregistered news feature selection and genuine future validation. Preserve Android V27 PAPER HOLD and A$100/10% cap.

---

## V34 — 2026-11-06: outcome-independent RBA policy-event coverage, cost-aware risk veto (PR #17)

**BLOCKER QUESTION:** Can a strategy selected only on earlier data achieve independently untouched OOS positive NET, with verified point-in-time news and real fill assumptions? Not demonstrated. PAPER ONLY HOLD; no Android promotion.

**DONE / DATA:** Source is the official RBA annual policy decision indexes for 2020, 2021, 2022, 2023, 2024, 2025 (61 dates, all meetings including holds, not selected using Bitcoin outcomes). Data `data/rba_policy_calendar_2020_2025.json` SHA256 `091b8313dd7445a16bd1944aeb96b24cab2f4a0ae3ae43d13ad01ad642f2d576`. 14:30 Australia/Sydney release time and daylight saving conversion, plus *assumed* 24h availability delay. Neutral event category; no signed rate-surprise, original revision history or actual first-observed bot timestamps. Source indexes: `https://www.rba.gov.au/monetary-policy/int-rate-decisions/YYYY/` for each YYYY 2020–2025. Sources verified 2026-11-06. This is systematic scheduled macro coverage, NOT comprehensive news.

**MARKET:** Official Kraken `XBTAUD_240.csv`, SHA256 `ed732a5cd906991b2d2b306b3266578dcea14b07c6f9b307cb4c3c3753eb296e`, member CRC 61c06c60; 13,763 bars, 20 gaps, three >=1000-bar gap-free segments 6863/3398/1999. No gap crossing. Full archive ZIP hash not verified. Historical prices inspected in V29–V33, so exploratory rather than untouched OOS. Three independent A$1000 wallets; max A$100 inclusive entry debit and <=10% cash; standard 80bps taker +5bps half-spread +5bps slippage per side, hypothetical next-open fills.

**STRATEGY ABLATION, A$100:** H50/200 price-only 10 trades gross +25.705656 fees 15.941756 spread .996373 slippage .996373 NET **+7.771157**. Post-release RBA 24h veto identical. 48h veto 10 trades gross +20.598813 fees 15.892818 spread .993312 slippage .993312 NET **+2.719374** (delta **-5.051783**; 1 fold trade audit changed). Delayed +7d placebo identical to price-only. H80/300 7 trades gross +51.333281 fees 11.448071 spread .715531 slippage .715531 NET **+38.454151**; 24h/48h/placebo identical. H80/300 worst test-fold DD -4.192577%. Same A$100 buy/hold **+129.286037**. Train+validation selector HOLD/h30_120/HOLD, actual selected test NET **-9.722842**. Positive H80 aggregate is hindsight and does NOT qualify for promotion.

**POSITION SENSITIVITY ON IDENTICAL PERIODS WITH SAME 80bps FEES:** H50/200 A$50 10 trades gross 13.483660 fees 8.036341 spread .502279 slippage .502279 NET **+4.442762**; A$100 NET +7.771157. H50/200 RBA 48h A$50 NET **+1.876934** vs A$100 +2.719374. H80/300 A$50 7 trades gross 26.118768 fees 5.758746 spread .359935 slippage .359935 NET **+19.640152** vs A$100 +38.454151. Synthetic test verifies each entry inclusive debit <= selected A$50/A$100 cap AND <=10% pre-entry cash; invalid >A$100 rejected. 16bps historical fee is NOT used.

**EVENT STUDY:** 61 scheduled dates; 46 had strictly prior matched non-event controls in gap-free segments (33/12/1), 15 unavailable/without match. 14 release events in selected test windows (10/4/0). First segment 33 events, 4h mean absolute BTC/AUD move after availability 0.697707% vs prior matched control 0.892645% (difference -0.194937 percentage points); 24h absolute 2.052160% vs 2.785318%; 48h 2.917463% vs 3.997144%. Other segments have 12 and 1 matched events and mixed effects. These are observational, non-independent, NOT a causal volatility or predictive finding. Event-entry NET long return and control comparisons in artifact. No news-derived NET advantage.

**TESTS / AUDIT:** `python -m unittest discover -s tests -p 'test_v27_position_sizing.py' -v` (5 passed); V31 hysteresis (8); V33 cross-regime (6); V34 RBA (7); **26 total passed**. Official Kraken study and V31 regression CI passed: V34 run `42121702456`, V31 run `42121702537`. Artifact `13458182758`, JSON SHA256 `cad1f4d0d18fc37c9e53badc650ff5b426d5ba5774e1672722ac1d678c222604`. Initial A$50/A$100 sensitivity code accidentally passed a display label as replay strategy; CI failed on run `42121378203`, fixed in commit `cecabb2559223615f460a3028134a649b59b67ba` and reran to green. `python -m research.v34_rba_systematic --output audit/v34-rba-systematic.json` reproduces official market report.

**STATUS:** DONE systematic macro calendar, as-of entry-only risk gate, prior matched controls, A$50/A$100 cost sensitivity, 26 safety tests, official Kraken report and PR. PARTIAL broader news representativeness, true first-observed article versions, untouched OOS and real fill data. BLOCKED strategy promotion. NOT ATTEMPTED Android APK/live trading. NEXT: systematic ordinary historical crypto/financial news with verified source revision/availability, predeclared event features and negative controls, train-only selection and independent future OOS. Preserve HOLD, paper-only, purple notification and Android safeguards.

---

V33 FINAL MERGE/REPRODUCIBILITY VERIFIED (2026-11-05): PR #16 MERGED as f24f4f5d4ddcb4578925da57b0c6f2ac61030e64. Final PR-head CI run 41924275473 PASSED 6 deterministic tests and official Kraken study, artifact 13369500422. The final artifact JSON SHA256 is c80b2462a55123cf3cd6d5007668f5f61c4da4179986d8b1399bee2262a97fff, byte-for-byte identical to earlier verified V33 run. Source and docs were read back from main. HOLD remains selected, no Android promotion.

## V33 — 2026-11-05: verified cross-regime selection and historical news ablations (PR #16)

DONE: V32 CI 41732325042 PASSED 4 tests and official Kraken 3-segment study, artifact 13277406975. V33 CI 41923977818 PASSED 6 tests and official-market study, artifact 13367538351. Three gap-free segments 6863/3398/1999 bars, 13,763 original 4h candles and 20 gaps. Official Kraken XBTAUD_240.csv SHA256 ed732a5cd906991b2d2b306b3266578dcea14b07c6f9b307cb4c3c3753eb296e; ZIP member CRC 61c06c60, full archive SHA unverified. Prices previously inspected; EXPLORATORY NOT untouched OOS.

Method: chronological 50% train, 20% validation, 30% test with 20-bar embargo; selector sees only train+validation. Three independently reset A$1,000 accounts; A$100 inclusive max paper debit / 10% cash. Standard published 80bps taker +5bps half-spread +5bps slippage per side. Hypothetical next-open fills; every completed hysteresis trade audit records gross, fees, spread, slippage, NET. Six price-only baselines also tested.

| Strategy | Trades | Gross A$ | Fees A$ | Spread A$ | Slippage A$ | NET A$ |
|---|---:|---:|---:|---:|---:|---:|
| SMA | 118 | see artifact | see artifact | see artifact | see artifact | -119.682481 |
| Momentum | 242 | see artifact | see artifact | see artifact | see artifact | -374.775403 |
| RSI | 158 | see artifact | see artifact | see artifact | see artifact | -225.519567 |
| Breakout | 133 | see artifact | see artifact | see artifact | see artifact | -197.561916 |
| Regime | 267 | see artifact | see artifact | see artifact | see artifact | -407.787388 |
| Trend ATR | 20 | see artifact | see artifact | see artifact | see artifact | -27.686213 |
| H50/200 | 10 | +25.705656 | 15.941756 | 0.996373 | 0.996373 | +7.771157 |
| H30/120 | 12 | +5.913666 | 18.871598 | 1.179478 | 1.179478 | -15.316887 |
| H80/300 | 7 | +51.333281 | 11.448071 | 0.715531 | 0.715531 | +38.454151 |
| H50/200 news veto | 10 | +25.705656 | 15.941756 | 0.996373 | 0.996373 | +7.771157 |
| H50/200 shifted placebo | 10 | +25.705656 | 15.941756 | 0.996373 | 0.996373 | +7.771157 |
| Same-A$100 buy/hold | 3 | see artifact | see artifact | see artifact | see artifact | +129.286037 |
| ACTUAL SELECTED HOLD | 0 | 0 | 0 | 0 | 0 | 0 |

H80/300 segment test NET: +18.208983, -7.361149, +27.606317. H80/300 half/standard/double cost NET +45.178506/+38.454151/+25.215557. Train+validation selector chose HOLD, h30_120, HOLD; selected test strategy lost -A$9.722842 in middle segment. Thus the attractive hindsight H80 aggregate did not survive causal selection. Worst drawdown, all baseline cost splits, per-trade audits and segment-specific results are in artifact.

News: 10 famous retrospective publication/revision timestamp events (+1h assumed latency) plus 9 ordinary clustered retrospective articles (+24h), total 19; only 2 during test windows, both veto and shifted placebo changed ZERO trades. Not actual first-observed. No demonstrated news predictiveness. The 135 November 2026 first-observed URLs are separate.

DONE: Official archive segment evaluation, causal selection, cost sensitivity, news negative controls, CI and trade audits. PARTIAL: systematic news coverage, real fills, untouched OOS. BLOCKED: strategy promotion without independent positive NET. NOT ATTEMPTED: Android APK or live orders. NEXT: systematically prespecify historical news sources/dates, quantify coverage and news availability, retest event-conditioned low-turnover filters with adequate samples; prospectively validate frozen candidates. Reproduce: python -m unittest discover -s tests -p 'test_v33_cross_regime.py' -v; python -m research.v33_cross_regime --output audit/v33-cross-regime.json. Android PAPER ONLY HOLD.

---

## V32 — 2026-11-04, all-segment research implementation (verification pending)

**DONE:** Added `research/v32_segments.py`, `tests/test_v32_segments.py`, and `.github/workflows/v32-segments.yml` on main. New experiment enumerates every gap-free >=1000-candle segment from the official Kraken BTC/AUD 4h archive, using timestamp gaps only (never returns) for segment inclusion. Each segment uses a fixed chronological 70/30 partition, 305-bar warmup, three V31 hysteresis strategies, trend/ATR control and equal-A$100 buy/hold. Existing 80bps taker + 5bps spread + 5bps slippage model and A$100 inclusive cap are inherited from V31. No segment is bridged across missing bars. Per-segment A$1000 accounts reset; results are exploratory and not untouched OOS.

**PARTIAL / UNVERIFIED:** GitHub files were written, but CI completion, tests, official archive download, segment counts, and performance outputs have NOT yet been verified. No numerical backtest results are claimed. Official archive member CRC and SHA are captured; full multi-part archive checksum remains unverified. No historical news expansion occurred in this iteration.

**BLOCKED:** Strategy promotion pending independently verified positive NET and representative news timestamps. Android remains PAPER-ONLY, selected HOLD, no new APK, no live orders.

**NEXT:** Read GitHub Actions run for V32, correct failures, obtain actual per-segment trade counts/gross/fees/spread/slippage/NET/drawdown and regime comparisons; expand representative historical news only after verifying the segment study. Reproduce: `python -m unittest discover -s tests -p 'test_v32_segments.py' -v`; `python -m research.v32_segments --output audit/v32-segment-coverage.json`.

---

## V31 — 2026-11-03, hysteresis walk-forward + ordinary historical-news controls (PR #15)

**STATUS:** DONE: three predeclared low-turnover regime/hysteresis strategies, 3 chronological train/validation/test folds, 20-bar embargo, no-future tests, 80bps fee-aware gross/cost/NET accounting, 11 sourced ordinary historical articles with duplicate clustering, prior matched controls and official-market CI. PARTIAL: representative news history, genuinely untouched OOS, real fill/market microstructure. BLOCKED: promotion. NOT ATTEMPTED: Android strategy changes/APK, live trading, maker queue fills.

**Market:** Kraken official `XBTAUD_240.csv`, 13,763 BTC/AUD four-hour bars, 20 gaps, selected longest gap-free 6,863 bars (2020-12-02–2024-01-20), member SHA256 `ed732a5cd906991b2d2b306b3266578dcea14b07c6f9b307cb4c3c3753eb296e`, ZIP CRC checked but full archive SHA not verified. Previously inspected history => all folds EXPLORATORY, NOT untouched OOS. Three independent A$1,000 reset accounts, max A$100 entry debit INCLUDING 80bps taker + 5bps half-spread + 5bps slippage per side, <=10% cash, next-open simulated fills and forced final-open liquidation. Candidate menu predeclared: 50/200, 30/120 and 80/300 SMA hysteresis with 7-day volatility entry filter, six-bar minimum hold and twelve-bar reentry cooldown; no hindsight in decisions. Three expanding train periods, each followed by 500-bar validation and disjoint test with 20-bar embargoes. Train-only selector requires >=2 trades and positive NET in BOTH training and validation; selected HOLD in all three folds.

**Official Kraken exploratory test diagnostics (SUMS of 3 separately reset A$1,000 accounts, NOT compounded):**

| Strategy | Trades | Gross A$ | Fees A$ | Spread A$ | Slippage A$ | NET A$ |
|---|---:|---:|---:|---:|---:|---:|
| SMA baseline | 100 | +76.372991 | 155.905584 | 9.744137 | 9.744137 | **-99.020869** |
| Trend+ATR baseline | 23 | +9.685320 | 36.380336 | 2.273775 | 2.273775 | **-31.242566** |
| Hysteresis 50/200 | 8 | +14.309450 | 12.696878 | 0.793562 | 0.793562 | **+0.025449** |
| Hysteresis 30/120 | 9 | +26.016662 | 14.349973 | 0.896886 | 0.896886 | **+9.872917** |
| Hysteresis 80/300 | 6 | +28.861058 | 9.704583 | 0.606551 | 0.606551 | **+17.943373** |
| Negative-news veto (50/200) | 8 | +14.309450 | 12.696878 | 0.793562 | 0.793562 | **+0.025449** |
| Shifted-news placebo (50/200) | 8 | +14.309450 | 12.696878 | 0.793562 | 0.793562 | **+0.025449** |
| Same-stake buy-and-hold | 3 positions | — | — | — | — | **+81.225523** |
| ACTUALLY SELECTED HOLD | 0 | 0 | 0 | 0 | 0 | **0** |

**Crucial selection discipline:** H80/300 test NET by fold **-A$8.630469, -A$15.992917, +A$42.566759**, but its corresponding training NET was **-A$63.288524, -A$84.542176, -A$93.240574** and validation had fewer than two trades each fold. It was never eligible for deployment, regardless of post-hoc positive aggregate. H30/120 test NET +A$2.811253, -A$26.877831, +A$33.939495; H50/200 -A$16.895227, -A$17.451088, +A$34.371764. Worst full-account test-fold DD: H50/200 -2.473%, H30/120 -2.758351%, H80/300 -3.139095%. H80/300 half/standard/double execution-cost NET by fold: (-6.907444,-8.630469,-12.026299), (-13.451274,-15.992917,-20.995771), (+43.855694,+42.566759,+40.023180). Trade costs are included in all NET figures. Selected HOLD missed hypothetical buy-and-hold gains, but avoids selecting candidates that failed earlier data.

**News expansion:** 11 independently linked Reuters/Euronews items from 2022–Jan 2023, selected as a CONVENIENCE SAMPLE (NOT systematic/random/representative) with explicit source-displayed local publication times converted to UTC; one known revision, +24h conservative assumed availability, topic clusters and two flagged price-following stories. Deduplicated to 9 clusters, including 5 neutral labels. Dataset SHA256 `3cdddd32f8057e8ac285813f0314c3aea85ba3c57fb41c33a9fd388f34f3e4ba`. Source-version histories NOT verified and publication time is NOT actual first-observed bot time. Strictly prior matched controls: 9/9 clusters matched, no omissions. 24h hypothetical long NET -2.880058% vs prior control -1.853917% (excess -1.026142 percentage points); 4h excess -0.101280 pp; 48h excess -2.711054 pp. These are descriptive, not causal or predictive, and mixed/neutral sentiment makes signflip tests unsuitable for signal claims. The existing 10-event news veto and +7d shifted placebo produced identical 50/200 trades: NO demonstrated news edge.

**Verified CI:** GitHub Actions run [41533351786](https://github.com/spirokopita/-BTC-AI-Trading-Bot/actions/runs/41533351786) PASSED 34 deterministic tests (8 V31 strategy + 4 V31 news + 8 V30 + 9 V29 + 5 V27), official Kraken walk-forward, ordinary-news matched study and provenance assertions. Artifact **13182014247** contains `audit/v31-hysteresis.json`, `audit/v31-news-coverage.json` and source news JSON. Reproduce: `python3 -m unittest discover -s tests -p 'test_v31_hysteresis.py' -v`, `python3 -m unittest discover -s tests -p 'test_v31_news_coverage.py' -v`, `python3 -m research.v31_hysteresis --output audit/v31-hysteresis.json`, `python3 -m research.v31_news_coverage --output audit/v31-news-coverage.json`.

**NEXT executable hypothesis:** Use all >=1000-bar contiguous Kraken archive segments (not just longest), with per-segment gap isolation, and compare H80/300 regime/hysteresis against same-stake buy-and-hold and price-only trend baseline across distinct regimes. Expand ordinary historical news using prespecified date/source sampling and source-version/availability provenance; do not select headlines by subsequent returns. Only promote after independently verified positive NET OOS and Android parity. PAPER ONLY; HOLD remains selected.

---

# BTC/AUD Research Experiment Ledger

## V30 — 2026-11-02, strictly prior matched historical news controls (PR #14)

**STATUS:** DONE: prior-time event controls, synthetic leakage tests, official Kraken historical matched study and reproduction of 12 strategy/news ablations. PARTIAL: historical news representativeness, matched-regime validity. BLOCKED: untouched positive NET edge. NOT ATTEMPTED: Android changes, live orders, paid data.

**Market/news provenance:** Kraken official `XBTAUD_240.csv`, 13,763 4h candles, 20 gaps; selected 6,863 contiguous bars from 2020-12-02 through 2024-01-20, member SHA256 `ed732a5cd906991b2d2b306b3266578dcea14b07c6f9b307cb4c3c3753eb296e` (full archive SHA NOT checked). News = 10 manually selected historical publications in `data/historical_news_reconstructed.json`, +1h after latest known revision, **NOT first observed**. All periods already inspected; exploratory, not untouched OOS.

**Matched-control hypothesis:** For each news event's first eligible four-hour OPEN, choose up to five strictly EARLIER, non-event control opens from the previous 180 days, matched to the same UTC weekday/4h slot and ranked by completed-bar 24h return direction and seven-day volatility. Exclude +/-7 days around all known news events; never use future candidate dates or future features to select controls. Compute hypothetical 4h/24h/48h long round-trip NET at 80bps taker + 5bps half-spread + 5bps slippage per side. This is descriptive and NOT a causal or deployable signal.

| Horizon | Matched events | Mean news NET | Mean control NET | News excess NET | Sentiment-aligned excess | Aligned positive | Descriptive sign-flip p |
|---|---:|---:|---:|---:|---:|---:|---:|
| 4h | 10 | -2.057950% | -0.632214% | -1.425736% | -0.420852% | 5/10 | 0.703125 |
| 24h | 10 | -1.629283% | -0.073195% | -1.556088% | +0.245267% | 6/10 | 0.884766 |
| 48h | 10 | -5.146879% | -0.228110% | -4.918770% | +1.158687% | 6/10 | 0.617188 |

**Result:** At 24h, event NET underperformed prior matched controls by 1.556 percentage points on average. Direction-aligned excess is weak, mixed, and statistically unconvincing even before accounting for severe selection bias and event dependence. **REJECT news-edge claim.** V29 strategy baseline reproduced: 12 controls, 5 chronological independently reset folds, price-only trend breakout 87 trades NET -A$154.604, negative-news veto identical, positive-news pulse 4 trades NET -A$11.085; same-stake buy/hold +A$92.018. HOLD stays selected; no Android strategy promotion. Gross, fees, spread, slippage, max DD, sensitivity and fold details are in V30 CI artifact, not omitted or claimed as new performance.

**Verified:** CI [41355350343](https://github.com/spirokopita/-BTC-AI-Trading-Bot/actions/runs/41355350343) passed 8 V30 + 9 V29 + 5 V27 tests, official Kraken sparse archive research, full 12-strategy rerun. Artifact `13102518396` includes `audit/v30-matched-news.json` and `audit/v30-strategy-control.json`. Reproduce with `python3 -m research.v30_matched_news --output audit/v30-matched-news.json` and `python3 -m research.v29_point_in_time --output audit/v30-strategy-control.json`. Local 8 synthetic tests also passed (stand-in V29 module with identical constants; official repo CI is authoritative).

**NEXT:** Obtain systematically sampled timestamped historic financial/crypto news with publication revisions and coverage gaps; run non-event controls across regimes, then test new low-turnover hysteresis strategies under 80bps fees. Freeze parameters before later genuinely unseen validation; do not infer news predictiveness from famous headlines. Paper only.

---


## V29 — 2026-11-02, historical news cross-reference and causal event-driven replay (PR #13)

**STATUS:** DONE: 10 timestamp-sourced retrospective articles, 30 post-availability event-horizon observations, 12 fixed strategy/ablation variants, 5 expanding chronological folds, 80bps taker plus spread/slippage, deterministic causality tests and real official Kraken archive CI. PARTIAL: historical news representativeness and market regime/news causal attribution. BLOCKED: strategy promotion absent independent prospective positive NET. NOT ATTEMPTED: live trading, Android changes/APK, paid data, maker queue fills.

**Evidence and provenance:** Kraken official `XBTAUD_240.csv`, 13,763 4h rows, 20 gaps, longest contiguous interval selected by length ONLY: 6,863 bars 2020-12-02T20:00:00Z to 2024-01-20T12:00:00Z. ZIP member CRC `61c06c60`, SHA256 `ed732a5cd906991b2d2b306b3266578dcea14b07c6f9b307cb4c3c3753eb296e`; full multipart archive SHA unverified. Research: `data/historical_news_reconstructed.json` contains 10 sourced UTC article times with source URLs, revision times where visible, conservative +1h availability delay and hand-coded event labels. These are NOT actual historical first-seen bot observations, and this set is heavily selection-biased. The 135 genuinely first-observed articles from November 2026 remain separate.

**PAPER simulations:** A$1,000 account reset for EACH of 5 chronological folds; A$100 maximum entry debit INCLUDING costs and <=10% cash; 80bps taker, 5bps half-spread, 5bps slippage per side. Signal uses completed 4h bar only; fill at next open; 20-bar fold embargo; terminal open liquidation; no gap bridging. Historical prices were previously inspected, so this is *point-in-time simulated*, but **NOT untouched OOS**. Aggregate figures below are SUMS ACROSS 5 INDEPENDENTLY RESET ACCOUNTS, not compounded.

| Frozen hypothesis | Trades | Gross A$ | Fees A$ | Spread A$ | Slippage A$ | NET A$ |
|---|---:|---:|---:|---:|---:|---:|
| SMA 10/20 | 197 | +82.202 | 305.945 | 19.122 | 19.122 | **-261.987** |
| Momentum | 434 | +7.508 | 636.125 | 39.758 | 39.758 | **-708.133** |
| RSI mean reversion | 290 | +41.553 | 440.850 | 27.553 | 27.553 | **-454.403** |
| ATR-free price breakout | 231 | +12.658 | 347.564 | 21.723 | 21.723 | **-378.351** |
| Volatility regime | 428 | -9.103 | 625.881 | 39.118 | 39.118 | **-713.219** |
| Trend + ATR + breakout | 87 | -4.348 | 133.561 | 8.348 | 8.348 | **-154.604** |
| News risk veto 48h | 87 | -4.348 | 133.561 | 8.348 | 8.348 | **-154.604** |
| News risk veto 7d (post-hoc) | 87 | -4.348 | 133.561 | 8.348 | 8.348 | **-154.604** |
| News +7d shifted veto placebo | 87 | -4.348 | 133.561 | 8.348 | 8.348 | **-154.604** |
| News-delay trend | 133 | +52.693 | 207.818 | 12.989 | 12.989 | **-181.102** |
| 24h positive-headline pulse (post-hoc) | 4 | -3.993 | 6.305 | 0.394 | 0.394 | **-11.085** |
| Positive-headline +7d placebo | 4 | +5.432 | 6.386 | 0.399 | 0.399 | **-1.752** |
| Equal A$100 buy-and-hold | 5 independent positions | — | — | — | — | **+92.018** |
| Selected HOLD | 0 | 0 | 0 | 0 | 0 | **0** |

**Fold detail / max drawdown:** For trend breakout, fold NET A$: -90.220697, -10.263097, -30.770499, -20.055090, -3.294585; worst fold full-account DD -9.02207%. For direct positive news pulse, fold NET -14.899083, 0, 0, +6.324526, -2.510596; worst fold DD -1.489908%. Other strategy/fold drawdowns and half/double-cost sensitivity for news/low-turnover variants are in the artifact. Buy-and-hold fold NET: +41.177772, -56.239730, -15.083632, +83.047670, +39.115992. No strategy has reproducible positive NET across folds.

**Event cross-reference:** 10 articles each evaluated at 4h, 24h and 48h from first tradable open AFTER conservative article availability; 30 total event-horizon rows. At 24h, 3/10 hypothetical taker roundtrips positive; mean gross +0.16%, mean NET -1.6293%. Event labels were assigned retrospectively, so neither causality nor predictive power follows. Example: 2023-03-13 US banking article +6.3245% NET 24h, but 2024-01-10 ETF approval article -2.5106% NET 24h. The news-veto variants made ZERO different trades versus the price-only control because no curated negative event overlapped a qualifying breakout entry; no news value was observed. The 24h positive pulse performed worse than its +7d placebo; the placebo is not a valid tradable signal.

**Reproduction / verified CI:** `python3 -m unittest discover -s tests -p 'test_v29_point_in_time.py' -v` (9 passed); `python3 -m unittest discover -s tests -p 'test_forward_gap_experiment.py' -v` (6 passed); `python3 -m unittest discover -s tests -p 'test_v27_position_sizing.py' -v` (5 passed); `python3 -m research.v29_point_in_time --output audit/v29-point-in-time.json`. GitHub Actions run [41322453783](https://github.com/spirokopita/-BTC-AI-Trading-Bot/actions/runs/41322453783) PASSED 20 tests, official market extraction and report. Artifact ID `13089114010` contains complete JSON with all 5 folds, 12 strategies, costs, drawdowns, sensitivity and event rows. Initial CI 41322194372 passed baseline, then two intermediate CI attempts 41322280526 / 41322287207 failed on a literal newline escape in the added 7d variant; corrected in commit `6d6f1d3` and latest CI passed. Changes were tested and read back; no strategy promotion.

**NEXT EXECUTABLE ACTION:** Systematically reconstruct a MUCH larger historical news sample using archived feeds/primary filings with timestamp+revision provenance, document coverage gaps and include random/non-event controls. Run news-feature ablations with purged chronological evaluation and evaluate whether signal value survives transaction costs, then freeze a candidate for genuinely new observations. Do not repeatedly optimize the same previously inspected periods. Keep HOLD, PAPER ONLY.

---


## V28 — 2026-11-01, 80bps post-archive research and cumulative first-observed news

**Status:** DONE: V28 source, six new deterministic tests, 11 prior causal/risk tests, real Kraken OHLC diagnostic, recovery of two immutable prior news artifacts, cumulative news merge and SHA read-back in PR CI [41299334042](https://github.com/spirokopita/-BTC-AI-Trading-Bot/actions/runs/41299334042). DONE: permanent main-branch corpus committed by GitHub Actions as f79b7005fe6b0afd9fae1ebad19ceebba41706a8 (135 rows read back). BLOCKED: genuinely untouched prospective OOS NET edge, matured news returns and Android strategy parity. NOT ATTEMPTED: real-money orders, maker fills, UI/APK rebuild, paid data.

**Market provenance:** 720 completed Kraken BTC/AUD four-hour OHLC candles from 2026-07-04 08:00 UTC to 2026-11-01 04:00 UTC; API raw-response SHA256 `e811edd4db3d1923698cec07b4f75068a09fd0d5ba101aaaffbbd94918bcf194`. The 188 post-archive candles cover 2026-10-01 00:00 UTC through 2026-11-01 04:00 UTC, with 532 prior observed warmup bars and zero internal gaps. Source is public Kraken REST OHLC; the unclosed current candle was excluded. **This is exploratory, not untouched prospective OOS**: V24 already examined October 2026. Frozen V27 parameters and HOLD selection, no retrospective promotion.

**Paper A$100 / A$1,000 initial account, 80bps taker + 5bps half-spread + 5bps slippage EACH SIDE, next-open hypothetical fills and forced final-open liquidation:**

| Frozen strategy | Completed trades | Gross A$ | Fees A$ | Spread A$ | Slippage A$ | NET A$ | Return on A$1,000 | Max drawdown |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| SMA | 8 | -4.621734 | 12.575838 | 0.785988 | 0.785988 | **-18.769547** | -1.876955% | -2.035112% |
| Momentum | 13 | -8.502888 | 20.274879 | 1.267176 | 1.267176 | **-31.312118** | -3.131212% | -3.131212% |
| RSI | 10 | +1.934155 | 15.760618 | 0.985040 | 0.985040 | **-15.796542** | -1.579654% | -1.620927% |
| Breakout | 4 | -0.676252 | 6.323332 | 0.395208 | 0.395208 | **-7.790000** | -0.779000% | -0.779000% |
| Regime | 4 | -0.899831 | 6.322889 | 0.395180 | 0.395180 | **-8.013081** | -0.801308% | -0.961199% |
| Slow SMA 50/200 +0.5% | 1 | -2.599042 | 1.564944 | 0.097808 | 0.097808 | **-4.359602** | -0.435960% | -0.656869% |
| Slow SMA 50/200 +2% | 1 | -2.379900 | 1.566696 | 0.097917 | 0.097917 | **-4.142430** | -0.414243% | -0.619304% |

**Same-A$100 buy/hold:** gross -A$7.874462, fees A$1.522783, spread A$0.095170, slippage A$0.095170, NET **-A$9.587585** (BTC price change -7.945395%). HOLD 0 trades and A$0 NET. Cost multiplier 0.5/2.0 sensitivity and each trade audit are preserved in V28 JSON artifact; 0.5 multiplier is NOT a maker-fill simulation. These are hypothetical price-based taker fills, not real executed trades.

**First-observed news recovery:** Recovered authentic V26 SQLite snapshot (134 articles, SHA256 `d0fa9804149f6c335ca0be93a55727be0808b22c4deca80d9de70a9961155e65`) and V27 snapshot (114, SHA256 `0355b822794c87006c6fc1649da1047e9745d8cfc1fac396488f9771299102c3`), and captured V28 current RSS (114, SHA256 `c2b877a89906dcf7c76825f7ab16d0c578a8b351d36e6155e77061189fdad200`). Merged 362 snapshot rows to **135 distinct canonical URLs**, preserving the earliest actually recorded `first_seen_ts`; corpus SHA256 `b79bc80e94a8c629c0070a6e28275232c3e3cecae96014e3eccd5bcbd4a304f6`. Bloomberg feed redirect remained blocked by host allowlist; other four feeds succeeded. No publication-time backdating, no historical news trading signal, and no matured post-first-seen outcome evaluation. The PR CI artifact is preserved; main-branch JSONL persistence succeeded in commit f79b7005fe6b0afd9fae1ebad19ceebba41706a8, 135 lines verified on read-back.

**Reproduction:** `python3 -m unittest discover -s tests -p 'test_v28_bridge_corpus.py' -v` (6 passed); `python3 -m unittest discover -s tests -p 'test_forward_gap_experiment.py' -v` (6 passed); `python3 -m unittest discover -s tests -p 'test_v27_position_sizing.py' -v` (5 passed); `python3 -m research.v28_recent_bridge --output audit/v28-recent-bridge.json`; `python3 -m news_intelligence.corpus --snapshot audit/v28-seed/v26 --snapshot audit/v28-seed/v27 --snapshot audit/v28-current.sqlite --output data/first_observed_news.jsonl --manifest audit/v28-corpus-manifest.json`. CI artifact ID 13080044027. Source PR [#12](https://github.com/spirokopita/-BTC-AI-Trading-Bot/pull/12).

**NEXT EXECUTABLE ACTION:** Collect genuinely new post-2026-11-01 completed BTC/AUD candles with recorded fetch times and measure news event returns only after horizon maturity. Research maker-limit execution only with queue/fill probability and adverse-selection assumptions. Preserve HOLD, A$100 hard paper cap, and 80bps current taker fee.

---


## V27 — 2026-11-01, approved A$100 paper cap and 2026 Kraken fee reality check

**Status:** DONE: paper sizing source, realistic fee model, four matched research scenarios, 11 deterministic research tests, official-market CI and new news snapshot. DONE: Android build/emulator verification passed (19/19). BLOCKED: independent prospective NET edge and cumulative point-in-time news history. NOT ATTEMPTED: live orders.

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

**Android and safety:** `PaperDecisionEngine` now min(A$100, 10% of cash) inclusive of actual rounded entry friction, 80bps paper taker fee; Kotlin unit assertions cover limit across cash/price combinations. Native source remains PAPER-ONLY, one long position, no live order route, stale/offline entry blocking. Android CI [41297522950](https://github.com/spirokopita/-BTC-AI-Trading-Bot/actions/runs/41297522950) PASSED: Kotlin JVM tests, Android 15 emulator **19 tests, zero failures/errors/skips**, APK built. Initial CI [41297322586](https://github.com/spirokopita/-BTC-AI-Trading-Bot/actions/runs/41297322586) failed on a test-only undefined `price` reference; corrected by commit `32c4a555` and rerun passed. Debug APK SHA256 `4d660e840b71ffc7804c51d8d1f5b5fc0e1807c0dcf3ba27477fbdc2e794c08e`. Stable signing secret not configured. PR #11 merged as `763dcf704e4d72998bcb8a81ab78d40c5b1b6dcf`. Research strategy proxies are not exact Android SMA10/20 crossover/stop parity.

**NEXT EXECUTABLE ACTION:** Persist first-observed news snapshots across runs, gather genuinely new BTC/AUD candles after 2026-11-01 observation, then evaluate frozen lower-turnover candidates with conservative 80bps taker fees and observed market costs. No strategy promotion without independent positive NET evidence.

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

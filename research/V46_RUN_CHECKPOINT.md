# V46 2026-11-13 AEDT — PAPER ONLY experiment checkpoint

## Five-line recovered state
1. Main RUN_SUMMARY V40: official Kraken 13,763 historical BTC/AUD 4h bars, 20 gaps, three eligible segments; latest 720 public bars through 2026-11-10 16:00 UTC.
2. Main V40: 1,900 news metadata rows / 841 distinct actual articles; zero historically verified as-of eligible; historical predictive news edge unproven.
3. Main V40: H80 FX veto identical to baseline; inspected-history selector HOLD/H50/HOLD net -A$14.351385 against A$100 buyhold +A$129.286037.
4. V44 PR #25 and V45 PR #26 are separate unmerged/dependent research branches; V45 historical CI previously passed; V45 source not present on main.
5. Android remains PAPER ONLY HOLD; A$100 inclusive entry cap/10% cash, 80bps taker plus execution friction; no live orders or APK changes.

## This run
DONE: reviewed main summary, ledger and research sources; created V46 PR #27 on V45 branch, prespecified 90/180/365-day age ablation across 2/3/4/5% dip thresholds, 70/90% exit gates, 50/70% permanent hoard, and no-sale same-buy benchmark. 48 configurations per eligible segment, up to 144 rows. Source and three deterministic safety tests committed.
PARTIAL: workflow triggered/verification pending; numeric backtest output not yet read back; no claims of returns or trade counts.
BLOCKED: untouched prospective OOS, verified historical news as-of availability, independent executable Android integration.
NOT ATTEMPTED: new news corpus ingestion, new market feed, APK build, live orders.
NEXT: verify CI/artifact and compute gross/cost/net, drawdown, trade counts, never-sell delta; compare to V45. Expand systematic historical news provenance; do not promote without untouched OOS net benefit.
Verification command: python -m unittest discover -s tests -p 'test_v46_hold_age_ablation.py' -v && python -m research.v46_hold_age_ablation
Research sources: official Kraken historical archive as loaded by research/v33_cross_regime.py; main RUN_SUMMARY V40. Historical news signal not used in V46.

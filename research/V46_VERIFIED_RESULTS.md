# V46 verified results — 2026-11-13 AEDT

GitHub Actions run 43323686647 SUCCESS; three deterministic tests passed and official Kraken archive study completed. Artifact 13990364447 (v46-hold-age-ablation.json), retrieved and independently parsed.

48 prespecified configurations per each of 3 gap-free segments (144 independent evaluations, A$1000 reset per fold). Historical data previously inspected, EXPLORATORY ONLY. 80bps taker and 10bps execution friction each side, net marked portfolio after estimated liquidation.

| Segment | Configs with >=1 bulk sale | Total bulk sale events across overlapping configs | Better than same-buy never-sell | Worse than same-buy never-sell |
|---|---:|---:|---:|---:|
| 6863 bars | 48/48 | 390 | 0 | 48 |
| 3398 bars | 32/48 | 56 | 32 | 0 |
| 1999 bars | 16/48 | 16 | 0 | 16 |
| TOTAL | 96/144 | 462 | 32 | 64 |

48 configurations tied the no-sell benchmark. First segment best relative deficit -A$21.495; worst -A$159.791. Middle segment best relative improvement +A$4.806 (4% dip, 90% exit, 50% permanent hoard, 180-day minimum lot age). No stable positive edge across regimes. No Android promotion; HOLD retained. Reported 'gross_proceeds_minus_basis' is actually realised profit after modeled selling costs and must NOT be labeled gross trading P&L; complete gross/fee/spread/slippage per-sale accounting remains a research gap.

DONE: code, deterministic tests, CI, artifact download, independent results parse, GitHub result checkpoint.
PARTIAL: 10k systematic historical news coverage, strict retrospective as-of data, prospective untouched OOS, explicit fee-component audit.
NOT ATTEMPTED: new news ingestion, fresh OHLCV beyond V40, Android APK, live trading.
NEXT: fee component breakdown and consistent A$50/A$100 benchmark, untouched OOS and news provenance; do not infer sell signal edge from 32 winning configurations chosen in hindsight.

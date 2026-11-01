# V29 point-in-time historical news/price research — 2026-11-02 AEDT

1. Android V27 remains PAPER-ONLY, A$100 inclusive max debit / 10% cash, 80bps current taker model, 19/19 prior emulator tests; no new APK.
2. Revalidated Kraken official XBTAUD_240.csv archive member SHA256 ed732a5c906991b2d2b306b3266578dcea14b07c6f9b307cb4c3c3753eb296e; 13,763 candles with 20 gaps; selected 6,863-bar contiguous 2020-12-02–2024-01-20 interval.
3. Reconstructed 10 timestamp-sourced historical crypto headlines with revision-aware UTC timestamps plus conservative 1h latency; 30 event-return observations (4h/24h/48h); NOT historical first-observed bot evidence.
4. Five expanding chronological exploratory folds compared 12 strategies at 80bps taker + 5bps half-spread + 5bps slippage each side, A$100 max entry; direct positive-news pulse 4 trades NET -A$11.085, +7d placebo 4 trades NET -A$1.752, price-only trend breakout 87 trades NET -A$154.604.
5. V29 GitHub Actions run 41322453783 passed 20 deterministic tests and official archive research; no news veto changed a trade, HOLD selected; no strategy promoted.

**DONE:** Added `research/v29_point_in_time.py`, `data/historical_news_reconstructed.json`, `tests/test_v29_point_in_time.py`, and V29 CI workflow. All 5 folds were previously inspected historically and remain EXPLORATORY, not untouched OOS. Current 2026 fees are scenarios on past prices, not historical fee facts.

**News ablations:** 48h veto, 7d veto and +7d shifted veto were identical to price-only trend breakout (87 trades, -A$154.604 NET) because the curated negative events never coincided with its entry signal. A direct 24h positive-news pulse lost A$11.085 across 4 completed trades; shifted +7d placebo lost A$1.752. No predictive benefit established.

**Historical event studies:** Ten articles, 30 event/horizon rows. At 24h, 3/10 gross-to-net hypothetical taker roundtrips were positive; average NET move -1.629%. This small selected sample is NOT causal or statistically sufficient. The results describe movement after conservative article availability, not an investable signal.

**Verification:** `python3 -m unittest discover -s tests -p 'test_v29_point_in_time.py' -v` (9 pass); `test_forward_gap_experiment.py` (6 pass); `test_v27_position_sizing.py` (5 pass); `python3 -m research.v29_point_in_time --output audit/v29-point-in-time.json` (official market pass). CI artifact 13089114010. Research PR #13.

**BLOCKED FOR PROMOTION:** No independent prospective positive NET edge. Ten prominent retrospectively selected articles cannot establish news predictiveness. Full market data archive checksum not verified, only ZIP member CRC and SHA256.

**NEXT:** Expand historical article coverage systematically with exact publication/update/availability provenance and topic controls; evaluate price-only vs news-conditioned variants on the same folds, report event overlap and uncertainty, then freeze for future OOS. Preserve PAPER-ONLY HOLD and no live execution.

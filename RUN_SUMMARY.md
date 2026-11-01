# V28 research run summary — 2026-11-01 AEDT

1. Android V27 PAPER-ONLY still enforces max A$100 / 10% simulated cash inclusive of entry costs, 80bps taker model; 19/19 emulator tests previously passed; no new APK.
2. Fetched 720 verified completed Kraken BTC/AUD 4h candles through 2026-11-01 04:00 UTC, including 188 gap-free bars after the 2026-09-30 archive.
3. Frozen seven-candidate A$100/80bps exploratory study: SMA 8 trades NET -A$18.769547, slow SMA 0.5% 1 trade NET -A$4.359602, same-stake buy/hold NET -A$9.587585.
4. Recovered 134 V26, 114 V27 and 114 V28 first-observed news snapshot rows; merged 362 to 135 distinct canonical URLs with source hashes and read-back.
5. GitHub Actions 41299334042 passed 17 deterministic tests and real-market/news research; selected HOLD A$0 NET; PR #12 awaiting merge at this checkpoint.

**DONE:** Real post-archive public Kraken data validation, seven frozen cost-aware paper diagnostics, six new tests, prior artifact recovery, cumulative news merge, provenance and read-back.

**PARTIAL:** Main-branch persistent corpus write awaits merge/push verification; no news causal predictive test yet.

**BLOCKED:** New untouched post-2026-11-01 market outcomes, mature first-observed news horizons, realistic maker fills and Android research strategy parity.

**NOT ATTEMPTED:** Live trading, new APK, private credentials, spending or destructive changes.

**Source PR:** https://github.com/spirokopita/-BTC-AI-Trading-Bot/pull/12

**CI:** https://github.com/spirokopita/-BTC-AI-Trading-Bot/actions/runs/41299334042

**Next:** Merge and verify durable first-observed corpus, collect future completed BTC/AUD candles and news return labels prospectively, then evaluate fixed lower-turnover strategies. PAPER ONLY.

# V26 research run summary — 2026-11-01 AEDT

1. Android V23 is unchanged and strictly PAPER-ONLY; no APK built or live order route enabled.
2. Verified official Kraken BTC/AUD 4h member SHA256 ed732a5cd906991b2d2b306b3266578dcea14b07c6f9b307cb4c3c3753eb296e; 13,763 observed bars and 20 gap boundaries.
3. Pre-2025 train/validation rejected all seven candidates; selected policy HOLD with zero trades and A$0 NET.
4. Later 2025–2026 diagnostic: baseline SMA NET -A$17.194309 (51 trades), slow 50/200 SMA 0.5% NET +A$3.069562 (6 trades), but slow validation NET -A$4.568657; no promotion.
5. V26 CI 41296254494 passed 6/6 safety tests and official-market research; captured 134 articles at actual first-seen time (final SQLite read-back) for future non-leaking event study.

**DONE:** Gap-safe two-fold forward-period experiment, explicit fee/spread/slippage ledger, fee sensitivity, same-stake buy/hold comparison and prospective RSS snapshot.

**PARTIAL:** News event study pending future observed price labels; 2025–2026 was previously inspected in V25 and is not untouched.

**BLOCKED:** Independent prospective positive NET evidence and Android strategy parity.

**NOT ATTEMPTED:** Android APK, real-money orders, paid datasets, destructive changes.

**Source branch:** v26-gap-safe-forward-evaluation

**CI:** https://github.com/spirokopita/-BTC-AI-Trading-Bot/actions/runs/41296254494

**Next:** Consolidate first-seen news snapshots, evaluate post-observation candles when matured, then run frozen slow SMA prospectively. Preserve HOLD and PAPER ONLY.

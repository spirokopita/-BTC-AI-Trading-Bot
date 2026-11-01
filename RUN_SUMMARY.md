# V27 algorithm and risk-sizing run summary — 2026-11-01 AEDT

1. Android PAPER-ONLY source now budgets min(10% cash, A$100) including entry friction; models current standard Kraken Pro tier-1 80bps taker fee; Android 15 emulator 19/19 passed; APK built.
2. Official Kraken BTC/AUD 4h archive reverified: 13,763 observed candles, 20 gap boundaries, member SHA256 ed732a5cd906991b2d2b306b3266578dcea14b07c6f9b307cb4c3c3753eb296e.
3. Matched A$50/A$100 experiments under legacy 16bps and current 80bps per-side taker fee used frozen seven strategies, chronological training/validation and two exploratory later folds.
4. At current 80bps, A$100 slow SMA +0.5%: 6 round trips, gross +A$9.106192, total costs A$10.732881, NET -A$1.626688; SMA NET -A$96.804378, same-stake buy/hold -A$16.092737.
5. V27 research CI 41297527028 passed 11 deterministic tests; Android CI 41297522950 passed 19/19 emulator tests and built APK; 114 first-seen news articles observed in evidence run; selected HOLD.

**DONE:** Paper budget and conservative fee model source changes, A$50/A$100 x 16bps/80bps research, fee sensitivity, benchmark, verified real-market CI and news snapshot.

**PARTIAL:** Prospective news outcome study unavailable; earlier 2025-26 diagnostic prices already inspected. Android source and APK verified, but signing is ephemeral debug (no stable signing secret).

**BLOCKED:** Independently new positive NET evidence, Android/research strategy parity, durable cumulative first-seen news history.

**NOT ATTEMPTED:** Live trading, private order API, paid datasets, spending or destructive changes.

**CI research:** https://github.com/spirokopita/-BTC-AI-Trading-Bot/actions/runs/41297527028

**CI Android verified:** https://github.com/spirokopita/-BTC-AI-Trading-Bot/actions/runs/41297522950 — 19/19 emulator tests, JVM tests, APK build, public Kraken audit.

**Next:** Persist multi-run first-seen news, extend fresh BTC/AUD market observations, and prospectively test frozen low-turnover strategies at 80bps taker costs; consider maker-limit execution only with fill-probability/adverse-selection modelling. PAPER ONLY.

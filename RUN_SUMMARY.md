# V27 algorithm and risk-sizing run summary — 2026-11-01 AEDT

1. Android PAPER-ONLY source now budgets min(10% cash, A$100) including entry friction; models current standard Kraken Pro tier-1 80bps taker fee; APK/emulator CI pending.
2. Official Kraken BTC/AUD 4h archive reverified: 13,763 observed candles, 20 gap boundaries, member SHA256 ed732a5cd906991b2d2b306b3266578dcea14b07c6f9b307cb4c3c3753eb296e.
3. Matched A$50/A$100 experiments under legacy 16bps and current 80bps per-side taker fee used frozen seven strategies, chronological training/validation and two exploratory later folds.
4. At current 80bps, A$100 slow SMA +0.5%: 6 round trips, gross +A$9.106192, total costs A$10.732881, NET -A$1.626688; SMA NET -A$96.804378, same-stake buy/hold -A$16.092737.
5. V27 CI 41297183117 passed 6 prior plus 5 new deterministic research tests and official archive study; 114 first-seen news articles observed in that run; selected HOLD and no strategy promoted.

**DONE:** Paper budget and conservative fee model source changes, A$50/A$100 x 16bps/80bps research, fee sensitivity, benchmark, verified real-market CI and news snapshot.

**PARTIAL:** Android build/instrumentation still running; prospective news outcome study unavailable; earlier 2025-26 diagnostic prices already inspected.

**BLOCKED:** Independently new positive NET evidence, Android/research strategy parity, durable cumulative first-seen news history.

**NOT ATTEMPTED:** Live trading, private order API, paid datasets, spending or destructive changes.

**CI research:** https://github.com/spirokopita/-BTC-AI-Trading-Bot/actions/runs/41297183117

**CI Android pending:** https://github.com/spirokopita/-BTC-AI-Trading-Bot/actions/runs/41297183119

**Next:** Verify Android build/emulator and read back artifact, preserve multi-run news history, and prospectively test frozen low-turnover strategies at current 80bps costs. PAPER ONLY.

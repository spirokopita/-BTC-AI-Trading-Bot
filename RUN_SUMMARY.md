# V19 engineering summary — 2026-10-28 AEDT

1. Native Android paper-only BTC/AUD monitor and SQLite wallet; trading OFF by default.
2. V19 fail-closed Kraken 4h OHLC/ticker parser and production HTTPS-to-SQLite sync.
3. Android 15 emulator: 12/12 instrumentation tests passed, 0 failed, 0 skipped.
4. Live public Kraken -> Android parser -> SQLite smoke VERIFIED; real orders 0.
5. Genuine strategy gross, costs and NET BTC/AUD return NOT MEASURED.

**CI:** https://github.com/spirokopita/-BTC-AI-Trading-Bot/actions/runs/40598355525
**Device test evidence:** https://github.com/spirokopita/-BTC-AI-Trading-Bot/actions/runs/40598355525/artifacts/12777354695
**Debug APK:** https://github.com/spirokopita/-BTC-AI-Trading-Bot/actions/runs/40598355525/artifacts/12777484530
**APK SHA-256:** a8f8e05357cb8965614552cd73599cbdcb15b1fbf135f89041b258fc19a9f090

**Broken / unverified:** physical Samsung installation, notification and widget visuals,
Doze recovery, stable signing/update continuity, long-horizon historical source and
out-of-sample after-fee profitability. Live emulator smoke is read-only and cannot
establish always-on Android uptime or an AI trading edge.

**Next:** physical-phone smoke and persistent signing, followed by provenance-audited
multi-year BTC/AUD history and untouched walk-forward NET performance analysis.

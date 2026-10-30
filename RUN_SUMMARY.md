# V22 engineering summary — 2026-10-31 AEDT

1. Native Android BTC/AUD app remains strictly paper-only, with no exchange keys or real order execution.
2. SQLite v4 persists gross fill notional, modeled costs and signed NET cash flow, retaining realised NET P&L.
3. Existing V2/V3 fills are backfilled non-destructively; V1 upgrades and fresh installs receive v4 schema.
4. V22 Android 15 emulator passed 18/18 tests (0 failures/errors/skips); live public Kraken SQLite smoke passed.
5. Genuine BTC/AUD strategy gross, costs and NET results remain NOT MEASURED; real orders 0.

**Source branch:** v22-persisted-gross-net-audit
**Verified CI:** https://github.com/spirokopita/-BTC-AI-Trading-Bot/actions/runs/41140286354
**Emulator evidence:** https://github.com/spirokopita/-BTC-AI-Trading-Bot/actions/runs/41140286354/artifacts/13018179083
**Debug APK:** https://github.com/spirokopita/-BTC-AI-Trading-Bot/actions/runs/41140286354/artifacts/13018488727
**APK SHA-256:** a81ebdd794a373ab4bfd9a3334a82da354d28f804e35c8a7a29f68924dc01e1b

**Completed:** ledger audit fields, deterministic integer backfill, execution history and widget labels, synthetic accounting/migration tests.

**Broken / unverified:** physical Samsung tests, stable signing, Doze timing and real-market strategy profitability.

**Next:** validate physical device and signing continuity, then source independently verifiable long-horizon BTC/AUD history.

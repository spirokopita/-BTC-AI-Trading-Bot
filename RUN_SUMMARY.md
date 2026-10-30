# V22 engineering summary — 2026-10-31 AEDT

1. Native Android BTC/AUD app remains strictly paper-only, with no exchange keys or real order execution.
2. SQLite v4 persists gross fill notional, modeled costs and signed NET cash flow, retaining realised NET P&L.
3. Existing V2/V3 fills are backfilled non-destructively; V1 upgrades and fresh installs receive v4 schema.
4. V22 Android migration and synthetic loss-accounting instrumentation added; CI execution not yet verified.
5. Genuine BTC/AUD strategy gross, costs and NET results remain NOT MEASURED; real orders 0.

**Source branch:** v22-persisted-gross-net-audit

**Completed:** ledger audit fields, deterministic integer backfill, execution history and widget labels, synthetic accounting/migration tests.

**Broken / unverified:** Android CI, physical Samsung tests, stable signing, Doze timing and real-market strategy profitability.

**Next:** inspect Android CI, fix failures if any, validate physical device and signing continuity, then source independently verifiable long-horizon BTC/AUD history.

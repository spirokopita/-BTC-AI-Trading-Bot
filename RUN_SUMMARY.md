# V23 engineering summary — 2026-11-01 AEDT

1. Native Android BTC/AUD application remains strictly paper-only, with trading OFF by default.
2. SQLite v4 keeps gross, costs, signed NET cash flow and realised NET P&L separate.
3. V23 adds populated V2->V4 migration and reopen regression for account, position, funding, candle, trade and news schema.
4. V23 Android 15 emulator tests and APK: PENDING CI; prior V22 18/18 result does not verify V23.
5. Genuine BTC/AUD strategy gross, costs and NET: NOT MEASURED; real orders: 0.

**Source branch:** v23-v2-migration-regression

**Completed in source:** V2 migration regression, versionCode 23, changelog.

**Broken / unverified:** CI outcome pending; Samsung device, persistent signing, Doze recovery, real-market after-fee performance.

**Synthetic accounting fixture:** partial SELL realised NET -A$59.50 (loss), not actual market P&L.

**Next:** verify emulator test and APK, then physical-device signing/widget/notification behaviour and longer BTC/AUD out-of-sample research.

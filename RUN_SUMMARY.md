# V23 engineering summary — 2026-11-01 AEDT

1. Native Android BTC/AUD application remains strictly paper-only, with trading OFF by default.
2. SQLite v4 keeps gross, costs, signed NET cash flow and realised NET P&L separate.
3. V23 adds populated V2->V4 migration and reopen regression for account, position, funding, candle, trade and news schema.
4. V23 Android 15 emulator executed 19/19 tests (0 failures/errors/skips); JVM tests and debug APK build passed.
5. Genuine BTC/AUD strategy gross, costs and NET: NOT MEASURED; real orders: 0.

**Source branch:** v23-v2-migration-regression

**Completed and emulator-verified:** V2 migration/reopen regression, versionCode 23, changelog.

**CI:** https://github.com/spirokopita/-BTC-AI-Trading-Bot/actions/runs/41246248077
**Test XML/logcat:** https://github.com/spirokopita/-BTC-AI-Trading-Bot/actions/runs/41246248077/artifacts/13059474276
**APK artifact:** https://github.com/spirokopita/-BTC-AI-Trading-Bot/actions/runs/41246248077/artifacts/13059647916
**APK SHA-256:** af114cb4757718ba1e38b351b44d06f38de77932bf92b590061dce0265667d92

**Broken / unverified:** Samsung device, persistent signing, Doze recovery, real-market after-fee performance.

**Synthetic accounting fixture:** partial SELL realised NET -A$59.50 (loss), not actual market P&L.

**Next:** verify emulator test and APK, then physical-device signing/widget/notification behaviour and longer BTC/AUD out-of-sample research.

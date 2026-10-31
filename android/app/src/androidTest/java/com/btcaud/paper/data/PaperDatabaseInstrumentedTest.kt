package com.btcaud.paper.data

import androidx.test.ext.junit.runners.AndroidJUnit4
import android.content.Context
import com.btcaud.paper.core.NewsObservation
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.After
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith

/** Requires Android emulator/device; cannot execute in SDK-free container. */
@RunWith(AndroidJUnit4::class)
class PaperDatabaseInstrumentedTest {
    private val context get() = InstrumentationRegistry.getInstrumentation().targetContext
    private lateinit var db: PaperDatabase

    @Before fun before() {
        context.deleteDatabase("btc_paper_v13.db")
        db = PaperDatabase(context)
    }
    @After fun after() { db.close(); context.deleteDatabase("btc_paper_v13.db") }

    @Test fun prefillAndRefillNeverCountAsTradingProfit() {
        assertEquals(100_000L, db.snapshot().account.cashCents)
        db.refill(100L)
        db.refill(200L)
        assertEquals(300_000L, db.snapshot().account.cashCents)
        assertEquals(300_000L, db.snapshot().account.cumulativeFundingCents)
        assertEquals(0L, db.snapshot().account.netPnlCents)
        assertEquals(2, db.snapshot().account.refillCount)
    }

    @Test fun resetPreservesFundingAudit() {
        db.refill(100L)
        db.reset(200L)
        assertEquals(100_000L, db.snapshot().account.cashCents)
        assertEquals(0L, db.snapshot().account.netPnlCents)
        db.readableDatabase.rawQuery("SELECT COUNT(*) FROM funding_audit", null).use { c ->
            assertTrue(c.moveToFirst()); assertEquals(3, c.getInt(0))
        }
    }

    @Test fun switchIsIdempotent() {
        assertTrue(db.setEnabled(true))
        assertFalse(db.setEnabled(true))
        assertTrue(db.setEnabled(false))
        assertFalse(db.setEnabled(false))
    }

    @Test fun pausedWorkerCannotCommitCandles() {
        val start = 1_800_000_000L
        val candle = PaperDatabase.Candle(start, 100L, 110L, 90L, 105L)
        assertFalse(db.recordCandles(listOf(candle), (start + 14_400L) * 1000L))
        assertNull(db.snapshot().latestCloseAudCents)
    }

    @Test fun completedCandleDeduplicatesAndPartialCandleRejected() {
        db.setEnabled(true)
        val start = 1_800_000_000L
        val candle = PaperDatabase.Candle(start, 100L, 110L, 90L, 105L)
        val now = (start + 14_400L) * 1000L
        assertTrue(db.recordCandles(listOf(candle), now))
        assertTrue(db.recordCandles(listOf(candle), now))
        assertEquals(105L, db.snapshot().latestCloseAudCents)
        db.readableDatabase.rawQuery("SELECT COUNT(*) FROM candles_4h", null).use { c ->
            assertTrue(c.moveToFirst()); assertEquals(1, c.getInt(0))
        }
        try {
            db.recordCandles(listOf(PaperDatabase.Candle(start + 14_400, 100, 110, 90, 105)), now)
            fail("forming candle should fail")
        } catch (_: IllegalArgumentException) { }
    }

    @Test fun v16FreshDatabaseHasStrategyAndNewsSchema() {
        val snapshot = db.snapshot()
        assertFalse(snapshot.tradingEnabled)
        assertNull(snapshot.latestNewsSeenMillis)
        assertTrue(snapshot.latestNews.isEmpty())
        assertEquals(100_000L, snapshot.estimatedEquityCents)
    }

    @Test fun paperExecutionIsPersistedAndIdempotent() {
        db.setEnabled(true)
        db.setTradingEnabled(true)
        val start = 1_800_000_000L // Aligned to a four-hour UTC boundary.
        val candles = (0..20).map { i ->
            val close = if (i == 20) 15_100_000L else 15_000_000L
            PaperDatabase.Candle(start + i * 14_400L,
                15_000_000L, 15_200_000L, 14_800_000L, close)
        }
        val now = (start + 21L * 14_400L + 600L) * 1000L
        assertTrue(db.recordCandles(candles, now))
        db.observeTickerAndPaperTrade(now, 15_100_000L)
        val holding = db.snapshot()
        assertTrue(holding.positionSats > 0L)
        assertEquals("BUY", holding.recentTrades.first().side)
        assertEquals(1, holding.recentTrades.size)
        val buy = holding.recentTrades.first()
        assertTrue(buy.grossCents > 0L)
        assertEquals(-buy.grossCents - buy.costsCents, buy.netCashFlowCents)
        assertNull(buy.realisedNetCents)

        // Re-polling the same completed candle must not produce a second BUY.
        db.observeTickerAndPaperTrade(now + 60_000L, 15_100_000L)
        assertEquals(1, db.snapshot().recentTrades.size)

        // An actual later public ticker observation would close this paper position.
        db.observeTickerAndPaperTrade(now + 120_000L, 14_500_000L)
        val finished = db.snapshot()
        assertEquals(0L, finished.positionSats)
        assertEquals("SELL", finished.recentTrades.first().side)
        assertEquals(2, finished.recentTrades.size)
        assertEquals(finished.realisedNetCents, finished.netPnlCents)
        val sell = finished.recentTrades.first()
        assertEquals(sell.grossCents - sell.costsCents, sell.netCashFlowCents)
        assertEquals(buy.netCashFlowCents + sell.netCashFlowCents, sell.realisedNetCents)
        assertTrue("The loss fixture must remain a loss", sell.realisedNetCents!! < 0L)

        db.observeTickerAndPaperTrade(now + 180_000L, 14_500_000L)
        assertEquals(2, db.snapshot().recentTrades.size)
    }

    @Test fun newsFirstObservationDoesNotChangeOnDuplicateHeadline() {
        db.setEnabled(true)
        val now = 1_800_000_000_000L
        assertTrue(db.recordNewsAttempt(now))
        assertFalse(db.recordNewsAttempt(now + 10_000L))
        val report = listOf(NewsObservation("Decrypt", "Bitcoin test headline",
            "https://decrypt.co/example-test", now - 86_400_000L, now, "BITCOIN"))
        db.storeNews(report, now, null)
        assertEquals(now, db.snapshot().latestNews.first().firstSeenMs)
        db.storeNews(report.map { it.copy(firstSeenMs = now + 9_000L) }, now + 9_000L, null)
        assertEquals(now, db.snapshot().latestNews.first().firstSeenMs)
        assertEquals(1, db.snapshot().latestNews.size)
    }

    @Test fun v3TradesMigrateGrossAndNetWithoutRewritingRealisedLoss() {
        db.close()
        context.deleteDatabase("btc_paper_v13.db")
        val legacy = context.openOrCreateDatabase("btc_paper_v13.db", Context.MODE_PRIVATE, null)
        legacy.execSQL("""CREATE TABLE paper_trade_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL, side TEXT NOT NULL,
            candle_s INTEGER NOT NULL, observed_ms INTEGER NOT NULL,
            price_cents INTEGER NOT NULL, quantity_sats INTEGER NOT NULL,
            costs_cents INTEGER NOT NULL, realised_net_cents INTEGER,
            reason TEXT NOT NULL)""")
        legacy.execSQL("""INSERT INTO paper_trade_events
            (session_id,side,candle_s,observed_ms,price_cents,quantity_sats,costs_cents,reason)
            VALUES (0,'BUY',14400,1000,1000000,10000000,1000,'legacy entry')""")
        legacy.execSQL("""INSERT INTO paper_trade_events
            (session_id,side,candle_s,observed_ms,price_cents,quantity_sats,costs_cents,realised_net_cents,reason)
            VALUES (0,'SELL',28800,2000,900000,10000000,900,-11900,'legacy loss')""")
        legacy.version = 3
        legacy.close()
        db = PaperDatabase(context)
        db.readableDatabase.rawQuery(
            "SELECT side,gross_cents,costs_cents,net_cash_flow_cents,realised_net_cents FROM paper_trade_events ORDER BY id",
            null
        ).use { c ->
            assertTrue(c.moveToNext())
            assertEquals("BUY", c.getString(0))
            assertEquals(100_000L, c.getLong(1))
            assertEquals(1_000L, c.getLong(2))
            assertEquals(-101_000L, c.getLong(3))
            assertTrue(c.isNull(4))
            assertTrue(c.moveToNext())
            assertEquals("SELL", c.getString(0))
            assertEquals(90_000L, c.getLong(1))
            assertEquals(900L, c.getLong(2))
            assertEquals(89_100L, c.getLong(3))
            assertEquals(-11_900L, c.getLong(4))
            assertFalse(c.moveToNext())
        }
    }


    @Test fun v2PopulatedAccountMigratesToV4WithoutChangingWalletOrTrades() {
        db.close()
        context.deleteDatabase("btc_paper_v13.db")
        val legacy = context.openOrCreateDatabase("btc_paper_v13.db", Context.MODE_PRIVATE, null)
        // This fixture has the V2 schema, not the V3 news columns or V4 audit fields.
        legacy.execSQL("""CREATE TABLE app_state (
            id INTEGER PRIMARY KEY, enabled INTEGER NOT NULL,
            cash_cents INTEGER NOT NULL, funding_cents INTEGER NOT NULL,
            refill_count INTEGER NOT NULL, reset_count INTEGER NOT NULL,
            last_attempt_ms INTEGER, last_success_ms INTEGER, last_error TEXT,
            trading_enabled INTEGER NOT NULL DEFAULT 0,
            position_sats INTEGER NOT NULL DEFAULT 0,
            position_basis_cents INTEGER NOT NULL DEFAULT 0,
            entry_price_cents INTEGER NOT NULL DEFAULT 0,
            last_evaluated_s INTEGER, last_decision TEXT NOT NULL,
            last_reason TEXT NOT NULL, ticker_cents INTEGER, ticker_ms INTEGER)""")
        legacy.execSQL("""CREATE TABLE funding_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL,
            amount_cents INTEGER NOT NULL, cash_after_cents INTEGER NOT NULL,
            funding_after_cents INTEGER NOT NULL, created_ms INTEGER NOT NULL)""")
        legacy.execSQL("""CREATE TABLE candles_4h (
            start_s INTEGER PRIMARY KEY, open_cents INTEGER NOT NULL,
            high_cents INTEGER NOT NULL, low_cents INTEGER NOT NULL,
            close_cents INTEGER NOT NULL, source TEXT NOT NULL)""")
        legacy.execSQL("""CREATE TABLE paper_trade_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL, side TEXT NOT NULL,
            candle_s INTEGER NOT NULL, observed_ms INTEGER NOT NULL,
            price_cents INTEGER NOT NULL, quantity_sats INTEGER NOT NULL,
            costs_cents INTEGER NOT NULL, realised_net_cents INTEGER,
            reason TEXT NOT NULL)""")
        // Synthetic A$3,000 funded, one partial close at a genuine loss:
        // BUY 0.10 BTC: gross 100000c + costs 1000c.
        // SELL 0.05 BTC: gross 45000c - costs 450c, realised -5950c.
        // Remaining position: 0.05 BTC, cost basis 50500c.
        legacy.execSQL("""INSERT INTO app_state (
            id,enabled,cash_cents,funding_cents,refill_count,reset_count,
            trading_enabled,position_sats,position_basis_cents,entry_price_cents,
            last_evaluated_s,last_decision,last_reason,ticker_cents,ticker_ms)
            VALUES (1,1,243550,300000,1,0,0,5000000,50500,1000000,
                    1800000000,'HOLD','legacy observation',900000,1800000000000)""")
        legacy.execSQL("""INSERT INTO funding_audit
            (kind,amount_cents,cash_after_cents,funding_after_cents,created_ms)
            VALUES ('PREFILL',100000,100000,100000,0)""")
        legacy.execSQL("""INSERT INTO funding_audit
            (kind,amount_cents,cash_after_cents,funding_after_cents,created_ms)
            VALUES ('REFILL',200000,300000,300000,100)""")
        legacy.execSQL("""INSERT INTO candles_4h
            (start_s,open_cents,high_cents,low_cents,close_cents,source)
            VALUES (1800000000,950000,1000000,890000,900000,'legacy-cache')""")
        legacy.execSQL("""INSERT INTO paper_trade_events
            (session_id,side,candle_s,observed_ms,price_cents,quantity_sats,
             costs_cents,reason)
            VALUES (0,'BUY',1800000000,1800000000000,1000000,10000000,
                    1000,'legacy buy')""")
        legacy.execSQL("""INSERT INTO paper_trade_events
            (session_id,side,candle_s,observed_ms,price_cents,quantity_sats,
             costs_cents,realised_net_cents,reason)
            VALUES (0,'SELL',1800014400,1800014400000,900000,5000000,
                    450,-5950,'legacy loss')""")
        legacy.version = 2
        legacy.close()

        db = PaperDatabase(context)
        val upgraded = db.snapshot() // Triggers V2 -> V4 migration.
        assertEquals(4, db.readableDatabase.version)
        assertEquals(243_550L, upgraded.account.cashCents)
        assertEquals(300_000L, upgraded.account.cumulativeFundingCents)
        assertEquals(1, upgraded.account.refillCount)
        assertTrue(upgraded.enabled)
        assertFalse(upgraded.tradingEnabled)
        assertEquals(5_000_000L, upgraded.positionSats)
        assertEquals(50_500L, upgraded.positionBasisCents)
        assertEquals(1_000_000L, upgraded.entryPriceCents)
        assertEquals(900_000L, upgraded.latestTickerAudCents)
        assertEquals(900_000L, upgraded.latestCloseAudCents)
        assertEquals("HOLD", upgraded.lastDecision)
        assertEquals(-5_950L, upgraded.realisedNetCents)
        assertEquals(2, upgraded.recentTrades.size)
        val sell = upgraded.recentTrades[0]
        val buy = upgraded.recentTrades[1]
        assertEquals("SELL", sell.side)
        assertEquals(45_000L, sell.grossCents)
        assertEquals(450L, sell.costsCents)
        assertEquals(44_550L, sell.netCashFlowCents)
        assertEquals(-5_950L, sell.realisedNetCents)
        assertEquals("BUY", buy.side)
        assertEquals(100_000L, buy.grossCents)
        assertEquals(1_000L, buy.costsCents)
        assertEquals(-101_000L, buy.netCashFlowCents)
        assertNull(buy.realisedNetCents)
        assertTrue(upgraded.latestNews.isEmpty())
        db.readableDatabase.rawQuery("SELECT COUNT(*) FROM funding_audit", null).use { c ->
            assertTrue(c.moveToFirst())
            assertEquals(2, c.getInt(0))
        }
        db.readableDatabase.rawQuery(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='news_items'", null
        ).use { c ->
            assertTrue(c.moveToFirst())
            assertEquals(1, c.getInt(0))
        }

        // Reopening an upgraded database must not double-backfill or reset anything.
        db.close()
        db = PaperDatabase(context)
        val reopened = db.snapshot()
        assertEquals(4, db.readableDatabase.version)
        assertEquals(upgraded.account, reopened.account)
        assertEquals(upgraded.positionSats, reopened.positionSats)
        assertEquals(upgraded.positionBasisCents, reopened.positionBasisCents)
        assertEquals(upgraded.recentTrades, reopened.recentTrades)
        assertEquals(-5_950L, reopened.realisedNetCents)
    }

    @Test fun oldV15AccountMigratesWithoutLosingFunding() {
        db.close()
        context.deleteDatabase("btc_paper_v13.db")
        val legacy = context.openOrCreateDatabase("btc_paper_v13.db", Context.MODE_PRIVATE, null)
        legacy.execSQL("""CREATE TABLE app_state(
            id INTEGER PRIMARY KEY,enabled INTEGER NOT NULL,cash_cents INTEGER NOT NULL,
            funding_cents INTEGER NOT NULL,refill_count INTEGER NOT NULL,
            reset_count INTEGER NOT NULL,last_attempt_ms INTEGER,
            last_success_ms INTEGER,last_error TEXT)""")
        legacy.execSQL("""CREATE TABLE candles_4h(
            start_s INTEGER PRIMARY KEY,open_cents INTEGER NOT NULL,
            high_cents INTEGER NOT NULL,low_cents INTEGER NOT NULL,
            close_cents INTEGER NOT NULL,source TEXT NOT NULL)""")
        legacy.execSQL("""CREATE TABLE funding_audit(
            id INTEGER PRIMARY KEY AUTOINCREMENT,kind TEXT NOT NULL,
            amount_cents INTEGER NOT NULL,cash_after_cents INTEGER NOT NULL,
            funding_after_cents INTEGER NOT NULL,created_ms INTEGER NOT NULL)""")
        legacy.execSQL("""INSERT INTO app_state(id,enabled,cash_cents,funding_cents,
            refill_count,reset_count) VALUES(1,1,120000,120000,1,0)""")
        legacy.version = 1
        legacy.close()

        db = PaperDatabase(context)
        val upgraded = db.snapshot()
        assertEquals(120_000L, upgraded.account.cashCents)
        assertEquals(120_000L, upgraded.account.cumulativeFundingCents)
        assertTrue(upgraded.enabled)
        assertFalse(upgraded.tradingEnabled)
        assertTrue(upgraded.latestNews.isEmpty())
    }
}

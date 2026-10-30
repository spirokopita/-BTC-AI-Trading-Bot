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

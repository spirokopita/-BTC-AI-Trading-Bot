package com.btcaud.paper.data

import androidx.test.ext.junit.runners.AndroidJUnit4
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
}

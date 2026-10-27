package com.btcaud.paper.network

import android.content.Context
import android.util.Log
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.btcaud.paper.core.MonitoringStatus
import com.btcaud.paper.data.PaperDatabase
import org.json.JSONArray
import org.json.JSONObject
import org.junit.After
import org.junit.Assert.*
import org.junit.Assume
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import java.io.IOException

/**
 * Android instrumented network/parser/SQLite tests. The live test is read-only,
 * never enables simulated entries, and reports a JUnit SKIP if offline.
 */
@RunWith(AndroidJUnit4::class)
class KrakenSqliteInstrumentedTest {
    private val context get() = InstrumentationRegistry.getInstrumentation().targetContext
    private lateinit var db: PaperDatabase

    @Before fun setup() {
        context.deleteDatabase("btc_paper_v13.db")
        db = PaperDatabase(context)
    }

    @After fun cleanup() {
        db.close()
        context.deleteDatabase("btc_paper_v13.db")
    }

    private val interval = 14_400L
    private val syntheticNowMs = 1_800_000_600_000L

    private fun fixtureOhlc(nowMs: Long = syntheticNowMs): String {
        val forming = nowMs / 1_000L / interval * interval
        val rows = JSONArray()
        for (i in 0..720) {
            val start = forming - (720L - i) * interval
            rows.put(JSONArray().put(start).put("110000.00").put("110050.00")
                .put("109950.00").put("110010.00").put("110000.00")
                .put("1.25").put(12))
        }
        return JSONObject().put("error", JSONArray())
            .put("result", JSONObject().put("XBTAUD", rows).put("last", forming)).toString()
    }

    private fun fixtureTicker(bid: String = "110000.00", ask: String = "110010.00") =
        JSONObject().put("error", JSONArray()).put("result", JSONObject().put("XBTAUD",
            JSONObject().put("b", JSONArray().put(bid))
                .put("a", JSONArray().put(ask))
                .put("c", JSONArray().put("110005.00")))).toString()

    @Test fun fixture721RowsOnly720CompletedPersistedTwiceWithoutTrades() {
        db.setEnabled(true) // monitoring ON; trading remains OFF
        val candles = KrakenPublicFeed.parseCompletedOhlc(fixtureOhlc(), syntheticNowMs)
        val ticker = KrakenPublicFeed.parseTickerCents(fixtureTicker())
        assertEquals(720, candles.size)
        assertEquals(11_000_500L, ticker)
        assertTrue(KrakenPublicFeed.persistObserved(db, candles, ticker, syntheticNowMs))
        assertTrue(KrakenPublicFeed.persistObserved(db, candles, ticker, syntheticNowMs + 60_000L))
        val snap = db.snapshot()
        assertEquals(candles.last().startS, snap.lastCandleEpochSeconds)
        assertEquals(ticker, snap.latestTickerAudCents)
        assertEquals(0L, snap.netPnlCents)
        assertFalse(snap.tradingEnabled)
        assertTrue(snap.recentTrades.isEmpty())
        db.readableDatabase.rawQuery("SELECT COUNT(*) FROM candles_4h", null).use {
            assertTrue(it.moveToFirst())
            assertEquals(720, it.getInt(0))
        }
        // A failed/offline sync must mark health STALE without creating an entry.
        db.recordFailure("Public feed unavailable")
        assertEquals(MonitoringStatus.STALE, db.snapshot().status(syntheticNowMs + 60_000L))
        db.setEnabled(false)
        assertFalse(KrakenPublicFeed.persistObserved(db, candles, ticker, syntheticNowMs + 120_000L))
        assertEquals(0L, db.snapshot().netPnlCents)
    }

    @Test fun rejectsStaleGapWrongMarketAndCrossedTickerWithoutWriting() {
        db.setEnabled(true)
        val good = fixtureOhlc()
        try {
            KrakenPublicFeed.parseCompletedOhlc(good, syntheticNowMs + 86_400_000L)
            fail("Stale source accepted")
        } catch (_: IllegalArgumentException) { }
        try {
            KrakenPublicFeed.parseCompletedOhlc(good.replace("XBTAUD", "ETHUSD"), syntheticNowMs)
            fail("Wrong market accepted")
        } catch (_: IllegalArgumentException) { }
        val broken = JSONObject(good)
        val rows = broken.getJSONObject("result").getJSONArray("XBTAUD")
        rows.getJSONArray(710).put(0, rows.getJSONArray(710).getLong(0) + interval)
        try {
            KrakenPublicFeed.parseCompletedOhlc(broken.toString(), syntheticNowMs)
            fail("Duplicate or gap accepted")
        } catch (_: IllegalArgumentException) { }
        try {
            KrakenPublicFeed.parseTickerCents(fixtureTicker("110020.00", "110010.00"))
            fail("Crossed ticker accepted")
        } catch (_: IllegalArgumentException) { }
        assertNull(db.snapshot().lastSuccessMillis)
        assertTrue(db.snapshot().recentTrades.isEmpty())
    }

    @Test fun liveKrakenNetworkToSqliteSmokePaperDisabled() {
        db.setEnabled(true)
        assertTrue(db.recordAttempt(System.currentTimeMillis()))
        val committed = try {
            KrakenPublicFeed.syncInto(db) // Actual production HTTPS -> parser -> SQLite path.
        } catch (e: IOException) {
            Log.w("BTCAUD_V19", "LIVE_NETWORK_UNAVAILABLE; test skipped", e)
            Assume.assumeNoException("Live Kraken network unavailable", e)
            return
        }
        assertTrue("Monitoring was unexpectedly paused", committed)
        val snap = db.snapshot()
        assertNotNull(snap.lastSuccessMillis)
        assertNotNull(snap.latestTickerAudCents)
        assertTrue(snap.latestTickerAudCents!! > 0L)
        assertFalse(snap.tradingEnabled)
        assertEquals(0L, snap.netPnlCents)
        assertTrue(snap.recentTrades.isEmpty())
        db.readableDatabase.rawQuery("SELECT COUNT(*) FROM candles_4h", null).use {
            assertTrue(it.moveToFirst())
            assertTrue("Expected at least 21 validated public bars", it.getInt(0) >= 21)
            assertTrue("Forming row must not be cached", it.getInt(0) <= 720)
        }
        Log.i("BTCAUD_V19", "LIVE_KRAKEN_SQLITE_VERIFIED; paper trades=0; net cents=0")
    }
}

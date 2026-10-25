package com.btcaud.paper.work

import android.content.Context
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import com.btcaud.paper.data.PaperDatabase
import com.btcaud.paper.network.KrakenPublicFeed
import com.btcaud.paper.notifications.StatusNotification
import com.btcaud.paper.widgets.DashboardWidget
import com.btcaud.paper.widgets.ToggleWidget
import androidx.glance.appwidget.updateAll
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/**
 * Public HTTP only; the ONLY executions are local SQLite paper events.
 * Fetch first, then atomically re-check user's enable/disable state.
 */
class MarketSyncWorker(context: Context, params: WorkerParameters) : CoroutineWorker(context, params) {
    override suspend fun doWork(): Result = withContext(Dispatchers.IO) {
        val db = PaperDatabase(applicationContext)
        try {
            if (!db.snapshot().enabled) return@withContext Result.success()
            val now = System.currentTimeMillis()
            if (!db.recordAttempt(now)) return@withContext Result.success()
            val candles = KrakenPublicFeed.fetchCompleted(now)
            val ticker = KrakenPublicFeed.fetchObservedTickerCents()
            val seenAt = System.currentTimeMillis()
            if (db.recordCandles(candles, seenAt)) {
                db.observeTickerAndPaperTrade(seenAt, ticker)
            }
            Result.success()
        } catch (e: Exception) {
            db.recordFailure("Public market/strategy sync failed: " + e.javaClass.simpleName)
            Result.retry()
        } finally {
            try {
                ToggleWidget().updateAll(applicationContext)
                DashboardWidget().updateAll(applicationContext)
                StatusNotification.refresh(applicationContext, db.snapshot())
            } finally { db.close() }
        }
    }
}

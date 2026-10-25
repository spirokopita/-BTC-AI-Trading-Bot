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

/** Fetch/cache only. Does NOT evaluate trades, create orders, or call private APIs. */
class MarketSyncWorker(context: Context, params: WorkerParameters) : CoroutineWorker(context, params) {
    override suspend fun doWork(): Result = withContext(Dispatchers.IO) {
        val db = PaperDatabase(applicationContext)
        try {
            if (!db.snapshot().enabled) return@withContext Result.success()
            val now = System.currentTimeMillis()
            if (!db.recordAttempt(now)) return@withContext Result.success()
            val candles = KrakenPublicFeed.fetchCompleted(now)
            db.recordCandles(candles, System.currentTimeMillis())
            Result.success()
        } catch (e: Exception) {
            db.recordFailure("Public OHLC sync failed: ${e.javaClass.simpleName}")
            Result.retry() // exponential retry policy managed by WorkManager
        } finally {
            try {
                ToggleWidget().updateAll(applicationContext)
                DashboardWidget().updateAll(applicationContext)
                StatusNotification.refresh(applicationContext, db.snapshot())
            } finally { db.close() }
        }
    }
}

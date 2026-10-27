package com.btcaud.paper.work

import android.content.Context
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import com.btcaud.paper.data.PaperDatabase
import com.btcaud.paper.network.KrakenPublicFeed
import com.btcaud.paper.network.NewsEye
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
            // Same validated public-network -> SQLite path exercised by V19 tests.
            KrakenPublicFeed.syncInto(db)
            Result.success()
        } catch (e: Exception) {
            db.recordFailure("Public market/strategy sync failed: " + e.javaClass.simpleName)
            Result.retry()
        } finally {
            try {
                // Independently collect bounded first-observed RSS headlines;
                // a broken news provider cannot prevent risk exits or mark the
                // price feed as healthy/unhealthy.
                try {
                    if (db.recordNewsAttempt(System.currentTimeMillis())) {
                        val report = NewsEye.collect()
                        db.storeNews(report.observations, System.currentTimeMillis(), report.warnings)
                    }
                } catch (e: Exception) {
                    db.recordNewsFailure("News eye: " + e.javaClass.simpleName)
                }
                ToggleWidget().updateAll(applicationContext)
                DashboardWidget().updateAll(applicationContext)
                StatusNotification.refresh(applicationContext, db.snapshot())
            } finally { db.close() }
        }
    }
}

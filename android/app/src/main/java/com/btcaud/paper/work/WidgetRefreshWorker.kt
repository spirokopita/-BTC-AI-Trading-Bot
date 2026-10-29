package com.btcaud.paper.work

import android.content.Context
import androidx.glance.appwidget.updateAll
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import com.btcaud.paper.data.PaperDatabase
import com.btcaud.paper.notifications.StatusNotification
import com.btcaud.paper.widgets.DashboardWidget
import com.btcaud.paper.widgets.ToggleWidget
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/**
 * Lightweight local-only status refresh. Unlike market sync this does not
 * require connectivity: offline cached prices can become visibly STALE.
 * WorkManager/Doze can delay the refresh; no exact or 24/7 guarantee.
 */
class WidgetRefreshWorker(context: Context, params: WorkerParameters) :
    CoroutineWorker(context, params) {
    override suspend fun doWork(): Result = withContext(Dispatchers.IO) {
        try {
            val snapshot = PaperDatabase(applicationContext).use { it.snapshot() }
            ToggleWidget().updateAll(applicationContext)
            DashboardWidget().updateAll(applicationContext)
            StatusNotification.refresh(applicationContext, snapshot)
            Result.success()
        } catch (_: Exception) {
            Result.retry()
        }
    }
}

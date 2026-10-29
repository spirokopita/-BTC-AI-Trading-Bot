package com.btcaud.paper.work

import android.content.Context
import androidx.work.Constraints
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import java.util.concurrent.TimeUnit

/** WorkManager is inexact: 15-minute minimum, Doze may delay execution. */
object WorkScheduler {
    private const val PERIODIC = "btc_paper_public_ohlc_periodic"
    private const val IMMEDIATE = "btc_paper_public_ohlc_immediate"
    const val WIDGET_REFRESH = "btc_paper_widget_refresh"

    fun start(context: Context, immediate: Boolean = true) {
        val manager = WorkManager.getInstance(context)
        val constraints = Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build()
        val periodic = PeriodicWorkRequestBuilder<MarketSyncWorker>(15, TimeUnit.MINUTES)
            .setConstraints(constraints)
            .build()
        manager.enqueueUniquePeriodicWork(PERIODIC, ExistingPeriodicWorkPolicy.KEEP, periodic)

        // Independent of internet availability. Keeps cached dashboard/status
        // from appearing fresh indefinitely after a connectivity outage.
        manager.enqueueUniquePeriodicWork(
            WIDGET_REFRESH, ExistingPeriodicWorkPolicy.KEEP,
            PeriodicWorkRequestBuilder<WidgetRefreshWorker>(15, TimeUnit.MINUTES).build(),
        )
        if (immediate) manager.enqueueUniqueWork(
            IMMEDIATE, ExistingWorkPolicy.REPLACE,
            OneTimeWorkRequestBuilder<MarketSyncWorker>().setConstraints(constraints).build(),
        )
    }

    fun stop(context: Context) {
        WorkManager.getInstance(context).apply {
            cancelUniqueWork(PERIODIC)
            cancelUniqueWork(IMMEDIATE)
            cancelUniqueWork(WIDGET_REFRESH)
        }
    }
}

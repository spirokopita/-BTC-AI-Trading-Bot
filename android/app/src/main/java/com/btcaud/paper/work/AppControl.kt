package com.btcaud.paper.work

import android.content.Context
import androidx.glance.appwidget.updateAll
import com.btcaud.paper.data.PaperDatabase
import com.btcaud.paper.notifications.StatusNotification
import com.btcaud.paper.widgets.DashboardWidget
import com.btcaud.paper.widgets.ToggleWidget
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/** All user control paths (app, widget, notification) converge here. */
object AppControl {
    suspend fun setEnabled(context: Context, enabled: Boolean) {
        withContext(Dispatchers.IO) {
            val changed = PaperDatabase(context).use { db -> db.setEnabled(enabled) }
            if (changed) {
                if (enabled) WorkScheduler.start(context) else WorkScheduler.stop(context)
            }
            refresh(context)
        }
    }

    suspend fun refill(context: Context) = withContext(Dispatchers.IO) {
        PaperDatabase(context).use { it.refill(System.currentTimeMillis()) }
        refresh(context)
    }

    suspend fun reset(context: Context) = withContext(Dispatchers.IO) {
        PaperDatabase(context).use { it.reset(System.currentTimeMillis()) }
        refresh(context)
    }

    suspend fun refresh(context: Context) {
        val snapshot = PaperDatabase(context).use { it.snapshot() }
        ToggleWidget().updateAll(context)
        DashboardWidget().updateAll(context)
        StatusNotification.refresh(context, snapshot)
    }
}

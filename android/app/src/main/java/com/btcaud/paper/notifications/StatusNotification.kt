package com.btcaud.paper.notifications

import android.Manifest
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Color
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import com.btcaud.paper.R
import com.btcaud.paper.core.MonitorPolicy
import com.btcaud.paper.core.MonitorSnapshot
import com.btcaud.paper.core.MonitoringStatus
import com.btcaud.paper.ui.MainActivity
import com.btcaud.paper.work.AppControl
import java.text.DateFormat
import java.util.Date
import java.util.Locale
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch

/**
 * Purple-accented, user-controlled status notification. Android owns the actual
 * status bar and system chips: this cannot recolor them or guarantee a Live Update.
 * When paused the notification is dismissible, but offers a safe Resume action.
 */
object StatusNotification {
    private const val CHANNEL = "paper_monitor"
    private const val ID = 1313

    /** Pure notification construction so action/freshness behaviour is device-testable. */
    fun buildNotification(
        context: Context,
        state: MonitorSnapshot,
        nowMs: Long = System.currentTimeMillis(),
    ): Notification {
        val status = state.status(nowMs)
        val lastPoll = state.lastSuccessMillis?.takeIf { it > 0L }?.let {
            DateFormat.getDateTimeInstance(DateFormat.SHORT, DateFormat.SHORT).format(Date(it))
        } ?: "never"

        // A cached ticker is not a live quote. Pausing or a delayed poll must
        // never make an old observed price appear current.
        val tickerTime = state.latestTickerMillis
        val tickerAge = if (tickerTime == null) -1L else nowMs - tickerTime
        val priceFresh = status == MonitoringStatus.RUNNING &&
            tickerAge in 0L..MonitorPolicy.FRESH_MILLIS
        val price = state.latestTickerAudCents?.takeIf { it > 0L }?.let {
            "A$" + String.format(Locale.US, "%,.2f", it / 100.0) +
                if (priceFresh) " (observed)" else " (STALE)"
        } ?: "NO DATA"
        val open = PendingIntent.getActivity(
            context, 0, Intent(context, MainActivity::class.java),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
        )
        val actionIsPause = state.enabled
        val control = PendingIntent.getBroadcast(
            context, if (actionIsPause) 1 else 2,
            Intent(context, NotificationActionReceiver::class.java).apply {
                action = if (actionIsPause) NotificationActionReceiver.ACTION_PAUSE
                         else NotificationActionReceiver.ACTION_RESUME
            },
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
        )
        return NotificationCompat.Builder(context, CHANNEL)
            .setSmallIcon(R.drawable.ic_status)
            .setContentTitle("BTC AI · PAPER · ${status.name}")
            .setContentText("Last poll: $lastPoll · BTC/AUD $price")
            .setStyle(NotificationCompat.BigTextStyle().bigText(
                "Last successful poll: $lastPoll\nBTC/AUD $price\n" +
                    "Periodic checks may be delayed by Android; simulated trades only."
            ))
            .setColor(Color.rgb(124, 58, 237))
            .setColorized(false) // Purple accent, not a system-wide status-bar color.
            .setOngoing(state.enabled)
            .setOnlyAlertOnce(true)
            .setContentIntent(open)
            .addAction(0, if (actionIsPause) "Pause" else "Resume", control)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .build()
    }

    fun refresh(context: Context, state: MonitorSnapshot) {
        if (Build.VERSION.SDK_INT >= 33 && ContextCompat.checkSelfPermission(
                context, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
        ) return
        val manager = context.getSystemService(NotificationManager::class.java)
        manager.createNotificationChannel(NotificationChannel(
            CHANNEL, "BTC AI paper monitor", NotificationManager.IMPORTANCE_LOW,
        ).apply { description = "Public price checks and simulated account status" })
        NotificationManagerCompat.from(context).notify(ID, buildNotification(context, state))
    }
}

class NotificationActionReceiver : BroadcastReceiver() {
    companion object {
        const val ACTION_PAUSE = "com.btcaud.paper.ACTION_PAUSE"
        const val ACTION_RESUME = "com.btcaud.paper.ACTION_RESUME"
    }

    override fun onReceive(context: Context, intent: Intent) {
        val enable = when (intent.action) {
            ACTION_PAUSE -> false
            ACTION_RESUME -> true
            else -> return
        }
        val pending = goAsync()
        CoroutineScope(SupervisorJob() + Dispatchers.IO).launch {
            try { AppControl.setEnabled(context.applicationContext, enable) }
            finally { pending.finish() }
        }
    }
}

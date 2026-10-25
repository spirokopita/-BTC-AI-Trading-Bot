package com.btcaud.paper.notifications

import android.Manifest
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
import com.btcaud.paper.core.MonitorSnapshot
import com.btcaud.paper.ui.MainActivity
import com.btcaud.paper.work.AppControl
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch

/** Purple-themed notification; Android/Samsung control actual status-bar chip colour. */
object StatusNotification {
    private const val CHANNEL = "paper_monitor"
    private const val ID = 1313

    fun refresh(context: Context, state: MonitorSnapshot) {
        val manager = context.getSystemService(NotificationManager::class.java)
        if (!state.enabled) { manager.cancel(ID); return }
        if (Build.VERSION.SDK_INT >= 33 && ContextCompat.checkSelfPermission(
                context, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
        ) return
        manager.createNotificationChannel(NotificationChannel(
            CHANNEL, "BTC AI paper monitor", NotificationManager.IMPORTANCE_LOW,
        ).apply { description = "Public price checks and simulated account status" })
        val open = PendingIntent.getActivity(
            context, 0, Intent(context, MainActivity::class.java),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
        )
        val pause = PendingIntent.getBroadcast(
            context, 1, Intent(context, NotificationActionReceiver::class.java).apply {
                action = NotificationActionReceiver.ACTION_PAUSE
            }, PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
        )
        val status = state.status(System.currentTimeMillis()).name
        val notification = NotificationCompat.Builder(context, CHANNEL)
            .setSmallIcon(R.drawable.ic_status)
            .setContentTitle("BTC AI · PAPER · $status")
            .setContentText("Periodic market checks; Android may delay background work")
            .setColor(Color.rgb(124, 58, 237))
            .setColorized(true) // system may ignore this outside eligible notification classes
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .setContentIntent(open)
            .addAction(0, "Pause", pause)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .build()
        NotificationManagerCompat.from(context).notify(ID, notification)
    }
}

class NotificationActionReceiver : BroadcastReceiver() {
    companion object { const val ACTION_PAUSE = "com.btcaud.paper.ACTION_PAUSE" }
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != ACTION_PAUSE) return
        val pending = goAsync()
        CoroutineScope(SupervisorJob() + Dispatchers.IO).launch {
            try { AppControl.setEnabled(context.applicationContext, false) }
            finally { pending.finish() }
        }
    }
}

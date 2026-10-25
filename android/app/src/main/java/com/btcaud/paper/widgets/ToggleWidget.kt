package com.btcaud.paper.widgets

import android.content.Context
import androidx.compose.ui.graphics.Color
import androidx.glance.GlanceId
import androidx.glance.GlanceModifier
import androidx.glance.action.ActionParameters
import androidx.glance.appwidget.action.actionRunCallback
import androidx.glance.appwidget.GlanceAppWidget
import androidx.glance.appwidget.GlanceAppWidgetReceiver
import androidx.glance.appwidget.action.ActionCallback
import androidx.glance.appwidget.provideContent
import androidx.glance.background
import androidx.glance.layout.Alignment
import androidx.glance.layout.Column
import androidx.glance.layout.fillMaxSize
import androidx.glance.layout.padding
import androidx.glance.text.Text
import androidx.glance.unit.ColorProvider
import androidx.glance.text.TextStyle
import androidx.glance.action.clickable
import androidx.glance.appwidget.updateAll
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import com.btcaud.paper.data.PaperDatabase
import com.btcaud.paper.work.AppControl

class ToggleWidget : GlanceAppWidget() {
    override suspend fun provideGlance(context: Context, id: GlanceId) {
        val snapshot = withContext(Dispatchers.IO) { PaperDatabase(context).use { it.snapshot() } }
        val label = if (snapshot.enabled) "ON · ${snapshot.status(System.currentTimeMillis())}" else "OFF · PAUSED"
        provideContent {
            Column(
                modifier = GlanceModifier.fillMaxSize().background(Color(0xFF170D29))
                    .padding(12.dp).clickable(onClick = if (snapshot.enabled) actionRunCallback<PauseAction>() else actionRunCallback<ResumeAction>()),
                verticalAlignment = Alignment.CenterVertically,
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                Text("BTC AI", style = TextStyle(color = ColorProvider(Color.White)))
                Text(label, style = TextStyle(color = ColorProvider(Color(0xFFBB86FC))))
                Text("PAPER ONLY", style = TextStyle(color = ColorProvider(Color.LightGray)))
            }
        }
    }
}
class ToggleWidgetReceiver : GlanceAppWidgetReceiver() { override val glanceAppWidget: GlanceAppWidget = ToggleWidget() }

/** Fixed actions, not toggle-by-read: repeated taps on a stale widget are idempotent. */
class PauseAction : ActionCallback {
    override suspend fun onAction(context: Context, glanceId: GlanceId, parameters: ActionParameters) {
        AppControl.setEnabled(context, false)
    }
}
class ResumeAction : ActionCallback {
    override suspend fun onAction(context: Context, glanceId: GlanceId, parameters: ActionParameters) {
        AppControl.setEnabled(context, true)
    }
}

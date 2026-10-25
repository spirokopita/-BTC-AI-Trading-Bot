package com.btcaud.paper.widgets

import android.content.Context
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import androidx.glance.GlanceId
import androidx.glance.GlanceModifier
import androidx.glance.appwidget.GlanceAppWidget
import androidx.glance.appwidget.GlanceAppWidgetReceiver
import androidx.glance.appwidget.provideContent
import androidx.glance.background
import androidx.glance.layout.Column
import androidx.glance.layout.fillMaxSize
import androidx.glance.layout.padding
import androidx.glance.text.Text
import androidx.glance.text.TextStyle
import androidx.glance.unit.ColorProvider
import com.btcaud.paper.data.PaperDatabase
import java.util.Locale

class DashboardWidget : GlanceAppWidget() {
    override suspend fun provideGlance(context: Context, id: GlanceId) {
        val state = withContext(Dispatchers.IO) {
            PaperDatabase(context).use { it.snapshot() }
        }
        fun aud(cents: Long) = "A$" + String.format(Locale.US, "%,.2f", cents / 100.0)
        val status = state.status(System.currentTimeMillis()).name
        provideContent {
            Column(GlanceModifier.fillMaxSize().background(Color(0xFF110B1E)).padding(12.dp)) {
                Text("BTC AI · PAPER · " + status,
                    style = TextStyle(color = ColorProvider(Color(0xFFBB86FC))))
                Text("EQUITY  " + aud(state.estimatedEquityCents),
                    style = TextStyle(color = ColorProvider(Color.White)))
                Text("NET AFTER COSTS  " + aud(state.netPnlCents),
                    style = TextStyle(color = ColorProvider(Color.White)))
                Text("BTC/AUD  " + (state.latestTickerAudCents?.let(::aud) ?: "NO DATA"),
                    style = TextStyle(color = ColorProvider(Color.White)))
                Text("Position  " + if (state.positionSats > 0L) "BTC PAPER" else "NONE",
                    style = TextStyle(color = ColorProvider(Color.LightGray)))
                Text("Strategy  " + if (state.tradingEnabled && state.enabled) "ARMED" else "OFF",
                    style = TextStyle(color = ColorProvider(Color.LightGray)))
                Text("Last decision: " + state.lastDecision,
                    style = TextStyle(color = ColorProvider(Color(0xFFBB86FC))))
            }
        }
    }
}
class DashboardWidgetReceiver : GlanceAppWidgetReceiver() {
    override val glanceAppWidget: GlanceAppWidget = DashboardWidget()
}

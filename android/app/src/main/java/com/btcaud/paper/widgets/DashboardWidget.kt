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
        val state = withContext(Dispatchers.IO) { PaperDatabase(context).use { it.snapshot() } }
        val equity = state.account.cashCents / 100.0 // V13 cash-only; no positions
        val net = state.account.netPnlCents / 100.0
        val price = state.latestCloseAudCents?.let { "A$" + String.format(Locale.US, "%,.2f", it / 100.0) } ?: "NO DATA"
        val status = state.status(System.currentTimeMillis()).name
        val signal = "DISABLED (no AI trades)"
        provideContent {
            Column(GlanceModifier.fillMaxSize().background(Color(0xFF110B1E)).padding(12.dp)) {
                Text("BTC AI · PAPER · $status", style = TextStyle(color = ColorProvider(Color(0xFFBB86FC))))
                Text("SIM EQUITY  A$" + String.format(Locale.US, "%,.2f", equity),
                    style = TextStyle(color = ColorProvider(Color.White)))
                Text("NET P&L  A$" + String.format(Locale.US, "%,.2f", net) + " (no trades)",
                    style = TextStyle(color = ColorProvider(Color.White)))
                Text("BTC/AUD  $price  · 4h closed", style = TextStyle(color = ColorProvider(Color.White)))
                Text("Position: NONE · Last trade: NONE", style = TextStyle(color = ColorProvider(Color.LightGray)))
                Text("AI: $signal", style = TextStyle(color = ColorProvider(Color.LightGray)))
                Text("Feed: ${if (state.lastError == null) status else "ERROR / $status"}",
                    style = TextStyle(color = ColorProvider(Color(0xFFBB86FC))))
            }
        }
    }
}
class DashboardWidgetReceiver : GlanceAppWidgetReceiver() { override val glanceAppWidget: GlanceAppWidget = DashboardWidget() }

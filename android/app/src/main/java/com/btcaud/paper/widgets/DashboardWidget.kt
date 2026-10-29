package com.btcaud.paper.widgets

import android.content.Context
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
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
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/** Compact, resizeable, read-only dashboard. All values come from persisted paper state. */
class DashboardWidget : GlanceAppWidget() {
    override suspend fun provideGlance(context: Context, id: GlanceId) {
        val view = withContext(Dispatchers.IO) {
            PaperDatabase(context).use { db ->
                DashboardWidgetPresentation.from(db.snapshot(), System.currentTimeMillis())
            }
        }
        provideContent {
            Column(GlanceModifier.fillMaxSize().background(Color(0xFF110B1E)).padding(8.dp)) {
                Text(view.title, style = TextStyle(color = ColorProvider(Color(0xFFBB86FC))))
                Text(view.equity, style = TextStyle(color = ColorProvider(Color.White)))
                Text(view.net, style = TextStyle(color = ColorProvider(Color.White)))
                Text(view.ticker, style = TextStyle(color = ColorProvider(Color.White)))
                Text(view.position, style = TextStyle(color = ColorProvider(Color.LightGray)))
                Text(view.lastTrade, style = TextStyle(color = ColorProvider(Color.LightGray)))
                Text(view.signal, style = TextStyle(color = ColorProvider(Color(0xFFBB86FC))))
                Text(view.health, style = TextStyle(color = ColorProvider(Color(0xFFFFC88A))))
            }
        }
    }
}

class DashboardWidgetReceiver : GlanceAppWidgetReceiver() {
    override val glanceAppWidget: GlanceAppWidget = DashboardWidget()
}

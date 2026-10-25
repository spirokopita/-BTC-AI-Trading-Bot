package com.btcaud.paper.ui

import android.Manifest
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import com.btcaud.paper.core.MonitorSnapshot
import com.btcaud.paper.core.HistoricalPaperReplay
import com.btcaud.paper.data.PaperDatabase
import com.btcaud.paper.work.AppControl
import com.btcaud.paper.work.WorkScheduler
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.text.DateFormat
import java.util.Date
import java.util.Locale

class MainActivity : ComponentActivity() {
    private val askNotificationPermission =
        registerForActivityResult(ActivityResultContracts.RequestPermission()) { }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        PaperDatabase(this).use {
            if (it.snapshot().enabled) WorkScheduler.start(this, immediate = false)
        }
        if (Build.VERSION.SDK_INT >= 33)
            askNotificationPermission.launch(Manifest.permission.POST_NOTIFICATIONS)
        setContent { PaperScreen(this) }
    }
}

private val accent = Color(0xFFA88AFF)
private val muted = Color(0xFFB5AFCA)
private val background = Color(0xFF0B0812)

@Composable
private fun PaperScreen(activity: MainActivity) {
    val scope = rememberCoroutineScope()
    var state by remember { mutableStateOf<MonitorSnapshot?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var research by remember { mutableStateOf<HistoricalPaperReplay.Report?>(null) }
    suspend fun reload() {
        state = withContext(Dispatchers.IO) { PaperDatabase(activity).use { it.snapshot() } }
    }
    LaunchedEffect(Unit) {
        while (true) {
            reload()
            delay(10_000)
        }
    }
    MaterialTheme(colorScheme = darkColorScheme(
        primary = accent, onPrimary = background, surface = background,
        onSurface = Color.White, background = background, onBackground = Color.White
    )) {
        Surface(Modifier.fillMaxSize(), color = background) {
            Column(
                Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(20.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                Text("BTC AI", style = MaterialTheme.typography.headlineLarge, color = accent)
                Text("V16 · LOCAL SIMULATION · NO WALLET · NO EXCHANGE KEYS", color = muted)
                val s = state
                if (s == null) {
                    Text("Loading local paper account...", color = Color.White)
                } else {
                    Text("MARKET MONITOR: " + s.status(System.currentTimeMillis()), color = accent)
                    Text("Estimated paper equity: " + aud(s.estimatedEquityCents),
                        style = MaterialTheme.typography.headlineMedium, color = Color.White)
                    Text("NET P&L after simulated costs: " + aud(s.netPnlCents), color = Color.White)
                    Text("Realised NET this simulation: " + aud(s.realisedNetCents), color = Color.White)
                    Text("Available simulated cash: " + aud(s.account.cashCents), color = Color.White)
                    Text("BTC/AUD observed ticker: " +
                        (s.latestTickerAudCents?.let(::aud) ?: "NO DATA"), color = Color.White)
                    Text("Last ticker observed: " + time(s.latestTickerMillis), color = muted)
                    Text("Last completed 4h close: " +
                        (s.latestCloseAudCents?.let(::aud) ?: "NO DATA"), color = muted)
                    Text("Last successful poll: " + time(s.lastSuccessMillis), color = muted)
                    if (s.lastError != null) Text("Feed warning: " + s.lastError,
                        color = Color(0xFFFFA1A1))
                    Button(onClick = {
                        scope.launch {
                            try { AppControl.setEnabled(activity, !s.enabled); reload() }
                            catch (e: Exception) { error = e.message ?: "Monitor toggle failed" }
                        }
                    }, modifier = Modifier.fillMaxWidth()) {
                        Text(if (s.enabled) "PAUSE MONITOR" else "START MONITOR")
                    }
                    OutlinedButton(onClick = {
                        WorkScheduler.start(activity, immediate = true)
                    }, enabled = s.enabled, modifier = Modifier.fillMaxWidth()) {
                        Text("REQUEST MARKET SYNC")
                    }
                    HorizontalDivider()
                    Text("PAPER STRATEGY", color = accent,
                        style = MaterialTheme.typography.titleLarge)
                    Text("SMA10/SMA20 crossover · 4h bars · max A$50 per entry",
                        color = Color.White)
                    Text("Rule-based baseline, NOT an AI model. Entries use an observed public " +
                        "ticker after the signal. Protective exits only run when Android polls.",
                        color = muted)
                    Text("Paper execution: " +
                        if (s.tradingEnabled && s.enabled) "ARMED" else "OFF / MONITOR PAUSED",
                        color = if (s.tradingEnabled && s.enabled) accent else muted)
                    Button(onClick = {
                        scope.launch {
                            try { AppControl.setTradingEnabled(activity, !s.tradingEnabled); reload() }
                            catch (e: Exception) { error = e.message ?: "Strategy toggle failed" }
                        }
                    }, enabled = s.enabled, modifier = Modifier.fillMaxWidth()) {
                        Text(if (s.tradingEnabled) "DISABLE PAPER TRADING" else "ENABLE PAPER TRADING")
                    }
                    Text("Last strategy decision: " + s.lastDecision, color = Color.White)
                    Text(s.lastDecisionReason, color = muted)
                    if (s.positionSats > 0) {
                        Text("OPEN SIMULATED BTC: " +
                            String.format(Locale.US, "%.8f", s.positionSats / 100_000_000.0),
                            color = Color.White)
                        Text("Entry: " + aud(s.entryPriceCents) +
                            " · Paid including costs: " + aud(s.positionBasisCents),
                            color = Color.White)
                        Text("Estimated liquidation value: " + aud(s.estimatedLiquidationCents),
                            color = Color.White)
                    } else {
                        Text("Open position: NONE", color = Color.White)
                    }
                    HorizontalDivider()
                    Text("RECENT SIMULATED EXECUTIONS", color = accent,
                        style = MaterialTheme.typography.titleLarge)
                    if (s.recentTrades.isEmpty()) {
                        Text("No paper trades yet. Waiting is a valid decision.", color = muted)
                    } else {
                        s.recentTrades.take(8).forEach { event ->
                            Column(verticalArrangement = Arrangement.spacedBy(3.dp)) {
                                Text(event.side + " · " + time(event.observedMs) +
                                    " · " + aud(event.priceCents), color = Color.White)
                                Text("Costs: " + aud(event.costsCents) +
                                    (event.realisedNetCents?.let { " · NET: " + aud(it) } ?: ""),
                                    color = muted)
                                Text(event.reason, color = muted)
                            }
                        }
                    }
                    HorizontalDivider()
                    HorizontalDivider()
                    Text("HISTORICAL REPLAY LAB", color = accent,
                        style = MaterialTheme.typography.titleLarge)
                    Text("Uses completed 4h bars already stored on this phone. " +
                        "It does not change the paper wallet or trade live.",
                        color = muted)
                    OutlinedButton(onClick = {
                        scope.launch {
                            try {
                                research = withContext(Dispatchers.IO) {
                                    PaperDatabase(activity).use { it.researchReplay() }
                                }
                            } catch (e: Exception) {
                                error = e.message ?: "Historical replay failed"
                            }
                        }
                    }, modifier = Modifier.fillMaxWidth()) { Text("REPLAY CACHED HISTORY") }
                    research?.let { report ->
                        Text("Bars analysed: " + report.bars +
                            " · Buys: " + report.buys + " · Sells: " + report.sells,
                            color = Color.White)
                        Text("Replay net return: " +
                            String.format(Locale.US, "%.2f%%", report.netReturnBps / 100.0) +
                            " · Max drawdown: " +
                            String.format(Locale.US, "%.2f%%", report.maxDrawdownBps / 100.0),
                            color = Color.White)
                        Text("Simulated ending equity: " + aud(report.endingEquityCents),
                            color = Color.White)
                        Text(report.warning, color = muted)
                    }
                    Text("NEWS EYE · READ-ONLY OBSERVATIONS", color = accent,
                        style = MaterialTheme.typography.titleLarge)
                    Text("Last successful RSS poll: " + time(s.latestNewsSeenMillis), color = muted)
                    if (s.newsWarning != null)
                        Text("News warning: " + s.newsWarning, color = Color(0xFFFFA1A1))
                    if (s.latestNews.isEmpty()) {
                        Text("No observed headlines yet. News does NOT trigger trades.", color = muted)
                    } else {
                        s.latestNews.take(5).forEach { article ->
                            Text(article.source + " · " + article.topic, color = accent)
                            Text(article.headline, color = Color.White)
                            Text("First seen: " + time(article.firstSeenMs), color = muted)
                        }
                    }
                    Text("Headlines are classified for research, not used for BUY/SELL until " +
                        "we have leakage-free historical validation.", color = muted)
                    HorizontalDivider()
                    Text("TEST FUNDS", color = accent)
                    Text("Funding: " + aud(s.account.cumulativeFundingCents) +
                        " · Refills: " + s.account.refillCount, color = Color.White)
                    OutlinedButton(onClick = { scope.launch {
                        try { AppControl.refill(activity); reload() }
                        catch (e: Exception) { error = e.message ?: "Refill failed" }
                    } }, modifier = Modifier.fillMaxWidth()) { Text("REFILL +A$1,000") }
                    OutlinedButton(onClick = { scope.launch {
                        try { AppControl.reset(activity); reload() }
                        catch (e: Exception) { error = e.message ?: "Reset failed" }
                    } }, modifier = Modifier.fillMaxWidth()) { Text("RESET PAPER SIMULATION TO A$1,000") }
                    Text("Refills are funding, not profit. Reset closes simulated exposure " +
                        "without pretending a sale; historical trade and funding audits remain.",
                        color = muted)
                    Text("Android WorkManager requests checks about every 15 minutes, but " +
                        "battery restrictions can delay them. Paper exits are not real stop orders. " +
                        "Market data and execution estimates cannot guarantee returns.",
                        color = muted)
                }
                if (error != null) Text("App error: " + error, color = Color(0xFFFFA1A1))
            }
        }
    }
}

private fun aud(cents: Long): String = "A$" +
    String.format(Locale.US, "%,.2f", cents / 100.0)
private fun time(millis: Long?): String =
    millis?.let { DateFormat.getDateTimeInstance().format(Date(it)) } ?: "Never"

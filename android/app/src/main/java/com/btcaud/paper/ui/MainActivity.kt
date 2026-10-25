package com.btcaud.paper.ui

import android.Manifest
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
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
import com.btcaud.paper.data.PaperDatabase
import com.btcaud.paper.work.AppControl
import com.btcaud.paper.work.WorkScheduler
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.util.Locale

class MainActivity : ComponentActivity() {
    private val askNotificationPermission = registerForActivityResult(ActivityResultContracts.RequestPermission()) { }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        // Persisted WorkManager jobs survive reboot. This also repairs jobs after app upgrade.
        PaperDatabase(this).use { if (it.snapshot().enabled) WorkScheduler.start(this, immediate = false) }
        if (Build.VERSION.SDK_INT >= 33) askNotificationPermission.launch(Manifest.permission.POST_NOTIFICATIONS)
        setContent { PaperScreen(this) }
    }
}

@Composable
private fun PaperScreen(activity: MainActivity) {
    val scope = rememberCoroutineScope()
    var state by remember { mutableStateOf<MonitorSnapshot?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    suspend fun reload() {
        state = withContext(Dispatchers.IO) { PaperDatabase(activity).use { it.snapshot() } }
    }
    LaunchedEffect(Unit) {
        while (true) { reload(); delay(15_000) }
    }
    val purple = Color(0xFF9B6AFF)
    MaterialTheme(colorScheme = darkColorScheme(primary = purple)) {
        Surface(Modifier.fillMaxSize(), color = Color(0xFF0B0812)) {
            Column(Modifier.fillMaxSize().padding(20.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Text("BTC AI", style = MaterialTheme.typography.headlineLarge, color = purple)
                Text("LOCAL PAPER MODE · NO WALLET · NO EXCHANGE KEYS", color = Color.LightGray)
                val s = state
                if (s == null) Text("Loading local state...") else {
                    Text("MONITOR  ${s.status(System.currentTimeMillis())}", color = purple)
                    Text("Simulated equity: ${aud(s.account.cashCents)}", style = MaterialTheme.typography.headlineMedium)
                    Text("NET P&L after costs: ${aud(s.account.netPnlCents)} (no trades yet)")
                    Text("BTC/AUD closed 4h candle: ${s.latestCloseAudCents?.let(::aud) ?: "NO DATA"}")
                    Text("Last successful poll: ${s.lastSuccessMillis?.let { java.text.DateFormat.getDateTimeInstance().format(java.util.Date(it)) } ?: "Never"}")
                    Text("Open positions: NONE · Last trade: NONE · AI: DISABLED")
                    if (s.lastError != null) Text("Feed warning: ${s.lastError}", color = Color(0xFFFFA1A1))
                    Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                        Button(onClick = {
                            scope.launch {
                                try { AppControl.setEnabled(activity, !s.enabled); reload() }
                                catch (e: Exception) { error = e.message ?: "Could not change monitoring" }
                            }
                        }) { Text(if (s.enabled) "PAUSE MONITOR" else "START MONITOR") }
                    }
                    Spacer(Modifier.height(8.dp))
                    Text("TEST FUNDS", color = purple)
                    Text("Funding: ${aud(s.account.cumulativeFundingCents)} · Refills: ${s.account.refillCount}")
                    Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                        Button(onClick = { scope.launch {
                            try { AppControl.refill(activity); reload() }
                            catch (e: Exception) { error = e.message ?: "Refill failed" }
                        } }) { Text("REFILL +A$1,000") }
                        Button(onClick = { scope.launch {
                            try { AppControl.reset(activity); reload() }
                            catch (e: Exception) { error = e.message ?: "Reset failed" }
                        } }) { Text("RESET TO A$1,000") }
                    }
                    Text("Refills are simulated deposits, never trading profit. Reset preserves the funding audit.", color = Color.LightGray)
                    Text("WorkManager checks approximately every 15 minutes when connected; Android may defer checks. Trading decisions and real-money orders are disabled.", color = Color.LightGray)
                }
                if (error != null) Text("App error: $error", color = Color.Red)
            }
        }
    }
}

private fun aud(cents: Long): String = "A$" + String.format(Locale.US, "%,.2f", cents / 100.0)

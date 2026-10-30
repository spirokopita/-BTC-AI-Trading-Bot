package com.btcaud.paper.widgets

import com.btcaud.paper.core.MonitorPolicy
import com.btcaud.paper.core.MonitorSnapshot
import com.btcaud.paper.core.MonitoringStatus
import java.util.Locale

/**
 * Pure, clock-injected widget presentation. A cached ticker or liquidation mark
 * must never be mistaken for a live quote, especially after Doze/offline/pause.
 * Values are estimates in a paper-only ledger; no live execution exists.
 */
internal data class DashboardWidgetView(
    val title: String,
    val equity: String,
    val net: String,
    val ticker: String,
    val position: String,
    val lastTrade: String,
    val signal: String,
    val health: String,
)

internal object DashboardWidgetPresentation {
    private fun aud(cents: Long): String =
        "A$" + String.format(Locale.US, "%,.2f", cents / 100.0)

    private fun signedAud(cents: Long): String =
        (if (cents < 0L) "-" else if (cents > 0L) "+" else "") +
            aud(kotlin.math.abs(cents))

    private fun age(nowMs: Long, observedMs: Long?): String {
        if (observedMs == null || observedMs <= 0L) return "never"
        val delta = nowMs - observedMs
        if (delta < 0L) return "clock mismatch"
        return if (delta < 60_000L) "<1m" else "${delta / 60_000L}m ago"
    }

    fun from(snapshot: MonitorSnapshot, nowMs: Long): DashboardWidgetView {
        val status = snapshot.status(nowMs)
        val tickerMs = snapshot.latestTickerMillis
        val tickerAge = tickerMs?.let { nowMs - it }
        val quoteFresh = status == MonitoringStatus.RUNNING &&
            snapshot.latestTickerAudCents != null && snapshot.latestTickerAudCents > 0L &&
            tickerAge != null && tickerAge in 0L..MonitorPolicy.FRESH_MILLIS

        val ticker = snapshot.latestTickerAudCents?.takeIf { it > 0L }?.let {
            "BTC/AUD ${aud(it)} · ${if (quoteFresh) "OBSERVED" else "STALE"} · ${age(nowMs, tickerMs)}"
        } ?: "BTC/AUD NO DATA"

        // Open positions are valued at an estimated liquidation price, not
        // guaranteed proceeds. Stale marks must be labelled on both P&L fields.
        val markWarning = if (snapshot.positionSats > 0L && !quoteFresh) " · STALE MARK" else ""
        val last = snapshot.recentTrades.firstOrNull()
        val lastTrade = if (last == null) "Last trade: NONE" else {
            val realised = last.realisedNetCents?.let { " · realised NET ${signedAud(it)}" } ?: ""
            "Last: ${last.side} gross ${aud(last.grossCents)} · costs ${aud(last.costsCents)} · NET flow ${signedAud(last.netCashFlowCents)}$realised"
        }
        val signal = when {
            !snapshot.tradingEnabled -> "SMA OFF · AI NOT TRAINED"
            !snapshot.enabled -> "SMA PAUSED · AI NOT TRAINED"
            status != MonitoringStatus.RUNNING -> "SMA WAITING FOR FEED · AI NOT TRAINED"
            else -> "SMA ${snapshot.lastDecision} · AI NOT TRAINED"
        }
        val health = "Health: ${status.name} · sync ${age(nowMs, snapshot.lastSuccessMillis)}" +
            if (snapshot.lastError != null) " · FEED ERROR" else ""

        return DashboardWidgetView(
            title = "BTC AI · PAPER · ${status.name}",
            equity = "EST. EQUITY ${aud(snapshot.estimatedEquityCents)}$markWarning",
            net = "NET after costs ${signedAud(snapshot.netPnlCents)}$markWarning",
            ticker = ticker,
            position = if (snapshot.positionSats > 0L)
                "Position: ${String.format(Locale.US, "%.8f", snapshot.positionSats / 100_000_000.0)} BTC PAPER"
                else "Position: NONE",
            lastTrade = lastTrade,
            signal = signal,
            health = health,
        )
    }
}

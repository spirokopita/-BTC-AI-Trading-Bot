package com.btcaud.paper.widgets

import com.btcaud.paper.core.MonitorSnapshot
import com.btcaud.paper.core.PaperAccount
import com.btcaud.paper.core.PaperTradeEvent
import org.junit.Assert.*
import org.junit.Test

/** Deterministic presenter tests; no exchange requests or financial claims. */
class DashboardWidgetPresentationTest {
    private val now = 1_800_000_000_000L
    private fun snapshot(
        enabled: Boolean = false,
        success: Long? = null,
        tickerMs: Long? = null,
        tickerCents: Long? = null,
        error: String? = null,
        trading: Boolean = false,
        position: Long = 0L,
        cash: Long = 100_000L,
        trades: List<PaperTradeEvent> = emptyList(),
    ) = MonitorSnapshot(
        enabled = enabled,
        lastSuccessMillis = success,
        lastAttemptMillis = success,
        lastCandleEpochSeconds = null,
        latestCloseAudCents = null,
        lastError = error,
        account = PaperAccount(cashCents = cash),
        tradingEnabled = trading,
        positionSats = position,
        latestTickerAudCents = tickerCents,
        latestTickerMillis = tickerMs,
        recentTrades = trades,
    )

    @Test fun pausedWithoutTickerIsNotLive() {
        val view = DashboardWidgetPresentation.from(snapshot(), now)
        assertTrue(view.title.contains("PAUSED"))
        assertEquals("BTC/AUD NO DATA", view.ticker)
        assertTrue(view.net.contains("A$0.00"))
        assertTrue(view.lastTrade.contains("NONE"))
        assertTrue(view.signal.contains("AI NOT TRAINED"))
    }

    @Test fun freshRunningTickerIsExplicitlyObserved() {
        val view = DashboardWidgetPresentation.from(
            snapshot(enabled = true, success = now - 60_000L,
                tickerMs = now - 30_000L, tickerCents = 11_000_000L, trading = true), now)
        assertTrue(view.ticker.contains("A$110,000.00"))
        assertTrue(view.ticker.contains("OBSERVED"))
        assertFalse(view.ticker.contains("STALE"))
        assertTrue(view.signal.contains("SMA"))
        assertTrue(view.health.contains("RUNNING"))
    }

    @Test fun tickerAgeOverridesRecentSuccessfulPoll() {
        val view = DashboardWidgetPresentation.from(
            snapshot(enabled = true, success = now - 60_000L,
                tickerMs = now - 46L * 60_000L, tickerCents = 11_000_000L), now)
        assertTrue(view.ticker.contains("STALE"))
        assertTrue(view.health.contains("RUNNING"))
    }

    @Test fun pausedCacheNeverLooksCurrent() {
        val view = DashboardWidgetPresentation.from(
            snapshot(tickerMs = now - 10_000L, tickerCents = 11_000_000L,
                trading = true), now)
        assertTrue(view.ticker.contains("STALE"))
        assertTrue(view.signal.contains("PAUSED"))
    }

    @Test fun feedErrorMarksCachedTickerStale() {
        val view = DashboardWidgetPresentation.from(
            snapshot(enabled = true, success = now - 60_000L,
                tickerMs = now - 10_000L, tickerCents = 11_000_000L,
                error = "timeout", trading = true), now)
        assertTrue(view.health.contains("STALE"))
        assertTrue(view.health.contains("FEED ERROR"))
        assertTrue(view.ticker.contains("STALE"))
        assertTrue(view.signal.contains("WAITING FOR FEED"))
    }

    @Test fun suspendedStateAndOpenPositionWarnOfStaleValuation() {
        val view = DashboardWidgetPresentation.from(
            snapshot(enabled = true, success = now - 3L * 60L * 60_000L,
                tickerMs = now - 3L * 60L * 60_000L, tickerCents = 10_000_000L,
                position = 1_000_000L, cash = 0L, trading = true), now)
        assertTrue(view.health.contains("SUSPENDED"))
        assertTrue(view.equity.contains("STALE MARK"))
        assertTrue(view.net.contains("STALE MARK"))
        assertTrue(view.position.contains("0.01000000 BTC PAPER"))
        assertTrue(view.net.contains("-A$"))
    }

    @Test fun losingRealisedPaperTradeIsShownAsLoss() {
        val trade = PaperTradeEvent("SELL", now - 60_000L, 10_000_000L,
            100_000L, 250L, -725L, "paper stop")
        val view = DashboardWidgetPresentation.from(
            snapshot(trades = listOf(trade)), now)
        assertTrue(view.lastTrade.contains("SELL"))
        assertTrue(view.lastTrade.contains("costs A$2.50"))
        assertTrue(view.lastTrade.contains("realised NET -A$7.25"))
    }

    @Test fun futureDatedTickerIsNeverFresh() {
        val view = DashboardWidgetPresentation.from(
            snapshot(enabled = true, success = now - 10_000L,
                tickerMs = now + 60_000L, tickerCents = 11_000_000L), now)
        assertTrue(view.ticker.contains("STALE"))
        assertTrue(view.ticker.contains("clock mismatch"))
    }
}

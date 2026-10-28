package com.btcaud.paper.notifications

import android.app.Notification
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.btcaud.paper.core.MonitorSnapshot
import com.btcaud.paper.core.PaperAccount
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith

/** Notification contract tests: no network, permissions or real orders required. */
@RunWith(AndroidJUnit4::class)
class StatusNotificationInstrumentedTest {
    private val context get() = InstrumentationRegistry.getInstrumentation().targetContext
    private val nowMs = 1_800_000_000_000L

    private fun snapshot(
        enabled: Boolean,
        success: Long?,
        tickerTime: Long?,
        tickerCents: Long? = 11_000_000L,
    ) = MonitorSnapshot(
        enabled = enabled,
        lastSuccessMillis = success,
        lastAttemptMillis = success,
        lastCandleEpochSeconds = null,
        latestCloseAudCents = null,
        lastError = null,
        account = PaperAccount(),
        latestTickerAudCents = tickerCents,
        latestTickerMillis = tickerTime,
    )

    @Test fun runningNotificationShowsFreshObservedPriceAndPauseAction() {
        val notification = StatusNotification.buildNotification(
            context, snapshot(true, nowMs - 60_000L, nowMs - 60_000L), nowMs
        )
        assertTrue(notification.flags and Notification.FLAG_ONGOING_EVENT != 0)
        assertEquals("Pause", notification.actions.single().title.toString())
        assertTrue(notification.extras.getCharSequence(Notification.EXTRA_TITLE).toString()
            .contains("RUNNING"))
        val body = notification.extras.getCharSequence(Notification.EXTRA_TEXT).toString()
        assertTrue(body.contains("Last poll:"))
        assertTrue(body.contains("A$110,000.00 (observed)"))
        assertFalse(body.contains("(STALE)"))
    }

    @Test fun pausedNotificationOffersResumeAndMarksCachedPriceStale() {
        val notification = StatusNotification.buildNotification(
            context, snapshot(false, nowMs - 60_000L, nowMs - 60_000L), nowMs
        )
        assertEquals(0, notification.flags and Notification.FLAG_ONGOING_EVENT)
        assertEquals("Resume", notification.actions.single().title.toString())
        assertTrue(notification.extras.getCharSequence(Notification.EXTRA_TITLE).toString()
            .contains("PAUSED"))
        assertTrue(notification.extras.getCharSequence(Notification.EXTRA_TEXT).toString()
            .contains("(STALE)"))
    }

    @Test fun staleAndSuspendedStatesNeverLabelOldPriceFresh() {
        for (ageMs in listOf(60L * 60_000L, 3L * 60L * 60_000L)) {
            val notification = StatusNotification.buildNotification(
                context, snapshot(true, nowMs - ageMs, nowMs - ageMs), nowMs
            )
            assertTrue(notification.flags and Notification.FLAG_ONGOING_EVENT != 0)
            assertEquals("Pause", notification.actions.single().title.toString())
            assertTrue(notification.extras.getCharSequence(Notification.EXTRA_TEXT).toString()
                .contains("(STALE)"))
        }
    }

    @Test fun missingTickerIsExplicitlyNoData() {
        val notification = StatusNotification.buildNotification(
            context, snapshot(true, null, null, null), nowMs
        )
        assertTrue(notification.extras.getCharSequence(Notification.EXTRA_TEXT).toString()
            .contains("NO DATA"))
        assertTrue(notification.extras.getCharSequence(Notification.EXTRA_TITLE).toString()
            .contains("WAITING"))
    }
}

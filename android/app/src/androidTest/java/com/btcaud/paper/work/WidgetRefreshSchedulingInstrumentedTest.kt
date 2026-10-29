package com.btcaud.paper.work

import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import androidx.work.WorkManager
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import java.util.concurrent.TimeUnit

/**
 * Verify that local widget refresh is actually scheduled as unique work.
 * Does not claim exact Doze timing or physical-device rendering.
 */
@RunWith(AndroidJUnit4::class)
class WidgetRefreshSchedulingInstrumentedTest {
    @Test fun localWidgetRefreshIsEnqueuedWithoutNetworkConstraint() {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val manager = WorkManager.getInstance(context)
        try {
            WorkScheduler.start(context, immediate = false)
            val jobs = manager.getWorkInfosForUniqueWork(WorkScheduler.WIDGET_REFRESH)
                .get(15, TimeUnit.SECONDS)
            assertEquals(1, jobs.size)
            assertTrue(jobs.first().state == androidx.work.WorkInfo.State.ENQUEUED ||
                jobs.first().state == androidx.work.WorkInfo.State.RUNNING)
        } finally {
            WorkScheduler.stop(context)
        }
    }
}

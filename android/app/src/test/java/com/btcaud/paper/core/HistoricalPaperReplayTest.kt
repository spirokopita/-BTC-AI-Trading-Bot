package com.btcaud.paper.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class HistoricalPaperReplayTest {
    private fun flat(n: Int) = List(n) { i ->
        HistoricalPaperReplay.Bar(1_800_000_000L + i * 14_400L,
            15_000_000L, 15_050_000L, 14_950_000L, 15_000_000L)
    }

    @Test fun emptyInputIsNotMarketProfit() {
        val r = HistoricalPaperReplay.run(emptyList())
        assertEquals(100_000L, r.endingEquityCents)
        assertTrue(r.warning.contains("minimum"))
    }

    @Test fun flatMarketHasNoManufacturedProfitOrTrades() {
        val r = HistoricalPaperReplay.run(flat(90))
        assertEquals(0, r.buys)
        assertEquals(0, r.sells)
        assertEquals(100_000L, r.endingEquityCents)
        assertEquals(0L, r.netReturnBps)
    }

    @Test fun gapsAreRejectedWithoutBackfillingPrices() {
        val bars = flat(80).toMutableList()
        bars.removeAt(30)
        val r = HistoricalPaperReplay.run(bars)
        assertEquals(0, r.buys)
        assertTrue(r.warning.contains("INVALID"))
    }

    @Test fun signalOnLastBarCannotExecuteWithoutNextOpen() {
        val original = flat(80)
        val edited = original.mapIndexed { i, b ->
            if (i == 79) b.copy(closeCents = 15_150_000L,
                highCents = 15_200_000L) else b
        }
        val r = HistoricalPaperReplay.run(edited)
        assertEquals(0, r.buys)
        assertEquals(0L, r.netReturnBps)
    }

    @Test fun newCrossoverCanExecuteOnlyOnFollowingBar() {
        val bars = flat(80).mapIndexed { i, b ->
            if (i == 26) b.copy(closeCents = 15_150_000L,
                highCents = 15_200_000L)
            else if (i > 26) b.copy(openCents = 15_150_000L,
                highCents = 15_200_000L, lowCents = 15_100_000L,
                closeCents = 15_150_000L)
            else b
        }
        val r = HistoricalPaperReplay.run(bars)
        assertTrue(r.buys > 0)
        assertTrue(r.endingEquityCents <= 100_000L) // flat after entry, friction costs
        assertTrue(r.warning.contains("TOO LITTLE"))
    }
}

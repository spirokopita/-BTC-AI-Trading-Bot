package com.btcaud.paper.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class PaperDecisionEngineTest {
    private fun bars(values: List<Long>) = values.mapIndexed { i, cents ->
        PaperDecisionEngine.Bar(14_400L * (100L + i), cents)
    }

    @Test fun noHistoryMeansHold() {
        val result = PaperDecisionEngine.evaluate(bars(listOf(1_000L)), 0L, 0L, 1_000L)
        assertEquals(PaperDecisionEngine.Action.HOLD, result.action)
    }

    @Test fun missingCandleMeansHold() {
        val data = bars(List(21) { 1000L }).toMutableList()
        data[12] = data[12].copy(startS = data[12].startS + 42L)
        val result = PaperDecisionEngine.evaluate(data, 0L, 0L, 1000L)
        assertEquals(PaperDecisionEngine.Action.HOLD, result.action)
    }

    @Test fun bullishCrossoverGivesBuySignal() {
        val values = List(20) { 1000L } + listOf(1300L)
        val result = PaperDecisionEngine.evaluate(bars(values), 0L, 0L, 1300L)
        assertEquals(PaperDecisionEngine.Action.BUY, result.action)
    }

    @Test fun sellStopUsesObservedPriceNotOldCandleClose() {
        val values = List(21) { 1000L }
        val result = PaperDecisionEngine.evaluate(bars(values), 5000L, 1000L, 960L)
        assertEquals(PaperDecisionEngine.Action.SELL, result.action)
    }

    @Test fun sizingReservesTradingCostsAndLimitsRisk() {
        val priceCents = 15_000_000L
        val qty = PaperDecisionEngine.buyQuantitySats(100_000L, priceCents)
        assertTrue(qty > 0)
        val fill = PaperDecisionEngine.fill(PaperFill.Side.BUY, qty, priceCents)
        assertTrue(fill.grossCents + fill.costsCents <= 10_000L)
        assertTrue(fill.grossCents + fill.costsCents >= 9_900L)
        val paper = PaperLedger(100_000L).buy(fill)
        assertTrue(paper.btcSats > 0L)
        assertTrue(paper.cashCents >= 90_000L)
    }

    @Test fun conservativeKrakenTierOneTakerFee() {
        assertEquals(80, PaperDecisionEngine.FEE_BPS)
        assertEquals(90, PaperDecisionEngine.COST_BPS)
    }

    @Test fun paperSizingNeverExceedsAud100EvenAfterRefills() {
        for (price in listOf(1_000_000L, 15_000_000L, 110_000_000L, 123_456_789L)) {
            for (cash in listOf(1_000L, 10_000L, 100_000L, 200_000L, 10_000_000L)) {
                val qty = PaperDecisionEngine.buyQuantitySats(cash, price)
                if (qty == 0L) continue
                val fill = PaperDecisionEngine.fill(PaperFill.Side.BUY, qty, price)
                val debit = fill.grossCents + fill.costsCents
                assertTrue("A$100 hard cap", debit <= 10_000L)
                assertTrue("10% available cash", debit <= cash / 10L)
            }
        }
        assertEquals(0L, PaperDecisionEngine.buyQuantitySats(0L, price))
        assertEquals(0L, PaperDecisionEngine.buyQuantitySats(100_000L, 0L))
    }

    @Test fun simulatedBuySellNetMatchesLedger() {
        val qty = 30_000L
        val buy = PaperDecisionEngine.fill(PaperFill.Side.BUY, qty, 15_000_000L)
        val sell = PaperDecisionEngine.fill(PaperFill.Side.SELL, qty, 16_000_000L)
        val entered = PaperLedger(100_000L).buy(buy)
        val exited = entered.sell(sell)
        assertEquals(exited.cashCents - 100_000L, ClosedPaperTrade(buy, sell).netPnlCents)
    }
}

package com.btcaud.paper.core

/** Pure paper-only accounting. No networking, exchange credentials, or order submission. */
data class PaperFill(val side: Side, val quantitySats: Long, val priceAudCentsPerBtc: Long,
                     val feeBps: Int, val spreadBps: Int, val slippageBps: Int) {
    init { require(quantitySats > 0 && priceAudCentsPerBtc > 0); require(feeBps in 0..10000 && spreadBps in 0..10000 && slippageBps in 0..10000) }
    enum class Side { BUY, SELL }
    private fun roundDiv(n: Long, d: Long): Long = Math.addExact(n, d / 2) / d
    val grossCents: Long get() = roundDiv(Math.multiplyExact(quantitySats, priceAudCentsPerBtc), 100_000_000L)
    fun basisPointsCost(bps: Int): Long = roundDiv(Math.multiplyExact(grossCents, bps.toLong()), 10_000L)
    val feeCents: Long get() = basisPointsCost(feeBps)
    val spreadCents: Long get() = basisPointsCost(spreadBps)
    val slippageCents: Long get() = basisPointsCost(slippageBps)
    val costsCents: Long get() = Math.addExact(Math.addExact(feeCents, spreadCents), slippageCents)
}

data class ClosedPaperTrade(val buy: PaperFill, val sell: PaperFill) {
    init { require(buy.side == PaperFill.Side.BUY && sell.side == PaperFill.Side.SELL); require(buy.quantitySats == sell.quantitySats) }
    val grossPnlCents: Long get() = Math.subtractExact(sell.grossCents, buy.grossCents)
    val feesCents: Long get() = Math.addExact(buy.feeCents, sell.feeCents)
    val spreadCents: Long get() = Math.addExact(buy.spreadCents, sell.spreadCents)
    val slippageCents: Long get() = Math.addExact(buy.slippageCents, sell.slippageCents)
    val totalCostsCents: Long get() = Math.addExact(Math.addExact(feesCents, spreadCents), slippageCents)
    val netPnlCents: Long get() = Math.subtractExact(grossPnlCents, totalCostsCents)
}

/** Deterministic single-position simulator. Cash never represents a real exchange balance. */
data class PaperLedger(val cashCents: Long, val btcSats: Long = 0L, val costBasisCents: Long = 0L) {
    init { require(cashCents >= 0 && btcSats >= 0 && costBasisCents >= 0) }
    fun buy(fill: PaperFill): PaperLedger {
        require(fill.side == PaperFill.Side.BUY && btcSats == 0L) { "One paper position only" }
        val debit = Math.addExact(fill.grossCents, fill.costsCents)
        require(cashCents >= debit) { "Insufficient simulated funds" }
        return PaperLedger(Math.subtractExact(cashCents, debit), fill.quantitySats, debit)
    }
    fun sell(fill: PaperFill): PaperLedger {
        require(fill.side == PaperFill.Side.SELL && btcSats == fill.quantitySats && btcSats > 0L)
        val credit = Math.subtractExact(fill.grossCents, fill.costsCents)
        require(credit >= 0L)
        return PaperLedger(Math.addExact(cashCents, credit))
    }
}

package com.btcaud.paper.core

/**
 * V16 deterministic baseline, NOT machine learning. Completed 4-hour candles only.
 * A signal is assessed after a candle closes; execution uses a separately observed
 * live public ticker price. No exchange account, broker API or private orders.
 */
object PaperDecisionEngine {
    const val INTERVAL_SECONDS = 14_400L
    const val FEE_BPS = 16
    const val SPREAD_BPS = 5
    const val SLIPPAGE_BPS = 5
    const val COST_BPS = FEE_BPS + SPREAD_BPS + SLIPPAGE_BPS
    const val MIN_HISTORY = 21

    enum class Action { BUY, SELL, HOLD }
    data class Bar(val startS: Long, val closeCents: Long)
    data class Decision(val action: Action, val reason: String)

    fun evaluate(
        bars: List<Bar>, positionSats: Long, entryPriceCents: Long,
        observedPriceCents: Long,
    ): Decision {
        if (observedPriceCents <= 0L) return Decision(Action.HOLD, "NO_VALID_TICKER")
        if (positionSats > 0L && entryPriceCents > 0L) {
            // Poll-level protective exits; not instant exchange stop orders.
            if (observedPriceCents.toDouble() <= entryPriceCents * 0.97)
                return Decision(Action.SELL, "3% observed-price stop")
            if (observedPriceCents.toDouble() >= entryPriceCents * 1.06)
                return Decision(Action.SELL, "6% observed-price target")
        }
        if (bars.size < MIN_HISTORY) return Decision(Action.HOLD, "WARMUP: 21 completed candles required")
        val tail = bars.takeLast(MIN_HISTORY)
        if (tail.any { it.startS <= 0L || it.closeCents <= 0L } ||
            tail.zipWithNext().any { (a, b) -> b.startS - a.startS != INTERVAL_SECONDS })
            return Decision(Action.HOLD, "DATA_GAP: new signals blocked")
        val closes = tail.map { it.closeCents.toDouble() }
        val previousFast = closes.subList(10, 20).average()
        val previousSlow = closes.subList(0, 20).average()
        val fast = closes.subList(11, 21).average()
        val slow = closes.subList(1, 21).average()
        if (positionSats > 0L) {
            if (previousFast >= previousSlow && fast < slow)
                return Decision(Action.SELL, "SMA10 crossed below SMA20")
            return Decision(Action.HOLD, "Position open; no exit signal")
        }
        if (previousFast <= previousSlow && fast > slow)
            return Decision(Action.BUY, "SMA10 crossed above SMA20")
        return Decision(Action.HOLD, "No bullish SMA10/SMA20 crossover")
    }

    /** Risk budget min(5% of cash, A$50), including estimated entry costs. */
    fun buyQuantitySats(cashCents: Long, priceCents: Long): Long {
        if (cashCents <= 0L || priceCents <= 0L) return 0L
        val budget = minOf(cashCents / 20L, 5_000L)
        if (budget < 100L) return 0L
        return Math.multiplyExact(Math.multiplyExact(budget, 100_000_000L), 10_000L) /
            Math.multiplyExact(priceCents, 10_000L + COST_BPS)
    }

    fun fill(side: PaperFill.Side, sats: Long, priceCents: Long) =
        PaperFill(side, sats, priceCents, FEE_BPS, SPREAD_BPS, SLIPPAGE_BPS)
}

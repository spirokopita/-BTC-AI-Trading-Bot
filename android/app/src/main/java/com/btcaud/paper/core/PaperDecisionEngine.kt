package com.btcaud.paper.core

/**
 * V16 baseline paper-only strategy. This is a transparent rules engine, NOT trained AI.
 * Consume only completed, contiguous 4-hour candles; one new candle = at most one decision.
 * It cannot access wallets, exchange credentials, or exchange order endpoints.
 */
object PaperDecisionEngine {
    const val INTERVAL_SECONDS = 14_400L
    const val COST_BPS = 26 // 16 fee + 5 spread + 5 slippage, per side (simulated)
    const val FEE_BPS = 16
    const val SPREAD_BPS = 5
    const val SLIPPAGE_BPS = 5
    const val MIN_HISTORY = 21

    enum class Action { BUY, SELL, HOLD }
    data class Bar(val startS: Long, val closeCents: Long)
    data class Decision(val action: Action, val reason: String)

    /** Crossover of previous/current 10-bar and 20-bar SMA, with position protection. */
    fun evaluate(bars: List<Bar>, positionSats: Long, entryPriceCents: Long): Decision {
        if (bars.size < MIN_HISTORY) return Decision(Action.HOLD, "WARMUP: need 21 completed bars")
        val tail = bars.takeLast(MIN_HISTORY)
        if (tail.any { it.closeCents <= 0L } ||
            tail.zipWithNext().any { (a, b) -> b.startS - a.startS != INTERVAL_SECONDS }) {
            return Decision(Action.HOLD, "DATA_GAP: trading blocked")
        }
        val latest = tail.last().closeCents
        val closes = tail.map { it.closeCents.toDouble() }
        val previousFast = closes.subList(10, 20).average()
        val previousSlow = closes.subList(0, 20).average()
        val fast = closes.subList(11, 21).average()
        val slow = closes.subList(1, 21).average()
        if (positionSats > 0L) {
            if (entryPriceCents <= 0L) return Decision(Action.HOLD, "INVALID_BASIS")
            // Close-only exits: these are not intrabar stop orders and can gap.
            if (latest <= entryPriceCents * 0.97) return Decision(Action.SELL, "3% close-price stop")
            if (latest >= entryPriceCents * 1.06) return Decision(Action.SELL, "6% close-price target")
            if (previousFast >= previousSlow && fast < slow) return Decision(Action.SELL, "SMA10 crossed below SMA20")
            return Decision(Action.HOLD, "Position open; no close-price exit")
        }
        if (previousFast <= previousSlow && fast > slow) return Decision(Action.BUY, "SMA10 crossed above SMA20")
        return Decision(Action.HOLD, "No confirmed SMA10/SMA20 bullish crossover")
    }

    /** At most 5% of cash and A$50, reserves a full side of simulated costs. */
    fun buyQuantitySats(cashCents: Long, priceCents: Long): Long {
        if (cashCents <= 0L || priceCents <= 0L) return 0L
        val budget = minOf(cashCents / 20L, 5_000L)
        if (budget < 100L) return 0L
        return (budget * 100_000_000L * 10_000L) /
            (priceCents * (10_000L + COST_BPS))
    }

    fun fill(side: PaperFill.Side, quantitySats: Long, priceCents: Long) =
        PaperFill(side, quantitySats, priceCents, FEE_BPS, SPREAD_BPS, SLIPPAGE_BPS)
}

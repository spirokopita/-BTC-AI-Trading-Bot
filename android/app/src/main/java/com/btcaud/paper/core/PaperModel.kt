package com.btcaud.paper.core

/** All money is integer Australian cents; no real wallet can be accessed. */
data class PaperAccount(
    val cashCents: Long = 100_000L,
    val cumulativeFundingCents: Long = 100_000L,
    val refillCount: Int = 0,
    val resetCount: Int = 0,
) {
    init {
        require(cashCents >= 0L && cumulativeFundingCents >= 0L)
        require(refillCount >= 0 && resetCount >= 0)
    }
    /** Legacy cash-only profit for compatibility; use MonitorSnapshot.netPnlCents for holdings. */
    val netPnlCents: Long get() = Math.subtractExact(cashCents, cumulativeFundingCents)
    fun refill(amountCents: Long = 100_000L): PaperAccount {
        require(amountCents in 1L..100_000_000L)
        return copy(cashCents = Math.addExact(cashCents, amountCents),
            cumulativeFundingCents = Math.addExact(cumulativeFundingCents, amountCents),
            refillCount = Math.addExact(refillCount, 1))
    }
    fun reset(): PaperAccount = PaperAccount(resetCount = Math.addExact(resetCount, 1))
}

enum class MonitoringStatus { PAUSED, WAITING, RUNNING, STALE, SUSPENDED }

object MonitorPolicy {
    const val FRESH_MILLIS = 45L * 60_000L
    const val SUSPENDED_MILLIS = 2L * 60L * 60_000L
    const val CANDLE_INTERVAL_SECONDS = 4L * 60L * 60L

    fun status(enabled: Boolean, lastSuccessMillis: Long?, nowMillis: Long): MonitoringStatus {
        if (!enabled) return MonitoringStatus.PAUSED
        if (lastSuccessMillis == null || lastSuccessMillis <= 0L) return MonitoringStatus.WAITING
        val age = nowMillis - lastSuccessMillis
        if (age < 0L) return MonitoringStatus.STALE
        return when {
            age <= FRESH_MILLIS -> MonitoringStatus.RUNNING
            age <= SUSPENDED_MILLIS -> MonitoringStatus.STALE
            else -> MonitoringStatus.SUSPENDED
        }
    }

    fun isCompletedCandle(startEpochSeconds: Long, nowEpochSeconds: Long): Boolean =
        startEpochSeconds > 0L && startEpochSeconds % CANDLE_INTERVAL_SECONDS == 0L &&
            nowEpochSeconds >= startEpochSeconds &&
            nowEpochSeconds - startEpochSeconds >= CANDLE_INTERVAL_SECONDS
}

data class PaperTradeEvent(
    val side: String,
    val observedMs: Long,
    val priceCents: Long,
    val quantitySats: Long,
    val costsCents: Long,
    val realisedNetCents: Long?,
    val reason: String,
    /** Gross execution notional, NOT gross P&L. */
    val grossCents: Long,
    /** Signed account movement: BUY negative, SELL positive; NOT trading profit. */
    val netCashFlowCents: Long,
)

/** P&L includes estimated exit friction when BTC is open, using the last OBSERVED price. */
data class MonitorSnapshot(
    val enabled: Boolean,
    val lastSuccessMillis: Long?,
    val lastAttemptMillis: Long?,
    val lastCandleEpochSeconds: Long?,
    val latestCloseAudCents: Long?,
    val lastError: String?,
    val account: PaperAccount,
    val tradingEnabled: Boolean = false,
    val positionSats: Long = 0L,
    val entryPriceCents: Long = 0L,
    val positionBasisCents: Long = 0L,
    val latestTickerAudCents: Long? = null,
    val latestTickerMillis: Long? = null,
    val lastDecision: String = "NOT_ARMED",
    val lastDecisionReason: String = "Paper strategy is off",
    val realisedNetCents: Long = 0L,
    val recentTrades: List<PaperTradeEvent> = emptyList(),
    val latestNewsSeenMillis: Long? = null,
    val newsWarning: String? = null,
    val latestNews: List<NewsObservation> = emptyList(),
) {
    fun status(nowMillis: Long): MonitoringStatus =
        if (enabled && lastError != null) MonitoringStatus.STALE
        else MonitorPolicy.status(enabled, lastSuccessMillis, nowMillis)

    val estimatedLiquidationCents: Long get() {
        val mark = latestTickerAudCents ?: latestCloseAudCents
        if (positionSats == 0L || mark == null || mark <= 0L) return 0L
        val hypotheticalSale = PaperDecisionEngine.fill(PaperFill.Side.SELL, positionSats, mark)
        return maxOf(0L, hypotheticalSale.grossCents - hypotheticalSale.costsCents)
    }
    val estimatedEquityCents: Long get() = Math.addExact(account.cashCents, estimatedLiquidationCents)
    val netPnlCents: Long get() = Math.subtractExact(estimatedEquityCents, account.cumulativeFundingCents)
}

package com.btcaud.paper.core

/** All money is integral AUD cents. No floating-point cash, no real wallet integration. */
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
    /** V13 does not hold BTC; when positions are ported, add net liquidation value here. */
    val netPnlCents: Long get() = Math.subtractExact(cashCents, cumulativeFundingCents)

    fun refill(amountCents: Long = 100_000L): PaperAccount {
        require(amountCents in 1L..100_000_000L) { "Invalid simulated refill" }
        return copy(
            cashCents = Math.addExact(cashCents, amountCents),
            cumulativeFundingCents = Math.addExact(cumulativeFundingCents, amountCents),
            refillCount = Math.addExact(refillCount, 1),
        )
    }

    /** Resets the *simulated* account, never market history or the append-only audit. */
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
        if (age < 0L) return MonitoringStatus.STALE // invalid/future clock, never imply healthy
        return when {
            age <= FRESH_MILLIS -> MonitoringStatus.RUNNING
            age <= SUSPENDED_MILLIS -> MonitoringStatus.STALE
            else -> MonitoringStatus.SUSPENDED
        }
    }

    /** Kraken's last OHLC row may still be forming. Only store a *finished* bar. */
    fun isCompletedCandle(startEpochSeconds: Long, nowEpochSeconds: Long): Boolean =
        startEpochSeconds > 0L && startEpochSeconds % CANDLE_INTERVAL_SECONDS == 0L &&
            nowEpochSeconds >= startEpochSeconds &&
            nowEpochSeconds - startEpochSeconds >= CANDLE_INTERVAL_SECONDS
}

/** Values used by UI/widgets. Price and profit are never fabricated from missing data. */
data class MonitorSnapshot(
    val enabled: Boolean,
    val lastSuccessMillis: Long?,
    val lastAttemptMillis: Long?,
    val lastCandleEpochSeconds: Long?,
    val latestCloseAudCents: Long?,
    val lastError: String?,
    val account: PaperAccount,
) {
    fun status(nowMillis: Long): MonitoringStatus =
        if (enabled && lastError != null) MonitoringStatus.STALE
        else MonitorPolicy.status(enabled, lastSuccessMillis, nowMillis)
}

package com.btcaud.paper.core

/**
 * Offline-only causal 4h research replay. Never touches the persisted account.
 * A decision from a COMPLETED candle can execute only at the NEXT candle open.
 * Intrabar protective stops assume the stop wins if stop and target both hit.
 * Historical fills are approximations, not exchange execution proof.
 */
object HistoricalPaperReplay {
    data class Bar(
        val startS: Long,
        val openCents: Long,
        val highCents: Long,
        val lowCents: Long,
        val closeCents: Long,
    )
    data class Report(
        val bars: Int,
        val buys: Int,
        val sells: Int,
        val netReturnBps: Long,
        val maxDrawdownBps: Long,
        val endingEquityCents: Long,
        val warning: String,
    )

    fun run(bars: List<Bar>, initialCents: Long = 100_000L): Report {
        require(initialCents >= 10_000L)
        if (bars.size < 65) return Report(bars.size, 0, 0, 0, 0, initialCents,
            "Only " + bars.size + " bars: minimum 65 for a useful baseline")
        val contiguous = bars.zipWithNext().all { (a, b) ->
            b.startS - a.startS == PaperDecisionEngine.INTERVAL_SECONDS
        }
        val valid = bars.all { b ->
            b.startS > 0L && b.startS % PaperDecisionEngine.INTERVAL_SECONDS == 0L &&
                b.lowCents > 0L && b.lowCents <= minOf(b.openCents, b.closeCents) &&
                b.highCents >= maxOf(b.openCents, b.closeCents)
        }
        if (!contiguous || !valid) return Report(bars.size, 0, 0, 0, 0,
            initialCents, "INVALID / MISSING MARKET BARS: replay refused")

        var ledger = PaperLedger(initialCents)
        var entryPrice = 0L
        var pending = PaperDecisionEngine.Action.HOLD
        var buys = 0
        var sells = 0
        var peak = initialCents
        var maxDrawdownBps = 0L

        fun closeAt(price: Long) {
            if (ledger.btcSats == 0L) return
            ledger = ledger.sell(PaperDecisionEngine.fill(PaperFill.Side.SELL,
                ledger.btcSats, price))
            entryPrice = 0L
            sells++
        }

        for (i in 21 until bars.size) {
            val current = bars[i]
            // Only the previous completed candle can place this queued order.
            if (pending == PaperDecisionEngine.Action.SELL && ledger.btcSats > 0L)
                closeAt(current.openCents)
            if (pending == PaperDecisionEngine.Action.BUY && ledger.btcSats == 0L) {
                val qty = PaperDecisionEngine.buyQuantitySats(ledger.cashCents, current.openCents)
                if (qty > 0L) {
                    ledger = ledger.buy(PaperDecisionEngine.fill(PaperFill.Side.BUY,
                        qty, current.openCents))
                    entryPrice = current.openCents
                    buys++
                }
            }
            pending = PaperDecisionEngine.Action.HOLD

            if (ledger.btcSats > 0L) {
                val stop = (entryPrice * 97L) / 100L
                val target = (entryPrice * 106L) / 100L
                // Opening gap first; if both intrabar hit, treat stop as first.
                when {
                    current.openCents <= stop -> closeAt(current.openCents)
                    current.openCents >= target -> closeAt(current.openCents)
                    current.lowCents <= stop -> closeAt(stop)
                    current.highCents >= target -> closeAt(target)
                }
            }

            // Causal signal evaluated only after this bar finishes.
            val tail = bars.subList(i - 20, i + 1).map {
                PaperDecisionEngine.Bar(it.startS, it.closeCents)
            }
            pending = PaperDecisionEngine.evaluate(tail, ledger.btcSats, entryPrice,
                current.closeCents).action
            val netValue = if (ledger.btcSats == 0L) ledger.cashCents else {
                val exit = PaperDecisionEngine.fill(PaperFill.Side.SELL,
                    ledger.btcSats, current.closeCents)
                ledger.cashCents + maxOf(0L, exit.grossCents - exit.costsCents)
            }
            peak = maxOf(peak, netValue)
            val dd = ((netValue - peak) * 10_000L) / peak
            maxDrawdownBps = minOf(maxDrawdownBps, dd)
        }
        val last = bars.last().closeCents
        val equity = if (ledger.btcSats == 0L) ledger.cashCents else {
            val exit = PaperDecisionEngine.fill(PaperFill.Side.SELL, ledger.btcSats, last)
            ledger.cashCents + maxOf(0L, exit.grossCents - exit.costsCents)
        }
        return Report(bars.size, buys, sells,
            (equity - initialCents) * 10_000L / initialCents,
            maxDrawdownBps, equity,
            if (bars.size < 1_000) "TOO LITTLE HISTORY FOR AI TRAINING OR STRATEGY PROMOTION"
            else "Historical replay only; require held-out tests and forward paper trading")
    }
}

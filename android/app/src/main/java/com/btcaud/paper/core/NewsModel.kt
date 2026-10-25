package com.btcaud.paper.core

/** Read-only news observations. These are NEVER direct trade instructions. */
data class NewsObservation(
    val source: String,
    val headline: String,
    val url: String,
    val publishedMs: Long?,
    val firstSeenMs: Long,
    val topic: String,
)

/** Descriptive tags only; this is NOT sentiment prediction or learned intelligence. */
object NewsTopic {
    fun classify(headline: String): String {
        val text = headline.lowercase()
        return when {
            listOf("bitcoin", "btc", "satoshi", "lightning network").any(text::contains) -> "BITCOIN"
            listOf("federal reserve", "interest rate", "inflation", "cpi", "jobs report",
                "central bank", "recession", "bond yields").any(text::contains) -> "MACRO"
            listOf("sec ", "regulation", "regulator", "lawsuit", "legislation", "etf approval",
                "compliance", "crypto ban").any(text::contains) -> "REGULATION"
            listOf("crypto", "stablecoin", "exchange", "blockchain", "ethereum").any(text::contains) -> "CRYPTO"
            else -> "OTHER"
        }
    }
}

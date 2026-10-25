package com.btcaud.paper.network

import com.btcaud.paper.data.PaperDatabase
import org.json.JSONObject
import java.math.BigDecimal
import java.math.RoundingMode
import java.net.HttpURLConnection
import java.net.URL

/** Public, no-key Kraken 4h OHLC. No private API, trading, wallet or withdrawals. */
object KrakenPublicFeed {
    private const val ENDPOINT = "https://api.kraken.com/0/public/OHLC?pair=XBTAUD&interval=240"

    fun fetchCompleted(nowMs: Long): List<PaperDatabase.Candle> {
        val conn = (URL(ENDPOINT).openConnection() as HttpURLConnection).apply {
            requestMethod = "GET"; connectTimeout = 10_000; readTimeout = 15_000
            setRequestProperty("Accept", "application/json")
            setRequestProperty("User-Agent", "BTCAUDPaper/16 (read-only public market observations)")
        }
        try {
            require(conn.responseCode == 200) { "Kraken HTTP ${conn.responseCode}" }
            val json = conn.inputStream.bufferedReader().use { reader ->
                JSONObject(reader.readText().take(2_000_000))
            }
            val errors = json.getJSONArray("error")
            require(errors.length() == 0) { "Kraken returned an API error" }
            val result = json.getJSONObject("result")
            val key = result.keys().asSequence().firstOrNull { it != "last" }
                ?: error("No OHLC series returned")
            val rows = result.getJSONArray(key)
            val nowS = nowMs / 1_000L
            val completed = mutableListOf<PaperDatabase.Candle>()
            for (i in 0 until rows.length()) {
                val r = rows.getJSONArray(i)
                val start = r.getLong(0)
                if (nowS - start < 14_400L) continue // never use the forming candle
                fun cents(index: Int): Long = BigDecimal(r.getString(index))
                    .multiply(BigDecimal(100)).setScale(0, RoundingMode.HALF_UP).longValueExact()
                completed += PaperDatabase.Candle(start, cents(1), cents(2), cents(3), cents(4))
            }
            // Kraken limits recent OHLC history; enough bars to warm up the 21-bar V16 signal.
            return completed.takeLast(250).also { require(it.isNotEmpty()) { "No completed Kraken candles" } }
        } finally { conn.disconnect() }
    }

    /** Price observed when polling, not a historical candle's future execution price. */
    fun fetchObservedTickerCents(): Long {
        val conn = (URL("https://api.kraken.com/0/public/Ticker?pair=XBTAUD")
            .openConnection() as HttpURLConnection).apply {
            requestMethod = "GET"
            connectTimeout = 10_000
            readTimeout = 15_000
            setRequestProperty("Accept", "application/json")
            setRequestProperty("User-Agent", "BTCAUDPaper/16 (public data only)")
        }
        try {
            require(conn.responseCode == 200) { "Kraken ticker HTTP " + conn.responseCode }
            val body = conn.inputStream.bufferedReader().use { it.readText().take(500_000) }
            val json = JSONObject(body)
            require(json.getJSONArray("error").length() == 0) { "Kraken ticker API error" }
            val result = json.getJSONObject("result")
            val key = result.keys().asSequence().firstOrNull() ?: error("No ticker result")
            val raw = result.getJSONObject(key).getJSONArray("c").getString(0)
            return BigDecimal(raw).multiply(BigDecimal(100))
                .setScale(0, RoundingMode.HALF_UP).longValueExact().also {
                    require(it > 0L) { "Ticker must be positive" }
                }
        } finally {
            conn.disconnect()
        }
    }
}

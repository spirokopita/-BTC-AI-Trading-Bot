package com.btcaud.paper.network

import com.btcaud.paper.core.MonitorPolicy
import com.btcaud.paper.data.PaperDatabase
import org.json.JSONObject
import java.math.BigDecimal
import java.math.RoundingMode
import java.net.HttpURLConnection
import java.net.URL

/** Read-only Kraken BTC/AUD source. Parser is shared by the worker and emulator tests. */
object KrakenPublicFeed {
    private const val BASE = "https://api.kraken.com/0/public/"
    private const val INTERVAL_S = MonitorPolicy.CANDLE_INTERVAL_SECONDS
    private const val MAX_AGE_S = 8L * 60L * 60L
    private val MARKET_KEYS = setOf("XBTAUD", "XXBTZAUD")

    private fun request(path: String, maxChars: Int): String {
        val conn = (URL(BASE + path).openConnection() as HttpURLConnection).apply {
            requestMethod = "GET"
            instanceFollowRedirects = false
            connectTimeout = 10_000
            readTimeout = 15_000
            setRequestProperty("Accept", "application/json")
            setRequestProperty("User-Agent", "BTCAUDPaper/19 (public observations only)")
        }
        try {
            require(conn.responseCode == 200) { "Kraken HTTP ${conn.responseCode}" }
            return conn.inputStream.bufferedReader(Charsets.UTF_8).use { reader ->
                val output = StringBuilder()
                val buffer = CharArray(8192)
                while (true) {
                    val n = reader.read(buffer)
                    if (n < 0) break
                    require(output.length + n <= maxChars) { "Oversized Kraken response" }
                    output.append(buffer, 0, n)
                }
                output.toString()
            }
        } finally { conn.disconnect() }
    }

    private fun marketResult(body: String, isOhlc: Boolean): Pair<String, JSONObject> {
        val envelope = JSONObject(body)
        require(envelope.getJSONArray("error").length() == 0) { "Kraken API error" }
        val result = envelope.getJSONObject("result")
        val keys = result.keys().asSequence().filter { !isOhlc || it != "last" }.toList()
        require(keys.size == 1 && keys[0] in MARKET_KEYS) {
            "Kraken response is not exclusively BTC/AUD"
        }
        return keys[0] to result
    }

    private fun decimal(raw: String, allowZero: Boolean = false): BigDecimal {
        val v = BigDecimal(raw)
        require(v.signum() > 0 || (allowZero && v.signum() == 0)) {
            "Non-positive market value"
        }
        return v
    }

    private fun cents(raw: String): Long =
        decimal(raw).multiply(BigDecimal(100))
            .setScale(0, RoundingMode.HALF_UP).longValueExact().also {
                require(it > 0L) { "Price rounds to zero cents" }
            }

    /** Accept 720 completed 4h candles plus a forming row, but never persist the forming row. */
    fun parseCompletedOhlc(body: String, nowMs: Long): List<PaperDatabase.Candle> {
        val (key, result) = marketResult(body, isOhlc = true)
        val rows = result.getJSONArray(key)
        require(rows.length() in 21..721) { "Implausible OHLC row count" }
        val nowS = nowMs / 1_000L
        var previous = -1L
        val completed = ArrayList<PaperDatabase.Candle>(rows.length())
        for (i in 0 until rows.length()) {
            val row = rows.getJSONArray(i)
            require(row.length() >= 8) { "Malformed OHLC row" }
            val start = row.getLong(0)
            require(start > previous && start > 0L && start % INTERVAL_S == 0L && start <= nowS) {
                "Unordered, unaligned or future OHLC candle"
            }
            previous = start
            val open = cents(row.getString(1))
            val high = cents(row.getString(2))
            val low = cents(row.getString(3))
            val close = cents(row.getString(4))
            decimal(row.getString(5)) // VWAP
            decimal(row.getString(6), allowZero = true) // volume
            require(row.getLong(7) >= 0L) { "Negative OHLC trade count" }
            require(low <= minOf(open, close) && high >= maxOf(open, close) && low <= high) {
                "Invalid OHLC price range"
            }
            if (start + INTERVAL_S <= nowS) {
                completed.add(PaperDatabase.Candle(start, open, high, low, close))
            }
        }
        require(completed.size >= 21) { "Fewer than 21 completed candles" }
        val tail = completed.takeLast(21)
        require(tail.zipWithNext().all { (a, b) -> b.startS - a.startS == INTERVAL_S }) {
            "Gap in last 21 completed candles"
        }
        val ageS = nowS - (completed.last().startS + INTERVAL_S)
        require(ageS in 0L..MAX_AGE_S) { "Completed OHLC source is stale" }
        return completed.takeLast(720)
    }

    fun parseTickerCents(body: String): Long {
        val (key, result) = marketResult(body, isOhlc = false)
        val ticker = result.getJSONObject(key)
        val bid = decimal(ticker.getJSONArray("b").getString(0))
        val ask = decimal(ticker.getJSONArray("a").getString(0))
        require(bid <= ask) { "Crossed BTC/AUD bid/ask" }
        return cents(ticker.getJSONArray("c").getString(0))
    }

    fun fetchCompleted(nowMs: Long): List<PaperDatabase.Candle> =
        parseCompletedOhlc(request("OHLC?pair=XBTAUD&interval=240", 2_000_000), nowMs)

    /** Kraken REST Ticker has no exchange quote timestamp; this is a poll observation. */
    fun fetchObservedTickerCents(): Long =
        parseTickerCents(request("Ticker?pair=XBTAUD", 500_000))

    /** Commit only validated sources; the database checks the enabled flag transactionally. */
    fun persistObserved(
        db: PaperDatabase, candles: List<PaperDatabase.Candle>,
        tickerCents: Long, observedAtMs: Long
    ): Boolean {
        require(tickerCents in 1L..1_000_000_000_000L)
        if (!db.recordCandles(candles, observedAtMs)) return false
        db.observeTickerAndPaperTrade(observedAtMs, tickerCents)
        return true
    }

    fun syncInto(db: PaperDatabase): Boolean {
        val candles = fetchCompleted(System.currentTimeMillis())
        val ticker = fetchObservedTickerCents()
        return persistObserved(db, candles, ticker, System.currentTimeMillis())
    }
}

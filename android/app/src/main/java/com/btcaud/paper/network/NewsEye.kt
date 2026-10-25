package com.btcaud.paper.network

import android.util.Xml
import com.btcaud.paper.core.NewsObservation
import com.btcaud.paper.core.NewsTopic
import org.xmlpull.v1.XmlPullParser
import java.io.ByteArrayInputStream
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL
import java.text.SimpleDateFormat
import java.util.Locale
import java.util.TimeZone

/**
 * Passive RSS observer, not a strategy engine. Sources are hard-coded HTTPS,
 * bounded and cross-host redirects are rejected. Article text never executes.
 */
object NewsEye {
    data class Source(val name: String, val rssUrl: String, val articleHost: String)
    data class FeedReport(val observations: List<NewsObservation>, val warnings: String?)
    private val sources = listOf(
        Source("CoinDesk", "https://www.coindesk.com/arc/outboundfeeds/rss/", "coindesk.com"),
        Source("Decrypt", "https://decrypt.co/feed", "decrypt.co"),
        Source("Cointelegraph", "https://cointelegraph.com/rss", "cointelegraph.com"),
    )
    private const val MAX_BYTES = 900_000

    fun collect(): FeedReport {
        val articles = mutableListOf<NewsObservation>()
        val failures = mutableListOf<String>()
        var successful = 0
        for (source in sources) {
            try {
                articles += fetch(source)
                successful++
            } catch (e: Exception) {
                failures += source.name + ": " + e.javaClass.simpleName
            }
        }
        if (successful == 0) throw IOException("All public RSS feeds unavailable")
        return FeedReport(articles.distinctBy { it.url }.take(120),
            if (failures.isEmpty()) null else "Some RSS feeds unavailable: " + failures.joinToString("; "))
    }

    private fun trustedHost(url: URL, expected: String): Boolean =
        url.protocol.equals("https", ignoreCase = true) &&
            (url.host.equals(expected, ignoreCase = true) ||
                url.host.lowercase().endsWith("." + expected.lowercase()))

    private fun fetch(source: Source): List<NewsObservation> {
        val target = URL(source.rssUrl)
        require(trustedHost(target, source.articleHost))
        val conn = (target.openConnection() as HttpURLConnection).apply {
            requestMethod = "GET"
            connectTimeout = 8_000
            readTimeout = 8_000
            setRequestProperty("User-Agent", "BTCAUDPaper/16 (RSS observation only)")
            setRequestProperty("Accept", "application/rss+xml, application/atom+xml, application/xml, text/xml")
        }
        try {
            require(conn.responseCode == 200) { "RSS HTTP " + conn.responseCode }
            require(trustedHost(conn.url, source.articleHost)) { "RSS redirected off trusted source" }
            val xml = conn.inputStream.use { it.readNBytes(MAX_BYTES + 1) }
            require(xml.size in 1..MAX_BYTES) { "RSS response too large" }
            val text = xml.toString(Charsets.UTF_8)
            require(!text.contains("<!DOCTYPE", ignoreCase = true) &&
                !text.contains("<!ENTITY", ignoreCase = true)) { "Unsafe XML document" }
            val parser = Xml.newPullParser()
            parser.setInput(ByteArrayInputStream(xml), "UTF-8")
            val results = mutableListOf<NewsObservation>()
            var inEntry = false
            var title = ""
            var link = ""
            var date = ""
            var depth = 0
            while (parser.eventType != XmlPullParser.END_DOCUMENT && results.size < 40) {
                when (parser.eventType) {
                    XmlPullParser.START_TAG -> {
                        val tag = parser.name.substringAfterLast(':').lowercase()
                        if (!inEntry && tag in listOf("item", "entry")) {
                            inEntry = true
                            depth = parser.depth
                            title = ""
                            link = ""
                            date = ""
                        } else if (inEntry) {
                            when (tag) {
                                "title" -> if (title.isEmpty()) title = parser.nextText().trim().take(220)
                                "link" -> {
                                    val href = parser.getAttributeValue(null, "href")
                                    if (href != null && link.isEmpty()) link = href.trim().take(700)
                                    else if (href == null && link.isEmpty())
                                        link = parser.nextText().trim().take(700)
                                }
                                "pubdate", "published", "updated" ->
                                    if (date.isEmpty()) date = parser.nextText().trim().take(80)
                            }
                        }
                    }
                    XmlPullParser.END_TAG -> {
                        val tag = parser.name.substringAfterLast(':').lowercase()
                        if (inEntry && parser.depth == depth && tag in listOf("item", "entry")) {
                            val valid = try { trustedHost(URL(link), source.articleHost) }
                                catch (_: Exception) { false }
                            if (title.isNotBlank() && valid) {
                                val observed = System.currentTimeMillis()
                                val published = publishedTime(date)?.takeIf { it <= observed + 300_000L }
                                results += NewsObservation(source.name, title, link,
                                    published, observed, NewsTopic.classify(title))
                            }
                            inEntry = false
                        }
                    }
                }
                parser.next()
            }
            return results
        } finally {
            conn.disconnect()
        }
    }

    private fun publishedTime(value: String): Long? {
        if (value.isBlank()) return null
        for (format in listOf("EEE, dd MMM yyyy HH:mm:ss Z", "EEE, dd MMM yyyy HH:mm Z")) {
            try {
                val parser = SimpleDateFormat(format, Locale.US).apply {
                    isLenient = false; timeZone = TimeZone.getTimeZone("UTC")
                }
                val parsed = parser.parse(value) ?: continue
                return parsed.time
            } catch (_: Exception) { }
        }
        return try { java.time.Instant.parse(value).toEpochMilli() } catch (_: Exception) { null }
    }
}

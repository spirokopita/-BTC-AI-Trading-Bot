package com.btcaud.paper.data

import android.content.ContentValues
import android.content.Context
import android.database.sqlite.SQLiteDatabase
import android.database.sqlite.SQLiteOpenHelper
import com.btcaud.paper.core.MonitorPolicy
import com.btcaud.paper.core.MonitorSnapshot
import com.btcaud.paper.core.PaperAccount
import com.btcaud.paper.core.PaperDecisionEngine
import com.btcaud.paper.core.PaperFill
import com.btcaud.paper.core.PaperLedger
import com.btcaud.paper.core.PaperTradeEvent
import com.btcaud.paper.core.NewsObservation

/**
 * Local transactional paper ledger. Database file name deliberately unchanged
 * so upgrading from V15 preserves the A$1,000 account and funding history.
 * SQLite v1 -> v2 is additive, with no destructive migration.
 */
class PaperDatabase(context: Context) : SQLiteOpenHelper(context, "btc_paper_v13.db", null, 3) {
    override fun onCreate(db: SQLiteDatabase) {
        db.execSQL("""CREATE TABLE app_state (
            id INTEGER PRIMARY KEY CHECK(id=1), enabled INTEGER NOT NULL DEFAULT 0,
            cash_cents INTEGER NOT NULL, funding_cents INTEGER NOT NULL,
            refill_count INTEGER NOT NULL, reset_count INTEGER NOT NULL,
            last_attempt_ms INTEGER, last_success_ms INTEGER, last_error TEXT,
            trading_enabled INTEGER NOT NULL DEFAULT 0,
            position_sats INTEGER NOT NULL DEFAULT 0,
            position_basis_cents INTEGER NOT NULL DEFAULT 0,
            entry_price_cents INTEGER NOT NULL DEFAULT 0,
            last_evaluated_s INTEGER,
            last_decision TEXT NOT NULL DEFAULT 'NOT_ARMED',
            last_reason TEXT NOT NULL DEFAULT 'Paper strategy is off',
            ticker_cents INTEGER, ticker_ms INTEGER)""")
        db.execSQL("""CREATE TABLE funding_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL,
            amount_cents INTEGER NOT NULL, cash_after_cents INTEGER NOT NULL,
            funding_after_cents INTEGER NOT NULL, created_ms INTEGER NOT NULL)""")
        db.execSQL("""CREATE TABLE candles_4h (
            start_s INTEGER PRIMARY KEY, open_cents INTEGER NOT NULL,
            high_cents INTEGER NOT NULL, low_cents INTEGER NOT NULL,
            close_cents INTEGER NOT NULL, source TEXT NOT NULL)""")
        createTradeTable(db)
        createNewsTable(db)
        db.execSQL("INSERT INTO app_state(id, enabled, cash_cents, funding_cents, refill_count, reset_count) VALUES(1,0,100000,100000,0,0)")
        db.execSQL("INSERT INTO funding_audit(kind, amount_cents, cash_after_cents, funding_after_cents, created_ms) VALUES('PREFILL',100000,100000,100000,0)")
    }

    private fun createTradeTable(db: SQLiteDatabase) {
        db.execSQL("""CREATE TABLE IF NOT EXISTS paper_trade_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL, side TEXT NOT NULL CHECK(side IN ('BUY','SELL')),
            candle_s INTEGER NOT NULL, observed_ms INTEGER NOT NULL,
            price_cents INTEGER NOT NULL, quantity_sats INTEGER NOT NULL,
            costs_cents INTEGER NOT NULL, realised_net_cents INTEGER,
            reason TEXT NOT NULL)""")
    }

    private fun createNewsTable(db: SQLiteDatabase) {
        db.execSQL("""CREATE TABLE IF NOT EXISTS news_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT, url TEXT NOT NULL UNIQUE,
            source TEXT NOT NULL, headline TEXT NOT NULL, topic TEXT NOT NULL,
            published_ms INTEGER, first_seen_ms INTEGER NOT NULL)""")
        db.execSQL("CREATE INDEX IF NOT EXISTS idx_news_first_seen ON news_items(first_seen_ms DESC)")
    }

    override fun onUpgrade(db: SQLiteDatabase, oldVersion: Int, newVersion: Int) {
        require(oldVersion in 1..2 && newVersion == 3) { "Unsupported database upgrade" }
        if (oldVersion < 2) {
            db.execSQL("ALTER TABLE app_state ADD COLUMN trading_enabled INTEGER NOT NULL DEFAULT 0")
            db.execSQL("ALTER TABLE app_state ADD COLUMN position_sats INTEGER NOT NULL DEFAULT 0")
            db.execSQL("ALTER TABLE app_state ADD COLUMN position_basis_cents INTEGER NOT NULL DEFAULT 0")
            db.execSQL("ALTER TABLE app_state ADD COLUMN entry_price_cents INTEGER NOT NULL DEFAULT 0")
            db.execSQL("ALTER TABLE app_state ADD COLUMN last_evaluated_s INTEGER")
            db.execSQL("ALTER TABLE app_state ADD COLUMN last_decision TEXT NOT NULL DEFAULT 'NOT_ARMED'")
            db.execSQL("ALTER TABLE app_state ADD COLUMN last_reason TEXT NOT NULL DEFAULT 'Paper strategy is off'")
            db.execSQL("ALTER TABLE app_state ADD COLUMN ticker_cents INTEGER")
            db.execSQL("ALTER TABLE app_state ADD COLUMN ticker_ms INTEGER")
            createTradeTable(db)
        }
        if (oldVersion < 3) {
            db.execSQL("ALTER TABLE app_state ADD COLUMN news_attempt_ms INTEGER")
            db.execSQL("ALTER TABLE app_state ADD COLUMN news_success_ms INTEGER")
            db.execSQL("ALTER TABLE app_state ADD COLUMN news_error TEXT")
            createNewsTable(db)
        }
    }

    private fun account(db: SQLiteDatabase): PaperAccount =
        db.rawQuery("SELECT cash_cents,funding_cents,refill_count,reset_count FROM app_state WHERE id=1", null).use { c ->
            check(c.moveToFirst()) { "Missing paper account" }
            PaperAccount(c.getLong(0), c.getLong(1), c.getInt(2), c.getInt(3))
        }

    fun snapshot(): MonitorSnapshot {
        val db = readableDatabase
        val state = db.rawQuery("""SELECT enabled,last_attempt_ms,last_success_ms,last_error,
            trading_enabled,position_sats,position_basis_cents,entry_price_cents,
            last_decision,last_reason,ticker_cents,ticker_ms FROM app_state WHERE id=1""", null).use { c ->
            check(c.moveToFirst())
            listOf(
                c.getInt(0).toString(),
                if (c.isNull(1)) "" else c.getLong(1).toString(),
                if (c.isNull(2)) "" else c.getLong(2).toString(),
                if (c.isNull(3)) "" else c.getString(3),
                c.getInt(4).toString(), c.getLong(5).toString(),
                c.getLong(6).toString(), c.getLong(7).toString(),
                c.getString(8), c.getString(9),
                if (c.isNull(10)) "" else c.getLong(10).toString(),
                if (c.isNull(11)) "" else c.getLong(11).toString(),
            )
        }
        val latest = db.rawQuery("SELECT start_s,close_cents FROM candles_4h ORDER BY start_s DESC LIMIT 1", null).use { c ->
            if (c.moveToFirst()) Pair(c.getLong(0), c.getLong(1)) else null
        }
        val realised = db.rawQuery("SELECT COALESCE(SUM(realised_net_cents),0) FROM paper_trade_events WHERE session_id=?", arrayOf(account(db).resetCount.toString())).use { c ->
            check(c.moveToFirst()); c.getLong(0)
        }
        val trades = db.rawQuery("""SELECT side,observed_ms,price_cents,quantity_sats,costs_cents,
            realised_net_cents,reason FROM paper_trade_events ORDER BY id DESC LIMIT 12""", null).use { c ->
            buildList {
                while (c.moveToNext()) add(PaperTradeEvent(c.getString(0), c.getLong(1), c.getLong(2),
                    c.getLong(3), c.getLong(4), if (c.isNull(5)) null else c.getLong(5), c.getString(6)))
            }
        }
        val newsStatus = db.rawQuery(
            "SELECT news_success_ms,news_error FROM app_state WHERE id=1", null
        ).use { c ->
            check(c.moveToFirst())
            Pair(if(c.isNull(0)) null else c.getLong(0),
                 if(c.isNull(1)) null else c.getString(1))
        }
        val observedNews = db.rawQuery("""SELECT source,headline,url,published_ms,first_seen_ms,topic
            FROM news_items ORDER BY first_seen_ms DESC, id DESC LIMIT 6""", null).use { c ->
            buildList {
                while (c.moveToNext()) add(NewsObservation(c.getString(0), c.getString(1),
                    c.getString(2), if(c.isNull(3)) null else c.getLong(3),
                    c.getLong(4), c.getString(5)))
            }
        }
        return MonitorSnapshot(
            enabled = state[0] == "1", lastAttemptMillis = state[1].toLongOrNull(),
            lastSuccessMillis = state[2].toLongOrNull(), lastError = state[3].ifBlank { null },
            lastCandleEpochSeconds = latest?.first, latestCloseAudCents = latest?.second,
            account = account(db), tradingEnabled = state[4] == "1",
            positionSats = state[5].toLong(), positionBasisCents = state[6].toLong(),
            entryPriceCents = state[7].toLong(), lastDecision = state[8],
            lastDecisionReason = state[9], latestTickerAudCents = state[10].toLongOrNull(),
            latestTickerMillis = state[11].toLongOrNull(),
            realisedNetCents = realised, recentTrades = trades,
            latestNewsSeenMillis = newsStatus.first, newsWarning = newsStatus.second,
            latestNews = observedNews,
        )
    }

    /** Controls are persistent and idempotent across UI/widgets/workers. */
    fun setEnabled(enabled: Boolean): Boolean {
        val db = writableDatabase
        db.beginTransaction()
        try {
            val old = db.rawQuery("SELECT enabled FROM app_state WHERE id=1", null).use { c ->
                check(c.moveToFirst()); c.getInt(0) != 0
            }
            if (old != enabled) db.update("app_state", ContentValues().apply {
                put("enabled", if (enabled) 1 else 0)
            }, "id=1", null)
            db.setTransactionSuccessful()
            return old != enabled
        } finally { db.endTransaction() }
    }

    fun setTradingEnabled(enabled: Boolean) {
        val db = writableDatabase
        db.beginTransaction()
        try {
            val v = ContentValues().apply {
                put("trading_enabled", if (enabled) 1 else 0)
                put("last_decision", if (enabled) "WAITING" else "NOT_ARMED")
                put("last_reason", if (enabled) "Waiting for fresh completed candle and public ticker" else "Paper strategy switched off")
            }
            check(db.update("app_state", v, "id=1", null) == 1)
            db.setTransactionSuccessful()
        } finally { db.endTransaction() }
    }

    fun refill(nowMs: Long, amountCents: Long = 100_000L): PaperAccount =
        mutateAccount(nowMs, "REFILL", amountCents) { it.refill(amountCents) }

    fun reset(nowMs: Long): PaperAccount = mutateAccount(nowMs, "RESET", 0L) { it.reset() }

    private fun mutateAccount(nowMs: Long, kind: String, amountCents: Long,
                              fn: (PaperAccount) -> PaperAccount): PaperAccount {
        val db = writableDatabase
        db.beginTransaction()
        try {
            val updated = fn(account(db))
            val v = ContentValues().apply {
                put("cash_cents", updated.cashCents)
                put("funding_cents", updated.cumulativeFundingCents)
                put("refill_count", updated.refillCount)
                put("reset_count", updated.resetCount)
                if (kind == "RESET") {
                    put("trading_enabled", 0)
                    put("position_sats", 0L)
                    put("position_basis_cents", 0L)
                    put("entry_price_cents", 0L)
                    putNull("last_evaluated_s")
                    put("last_decision", "NOT_ARMED")
                    put("last_reason", "Simulation reset; old trades retained in audit")
                }
            }
            check(db.update("app_state", v, "id=1", null) == 1)
            db.insertOrThrow("funding_audit", null, ContentValues().apply {
                put("kind", kind); put("amount_cents", amountCents)
                put("cash_after_cents", updated.cashCents)
                put("funding_after_cents", updated.cumulativeFundingCents)
                put("created_ms", nowMs)
            })
            db.setTransactionSuccessful()
            return updated
        } finally { db.endTransaction() }
    }

    fun recordAttempt(nowMs: Long): Boolean = writableDatabase.update(
        "app_state", ContentValues().apply { put("last_attempt_ms", nowMs) },
        "id=1 AND enabled=1", null) == 1

    fun recordFailure(message: String) {
        writableDatabase.update("app_state", ContentValues().apply {
            put("last_error", message.take(200))
        }, "id=1 AND enabled=1", null)
    }

    data class Candle(val startS: Long, val openCents: Long, val highCents: Long,
                      val lowCents: Long, val closeCents: Long) {
        fun isValid(nowS: Long): Boolean =
            MonitorPolicy.isCompletedCandle(startS, nowS) && lowCents > 0 &&
                openCents in lowCents..highCents && closeCents in lowCents..highCents
    }

    fun recordCandles(candles: List<Candle>, nowMs: Long): Boolean {
        val nowS = nowMs / 1_000L
        require(candles.isNotEmpty())
        require(candles.all { it.isValid(nowS) })
        val sorted = candles.distinctBy { it.startS }.sortedBy { it.startS }
        require(sorted.zipWithNext().all { (a, b) ->
            b.startS - a.startS == MonitorPolicy.CANDLE_INTERVAL_SECONDS
        }) { "Missing candle in fetched tail" }
        require(nowS - sorted.last().startS <= 2L * MonitorPolicy.CANDLE_INTERVAL_SECONDS) {
            "Exchange candles are stale"
        }
        val db = writableDatabase
        db.beginTransaction()
        try {
            val enabled = db.rawQuery("SELECT enabled FROM app_state WHERE id=1", null).use { c ->
                check(c.moveToFirst()); c.getInt(0) == 1
            }
            if (enabled) {
                sorted.forEach { candle ->
                    db.insertWithOnConflict("candles_4h", null, ContentValues().apply {
                        put("start_s", candle.startS); put("open_cents", candle.openCents)
                        put("high_cents", candle.highCents); put("low_cents", candle.lowCents)
                        put("close_cents", candle.closeCents)
                        put("source", "kraken-public-OHLC")
                    }, SQLiteDatabase.CONFLICT_IGNORE)
                }
                db.update("app_state", ContentValues().apply {
                    put("last_success_ms", nowMs); putNull("last_error")
                }, "id=1", null)
            }
            db.setTransactionSuccessful()
            return enabled
        } finally { db.endTransaction() }
    }

    /**
     * Atomic decision+execution. Never backfills historical trades on enabling.
     * Signals require a recently closed bar; the fill references a separately
     * observed public ticker, not a price known only after the signal.
     */
    fun observeTickerAndPaperTrade(nowMs: Long, observedPriceCents: Long) {
        require(observedPriceCents in 1L..1_000_000_000_000L)
        val db = writableDatabase
        db.beginTransaction()
        try {
            val state = db.rawQuery("""SELECT enabled,trading_enabled,cash_cents,position_sats,
                position_basis_cents,entry_price_cents,last_evaluated_s,reset_count
                FROM app_state WHERE id=1""", null).use { c ->
                check(c.moveToFirst())
                listOf(c.getLong(0),c.getLong(1),c.getLong(2),c.getLong(3),
                    c.getLong(4),c.getLong(5),if(c.isNull(6)) -1L else c.getLong(6),c.getLong(7))
            }
            if (state[0] != 1L) return // Pause takes effect before a late worker writes.
            val updated = ContentValues().apply {
                put("ticker_cents", observedPriceCents); put("ticker_ms", nowMs)
            }
            if (state[1] != 1L) {
                db.update("app_state", updated, "id=1 AND enabled=1", null)
                db.setTransactionSuccessful()
                return
            }
            val bars = db.rawQuery("""SELECT start_s,close_cents FROM candles_4h
                ORDER BY start_s DESC LIMIT 21""", null).use { c ->
                buildList {
                    while (c.moveToNext()) add(PaperDecisionEngine.Bar(c.getLong(0), c.getLong(1)))
                }.asReversed()
            }
            val newest = bars.lastOrNull()
            val validAge = newest != null &&
                nowMs / 1000L - newest.startS in MonitorPolicy.CANDLE_INTERVAL_SECONDS..(2 * MonitorPolicy.CANDLE_INTERVAL_SECONDS)
            val validTicker = newest != null && observedPriceCents.toDouble() in
                (newest.closeCents * 0.70)..(newest.closeCents * 1.30)
            if (!validAge || !validTicker) {
                updated.put("last_decision", "HOLD")
                updated.put("last_reason", "Stale candle or ticker differs >30% from last close")
            } else {
                val decision = PaperDecisionEngine.evaluate(bars, state[3], state[5], observedPriceCents)
                val unseen = newest!!.startS > state[6]
                val freshEntryWindow = nowMs / 1000L - newest.startS <=
                    MonitorPolicy.CANDLE_INTERVAL_SECONDS + 3600L
                val freshExitSignal = unseen && freshEntryWindow
                updated.put("last_evaluated_s", newest.startS)
                val shouldTrade = when(decision.action) {
                    PaperDecisionEngine.Action.BUY -> unseen && freshEntryWindow && state[3] == 0L
                    PaperDecisionEngine.Action.SELL ->
                        state[3] > 0L && (decision.reason.contains("observed-price") || freshExitSignal)
                    else -> false
                }
                var reason = decision.reason
                var finalAction = if (shouldTrade) decision.action.name else "HOLD"
                if (decision.action == PaperDecisionEngine.Action.BUY && !freshEntryWindow)
                    reason = "Entry signal expired; not backfilling"
                if (shouldTrade && decision.action == PaperDecisionEngine.Action.BUY) {
                    val quantity = PaperDecisionEngine.buyQuantitySats(state[2], observedPriceCents)
                    if (quantity <= 0L) {
                        finalAction = "HOLD"
                        reason = "Insufficient paper cash for minimum trade"
                    } else {
                        val fill = PaperDecisionEngine.fill(PaperFill.Side.BUY, quantity, observedPriceCents)
                        val next = PaperLedger(state[2]).buy(fill)
                        updated.put("cash_cents", next.cashCents)
                        updated.put("position_sats", next.btcSats)
                        updated.put("position_basis_cents", next.costBasisCents)
                        updated.put("entry_price_cents", observedPriceCents)
                        addTradeEvent(db, "BUY", state[7].toInt(), newest.startS, nowMs,
                            fill, null, decision.reason)
                    }
                } else if (shouldTrade && decision.action == PaperDecisionEngine.Action.SELL) {
                    val fill = PaperDecisionEngine.fill(PaperFill.Side.SELL, state[3], observedPriceCents)
                    val next = PaperLedger(state[2], state[3], state[4]).sell(fill)
                    val realised = next.cashCents - state[2] - state[4]
                    updated.put("cash_cents", next.cashCents)
                    updated.put("position_sats", 0L)
                    updated.put("position_basis_cents", 0L)
                    updated.put("entry_price_cents", 0L)
                    addTradeEvent(db, "SELL", state[7].toInt(), newest.startS, nowMs,
                        fill, realised, decision.reason)
                }
                updated.put("last_decision", finalAction)
                updated.put("last_reason", reason.take(160))
            }
            db.update("app_state", updated, "id=1 AND enabled=1", null)
            db.setTransactionSuccessful()
        } finally { db.endTransaction() }
    }

    /**
     * Atomically throttle public RSS polling to roughly once every 30 minutes.
     * News is a passive observation source, never an automatic BUY/SELL signal.
     */
    fun recordNewsAttempt(nowMs: Long): Boolean {
        val cutoff = nowMs - 30L * 60_000L
        return writableDatabase.update("app_state", ContentValues().apply {
            put("news_attempt_ms", nowMs)
        }, "id=1 AND enabled=1 AND (news_attempt_ms IS NULL OR news_attempt_ms <= ?)",
            arrayOf(cutoff.toString())) == 1
    }

    fun storeNews(observations: List<NewsObservation>, nowMs: Long, warning: String?) {
        val db = writableDatabase
        db.beginTransaction()
        try {
            val enabled = db.rawQuery("SELECT enabled FROM app_state WHERE id=1", null).use { c ->
                check(c.moveToFirst()); c.getInt(0) == 1
            }
            if (enabled) {
                observations.take(120).forEach { item ->
                    db.insertWithOnConflict("news_items", null, ContentValues().apply {
                        put("url", item.url.take(700))
                        put("source", item.source.take(50))
                        put("headline", item.headline.take(220))
                        put("topic", item.topic.take(25))
                        if (item.publishedMs == null) putNull("published_ms")
                        else put("published_ms", item.publishedMs)
                        put("first_seen_ms", item.firstSeenMs)
                    }, SQLiteDatabase.CONFLICT_IGNORE)
                }
                db.execSQL("""DELETE FROM news_items WHERE id NOT IN (
                    SELECT id FROM news_items ORDER BY first_seen_ms DESC, id DESC LIMIT 600)""")
                db.update("app_state", ContentValues().apply {
                    put("news_success_ms", nowMs)
                    if (warning == null) putNull("news_error")
                    else put("news_error", warning.take(240))
                }, "id=1", null)
            }
            db.setTransactionSuccessful()
        } finally { db.endTransaction() }
    }

    fun recordNewsFailure(message: String) {
        writableDatabase.update("app_state", ContentValues().apply {
            put("news_error", message.take(240))
        }, "id=1 AND enabled=1", null)
    }

    private fun addTradeEvent(db: SQLiteDatabase, side: String, session: Int,
                              candleS: Long, nowMs: Long, fill: PaperFill,
                              realised: Long?, reason: String) {
        db.insertOrThrow("paper_trade_events", null, ContentValues().apply {
            put("session_id", session); put("side", side); put("candle_s", candleS)
            put("observed_ms", nowMs); put("price_cents", fill.priceAudCentsPerBtc)
            put("quantity_sats", fill.quantitySats); put("costs_cents", fill.costsCents)
            if (realised == null) putNull("realised_net_cents") else put("realised_net_cents", realised)
            put("reason", reason)
        })
    }
}

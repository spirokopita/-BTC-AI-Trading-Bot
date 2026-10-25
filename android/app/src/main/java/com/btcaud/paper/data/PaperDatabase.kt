package com.btcaud.paper.data

import android.content.ContentValues
import android.content.Context
import android.database.sqlite.SQLiteDatabase
import android.database.sqlite.SQLiteOpenHelper
import com.btcaud.paper.core.MonitorPolicy
import com.btcaud.paper.core.MonitorSnapshot
import com.btcaud.paper.core.PaperAccount

/** On-device paper-only store. No wallet address, private key, exchange credentials or orders. */
class PaperDatabase(context: Context) : SQLiteOpenHelper(context, "btc_paper_v13.db", null, 1) {
    override fun onCreate(db: SQLiteDatabase) {
        db.execSQL("""CREATE TABLE app_state (
            id INTEGER PRIMARY KEY CHECK(id=1), enabled INTEGER NOT NULL DEFAULT 0,
            cash_cents INTEGER NOT NULL, funding_cents INTEGER NOT NULL,
            refill_count INTEGER NOT NULL, reset_count INTEGER NOT NULL,
            last_attempt_ms INTEGER, last_success_ms INTEGER, last_error TEXT)""")
        db.execSQL("""CREATE TABLE funding_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL,
            amount_cents INTEGER NOT NULL, cash_after_cents INTEGER NOT NULL,
            funding_after_cents INTEGER NOT NULL, created_ms INTEGER NOT NULL)""")
        db.execSQL("""CREATE TABLE candles_4h (
            start_s INTEGER PRIMARY KEY, open_cents INTEGER NOT NULL,
            high_cents INTEGER NOT NULL, low_cents INTEGER NOT NULL,
            close_cents INTEGER NOT NULL, source TEXT NOT NULL)""")
        db.execSQL("INSERT INTO app_state(id, enabled, cash_cents, funding_cents, refill_count, reset_count) VALUES(1,0,100000,100000,0,0)")
        db.execSQL("INSERT INTO funding_audit(kind, amount_cents, cash_after_cents, funding_after_cents, created_ms) VALUES('PREFILL',100000,100000,100000,0)")
    }

    override fun onUpgrade(db: SQLiteDatabase, oldVersion: Int, newVersion: Int) {
        error("No destructive migration is permitted; implement a versioned migration")
    }

    private fun account(db: SQLiteDatabase): PaperAccount =
        db.rawQuery("SELECT cash_cents,funding_cents,refill_count,reset_count FROM app_state WHERE id=1", null).use { c ->
            check(c.moveToFirst()) { "Missing paper account" }
            PaperAccount(c.getLong(0), c.getLong(1), c.getInt(2), c.getInt(3))
        }

    fun snapshot(): MonitorSnapshot {
        val db = readableDatabase
        val row = db.rawQuery("SELECT enabled,last_attempt_ms,last_success_ms,last_error FROM app_state WHERE id=1", null).use { c ->
            check(c.moveToFirst())
            listOf(
                c.getInt(0).toString(),
                if (c.isNull(1)) "" else c.getLong(1).toString(),
                if (c.isNull(2)) "" else c.getLong(2).toString(),
                if (c.isNull(3)) "" else c.getString(3),
            )
        }
        val latest = db.rawQuery("SELECT start_s,close_cents FROM candles_4h ORDER BY start_s DESC LIMIT 1", null).use { c ->
            if (c.moveToFirst()) Pair(c.getLong(0), c.getLong(1)) else null
        }
        return MonitorSnapshot(
            enabled = row[0] == "1", lastAttemptMillis = row[1].toLongOrNull(),
            lastSuccessMillis = row[2].toLongOrNull(), lastError = row[3].ifBlank { null },
            lastCandleEpochSeconds = latest?.first, latestCloseAudCents = latest?.second,
            account = account(db),
        )
    }

    /** Idempotent master switch. Workers re-check this flag *after* network calls. */
    fun setEnabled(enabled: Boolean): Boolean {
        val db = writableDatabase
        db.beginTransaction()
        return try {
            val old = db.rawQuery("SELECT enabled FROM app_state WHERE id=1", null).use { c ->
                check(c.moveToFirst()); c.getInt(0) != 0
            }
            if (old != enabled) {
                val values = ContentValues().apply { put("enabled", if (enabled) 1 else 0) }
                db.update("app_state", values, "id=1", null)
            }
            db.setTransactionSuccessful()
            old != enabled
        } finally { db.endTransaction() }
    }

    /** Simulated refill is accounted as funding, NOT profit. Audit never deleted. */
    fun refill(nowMs: Long, amountCents: Long = 100_000L): PaperAccount = mutateAccount(nowMs, "REFILL", amountCents) { it.refill(amountCents) }

    /** Explicit simulated reset; does not erase source candles or audit. */
    fun reset(nowMs: Long): PaperAccount = mutateAccount(nowMs, "RESET", 0L) { it.reset() }

    private fun mutateAccount(nowMs: Long, kind: String, amountCents: Long, fn: (PaperAccount) -> PaperAccount): PaperAccount {
        val db = writableDatabase
        db.beginTransaction()
        return try {
            val updated = fn(account(db))
            val values = ContentValues().apply {
                put("cash_cents", updated.cashCents); put("funding_cents", updated.cumulativeFundingCents)
                put("refill_count", updated.refillCount); put("reset_count", updated.resetCount)
            }
            check(db.update("app_state", values, "id=1", null) == 1)
            db.insertOrThrow("funding_audit", null, ContentValues().apply {
                put("kind", kind); put("amount_cents", amountCents)
                put("cash_after_cents", updated.cashCents)
                put("funding_after_cents", updated.cumulativeFundingCents)
                put("created_ms", nowMs)
            })
            db.setTransactionSuccessful()
            updated
        } finally { db.endTransaction() }
    }

    fun recordAttempt(nowMs: Long): Boolean = writableDatabase.run {
        update("app_state", ContentValues().apply { put("last_attempt_ms", nowMs) }, "id=1 AND enabled=1", null) == 1
    }

    fun recordFailure(message: String) {
        writableDatabase.update("app_state", ContentValues().apply {
            put("last_error", message.take(200))
        }, "id=1 AND enabled=1", null)
    }

    data class Candle(val startS: Long, val openCents: Long, val highCents: Long, val lowCents: Long, val closeCents: Long) {
        fun isValid(nowS: Long): Boolean =
            MonitorPolicy.isCompletedCandle(startS, nowS) && lowCents > 0 &&
                openCents in lowCents..highCents && closeCents in lowCents..highCents
    }

    /** Only a contiguous, recent completed tail is accepted as healthy. No trading in V13. */
    fun recordCandles(candles: List<Candle>, nowMs: Long): Boolean {
        val nowS = nowMs / 1_000L
        require(candles.isNotEmpty())
        require(candles.all { it.isValid(nowS) })
        val sorted = candles.distinctBy { it.startS }.sortedBy { it.startS }
        require(sorted.zipWithNext().all { (a, b) -> b.startS - a.startS == MonitorPolicy.CANDLE_INTERVAL_SECONDS }) {
            "Missing candle in fetched tail"
        }
        require(nowS - sorted.last().startS <= 2L * MonitorPolicy.CANDLE_INTERVAL_SECONDS) {
            "Exchange data is stale"
        }
        val db = writableDatabase
        db.beginTransaction()
        return try {
            val enabled = db.rawQuery("SELECT enabled FROM app_state WHERE id=1", null).use { c ->
                check(c.moveToFirst()); c.getInt(0) == 1
            }
            if (enabled) {
                sorted.forEach { candle ->
                    db.insertWithOnConflict("candles_4h", null, ContentValues().apply {
                        put("start_s", candle.startS); put("open_cents", candle.openCents)
                        put("high_cents", candle.highCents); put("low_cents", candle.lowCents)
                        put("close_cents", candle.closeCents); put("source", "kraken-public-OHLC")
                    }, SQLiteDatabase.CONFLICT_IGNORE)
                }
                db.update("app_state", ContentValues().apply {
                    put("last_success_ms", nowMs); putNull("last_error")
                }, "id=1", null)
            }
            db.setTransactionSuccessful()
            enabled
        } finally { db.endTransaction() }
    }
}

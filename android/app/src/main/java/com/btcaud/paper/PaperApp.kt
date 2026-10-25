package com.btcaud.paper

import android.app.Application
import com.btcaud.paper.data.PaperDatabase
import com.btcaud.paper.work.WorkScheduler

class PaperApp : Application() {
    override fun onCreate() {
        super.onCreate()
        PaperDatabase(this).use { db ->
            if (db.snapshot().enabled) WorkScheduler.start(this, immediate = false)
        }
    }
}

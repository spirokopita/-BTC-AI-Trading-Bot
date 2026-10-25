package com.btcaud.paper.core

import org.junit.Assert.assertEquals
import org.junit.Test

class NewsTopicTest {
    @Test fun bitcoinHeadlineIsTagged() {
        assertEquals("BITCOIN", NewsTopic.classify("Bitcoin price rallies after halving"))
    }
    @Test fun macroHeadlineIsTagged() {
        assertEquals("MACRO", NewsTopic.classify("Federal Reserve interest rate decision"))
    }
    @Test fun irrelevantHeadlineNotTradingSignal() {
        assertEquals("OTHER", NewsTopic.classify("Local football club results"))
    }
    @Test fun classificationCannotProvideOrderSide() {
        val label = NewsTopic.classify("BTC crashes after ETF approval")
        assertEquals("BITCOIN", label)
    }
}

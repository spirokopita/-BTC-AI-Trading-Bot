"""Roadmap 7 causal scheduling, restart recovery and fee gate tests."""
from datetime import datetime,timezone
from pathlib import Path
from unittest.mock import patch
import tempfile
import sqlite3
import unittest

from data_layer.storage import Candle,CandleStore
from news_intelligence.store import NewsStore
from strategy_loop import PaperStrategyLoop,LoopSettings,DecisionJournal
from strategy_loop.engine import checked_market_bars
from strategy_loop.cli import instance_lock

BASE=1704067200  # UTC, divisible by 4 hours
STEP=4*3600


def make_bars(count=245, breakout=True):
    bars=[]
    prev=100.
    for i in range(count):
        price=100. + .05*i
        if breakout and i==count-1:price=price+9.
        bars.append(Candle(BASE+i*STEP,prev,max(prev,price)*1.001,
                            min(prev,price)*.999,price,100.))
        prev=price
    return bars


class ContinuousPaperLoopTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        base=Path(self.tmp.name)
        self.market=base/'prices.sqlite';self.news=base/'news.sqlite';self.wallet=base/'wallet.sqlite';self.journal=base/'audit.sqlite'
        self.bars=make_bars()
        self.close_ts=self.bars[-1].ts+STEP
        self.now=self.close_ts+60
        with CandleStore(self.market) as data:data.upsert('kraken','BTC/AUD',240,self.bars,source='kraken_csv:SYNTHETIC_TEST_NOT_REAL')
        self.loop=PaperStrategyLoop(self.market,self.news,self.wallet,self.journal)

    def tearDown(self):self.tmp.cleanup()

    def article(self, seen=None):
        seen=self.close_ts-60 if seen is None else seen
        with NewsStore(self.news) as store:
            store.ingest([{'source':'test','url':'https://example.com/bitcoin-etf-record-approval',
              'headline':'Bitcoin ETF approved: record high rally',
              'published_ts':seen-100,'first_seen_ts':seen}])

    def test_no_news_no_orders_and_replay_exactly_once(self):
        a=self.loop.once(now=self.now)
        self.assertEqual(a['processed_new_candles'],245)
        self.assertEqual(a['new_orders'],0)
        self.assertEqual(a['status']['mode'],'PAPER_ONLY')
        self.assertEqual(a['status']['cash_quote'],1000)
        b=self.loop.once(now=self.now)
        self.assertEqual(b['processed_new_candles'],0)
        self.assertEqual(b['new_orders'],0)
        with DecisionJournal(self.journal) as j:
            self.assertEqual(j.db.execute('SELECT COUNT(*) FROM decisions').fetchone()[0],245)

    def test_news_seen_only_after_close_cannot_trade(self):
        self.article(seen=self.close_ts+30)
        with patch('strategy_loop.engine.validated_news_edge',return_value={'approved':True,'predicted_gross_move':.15,'category':['etf'],'evidence_as_of':self.close_ts-100}):
            out=self.loop.once(now=self.now)
        self.assertEqual(out['new_orders'],0)
        self.assertEqual(len(out['status']['pending']),0)

    def test_validated_fee_positive_news_and_breakout_queues_paper_only(self):
        self.article()
        with patch('strategy_loop.engine.validated_news_edge',return_value={'approved':True,'predicted_gross_move':.15,'category':['etf'],'evidence_as_of':self.close_ts-100}):
            out=self.loop.once(now=self.now)
        self.assertEqual(out['new_orders'],1)
        self.assertEqual(out['recent_decisions'][-1]['decision'],'BUY')
        self.assertEqual(out['status']['cash_quote'],1000)
        self.assertEqual(out['status']['position'],None)
        self.assertEqual(len(out['status']['pending']),1)
        second=self.loop.once(now=self.now)
        self.assertEqual(second['new_orders'],0)
        # First future candle is allowed to fill exactly one queued BUY.
        nextbar=Candle(self.bars[-1].ts+STEP,self.bars[-1].close,
                       self.bars[-1].close*1.002,self.bars[-1].close*.997,
                       self.bars[-1].close,100)
        with CandleStore(self.market) as m:m.upsert('kraken','BTC/AUD',240,[nextbar],source='kraken_csv:SYNTHETIC_TEST_NOT_REAL')
        future=self.loop.once(now=self.now+STEP)
        self.assertIsNotNone(future['status']['position'])
        self.assertEqual(future['audit']['fills'],1)
        self.assertEqual(len(future['status']['pending']),0)

    def test_low_forecast_cannot_pass_full_cost_gate(self):
        self.article()
        with patch('strategy_loop.engine.validated_news_edge',return_value={'approved':True,'predicted_gross_move':.005,'category':['etf'],'evidence_as_of':self.close_ts-100}):
            out=self.loop.once(now=self.now)
        self.assertEqual(out['new_orders'],0)
        self.assertEqual(out['recent_decisions'][-1]['reason'],'forecast_below_full_round_trip_costs')

    def test_missing_bar_blocks_entire_run_and_wallet(self):
        with CandleStore(self.market) as store:
            store.db.execute('DELETE FROM candles WHERE ts=?',(self.bars[25].ts,));store.db.commit()
        with self.assertRaisesRegex(ValueError,'Missing/non-contiguous'):
            self.loop.once(now=self.now)
        self.assertFalse(self.wallet.exists())
        with DecisionJournal(self.journal) as j:
            self.assertEqual(j.db.execute('SELECT status FROM health ORDER BY id DESC LIMIT 1').fetchone()[0],'ERROR')

    def test_untrusted_source_cannot_be_relabelled(self):
        with CandleStore(self.market) as store:
            store.db.execute('UPDATE candles SET source=?',('btc_usdt_proxy',));store.db.commit()
        with self.assertRaisesRegex(ValueError,'provenance'):self.loop.once(now=self.now)

    def test_stale_feed_fails_without_trading(self):
        with self.assertRaisesRegex(ValueError,'Stale'):self.loop.once(now=self.close_ts+9*3600)
        self.assertFalse(self.wallet.exists())

    def test_network_outage_no_new_entry(self):
        self.article()
        with patch('strategy_loop.engine.validated_news_edge',return_value={'approved':True,'predicted_gross_move':.15,'category':['etf'],'evidence_as_of':self.close_ts-100}):
            out=self.loop.once(now=self.now,market_ok=False)
        self.assertEqual(out['new_orders'],0)
        self.assertEqual(out['recent_decisions'][-1]['reason'],'unhealthy_public_feeds')

    def test_maker_limit_expires_after_three_bars(self):
        self.article()
        with patch('strategy_loop.engine.validated_news_edge',return_value={'approved':True,'predicted_gross_move':.15,'category':['etf'],'evidence_as_of':self.close_ts-100}):
            self.loop.once(now=self.now)
        with CandleStore(self.market) as db:
            last=self.bars[-1]
            # Never trade through the 10bp lower maker limit, so no fill.
            fresh=[]
            for k in range(1,4):
                fresh.append(Candle(last.ts+k*STEP,last.close,last.close*1.002,
                                    last.close*.9998,last.close,100.))
            db.upsert('kraken','BTC/AUD',240,fresh,source='kraken_csv:SYNTHETIC_TEST_NOT_REAL')
        result=self.loop.once(now=self.now+3*STEP)
        self.assertIsNone(result['status']['position'])
        self.assertEqual(result['status']['pending'],[])
        self.assertEqual(result['audit']['fills'],0)

    def test_protective_stop_works_during_market_and_news_outage(self):
        from paper_engine import PaperEngine
        self.loop.once(now=self.now)
        with PaperEngine(self.wallet,interval=240) as paper:
            paper.place_buy(49,kind='market',client_id='manual-synthetic')
        last=self.bars[-1]
        nextbar=Candle(last.ts+STEP,last.close,last.close*1.001,
                       last.close*.80,last.close*.85,100)
        with CandleStore(self.market) as db:
            db.upsert('kraken','BTC/AUD',240,[nextbar],source='kraken_csv:SYNTHETIC_TEST_NOT_REAL')
        outcome=self.loop.once(now=self.now+STEP,market_ok=False,news_ok=False)
        self.assertEqual(outcome['audit']['closed_trades'],1)
        self.assertIsNone(outcome['status']['position'])
        self.assertLess(outcome['status']['cash_quote'],1000)

    def test_maker_order_not_guaranteed_to_fill_on_touch(self):
        self.article()
        with patch('strategy_loop.engine.validated_news_edge',return_value={'approved':True,'predicted_gross_move':.15,'category':['etf'],'evidence_as_of':self.close_ts-100}):
            self.loop.once(now=self.now)
        from paper_engine import PaperEngine
        with PaperEngine(self.wallet,interval=240) as p:
            limit=p.status()['pending'][0]['limit_mid']
        last=self.bars[-1]
        nextbar=Candle(last.ts+STEP,last.close,last.close*1.001,limit,last.close,100)
        with CandleStore(self.market) as db:
            db.upsert('kraken','BTC/AUD',240,[nextbar],source='kraken_csv:SYNTHETIC_TEST_NOT_REAL')
        result=self.loop.once(now=self.now+STEP)
        self.assertIsNone(result['status']['position'])
        self.assertEqual(len(result['status']['pending']),1)

    def test_lock_prevents_duplicate_daemons(self):
        lock=Path(self.tmp.name)/'process.lock'
        with instance_lock(lock):
            with self.assertRaises(RuntimeError):
                with instance_lock(lock):pass

    def test_historical_replay_does_not_retrospectively_trade(self):
        self.article()
        # historical bars are replayed for warmup; model even if spoofed as perfect
        # cannot submit orders on the historical bars.
        with patch('strategy_loop.engine.validated_news_edge',return_value={'approved':True,'predicted_gross_move':.15,'category':['etf'],'evidence_as_of':self.close_ts-100}):
            state=self.loop.once(now=self.now)
        self.assertLessEqual(state['new_orders'],1)
        with DecisionJournal(self.journal) as journal:
            buys=journal.db.execute("SELECT COUNT(*) FROM decisions WHERE decision='BUY'").fetchone()[0]
            self.assertLessEqual(buys,1)


if __name__=='__main__':unittest.main()

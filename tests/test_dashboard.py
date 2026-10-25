"""Dashboard is a GET-only, fail-closed local view; never invokes order methods."""
from datetime import datetime, timezone
from pathlib import Path
import http.client
import hashlib
import json
import sqlite3
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from dashboard import DashboardSources, read_snapshot
from dashboard.server import handler_for, main
from data_layer.storage import Candle, CandleStore
from news_intelligence.store import NewsStore
from paper_engine import PaperEngine
from strategy_loop import DecisionJournal

BASE=240*60*10000
STEP=240*60

class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.src=DashboardSources(self.root/'market.sqlite',self.root/'paper.sqlite',self.root/'news.sqlite',self.root/'journal.sqlite')

    def tearDown(self):
        self.temp.cleanup()

    def _paper(self):
        with PaperEngine(self.src.wallet) as engine:
            engine.on_candle(Candle(BASE,100,102,99,100,10))
            engine.place_buy(50,client_id='test_buy')
            engine.on_candle(Candle(BASE+STEP,100,103,99,101,10))
            engine.place_sell(client_id='test_sell')
            engine.on_candle(Candle(BASE+2*STEP,105,106,104,105,10))
            self.assertEqual(len(engine.trades()),1)

    def test_missing_dbs_no_creation_no_fabricated_zero(self):
        v=read_snapshot(self.src,now=BASE+STEP)
        self.assertIsNone(v['account'])
        self.assertEqual(v['market'],[])
        self.assertIsNone(v['news'])
        self.assertIsNone(v['journal'])
        self.assertFalse(v['historical_profitability_verified'])
        self.assertFalse(any(p.exists() for p in [self.src.market,self.src.wallet,self.src.news,self.src.journal]))

    def test_real_wallet_ledger_net_and_fee_reconcile(self):
        self._paper()
        s=read_snapshot(self.src,now=BASE+3*STEP)
        a=s['account'];self.assertEqual(a['closed_trades'],1)
        self.assertIsNone(a['position'])
        self.assertAlmostEqual(a['cash_quote'],a['initial_quote']+a['realized_net_quote'])
        self.assertAlmostEqual(a['realized_gross_quote']-a['total_costs_quote'],a['realized_net_quote'],places=6)
        self.assertAlmostEqual(a['total_estimated_net_quote'],a['realized_net_quote'])
        self.assertAlmostEqual(a['trades'][0]['entry_fee_quote']+a['trades'][0]['exit_fee_quote'],a['trades'][0]['fees_quote'])
        self.assertEqual(a['mode'],'PAPER_ONLY')

    def test_open_position_mark_to_net_liquidation(self):
        with PaperEngine(self.src.wallet) as engine:
            engine.on_candle(Candle(BASE,100,101,99,100,10))
            engine.place_buy(50)
            engine.on_candle(Candle(BASE+STEP,100,102,99,101,10))
            self.assertIsNotNone(engine.status()['position'])
            expected=engine.status()['equity_net_quote']
        got=read_snapshot(self.src,now=BASE+2*STEP)['account']
        self.assertAlmostEqual(got['equity_net_quote'],expected,places=7)
        self.assertAlmostEqual(got['estimated_unrealized_net_quote'],got['equity_net_quote']-got['initial_quote'])
        self.assertGreater(got['position']['quantity_btc'],0)

    def test_risk_halt_and_stale(self):
        with PaperEngine(self.src.wallet) as engine:
            engine.on_candle(Candle(BASE,100,101,99,100,10))
            engine.place_buy(50)
            engine.on_candle(Candle(BASE+STEP,100,100,92,93,10))
            # A single small trade could not trigger the whole-wallet halt; direct DB fixtures can.
        with sqlite3.connect(self.src.wallet) as db:
            db.execute('UPDATE wallet SET halted_reason=? WHERE id=1',('test_risk_lock',));db.commit()
        out=read_snapshot(self.src,now=BASE+10*STEP)
        self.assertTrue(any('risk lock ACTIVE' in x for x in out['warnings']))
        self.assertTrue(any('price is stale' in x for x in out['warnings']))

    def test_corrupt_wallet_does_not_report_fake_zero(self):
        self.src.wallet.write_bytes(b'not a valid sqlite file')
        out=read_snapshot(self.src)
        self.assertIsNone(out['account'])
        self.assertTrue(any('inconsistent' in x for x in out['warnings']))

    def test_reads_market_news_health_but_never_creates_missing_wallet(self):
        with CandleStore(self.src.market) as market:
            market.upsert('kraken','BTC/AUD',240,[Candle(BASE,100,105,90,101,5),Candle(BASE+2*STEP,102,110,100,104,7)],source='kraken_csv:SYNTHETIC_UNIT_TEST')
        with NewsStore(self.src.news) as news:
            news.ingest([{'source':'test','url':'https://example.com/bitcoin-news-growth',
                'headline':'Bitcoin ETF fund inflows accelerate', 'published_ts':BASE,'first_seen_ts':BASE+60}])
            news.record_feed_attempt('test', BASE+STEP, success=True)
        with DecisionJournal(self.src.journal) as journal:
            journal.heartbeat('OK','sample-only',BASE+3*STEP)
            journal.log(BASE,'HOLD','test',{'paper_only':True},BASE+STEP)
        out=read_snapshot(self.src,now=BASE+3*STEP)
        self.assertEqual(out['market'][0]['candle_count'],2)
        self.assertEqual(out['market'][0]['missing_interval_count'],1)
        self.assertEqual(len(out['news']['articles']),1)
        self.assertEqual(out['journal']['decisions'][0]['decision'],'HOLD')
        self.assertTrue(any('gaps detected' in x for x in out['warnings']))
        self.assertFalse(self.src.wallet.exists())

    def test_query_only_no_db_changes(self):
        self._paper()
        before=hashlib.sha256(self.src.wallet.read_bytes()).hexdigest()
        before_st=self.src.wallet.stat().st_mtime_ns
        for _ in range(3):read_snapshot(self.src,now=BASE+3*STEP)
        self.assertEqual(hashlib.sha256(self.src.wallet.read_bytes()).hexdigest(),before)
        self.assertEqual(self.src.wallet.stat().st_mtime_ns,before_st)

    def test_readonly_account_reconciliation_error_is_not_hidden(self):
        self._paper()
        with sqlite3.connect(self.src.wallet) as db:
            db.execute('UPDATE wallet SET cash=cash+100 WHERE id=1');db.commit()
        out=read_snapshot(self.src)
        self.assertIsNone(out['account'])
        self.assertTrue(any('account: unavailable' in x for x in out['warnings']))

    def test_http_only_get_and_dns_rebinding_protection(self):
        self._paper()
        server=ThreadingHTTPServer(('127.0.0.1',0),handler_for(self.src))
        t=threading.Thread(target=server.serve_forever,daemon=True);t.start()
        try:
            port=server.server_address[1]
            def call(method,path,host='127.0.0.1'):
                c=http.client.HTTPConnection('127.0.0.1',port,timeout=5)
                c.request(method,path,headers={'Host':host})
                r=c.getresponse();body=r.read();status=r.status;headers=dict(r.getheaders());c.close();return status,body,headers
            status,body,headers=call('GET','/api/status')
            self.assertEqual(status,200)
            self.assertEqual(json.loads(body)['account']['closed_trades'],1)
            self.assertEqual(headers['Cache-Control'],'no-store')
            self.assertIn("default-src 'none'",headers['Content-Security-Policy'])
            for method in ('POST','PUT','PATCH','DELETE'):
                self.assertEqual(call(method,'/api/status')[0],405)
            self.assertEqual(call('GET','/api/status','attacker.example')[0],403)
            self.assertEqual(call('GET','/bad')[0],404)
            self.assertEqual(call('GET','/api/status?command=buy')[0],400)
            self.assertEqual(call('GET','/')[0],200)
            self.assertEqual(call('GET','/app.js')[0],200)
        finally:
            server.shutdown();server.server_close();t.join(5)

    def test_public_host_refused(self):
        with self.assertRaises(SystemExit):main(['--host','0.0.0.0'])

if __name__=='__main__':unittest.main()

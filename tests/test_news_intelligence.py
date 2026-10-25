"""Roadmap 6: news availability firewall and non-fabricated fee-aware labels."""
from dataclasses import replace
from datetime import datetime,timezone
from email.message import Message
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock
from data_layer.storage import CandleStore,Candle
from news_intelligence.feeds import FeedSource,parse_feed,fetch_feed
from news_intelligence.store import NewsStore
from news_intelligence.signals import classify,event_study,train_signal_quality,event_signal_asof,category_impact_summary
from news_intelligence.cli import study_from_dbs,sync
from trading_costs import FeeSettings

BASE=int(datetime(2026,1,1,tzinfo=timezone.utc).timestamp())
STEP=14400
RSS=b'''<rss version="2.0"><channel><item><title>Bitcoin ETF approval boosts inflows</title>
<link>https://www.coindesk.com/markets/test-article?utm_source=x</link>
<description>Institutional adoption grows</description>
<pubDate>Thu, 01 Jan 2026 04:00:00 GMT</pubDate></item></channel></rss>'''
ATOM=b'''<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Bitcoin exchange hack crash</title>
<link rel="alternate" href="https://cointelegraph.com/news/sample"/>
<published>2026-01-01T08:00:00Z</published><summary>stolen bitcoin</summary></entry></feed>'''

def bars(num=60,step_change=.5):
    return [Candle(BASE+i*STEP,100+i*step_change,100+i*step_change+.1,
                   100+i*step_change-.1,100+i*step_change,10.) for i in range(num)]


class NewsModuleTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
    def tearDown(self):self.temp.cleanup()

    def test_rss_and_atom_have_timezone_and_first_observed(self):
        r=parse_feed(RSS,FeedSource('CoinDesk','https://www.coindesk.com/arc/outboundfeeds/rss/'),observed_at=BASE+3*STEP)
        self.assertEqual(r[0]['published_ts'],BASE+STEP)
        self.assertEqual(r[0]['first_seen_ts'],BASE+3*STEP)
        self.assertEqual(r[0]['headline'],'Bitcoin ETF approval boosts inflows')
        a=parse_feed(ATOM,FeedSource('Cointelegraph','https://cointelegraph.com/rss'),observed_at=BASE+3*STEP)
        self.assertEqual(a[0]['published_ts'],BASE+2*STEP)
        self.assertEqual(a[0]['url'],'https://cointelegraph.com/news/sample')

    def test_reject_entity_attack_oversize_bad_timestamps(self):
        src=FeedSource('CoinDesk','https://www.coindesk.com/arc/outboundfeeds/rss/')
        with self.assertRaises(ValueError):parse_feed(b'<!DOCTYPE x [<!ENTITY evil "malicious">]><rss/>',src,observed_at=BASE)
        with self.assertRaises(ValueError):parse_feed(b'x'*2_000_001,src,observed_at=BASE)
        self.assertEqual(parse_feed(RSS,src,observed_at=BASE),[])
        with self.assertRaises(ValueError):parse_feed(RSS,src,observed_at=BASE+3*STEP,limit=151)

    def test_news_idempotence_and_syndication(self):
        rows=parse_feed(RSS,FeedSource('CoinDesk','https://www.coindesk.com/arc/outboundfeeds/rss/'),observed_at=BASE+3*STEP)
        with NewsStore(self.root/'news.sqlite') as db:
            self.assertEqual(db.ingest(rows)['inserted'],1)
            self.assertEqual(db.ingest(rows)['duplicates'],1)
            copy={**rows[0],'source':'The Block','url':'https://www.theblock.co/sample','first_seen_ts':BASE+4*STEP}
            self.assertEqual(db.ingest([copy])['duplicates'],1)
            self.assertEqual(len(db.items()),1)
            self.assertEqual(db.items()[0].first_seen_ts,BASE+3*STEP)
            self.assertEqual(db.items()[0].available_ts,BASE+3*STEP)
            self.assertEqual(db.items()[0].categories,('etf','institutional'))
            self.assertEqual(db.items()[0].assets,('BTC',))

    def test_invalid_url_and_bad_first_seen_transaction_rollback(self):
        d=parse_feed(RSS,FeedSource('CoinDesk','https://www.coindesk.com/arc/outboundfeeds/rss/'),observed_at=BASE+3*STEP)[0]
        with NewsStore(self.root/'news.sqlite') as db:
            with self.assertRaises(ValueError):db.ingest([d,{**d,'url':'file:///etc/passwd'}])
            self.assertEqual(db.items(),[])
            with self.assertRaises(ValueError):db.ingest([{**d,'first_seen_ts':BASE}])
            self.assertEqual(db.items(),[])

    def test_fee_adjusted_prices_before_and_after_availability(self):
        with NewsStore(self.root/'news.sqlite') as db:
            db.ingest(parse_feed(RSS,FeedSource('CoinDesk','https://www.coindesk.com/arc/outboundfeeds/rss/'),observed_at=BASE+3*STEP))
            data=event_study(db.items(),bars(),interval=240,horizons_hours=(4,24))
        self.assertEqual(len(data['results']),2)
        ev=data['results'][0]
        self.assertEqual(ev['baseline_last_known_close_ts'],BASE+3*STEP)
        self.assertEqual(ev['future_close_ts'],BASE+4*STEP)
        self.assertAlmostEqual(ev['gross_change_pct'],100*(101.5/101-1),places=4)
        self.assertGreater(ev['trading_fees_quote'],0)
        self.assertLess(ev['fee_adjusted_net_return_pct'],ev['gross_change_pct'])
        self.assertEqual(category_impact_summary(data)[0]['observations'],1)
        with NewsStore(self.root/'news.sqlite') as db:
            free=event_study(db.items(),bars(),fee_settings=FeeSettings.zero(),horizons_hours=(4,))
        self.assertGreater(free['results'][0]['fee_adjusted_net_return_pct'],ev['fee_adjusted_net_return_pct'])

    def test_missing_prices_or_gaps_are_not_imputed(self):
        with NewsStore(self.root/'news.sqlite') as db:
            db.ingest(parse_feed(RSS,FeedSource('CoinDesk','https://www.coindesk.com/arc/outboundfeeds/rss/'),observed_at=BASE+3*STEP))
            news=db.items()
        with self.assertRaisesRegex(ValueError,'Empty'):event_study(news,[])
        bad=bars();del bad[9]
        with self.assertRaisesRegex(ValueError,'Gapped'):event_study(news,bad)

    def test_asof_maturity_blocks_future_candles_and_undiscovered_news(self):
        source=FeedSource('CoinDesk','https://www.coindesk.com/arc/outboundfeeds/rss/')
        with NewsStore(self.root/'news.sqlite') as news, CandleStore(self.root/'market.sqlite') as market:
            news.ingest(parse_feed(RSS,source,observed_at=BASE+3*STEP))
            market.upsert('kraken','BTC/AUD',240,bars(60),source='kraken_csv:synthetic_named_fixture')
        study=study_from_dbs(news_db=self.root/'news.sqlite',market_db=self.root/'market.sqlite',
                            interval=240,horizons_hours=(4,),as_of_ts=BASE+3*STEP)
        self.assertEqual(study['market_candles'],3)
        self.assertEqual(study['results'],[])
        # Future data still not counted if as-of is before a candle's CLOSE.
        future=study_from_dbs(news_db=self.root/'news.sqlite',market_db=self.root/'market.sqlite',
                             interval=240,horizons_hours=(4,),as_of_ts=BASE+4*STEP)
        self.assertEqual(len(future['results']),1)
        self.assertEqual(future['results'][0]['future_close_ts'],BASE+4*STEP)
        with self.assertRaisesRegex(ValueError,'News database'):
            study_from_dbs(news_db=self.root/'news.sqlite',market_db=self.root/'market.sqlite',
                      interval=240,horizons_hours=(4,),as_of_ts=BASE+2*STEP)

    def test_signal_quality_purged_split_and_strict_asof(self):
        synth=[]
        for i in range(60):
            t=BASE+i*24*3600
            synth.append({'article_id':i,'category_tags':('etf',),'horizon_hours':24,
               'available_ts':t,'future_close_ts':t+24*3600,
               'fee_adjusted_net_return_pct':2.5 if i<56 else -3.0})
        data={'results':synth}
        q=train_signal_quality(data,as_of_ts=BASE+59*24*3600,horizon_hours=24)
        self.assertIn('etf',q['qualified_categories'])
        before=train_signal_quality(data,as_of_ts=BASE+30*24*3600,horizon_hours=24)
        self.assertNotIn('etf',before['qualified_categories'])
        with NewsStore(self.root/'news.sqlite') as db:
            db.ingest(parse_feed(RSS,FeedSource('CoinDesk','https://www.coindesk.com/arc/outboundfeeds/rss/'),observed_at=BASE+3*STEP))
            article=db.items()[0]
        self.assertEqual(event_signal_asof(article,q,decision_ts=BASE+5*STEP)['bias'],'unavailable')
        valid_quality={**q,'as_of_ts':BASE+2*STEP}
        self.assertEqual(event_signal_asof(article,valid_quality,decision_ts=BASE+5*STEP)['bias'],'research_candidate_long')

    def test_one_feed_failure_does_not_abort_other_sources(self):
        def fake(feed,**kwargs):
            if feed.name=='CoinDesk':raise TimeoutError('timed out')
            return {'items':[],'not_modified':True}
        with NewsStore(self.root/'news.sqlite') as db:
            result=sync(db,now=BASE+3*STEP,fetcher=fake)
            self.assertEqual(result['feeds'][0]['status'],'error')
            self.assertEqual(len(result['feeds']),5)
            self.assertEqual(db.db.execute("SELECT last_error FROM feed_state WHERE feed='CoinDesk'").fetchone()[0],
                             'TimeoutError: timed out')


    def test_btc_first_asset_filter_excludes_unrelated_altcoin(self):
        articles=[{'source':'test','url':'https://cointelegraph.com/solana-sample',
             'headline':'Solana token rallies despite network interruption',
             'published_ts':BASE+STEP,'first_seen_ts':BASE+3*STEP},
            {'source':'test','url':'https://cointelegraph.com/rates-sample',
             'headline':'Federal Reserve interest rate change',
             'published_ts':BASE+STEP,'first_seen_ts':BASE+4*STEP}]
        with NewsStore(self.root/'news.sqlite') as db:
            db.ingest(articles)
            by_head={z.headline:z for z in db.items()}
            self.assertEqual(by_head['Solana token rallies despite network interruption'].assets,('SOL',))
            self.assertIn('MACRO',by_head['Federal Reserve interest rate change'].assets)
            report=event_study(db.items(),bars(),horizons_hours=(4,))
            self.assertEqual(len(report['results']),1)
            self.assertEqual(report['skipped']['unrelated_to_btc'],1)

    def test_http304_and_conditional_headers(self):
        from urllib.error import HTTPError
        src=FeedSource('CoinDesk','https://www.coindesk.com/arc/outboundfeeds/rss/')
        captured=[]
        def fake_opener(request,timeout):
            captured.append(request)
            raise HTTPError(src.url,304,'Not Modified',Message(),None)
        got=fetch_feed(src,observed_at=BASE+2*STEP,etag='some-etag',opener=fake_opener)
        self.assertTrue(got['not_modified'])
        self.assertEqual(captured[0].get_header('If-none-match'),'some-etag')
        with self.assertRaises(ValueError):fetch_feed(FeedSource('unknown','https://evil.invalid/rss'),opener=fake_opener)

    def test_no_real_market_db_refused(self):
        with NewsStore(self.root/'news.sqlite') as db:
            db.ingest(parse_feed(RSS,FeedSource('CoinDesk','https://www.coindesk.com/arc/outboundfeeds/rss/'),observed_at=BASE+3*STEP))
        with self.assertRaisesRegex(ValueError,'must exist'):
            study_from_dbs(news_db=self.root/'news.sqlite',market_db=self.root/'nonexistent.sqlite',
                          interval=240,horizons_hours=(4,),as_of_ts=BASE+5*STEP)

if __name__=='__main__':unittest.main()

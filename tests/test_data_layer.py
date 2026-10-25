"""Deterministic offline tests. Mock external network; no exchange orders."""
import csv
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import Mock
from data_layer.storage import Candle,CandleStore,import_kraken_zip,import_csv,ingest_stream
from data_layer.kraken import KrakenOHLC,KrakenError,sync


class HTTP:
    def __init__(self,body,status=200,headers=None):
        self.body=body;self.status_code=status;self.headers=headers or {}
    def raise_for_status(self):
        if self.status_code>=400:raise ValueError('HTTP failure')
    def json(self):return self.body


def krrow(ts,price=100):return [ts,str(price),str(price+2),str(price-2),str(price+1),'100','0.5',15]


class DataLayerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.db=CandleStore(Path(self.tmp.name)/'market.db')
    def tearDown(self):self.db.close();self.tmp.cleanup()

    def test_import_valid_archive_and_report_gaps(self):
        p=Path(self.tmp.name)/'XBTAUD_240.csv'
        p.write_text('14401,100,105,99,101,0.5,5\n43200,101,107,100,106,0.9,10\n')
        # Aligned timestamps; gap of one missing 4h candle.
        with self.assertRaises(ValueError):import_csv(self.db,p,240)
        # Valid known 4h aligned seconds.
        p.write_text('14400,100,105,99,101,0.5,5\n43200,101,107,100,106,0.9,10\n')
        z=import_csv(self.db,p,240)
        self.assertEqual(z['written'],2)
        self.assertEqual(self.db.coverage(interval=240)['n'],2)
        gaps=self.db.gaps(interval=240)
        self.assertEqual(gaps[0]['missing_intervals'],1)
        self.assertEqual(gaps[0]['status'],'UNKNOWN_GAP_OR_ZERO_TRADES')
        self.assertEqual(import_csv(self.db,p,240)['written'],2)
        self.assertEqual(self.db.coverage(interval=240)['n'],2)

    def test_chunked_idempotent_import(self):
        import io
        stream=io.StringIO('14400,100,102,99,101,1,1\n28800,101,103,100,102,1,2\n')
        report=ingest_stream(self.db,stream,240,'archive-chunk',chunk_size=1)
        self.assertEqual(report['received'],2)
        self.assertEqual(self.db.coverage(interval=240)['n'],2)
        stream.seek(0)
        report=ingest_stream(self.db,stream,240,'archive-chunk',chunk_size=1)
        self.assertEqual(report['received'],2)
        self.assertEqual(self.db.coverage(interval=240)['n'],2)

    def test_validation_transaction_rolls_back_all_rows(self):
        candles=[Candle(14400,100,102,99,101,1,2),Candle(28800,100,90,99,101,1,2)]
        with self.assertRaises(ValueError):self.db.upsert('kraken','BTC/AUD',240,candles,'test')
        self.assertEqual(self.db.coverage(interval=240)['n'],0)

    def test_csv_filename_cannot_mislabel_btc_usd_as_aud(self):
        wrong=Path(self.tmp.name)/'XBTUSD_240.csv'
        wrong.write_text('14400,100,101,99,100,1,1\n')
        with self.assertRaises(ValueError):import_csv(self.db,wrong,240)
        self.assertEqual(self.db.coverage(interval=240)['n'],0)

    def test_prevent_cross_exchange_or_pair_contamination(self):
        candle=[Candle(14400,100,102,99,101,1,2)]
        with self.assertRaises(ValueError):self.db.upsert('binance','BTC/AUD',240,candle,'incorrect')
        with self.assertRaises(ValueError):self.db.upsert('kraken','BTC/USDT',240,candle,'incorrect')

    def test_zip_import_selects_only_requested_pair_and_interval(self):
        z=Path(self.tmp.name)/'q3.zip'
        with zipfile.ZipFile(z,'w') as f:
            f.writestr('XBTUSD_240.csv','14400,100,101,99,100,1,1\n')
            f.writestr('nested/XXBTZAUD_240.csv','14400,100,101,99,100,1,1\n')
            f.writestr('XXBTZAUD_60.csv','3600,100,101,99,100,1,1\n')
        imported=import_kraken_zip(self.db,z,[240])
        self.assertEqual(len(imported),1)
        self.assertEqual(self.db.coverage(interval=240)['n'],1)
        self.assertEqual(self.db.coverage(interval=60)['n'],0)

    def test_drop_in_progress_candle_and_upsert(self):
        now=14400*4+60
        data={'error':[],'result':{'XXBTZAUD':[krrow(14400),krrow(28800),krrow(57600)],'last':57600}}
        api=KrakenOHLC(session=Mock(get=Mock(return_value=HTTP(data))),clock=lambda:now,sleep=lambda _:None,retries=2)
        result=sync(self.db,api,240)
        self.assertEqual(result['dropped_open'],1)
        self.assertEqual(self.db.coverage(interval=240)['n'],2)
        self.assertIn('API_LAST_720_ONLY_IMPORT_KRAKEN_ARCHIVE_FOR_LONG_HISTORY',result['warnings'])
        self.assertEqual(sync(self.db,api,240)['written'],2)

    def test_rate_limit_retries_then_succeeds(self):
        data={'error':[],'result':{'XXBTZAUD':[krrow(14400)],'last':14400}}
        sess=Mock(get=Mock(side_effect=[HTTP({},429,{'Retry-After':'2'}),HTTP(data)]))
        wait=[]
        api=KrakenOHLC(session=sess,clock=lambda:40000,sleep=wait.append,min_interval=0,retries=3)
        self.assertEqual(len(api.fetch(240)['closed']),1)
        self.assertEqual(wait,[2.])

    def test_non_transient_exchange_error_fails(self):
        body={'error':['EQuery:Unknown asset pair'],'result':{}}
        api=KrakenOHLC(session=Mock(get=Mock(return_value=HTTP(body))),clock=lambda:40000,sleep=lambda _:None)
        with self.assertRaises(KrakenError):api.fetch(240)

    def test_history_gap_detected(self):
        self.db.upsert('kraken','BTC/AUD',240,[Candle(14400,100,101,99,100,1,1)],'archive')
        data={'error':[],'result':{'XXBTZAUD':[krrow(14400*5),krrow(14400*6)],'last':14400*6}}
        api=KrakenOHLC(session=Mock(get=Mock(return_value=HTTP(data))),clock=lambda:14400*8,sleep=lambda _:None)
        result=sync(self.db,api,240)
        self.assertIn('UNBRIDGED_API_HISTORY_GAP_IMPORT_ARCHIVE_OR_TRADES',result['warnings'])
        self.assertEqual(self.db.coverage(interval=240)['n'],3)

    def test_export_retains_raw_utc(self):
        self.db.upsert('kraken','BTC/AUD',240,[Candle(14400,100,101,99,100,1,2)],'test')
        path=Path(self.tmp.name)/'out.csv'
        self.assertEqual(self.db.export_csv(path,interval=240),1)
        with path.open() as f:
            self.assertEqual(list(csv.DictReader(f))[0]['timestamp'],'14400')

if __name__=='__main__':unittest.main()

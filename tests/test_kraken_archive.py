"""Deterministic safety controls. Synthetic candles are NEVER market evidence."""
import io
import tempfile
import unittest
import zipfile
from pathlib import Path
from research.kraken_archive import (
    MultipartReader, member_name, parse_csv, latest_contiguous, load, run_experiment, STEP)

class KrakenArchiveTest(unittest.TestCase):
    def test_multipart_zip_crosses_part_boundaries(self):
        out=io.BytesIO()
        with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
            z.writestr('MANIFEST.json','{"fixture":true}')
            z.writestr('candles/XBTAUD_240.csv','14400,1,2,1,2,3,1\n')
        raw=out.getvalue()
        parts=[raw[:19],raw[19:87],raw[87:]]
        stream=MultipartReader([len(x) for x in parts],
            lambda i,start,n:parts[i][start:start+n])
        with zipfile.ZipFile(stream) as z:
            self.assertEqual(z.read(member_name(z.namelist())),
                b'14400,1,2,1,2,3,1\n')
        self.assertEqual(stream.seek(0,2),len(raw))
        self.assertEqual(stream.read(),b'')

    def test_ambiguous_member_rejected(self):
        with self.assertRaises(ValueError):
            member_name(['XBTAUD_240.csv','BTCAUD_240.csv'])

    def test_no_gap_fabrication(self):
        bars=[(i*STEP,100,101,99,100,1) for i in (1,2,3,7,8,9)]
        # No segment is long enough; fail closed rather than interpolate prices.
        with self.assertRaises(ValueError):
            latest_contiguous(bars)

    def test_invalid_candle_and_duplicate_rejected(self):
        with self.assertRaisesRegex(ValueError,'invalid'):
            parse_csv(b'14400,100,99,98,100,1,2\n')
        with self.assertRaisesRegex(ValueError,'Duplicate'):
            parse_csv(b'14400,100,101,99,100,1,2\n'*1000)

    def test_offline_fixture_is_explicitly_not_verified_market(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'fixture.csv'
            p.write_text(''.join(
                f'{(i+1)*STEP},100,102,99,101,1,2\n' for i in range(1500)))
            bars,prov=load(p)
            self.assertEqual(len(bars),1500)
            self.assertEqual(prov['gap_count'],0)
            self.assertEqual(prov['source'],'LOCAL_FIXTURE_NOT_VERIFIED_MARKET')

    def test_train_validation_test_embargo_and_net_fields(self):
        # This test is protocol-only, NOT a profitability result.
        bars=[]
        for i in range(1800):
            p=100+i*.01
            bars.append(((i+1)*STEP,p,p+1,p-1,p+.1,1))
        report=run_experiment(bars,{'source':'SYNTHETIC_TEST'})
        self.assertLess(report['train_end_utc'],report['validation_start_utc'])
        self.assertLess(report['validation_end_utc'],report['test_start_utc'])
        self.assertEqual(len(report['test_folds']),2)
        self.assertEqual(report['promotion'].startswith('REJECTED'),True)
        for fold in report['test_folds']:
            self.assertIn('sma',fold['strategies'])
            self.assertIn('net_aud',fold['strategies']['sma'])
            self.assertIn('fees_aud',fold['strategies']['sma'])
            self.assertIn('max_drawdown_pct',fold['strategies']['sma'])

if __name__=='__main__': unittest.main()

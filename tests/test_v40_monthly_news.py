"""V40 bounded source requests and no fabricated historical first-observed."""
import sys
import types
import unittest
from unittest.mock import patch
from research.v40_monthly_news import candidate_months,sample_months,build,MAX_MONTHS_PER_RUN

class V40NewsTests(unittest.TestCase):
    def fake_module(self):
        fake=types.ModuleType('research.v38_archive_ingest')
        fake.MONTHS=('2020-01',)
        fake.merge=lambda rows:sorted(rows,key=lambda r:r['canonical_url'])
        fake.join_market=lambda rows,bars:{'retrospective_time_aligned':0,'strict_asof_eligible':0}
        return fake

    def test_months_calendar_not_price_selected(self):
        months=candidate_months()
        self.assertEqual(len(months),MAX_MONTHS_PER_RUN)
        self.assertEqual(months[0],'2020-02')
        self.assertEqual(months[6],'2026-02')
        self.assertEqual(len(set(months)),len(months))
        self.assertTrue(all(int(m[-2:]) not in (1,4,7,10) for m in months))
        with self.assertRaises(ValueError):candidate_months(13)

    def test_bounded_fetch_restores_original_months(self):
        fake=self.fake_module();seen=[]
        def fetch(source,at):
            m=fake.MONTHS[0];seen.append(m)
            return ([{'canonical_url':'https://example.com/'+m,
                'source_ids':['cryptocurrency_cv'],
                'published_at_utc':m+'-12T12:00:00+00:00',
                'first_verified_capture_at_utc':None}], 'OK_DATE_FILTERS_VERIFIED')
        with patch.dict(sys.modules,{'research.v38_archive_ingest':fake}):
            from research import v38_archive_ingest
            with patch.object(v38_archive_ingest,'MONTHS',('2020-01',)):
                rows,status=sample_months(candidate_months(3),
                    '2026-11-11T00:00:00+00:00',fetch)
                self.assertEqual(v38_archive_ingest.MONTHS,('2020-01',))
        self.assertEqual(len(rows),3)
        self.assertEqual(len(seen),3)
        self.assertTrue(all(s['ok'] for s in status.values()))

    def test_month_mismatch_never_counted(self):
        fake=self.fake_module()
        def bad(source,at):
            return ([{'source_ids':['cryptocurrency_cv'],
                'published_at_utc':'2024-12-31T23:00:00+00:00'}],
                'OK_DATE_FILTERS_VERIFIED')
        with patch.dict(sys.modules,{'research.v38_archive_ingest':fake}):
            rows,status=sample_months(candidate_months(1),
                '2026-11-11T00:00:00+00:00',bad)
        self.assertEqual(rows,[])
        self.assertFalse(next(iter(status.values()))['ok'])

    def test_claimed_capture_rejected(self):
        fake=self.fake_module()
        def bad(source,at):
            return ([{'source_ids':['cryptocurrency_cv'],
                'published_at_utc':'2020-02-01T00:00:00+00:00',
                'first_verified_capture_at_utc':'2020-02-01T00:00:00+00:00'}],
                'OK_DATE_FILTERS_VERIFIED')
        with patch.dict(sys.modules,{'research.v38_archive_ingest':fake}):
            rows,status=sample_months(candidate_months(1),
                '2026-11-11T00:00:00+00:00',bad)
        self.assertEqual(rows,[])
        self.assertFalse(next(iter(status.values()))['ok'])

    def test_audit_preserves_paper_safety(self):
        fake=self.fake_module()
        def empty(source,at):return [],'OK_DATE_FILTERS_VERIFIED'
        with patch.dict(sys.modules,{'research.v38_archive_ingest':fake}):
            report=build(candidate_months(1),'2026-11-11T00:00:00+00:00',empty)
        self.assertEqual(report['android_strategy'],'HOLD')
        self.assertEqual(report['max_paper_entry_aud'],100)
        self.assertEqual(report['historically_verified_capture_rows'],0)
        self.assertEqual(report['historical_article_version_rows'],0)
        self.assertFalse(report['target_met'])

    def test_too_many_or_duplicate_requests_blocked(self):
        fake=self.fake_module()
        with patch.dict(sys.modules,{'research.v38_archive_ingest':fake}):
            with self.assertRaises(ValueError):
                sample_months(candidate_months()+('2021-03',),
                              '2026-11-11T00:00:00+00:00')
            with self.assertRaises(ValueError):
                sample_months(('2020-02','2020-02'),'2026-11-11T00:00:00+00:00')

if __name__=='__main__':unittest.main()

"""V28 deterministic causal, gap and first-observed corpus regressions."""
import hashlib
from pathlib import Path
import sqlite3
import tempfile
import unittest
from news_intelligence.corpus import build, merge, read_existing
from research.v28_recent_bridge import bridge_window, CUTOFF, STEP


def rows(n, start):
    return [(start+i*STEP, 100., 101., 99., 100., 1.) for i in range(n)]


class V28BridgeTest(unittest.TestCase):
    def test_post_archive_window_never_uses_future_to_select(self):
        bars = rows(240, CUTOFF-220*STEP)
        self.assertEqual(bridge_window(bars), (220, 240))
        self.assertEqual(bridge_window(bars+rows(3, bars[-1][0]+STEP))[0], 220)

    def test_no_missing_bar_or_insufficient_warmup(self):
        bars = rows(240, CUTOFF-220*STEP)
        with self.assertRaisesRegex(ValueError, 'Missing'):
            bridge_window(bars[:225]+bars[226:])
        with self.assertRaisesRegex(ValueError, 'warmup'):
            bridge_window(rows(206, CUTOFF-200*STEP))
        with self.assertRaisesRegex(ValueError, 'No bars beyond'):
            bridge_window(rows(210, CUTOFF-250*STEP))

    def test_short_future_refused(self):
        with self.assertRaisesRegex(ValueError, 'Insufficient post-cutoff'):
            bridge_window(rows(222, CUTOFF-220*STEP))


class V28CorpusTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.now = 1793600000
        self.old = {'source':'CoinDesk','url':'https://www.coindesk.com/a?utm_source=x',
                    'headline':'Bitcoin network update from exchange','summary':'',
                    'published_ts':1793500000,'first_seen_ts':1793501000}

    def tearDown(self):
        self.tmp.cleanup()

    def db(self, name, rows):
        path = self.root/name
        with sqlite3.connect(path) as db:
            db.execute('CREATE TABLE news (source TEXT,url TEXT,headline TEXT,summary TEXT,published_ts INTEGER,first_seen_ts INTEGER)')
            for r in rows:
                db.execute('INSERT INTO news VALUES (?,?,?,?,?,?)',tuple(r[k] for k in
                    ('source','url','headline','summary','published_ts','first_seen_ts')))
        return path

    def test_snapshot_merges_earliest_evidenced_observation_and_is_idempotent(self):
        earlier = self.db('v26.sqlite',[self.old])
        later = dict(self.old,url='https://www.coindesk.com/a',first_seen_ts=1793502000)
        second = dict(self.old,url='https://www.coindesk.com/b',first_seen_ts=1793503000)
        newer = self.db('v27.sqlite',[later,second])
        output = self.root/'firstseen.jsonl'
        manifest = self.root/'manifest.json'
        report = build(existing=output,snapshots=[earlier,newer],output=output,
                       manifest=manifest,now=self.now)
        self.assertEqual(report['unique_cumulative_rows'],2)
        self.assertEqual(report['snapshot_rows'],3)
        self.assertEqual(read_existing(output,now=self.now)[0]['first_seen_ts'],1793501000)
        self.assertEqual(report['corpus_sha256'],hashlib.sha256(output.read_bytes()).hexdigest())
        repeat = build(existing=output,snapshots=[newer],output=output,
                       manifest=manifest,now=self.now)
        self.assertEqual(repeat['corpus_sha256'],report['corpus_sha256'])
        self.assertEqual(repeat['unique_cumulative_rows'],2)

    def test_reject_future_first_seen_or_non_https(self):
        bad = dict(self.old,first_seen_ts=self.now+1000)
        with self.assertRaisesRegex(ValueError,'future-dated'):
            merge([], [bad],now=self.now)
        bad = dict(self.old,url='http://www.coindesk.com/a')
        with self.assertRaisesRegex(ValueError,'HTTPS'):
            merge([], [bad],now=self.now)

    def test_reject_missing_schema(self):
        path = self.root/'bad.sqlite'
        with sqlite3.connect(path) as db:
            db.execute('CREATE TABLE news (headline TEXT)')
        with self.assertRaisesRegex(ValueError,'schema'):
            build(existing=self.root/'missing',snapshots=[path],output=self.root/'out',
                  manifest=self.root/'manifest',now=self.now)

if __name__=='__main__': unittest.main()

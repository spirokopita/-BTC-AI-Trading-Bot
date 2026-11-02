"""V31 synthetic news provenance and market-control tests."""
import json, tempfile, unittest
from pathlib import Path
from research.v31_news_coverage import KIND, DAY, parse_news, run
from tests.test_v30_matched_news import candles

def item(id,pub,cluster,polarity=0):
    return dict(id=id,published_at_utc=pub,category="fixture",polarity=polarity,
        cluster=cluster,source="fixture",url="https://example.org/"+id,
        displayed_time="UTC",market_following=False)

class TestV31News(unittest.TestCase):
    def parse(self,articles):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"news.json"
            p.write_text(json.dumps(dict(dataset_type=KIND,articles=articles)))
            return parse_news(p)
    def test_cluster_dedup_and_24h_latency(self):
        a,info=self.parse([item("a","2022-01-01T00:00:00Z","one"),
            item("b","2022-01-01T01:00:00Z","one"),
            item("c","2022-01-02T00:00:00Z","two")])
        self.assertEqual(info["raw_articles"],3)
        self.assertEqual(info["unique_clusters"],2)
        self.assertEqual(a[0]["available_ts"],1641081600)
    def test_updated_version_delays_availability(self):
        x=item("a","2022-01-01T00:00:00Z","one")
        x["updated_at_utc"]="2022-01-02T00:00:00Z"
        a,_=self.parse([x])
        self.assertEqual(a[0]["available_ts"],1641168000)
    def test_duplicate_url_fails(self):
        a=item("a","2022-01-01T00:00:00Z","one")
        b=dict(a,id="b")
        with self.assertRaisesRegex(ValueError,"duplicate"):
            self.parse([a,b])
    def test_no_future_controls_for_new_news(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"news.json"
            start=candles(1200)[800][0]
            from datetime import datetime, timezone
            pub=datetime.fromtimestamp(start-DAY-10,timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            p.write_text(json.dumps(dict(dataset_type=KIND,articles=[item("a",pub,"one")])))
            bars=candles(1200)
            report=run(bars,p,{"source":"SYNTHETIC"})
            self.assertEqual(report["selection"],"HOLD")
            for row in report["matched"]["rows"]:
                self.assertTrue(all(t<row["event_open_ts"] for t in row["control_open_ts"]))
                self.assertGreaterEqual(row["event_open_ts"],row["available_ts"])

if __name__=="__main__":unittest.main()

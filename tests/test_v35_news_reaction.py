"""Deterministic V35 paper-only event-reaction safety and provenance tests."""
import json, tempfile, unittest
from pathlib import Path
from research.v35_news_reaction import (
    KIND, load_articles, candidate_indices, replay_events, THRESHOLDS, STEP)

def bars(n=500):
    out=[]
    for i in range(n):
        p=100.
        if i==351: p=102.
        if 352<=i<=356: p=103.
        if i>=357: p=105.
        close=102. if i==350 else p
        out.append((1700000000+i*STEP,p,max(p,close),min(p,close),close,1.))
    return out

def event(b,i=350):
    return [dict(id="event",available_ts=b[i][0],source_kind="ordinary_article")]

class V35Tests(unittest.TestCase):
    def test_news_revision_delay_and_market_following_exclusion(self):
        obj=dict(dataset_type=KIND,articles=[
            dict(id="a",url="https://example.org/a",published_at_utc="2022-01-01T00:00:00Z",
                 updated_at_utc="2022-01-03T00:00:00Z",category="policy",market_following=False),
            dict(id="b",url="https://example.org/b",published_at_utc="2022-01-01T00:00:00Z",
                 category="price_recap",market_following=True)])
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"news.json";path.write_text(json.dumps(obj))
            ev,prov=load_articles(path)
        self.assertEqual(len(ev),1)
        self.assertEqual(prov["excluded_market_following"],1)
        from research.v29_point_in_time import ts
        self.assertEqual(ev[0]["available_ts"],ts("2022-01-04T00:00:00Z"))

    def test_reaction_requires_completed_bar(self):
        b=bars()
        r=replay_events(b,305,450,event(b),.005,audit=True)
        self.assertEqual(r["trades"],1)
        row=r["trade_audit"][0]
        self.assertEqual(row["observed_reaction_open_ts"],b[350][0])
        self.assertEqual(row["decision_ts"],b[351][0])
        self.assertEqual(row["exit_ts"],b[357][0])
        self.assertGreater(row["net"],0)

    def test_future_prices_do_not_change_earlier_decision(self):
        b=bars()
        first=replay_events(b,305,450,event(b),.005,audit=True)
        b[357]=(b[357][0],90.,90.,90.,90.,1.)
        second=replay_events(b,305,450,event(b),.005,audit=True)
        self.assertEqual(first["trade_audit"][0]["decision_ts"],
                         second["trade_audit"][0]["decision_ts"])
        self.assertEqual(first["trade_audit"][0]["reaction_pct"],
                         second["trade_audit"][0]["reaction_pct"])
        self.assertLess(second["net_aud"],first["net_aud"])

    def test_future_news_is_not_traded(self):
        b=bars()
        ev=[dict(id="future",available_ts=b[460][0])]
        self.assertEqual(replay_events(b,305,450,ev,.005)["trades"],0)

    def test_delayed_placebos_cannot_move_news_earlier(self):
        b=bars(700)
        ev=event(b)
        base=candidate_indices(b,305,650,ev,0)[0][0]
        week=candidate_indices(b,305,650,ev,7*86400)[0][0]
        month=candidate_indices(b,305,650,ev,28*86400)[0][0]
        self.assertEqual(week-base,42)
        self.assertEqual(month-base,168)

    def test_gaps_fail_closed(self):
        b=bars()
        b[340]=(b[340][0]+STEP,*b[340][1:])
        with self.assertRaises(ValueError):
            replay_events(b,305,450,event(b),.005)

    def test_fee_audit_and_caps_and_negative_losses(self):
        b=bars()
        b[357]=(b[357][0],99.,99.,99.,99.,1.)
        r=replay_events(b,305,450,event(b),.005,audit=True)
        self.assertEqual(r["trades"],1)
        self.assertEqual(r["losses"],1)
        t=r["trade_audit"][0]
        self.assertLessEqual(t["entry_debit_aud"],100+1e-8)
        self.assertLessEqual(t["entry_debit_aud"],.1*t["cash_before_entry_aud"]+1e-8)
        self.assertAlmostEqual(t["gross"]-t["fees"]-t["spread"]-t["slippage"],t["net"])
        self.assertAlmostEqual(r["net_aud"],round(t["net"],6))

    def test_aud50_vs_aud100_and_invalid_limits(self):
        b=bars()
        small=replay_events(b,305,450,event(b),.005,max_entry_debit=50,audit=True)
        large=replay_events(b,305,450,event(b),.005,max_entry_debit=100,audit=True)
        self.assertLessEqual(small["trade_audit"][0]["entry_debit_aud"],50+1e-8)
        self.assertLessEqual(large["trade_audit"][0]["entry_debit_aud"],100+1e-8)
        self.assertGreater(large["net_aud"],small["net_aud"])
        with self.assertRaises(ValueError):
            replay_events(b,305,450,event(b),.005,max_entry_debit=101)

if __name__=="__main__":
    unittest.main()

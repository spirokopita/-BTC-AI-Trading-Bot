"""V36 deterministic leakage, cost, gap, provenance and selection tests."""
import math
import unittest
from research.v29_point_in_time import STEP
from research.v36_volatility_news_gates import (
    SPECS, SELECTABLE, available_article, volatility_ratio,
    make_veto, replay_variant, choose, coverage)

def bars(n=520):
    out=[]
    for i in range(n):
        p=100*math.exp(.0008*i)*(1+.001*math.sin(i*.27))
        out.append((1700000000+i*STEP,p,p*1.002,p*.998,p,1.))
    return out

class V36Tests(unittest.TestCase):
    def test_registered_variants_are_explicit_and_paper_only(self):
        self.assertIn("h80_edge25_vol15_news7d",SPECS)
        self.assertNotIn("h80_edge25_vol15_placebo7d",SELECTABLE)
        with self.assertRaises(ValueError):
            make_veto(bars(),[],"unknown")

    def test_volatility_uses_completed_bars_only(self):
        b=bars()
        before=volatility_ratio(b,350)
        b[350]=(b[350][0],999.,999.,999.,999.,1.)
        self.assertAlmostEqual(before,volatility_ratio(b,350),places=12)
        with self.assertRaises(ValueError):
            volatility_ratio(b,100)

    def test_future_prices_do_not_change_past_veto(self):
        b=bars()
        veto=make_veto(b,[],"h80_edge25_vol15")
        before=veto(b[350][0])
        b[400]=(b[400][0],1.,1.,1.,1.,1.)
        self.assertEqual(before,make_veto(b,[],"h80_edge25_vol15")(b[350][0]))

    def test_news_only_available_asof_and_delayed_placebo(self):
        b=bars()
        at=b[350][0]
        e=[dict(source_kind="ordinary_article",available_ts=at+STEP)]
        self.assertFalse(available_article(e,at))
        self.assertTrue(available_article(e,at+STEP))
        self.assertFalse(available_article(e,at+STEP,shift=7*86400))
        self.assertTrue(available_article(e,at+STEP+7*86400,shift=7*86400))
        e=[dict(source_kind="scheduled_rba",available_ts=at)]
        self.assertFalse(available_article(e,at))
        with self.assertRaises(ValueError):
            available_article(e,at,shift=-STEP)

    def test_future_news_cannot_veto_past_entry(self):
        b=bars()
        at=b[350][0]
        e=[dict(source_kind="ordinary_article",available_ts=at+STEP)]
        self.assertFalse(make_veto(b,e,"h80_news7d")(at))
        self.assertTrue(make_veto(b,e,"h80_news7d")(at+STEP))

    def test_cost_and_risk_reconciliation_and_sizing(self):
        b=bars()
        a=replay_variant(b,305,500,[],"h80_base",audit=True)
        small=replay_variant(b,305,500,[],"h80_base",max_entry_debit=50,audit=True)
        self.assertGreater(a["trades"],0)
        self.assertEqual(a["trades"],small["trades"])
        for t in a["trade_audit"]:
            self.assertLessEqual(t["entry_debit_aud"],100+1e-8)
            self.assertLessEqual(t["entry_debit_aud"],.1*t["cash_before_entry_aud"]+1e-8)
            self.assertAlmostEqual(t["net"],t["gross"]-t["fees"]-t["spread"]-t["slippage"])
        self.assertLessEqual(small["trade_audit"][0]["entry_debit_aud"],50+1e-8)
        with self.assertRaises(ValueError):
            replay_variant(b,305,500,[],"h80_base",max_entry_debit=101)

    def test_negative_trade_counted_as_loss(self):
        b=bars()
        for i in range(380,len(b)):
            p=b[i][1]*.45
            b[i]=(b[i][0],p,p*1.002,p*.998,p,1.)
        r=replay_variant(b,305,500,[],"h80_base",audit=True)
        self.assertGreater(r["trades"],0)
        self.assertGreater(r["losses"],0)
        self.assertTrue(any(t["net"]<0 for t in r["trade_audit"]))

    def test_gap_fails_closed(self):
        b=bars()
        b[390]=(b[390][0]+STEP,*b[390][1:])
        with self.assertRaises(ValueError):
            replay_variant(b,305,500,[],"h80_base")

    def test_selector_never_uses_test_results(self):
        good=dict(trades=3,net_aud=3.)
        bad=dict(trades=0,net_aud=-9.)
        train={k:bad for k in SELECTABLE}
        val={k:bad for k in SELECTABLE}
        self.assertEqual(choose(train,val),"HOLD")
        train=dict(train,h80_edge25=good)
        val=dict(val,h80_edge25=good)
        self.assertEqual(choose(train,val),"h80_edge25")

    def test_coverage_does_not_call_reconstruction_first_observed(self):
        e=[dict(source_kind="ordinary_article",available_ts=1609459200)]
        x=coverage(e)
        self.assertEqual(x["article_events"],1)
        self.assertEqual(x["first_observed_historical_versions"],0)
        self.assertEqual(x["total_months"],84)
        self.assertEqual(x["empty_article_months_2020_2026"],83)

if __name__=="__main__":
    unittest.main()

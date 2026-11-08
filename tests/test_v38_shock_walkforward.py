"""V38 shock-event low-turnover research safety and causal tests."""
import math
import unittest
from research.v38_shock_walkforward import (
    SPECS, SELECTABLE, shock_recent, veto, run_variant, choose)
from research.v29_point_in_time import STEP

def bars(n=530):
    out=[]
    for i in range(n):
        p=100*math.exp(.0008*i)*(1+.001*math.sin(i*.27))
        out.append((1700006400+i*STEP,p,p*1.002,p*.998,p,1.))
    return out

class V38ShockTests(unittest.TestCase):
    def test_negative_shock_detected_only_after_completed_candle(self):
        b=bars()
        j=345
        p=b[j-1][4]*.95
        b[j]=(b[j][0],p,p*1.002,p*.998,p,1.)
        self.assertFalse(shock_recent(b,j,.040))
        self.assertTrue(shock_recent(b,j+1,.040))
        self.assertFalse(shock_recent(b,j+1,.040,delay=42))

    def test_future_prices_do_not_change_past_decision(self):
        b=bars()
        at=b[350][0]
        x=veto(b,"h80_down25")(at)
        b[351]=(b[351][0],1.,1.,1.,1.,1.)
        self.assertEqual(x,veto(b,"h80_down25")(at))

    def test_placebo_uses_older_not_future_events(self):
        b=bars()
        j=350
        p=b[j-1][4]*.94
        b[j]=(b[j][0],p,p*1.002,p*.998,p,1.)
        self.assertTrue(shock_recent(b,j+1,.040))
        self.assertTrue(shock_recent(b,j+43,.040,delay=42))
        self.assertFalse(shock_recent(b,j+43,.040))

    def test_invalid_threshold_and_variant_rejected(self):
        with self.assertRaises(ValueError):
            shock_recent(bars(),350,.05)
        with self.assertRaises(ValueError):
            veto(bars(),"made_up")
        self.assertNotIn("h80_down25_placebo7d",SELECTABLE)

    def test_paper_risk_and_negative_outcomes(self):
        b=bars()
        r=run_variant(b,305,520,"h80_base",audit=True)
        self.assertGreater(r["trades"],0)
        for t in r["trade_audit"]:
            self.assertLessEqual(t["entry_debit_aud"],100+1e-8)
            self.assertLessEqual(t["entry_debit_aud"],
                                 .1*t["cash_before_entry_aud"]+1e-8)
            self.assertAlmostEqual(t["net"],t["gross"]-t["fees"]-
                                   t["spread"]-t["slippage"])
        for i in range(400,len(b)):
            p=b[i][1]*.45
            b[i]=(b[i][0],p,p*1.002,p*.998,p,1.)
        r=run_variant(b,305,520,"h80_base",audit=True)
        self.assertGreater(r["losses"],0)
        self.assertTrue(any(t["net"]<0 for t in r["trade_audit"]))

    def test_A50_vs_A100_and_invalid_cap(self):
        b=bars()
        a=run_variant(b,305,520,"h80_base",max_entry_debit=100,audit=True)
        c=run_variant(b,305,520,"h80_base",max_entry_debit=50,audit=True)
        self.assertEqual(a["trades"],c["trades"])
        self.assertLessEqual(c["trade_audit"][0]["entry_debit_aud"],50+1e-8)
        with self.assertRaises(ValueError):
            run_variant(b,305,520,"h80_base",max_entry_debit=101)

    def test_gap_fails_closed(self):
        b=bars()
        b[400]=(b[400][0]+STEP,*b[400][1:])
        with self.assertRaises(ValueError):
            run_variant(b,305,520,"h80_base")

    def test_train_only_selector_never_uses_test(self):
        bad=dict(trades=1,net_aud=-3.)
        good=dict(trades=3,net_aud=2.)
        train={k:bad for k in SELECTABLE}
        val={k:bad for k in SELECTABLE}
        self.assertEqual(choose(train,val),"HOLD")
        train["h80_down25"]=good
        val["h80_down25"]=good
        self.assertEqual(choose(train,val),"h80_down25")

if __name__=="__main__":unittest.main()

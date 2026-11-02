"""V31 deterministic SYNTHETIC safety tests, never real-market performance."""
import math, unittest
from research.v31_hysteresis import (WARMUP, STEP, PARAMS, VARIANTS, features,
    decision, replay, choose, run, news_risk)

START=1609459200
def candles(n=2600):
    out=[]
    for i in range(n):
        price=30000+7*i+1200*math.sin(i/85)+200*math.sin(i/7)
        out.append((START+i*STEP,price,price*1.012,price*.988,price*1.001,1.))
    return out

class TestV31(unittest.TestCase):
    def setUp(self):self.bars=candles()
    def test_future_candle_cannot_change_features_or_decision(self):
        i=900
        old=features(self.bars,i,50,200)
        changed=list(self.bars)
        t,o,h,l,c,v=changed[i]
        changed[i]=(t,o*3,h*3,l*.1,c*3,v)
        self.assertEqual(old,features(changed,i,50,200))
        self.assertEqual(decision(self.bars,i,"h50_200"),
                         decision(changed,i,"h50_200"))
    def test_news_availability_and_placebo(self):
        t=self.bars[850][0]
        future=dict(id="x",available_ts=t+STEP,sentiment=-1)
        self.assertFalse(news_risk([future],t,"h50_200_news"))
        self.assertTrue(news_risk([future],t+STEP,"h50_200_news"))
        self.assertFalse(news_risk([future],t+STEP,"h50_200_placebo"))
    def test_trade_reconciliation_and_entry_caps(self):
        for name in VARIANTS:
            result=replay(self.bars,500,2200,name,audit=True)
            self.assertEqual(result["trades"],len(result["trade_audit"]))
            self.assertAlmostEqual(result["net_aud"],result["gross_aud"]-
                result["fees_aud"]-result["spread_aud"]-result["slippage_aud"],places=4)
            self.assertEqual(result["trades"],result["wins"]+result["losses"])
            self.assertTrue(all(observed<at for at,observed,action in result["decision_audit"]))
            self.assertTrue(all(row["exit_ts"]>row["entry_ts"] for row in result["trade_audit"]))
    def test_gap_fails_closed(self):
        bad=list(self.bars)
        t,o,h,l,c,v=bad[600];bad[600]=(t+STEP,o,h,l,c,v)
        with self.assertRaisesRegex(ValueError,"gap"):
            replay(bad,500,900,"h50_200")
    def test_cost_sensitivity(self):
        for name in PARAMS:
            net=[replay(self.bars,500,2200,name,cost_mult=x)["net_aud"] for x in (.5,1.,2.)]
            self.assertGreaterEqual(net[0]+1e-5,net[1])
            self.assertGreaterEqual(net[1]+1e-5,net[2])
    def test_selection_does_not_use_test(self):
        good=dict(trades=3,net_aud=5.)
        bad=dict(trades=3,net_aud=-2.)
        train={n:good for n in PARAMS}
        val={n:bad for n in PARAMS}
        self.assertEqual(choose(train,val),"HOLD")
        val["h30_120"]=good
        self.assertEqual(choose(train,val),"h30_120")
    def test_no_news_future_changes_past_replay(self):
        a=replay(self.bars,500,1000,"h50_200_news")
        e=[dict(id="future",sentiment=-1,available_ts=self.bars[1100][0])]
        b=replay(self.bars,500,1000,"h50_200_news",e)
        self.assertEqual(a,b)
    def test_run_requires_no_promotion(self):
        report=run(self.bars,[],{"source":"SYNTHETIC"},"fixture")
        self.assertEqual(report["selected_policy"],"HOLD")
        self.assertEqual(len(report["folds"]),3)
        self.assertIn("NOT untouched",report["limitations"][0])
        self.assertEqual(len(report["aggregate_independent_reset_folds"]),5)

if __name__=="__main__":unittest.main()

"""Synthetic V33 leakage, split, reconciliation and cost tests."""
import math, unittest
from research.kraken_archive import STEP
from research.v33_cross_regime import boundaries, one_segment, evaluate, historical_news
from research.v32_segments import segments

def bars(n=1300,offset=0):
    out=[]
    for i in range(n):
        p=30000+7*i+600*math.sin(i/55)
        out.append((1609459200+(offset+i)*STEP,p,p*1.015,p*.985,p*1.001,1.))
    return out

class TestV33(unittest.TestCase):
    def test_chronological_embargo(self):
        tr,vs,ve,ts=boundaries(1300)
        self.assertGreaterEqual(vs-tr,20)
        self.assertGreaterEqual(ts-ve,20)
        self.assertGreaterEqual(tr,305)
    def test_future_prices_do_not_change_selection(self):
        x=bars()
        a=one_segment(x,[])
        changed=list(x)
        for i in range(910,len(x)):
            t,o,h,l,c,v=changed[i]
            changed[i]=(t,o*1.4,h*1.4,l*1.4,c*1.4,v)
        b=one_segment(changed,[])
        self.assertEqual(a["train_validation_selected"],b["train_validation_selected"])
        self.assertEqual(a["training"],b["training"])
        self.assertEqual(a["validation"],b["validation"])
    def test_future_news_does_not_change_past(self):
        x=bars()
        a=one_segment(x,[])
        future=dict(id="future",sentiment=-1,available_ts=x[-1][0]+86400)
        b=one_segment(x,[future])
        self.assertEqual(a["test"],b["test"])
    def test_costs_and_no_promotion(self):
        x=bars()
        a=evaluate(x,{"source":"SYNTHETIC"},[],{"kind":"SYNTHETIC"})
        self.assertEqual(a["selected_paper_policy"],"HOLD")
        self.assertEqual(a["eligible_segments"],1)
        for row in a["folds"][0]["test"].values():
            self.assertAlmostEqual(row["net_aud"],row["gross_aud"]-
                row["fees_aud"]-row["spread_aud"]-row["slippage_aud"],places=4)
            self.assertEqual(row["trades"],len(row["trade_audit"]))
    def test_gap_isolation(self):
        a=bars(1300)
        b=bars(1300,offset=1302)
        report=evaluate(a+b,{"source":"SYNTHETIC"},[],{"kind":"SYNTHETIC"})
        self.assertEqual(report["eligible_segments"],2)
        self.assertEqual(len(report["folds"]),2)
    def test_retrospective_news_marked(self):
        events,provenance=historical_news()
        self.assertGreaterEqual(len(events),19)
        self.assertIn("NOT_FIRST_OBSERVED",provenance["provenance"])
        self.assertTrue(all(e["available_ts"]>0 for e in events))
if __name__=="__main__":unittest.main()

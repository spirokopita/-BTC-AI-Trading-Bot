import unittest
from research.v43_hoarder import replay,STEP
def bars(prices):
    return [(1700006400+i*STEP,p,p*1.01,p*.99,p,1) for i,p in enumerate(prices)]
class HoarderTests(unittest.TestCase):
    def test_never_sell_cost_reconciliation_and_caps(self):
        x=replay(bars([100]*185+[90]*220+[75]*210),180,615,"hoard_tiered")
        self.assertEqual(x["sells"],0);self.assertGreater(x["buys"],0)
        self.assertAlmostEqual(x["gross_aud"]-x["fees_aud"]-x["spread_aud"]-x["slippage_aud"],x["net_liquidation_aud"],places=6)
        for o in x["orders"]:
            self.assertLessEqual(o["debit"],100+1e-8)
            self.assertLessEqual(o["debit"],.1*o["cash_before"]+1e-8)
    def test_no_dip_no_purchase(self):
        x=replay(bars([100]*400),180,400,"hoard_10")
        self.assertEqual(x["buys"],0);self.assertEqual(x["net_liquidation_aud"],0)
    def test_gap_rejected(self):
        b=bars([100]*400);b[200]=(b[200][0]+STEP,*b[200][1:])
        with self.assertRaises(ValueError): replay(b,180,400,"hoard_5")
    def test_double_friction_worse(self):
        b=bars([100]*185+[80]*220)
        self.assertLess(replay(b,180,len(b),"hoard_10",cost_mult=2)["net_liquidation_aud"],
            replay(b,180,len(b),"hoard_10",cost_mult=.5)["net_liquidation_aud"])
if __name__=="__main__":unittest.main()

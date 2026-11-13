import unittest
from research.v45_lot_aware_cycle import replay
class Costs(unittest.TestCase):
 def test_cap_and_cost_nonnegative(self):
  bars=[(1700000000+i*14400,100.,101.,99.,100.,1.) for i in range(1600)]
  feat=[None]*1080+[(.05,.9)]*520
  a=replay(bars,feat,1080,len(bars),.04,.9,.7,max_entry_debit=50.)
  b=replay(bars,feat,1080,len(bars),.04,.9,.7,max_entry_debit=100.)
  self.assertGreater(a["buys"],0)
  self.assertGreaterEqual(b["hoard_btc"],a["hoard_btc"])
  for x in (a,b):
   self.assertGreaterEqual(x["fees_paid_aud"],0)
   self.assertGreaterEqual(x["spread_paid_aud"],0)
   self.assertGreaterEqual(x["slippage_paid_aud"],0)
   self.assertEqual(x["bulk_sales"],0)
if __name__=="__main__":unittest.main()

import unittest
from research.v45_lot_aware_cycle import replay
from research.v44_hoarder_grid import features,LOOKBACK
from research.v29_point_in_time import STEP
def bars(prices):
 return [(1700006400+i*STEP,p,p*1.01,p*.99,p,1) for i,p in enumerate(prices)]
class LotTests(unittest.TestCase):
 def test_no_early_sales_and_permanent_reserve(self):
  b=bars([100.]*1100+[80.]*400+[130.]*1200)
  f=features(b)
  r=replay(b,f,1100,len(b),.02,.70,.7)
  self.assertGreater(r["buys"],0)
  self.assertGreater(r["hoard_btc"],0)
  for s in r["sales"]:self.assertGreaterEqual(s["lots"],1)
 def test_never_sell_comparator(self):
  b=bars([100.]*1100+[80.]*400+[130.]*1200)
  r=replay(b,features(b),1100,len(b),.02,.70,.7,enable_sells=False)
  self.assertEqual(r["bulk_sales"],0)
 def test_no_lookahead_when_future_prices_change(self):
  a=bars([100.]*1100+[80.]*400+[130.]*1200)
  b=bars([100.]*1100+[80.]*400+[130.]*1190+[999.]*10)
  x=replay(a,features(a),1100,len(a)-10,.02,.7,.7)
  y=replay(b,features(b),1100,len(b)-10,.02,.7,.7)
  self.assertEqual(x,y)
if __name__=="__main__":unittest.main()

import unittest
from research.v46_hold_age_ablation import study,AGES
class TestV46(unittest.TestCase):
 def test_age_units(self):
  self.assertEqual(AGES,(540,1080,2190))
 def test_no_lookahead_or_trade_on_too_short_series(self):
  from research.v45_lot_aware_cycle import replay
  from research.v44_hoarder_grid import features
  b=[(1700000000+i*14400,p,p,p,p,1) for i,p in enumerate([100.]*1100+[80.]*600)]
  r=replay(b,features(b),1100,len(b),.02,.7,.7,minimum_age=2190)
  self.assertEqual(r["bulk_sales"],0)
 def test_no_sale_comparator_has_no_sales(self):
  from research.v45_lot_aware_cycle import replay
  from research.v44_hoarder_grid import features
  b=[(1700000000+i*14400,p,p,p,p,1) for i,p in enumerate([100.]*1100+[80.]*600)]
  r=replay(b,features(b),1100,len(b),.02,.7,.7,enable_sells=False)
  self.assertEqual(r["bulk_sales"],0)
if __name__=="__main__":unittest.main()

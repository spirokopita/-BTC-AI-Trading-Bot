import sys
import unittest
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'user_data' / 'strategies'))
from v3_outcomes import future_net_trade_labels, net_return, HOLD_BARS

class V3OutcomeTests(unittest.TestCase):
    def test_flat_market_loses_fees(self):
        n=HOLD_BARS+3
        c=np.full(n,100.0)
        a=future_net_trade_labels(c,c,c,c)
        self.assertLess(a[0],-0.016)
        self.assertAlmostEqual(a[0],net_return(100,100))
        self.assertTrue(np.isnan(a[-HOLD_BARS]))

    def test_take_target_after_entry(self):
        n=HOLD_BARS+3
        o=np.full(n,100.0);h=o.copy();l=o.copy();c=o.copy()
        h[2]=110.0
        a=future_net_trade_labels(o,h,l,c)
        self.assertGreater(a[0],0.05)

    def test_stop_takes_precedence_if_ohlc_ambiguous(self):
        n=HOLD_BARS+3
        o=np.full(n,100.0);h=o.copy();l=o.copy();c=o.copy()
        h[1]=110.0;l[1]=93.0
        a=future_net_trade_labels(o,h,l,c)
        self.assertLess(a[0],-.06)

    def test_gap_down_worse_than_stop(self):
        n=HOLD_BARS+3
        o=np.full(n,100.0);h=o.copy();l=o.copy();c=o.copy()
        o[2]=90.;h[2]=90.;l[2]=90.;c[2]=90.
        a=future_net_trade_labels(o,h,l,c)
        self.assertTrue(a[0] < -.06)

    def test_no_time_travel_at_dataset_end(self):
        n=HOLD_BARS+1
        p=np.full(n,100.0)
        a=future_net_trade_labels(p,p,p,p)
        self.assertTrue(np.isnan(a[-1]))
        self.assertTrue(np.isfinite(a[0]))

    def test_transaction_friction(self):
        self.assertTrue(-0.019 < net_return(100,100) < -0.016)

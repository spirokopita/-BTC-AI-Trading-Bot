import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'research'))
from breakout_walk_forward import net_ratio,label_train_end,load_data,add_indicators,replay
from trading_costs import FeeSettings
import tempfile
import pandas as pd
import numpy as np

class V4Tests(unittest.TestCase):
    def test_fees_reduce_flat_trade(self):
        self.assertTrue(.981<net_ratio(100,100)<.984)
    def test_causality_embargo(self):
        self.assertEqual(label_train_end(500),380)
        with self.assertRaises(ValueError): label_train_end(50)
    def test_no_candle_gap_acceptance(self):
        dates=pd.date_range('2021-01-01',periods=400,freq='4h',tz='UTC')
        d=pd.DataFrame({'datetime':dates.astype(str), 'open':100,'high':101,'low':99,'close':100,'volume':1})
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'s.csv';d.to_csv(p,index=False)
            self.assertEqual(len(load_data(str(p))),400)
            d=d.drop(index=7);d.to_csv(p,index=False)
            with self.assertRaises(ValueError):load_data(str(p))
    def test_breakout_excludes_current_candle(self):
        dates=pd.date_range('2020-01-01',periods=350,freq='4h',tz='UTC')
        closes=np.full(350,100.,dtype=float);closes[-1]=150
        d=pd.DataFrame({'date':dates,'open':closes,'high':closes+1,'low':closes-1,'close':closes,'volume':1.})
        x,_=add_indicators(d)
        self.assertLess(x.iloc[-1]['prior20dayhigh'],150)
        self.assertTrue(bool(x.iloc[-1]['entry']))
    def test_no_trades_if_no_setup(self):
        dates=pd.date_range('2020-01-01',periods=700,freq='4h',tz='UTC')
        d=pd.DataFrame({'date':dates,'open':100.,'high':101.,'low':99.,'close':100.,'volume':1.})
        x,_=add_indicators(d)
        z=replay(x,200,699)
        self.assertEqual(z['trades'],0)
        self.assertEqual(z['return_pct'],0)
    def test_stop_first_in_same_bar(self):
        d=pd.DataFrame({'date':pd.date_range('2020-01-01',periods=6,freq='4h',tz='UTC'),
         'open':[100]*6,'high':[100,100,101,130,101,101],'low':[99,99,99,85,99,99],
         'close':[100]*6,'volume':[1]*6,'entry':[False,True,False,False,False,False],
         'exit':[False]*6})
        z=replay(d,0,5)
        self.assertEqual(z['trades'],1)
        self.assertEqual(z['recent_trades'][0]['exit'],'stop')
        self.assertLess(z['recent_trades'][0]['net'],0)
    def test_trade_fees_on_versus_off_reconcile_in_replay(self):
        # Signal -> next open buy -> signal -> next open sell at same mid.
        # 0% gross movement must lose money with fees but not without.
        d=pd.DataFrame({'date':pd.date_range('2022-01-01',periods=5,freq='4h',tz='UTC'),
            'open':[100.]*5,'high':[100.]*5,'low':[100.]*5,
            'close':[100.]*5,'volume':[1.]*5,
            'entry':[False,True,False,False,False],
            'exit':[False,False,True,False,False],
            'atr':[.02]*5})
        on=replay(d,0,4)
        off=replay(d,0,4,settings=FeeSettings.zero())
        self.assertEqual(on['trades'],1)
        self.assertEqual(off['trades'],1)
        self.assertLess(on['equity'],1000)
        self.assertEqual(off['equity'],1000)
        self.assertGreater(on['total_trading_fees_quote'],0)
        self.assertEqual(off['total_trading_fees_quote'],0)
        t=on['recent_trades'][0]
        self.assertAlmostEqual(t['gross_pnl_quote']-t['total_costs_quote'],t['net_pnl_quote'])
        self.assertIn('entry_fee_quote',t)
        self.assertIn('exit_fee_quote',t)

if __name__=='__main__':unittest.main()

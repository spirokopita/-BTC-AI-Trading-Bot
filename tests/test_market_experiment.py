"""Deterministic synthetic controls; these are NOT real BTC/AUD performance."""
import unittest
from research.market_experiment import STEP, parse_kraken, signal, simulate, experiment

BASE = 1704067200

def bars(n=700):
    out=[]
    for i in range(n):
        price=100+i*.03+3*((i%40)/40)
        out.append((BASE+i*STEP,price,price+1,price-1,price,5.))
    return out

class ResearchControls(unittest.TestCase):
    def test_excludes_unfinished_candle(self):
        rows=[[b[0],str(b[1]),str(b[2]),str(b[3]),str(b[4]),'0',str(b[5]),'2'] for b in bars()]
        payload={'error':[],'result':{'XXBTZAUD':rows,'last':123}}
        self.assertEqual(len(parse_kraken(payload,BASE+699*STEP)),699)

    def test_rejects_gap_duplicate_wrong_pair(self):
        rows=[[b[0],str(b[1]),str(b[2]),str(b[3]),str(b[4]),'0',str(b[5]),'2'] for b in bars()]
        rows[400][0]+=STEP
        with self.assertRaisesRegex(ValueError,'Duplicate|Non-contiguous'):
            parse_kraken({'error':[],'result':{'XXBTZAUD':rows}},BASE+701*STEP)
        with self.assertRaisesRegex(ValueError,'pair'):
            parse_kraken({'error':[],'result':{'XBTUSD':rows}},BASE+701*STEP)

    def test_signal_cannot_see_future(self):
        x=bars()
        original=signal(x,200,'momentum')
        y=list(x)
        y[201]=(y[201][0],10000,10001,9999,10000,5.)
        self.assertEqual(original,signal(y,200,'momentum'))

    def test_costs_reconcile_and_reduce_net(self):
        x=bars()
        paid=simulate(x,380,500,'momentum')
        free=simulate(x,380,500,'momentum',fee_multiplier=0)
        self.assertAlmostEqual(paid['gross_aud']-paid['fees_aud']-paid['spread_aud']-
                               paid['slippage_aud'],paid['net_aud'],places=4)
        self.assertGreaterEqual(free['net_aud'],paid['net_aud'])
        self.assertEqual(paid['trades'],paid['wins']+paid['losses']+
                         sum(t['net_aud']==0 for t in paid['trade_log']))

    def test_train_selection_unaffected_by_future_test(self):
        x=bars()
        first=experiment(x)['folds'][0]['selected_FROM_TRAIN_ONLY']
        y=list(x)
        for i in range(380,500):
            z=y[i];y[i]=(z[0],z[1]*1.5,z[2]*1.5,z[3]*1.5,z[4]*1.5,z[5])
        self.assertEqual(first,experiment(y)['folds'][0]['selected_FROM_TRAIN_ONLY'])

if __name__=='__main__':
    unittest.main()

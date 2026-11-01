"""Deterministic V30 safety tests on SYNTHETIC candles, not market returns."""
import math, unittest
from research.v30_matched_news import (LOOKBACK, STEP, pre_open_state,
    select_controls, matched_study, roundtrip_pct, signflip_pvalue)

START=1609459200
def candles(n=1200):
    out=[]
    for i in range(n):
        p=30000+i*9+300*math.sin(i/16)
        out.append((START+i*STEP,p,p*1.01,p*.99,p*1.001,1.))
    return out

def event(bars,i,name='a',sentiment=1):
    return dict(id=name,category='fixture',sentiment=sentiment,available_ts=bars[i][0]-1)

class TestV30(unittest.TestCase):
    def setUp(self):self.bars=candles()
    def test_no_future_market_in_pre_open_features(self):
        i=800;a=pre_open_state(self.bars,i)
        changed=list(self.bars)
        t,o,h,l,c,v=changed[i]
        changed[i]=(t,o,h*10,l/10,c*10,v)
        self.assertEqual(a,pre_open_state(changed,i))
    def test_no_future_controls(self):
        i=800;chosen=select_controls(self.bars,i,[i],5)
        self.assertTrue(chosen)
        self.assertTrue(all(j<i-LOOKBACK and (i-j)%LOOKBACK==0 for j in chosen))
    def test_controls_avoid_news_windows(self):
        i=800;chosen=select_controls(self.bars,i,[i,650,700],5)
        self.assertTrue(all(abs(j-k)>LOOKBACK for j in chosen for k in [i,650,700]))
    def test_market_future_cannot_change_control_selection(self):
        i=800;baseline=select_controls(self.bars,i,[i],5)
        changed=list(self.bars)
        for j in range(i+1,len(changed)):
            t,o,h,l,c,v=changed[j]
            changed[j]=(t,o*2,h*2,l*2,c*2,v)
        self.assertEqual(baseline,select_controls(changed,i,[i],5))
    def test_no_publication_leakage(self):
        i=800;r=matched_study(self.bars,[event(self.bars,i)])
        self.assertEqual(r['news_events_matched'],1)
        self.assertEqual(len(r['summary']),3)
        self.assertTrue(all(row['event_open_ts']>=row['available_ts'] for row in r['rows']))
    def test_costs_always_included(self):
        flat=candles(500)
        for j,b in enumerate(flat):
            flat[j]=(b[0],100.,101.,99.,100.,1.)
        self.assertLess(roundtrip_pct(flat,250,6),-1.7)
    def test_signflip(self):
        self.assertEqual(signflip_pvalue([1.,2.]),.5)
        self.assertIsNone(signflip_pvalue([]))
    def test_gap_fails_closed(self):
        bad=list(self.bars)
        t,o,h,l,c,v=bad[300];bad[300]=(t+STEP,o,h,l,c,v)
        with self.assertRaisesRegex(ValueError,'Gaps'):
            matched_study(bad,[event(bad,800)])

if __name__=='__main__':unittest.main()

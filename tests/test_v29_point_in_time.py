"""Deterministic V29 safety tests on SYNTHETIC candles, not market results."""
import json, tempfile, unittest
from pathlib import Path
from research.v29_point_in_time import STEP,asof,signal,simulate,event_study,news_load,run

START=1609459200
def candles(n=1400):
    out=[]
    for i in range(n):
        p=30000+8*i+1800*((i//36)%2)+200*((i%19)/19)
        out.append((START+i*STEP,p,p*1.015,p*.985,p*1.001,1.))
    return out

def news(at):
    return dict(id='fixture',available_ts=at,sentiment=-1,category='security')

class TestV29(unittest.TestCase):
    def setUp(self): self.bars=candles()
    def test_no_future_news(self):
        t=self.bars[450][0]
        self.assertEqual(asof([news(t+STEP)],t),[])
        self.assertEqual(len(asof([news(t+STEP)],t+STEP)),1)
    def test_future_headline_does_not_change_past_signal(self):
        for name in ('news_veto','news_veto_7d','news_delay'):
            self.assertEqual(signal(self.bars,550,name,[]),
                             signal(self.bars,550,name,[news(self.bars[900][0])]))
    def test_future_bar_close_does_not_change_decision(self):
        i=600
        changed=list(self.bars)
        t,o,h,l,c,v=changed[i+1]
        changed[i+1]=(t,o,h*10,l/10,c*10,v)
        self.assertEqual(signal(changed,i,'trend_breakout'),signal(self.bars,i,'trend_breakout'))
    def test_gap_fail_closed(self):
        changed=list(self.bars)
        t,o,h,l,c,v=changed[700]
        changed[700]=(t+STEP,o,h,l,c,v)
        with self.assertRaisesRegex(ValueError,'gap'):
            simulate(changed,600,850,'sma')
    def test_trade_cost_reconciliation(self):
        for name in ('sma','momentum','rsi','breakout','regime','trend_breakout','news_veto','news_veto_7d'):
            x=simulate(self.bars,250,1000,name,[],audit=True)
            self.assertEqual(x['trades'],len(x['trade_audit']))
            self.assertAlmostEqual(x['net_aud'],
                x['gross_aud']-x['fees_aud']-x['spread_aud']-x['slippage_aud'],places=4)
            self.assertEqual(x['trades'],x['wins']+x['losses'])
            self.assertTrue(all(y['observed_max_open_ts']<y['decision_ts'] for y in x['decision_audit']))
    def test_cost_sensitivity(self):
        vals=[simulate(self.bars,300,1000,'sma',mult=m)['net_aud'] for m in (.5,1.,2.)]
        self.assertGreaterEqual(vals[0],vals[1]);self.assertGreaterEqual(vals[1],vals[2])
    def test_revisions_and_latency(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'news.json'
            p.write_text(json.dumps(dict(
                dataset_type='RETROSPECTIVE_PUBLISHED_TIMESTAMP_RECONSTRUCTION_NOT_FIRST_OBSERVED',
                events=[dict(id='a',published_at_utc='2022-01-01T00:00:00Z',
                    updated_at_utc='2022-01-01T03:00:00Z',
                    sentiment=-1,url='https://example.com/a')])))
            ev,_=news_load(p)
            self.assertEqual(ev[0]['available_ts'], 1641009600)
            self.assertEqual(asof(ev,1641009600-1),[])
    def test_event_open_after_available(self):
        t=self.bars[450][0]
        x=news(t+1)
        rows=event_study(self.bars,[x])
        self.assertEqual(len(rows),3)
        self.assertTrue(all(z['first_tradable_open_ts']>=x['available_ts'] for z in rows))
    def test_research_cannot_promote(self):
        report=run(self.bars,[news(self.bars[400][0])],{'source':'SYNTHETIC'},'fixture')
        self.assertEqual(report['selection'],'HOLD')
        self.assertEqual(len(report['chronological_expanding_folds']),5)
        self.assertIn('RETROSPECTIVE',report['news_data_kind'])

if __name__=='__main__':unittest.main()

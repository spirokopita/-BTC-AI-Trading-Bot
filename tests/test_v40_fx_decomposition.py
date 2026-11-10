"""V40 strict-as-of FX decomposition and PAPER train-only selection tests."""
import math
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from research.v40_fx_decomposition import (decomposition,entry_veto,rate_asof,
                                            select,CANDIDATES,PERIOD)
STEP=14400
START=int(datetime(2023,1,1,tzinfo=timezone.utc).timestamp())

def bars(n=600):
    return [(START+i*STEP,p,p*1.001,p*.999,p,1.)
            for i in range(n) for p in [20000*math.exp(.00025*i)]]

def fx_fixture():
    return SimpleNamespace(times=[START+i*86400 for i in range(150)],
                           rates=[.75*math.exp(-.001*i) for i in range(150)])

class V40DecompositionTests(unittest.TestCase):
    def test_identity_and_completed_only(self):
        b=bars();fx=fx_fixture();before=decomposition(b,400,fx)
        self.assertAlmostEqual(before['btc_aud_log30'],
            before['implied_btc_usd_log30']-before['aud_usd_log30'])
        self.assertEqual(before['latest_completed_candle_ts'],b[399][0])
        self.assertLessEqual(before['latest_fx_assumed_available_ts'],b[400][0])
        b[400]=(b[400][0],999999.,999999.,999999.,999999.,1.)
        self.assertEqual(before,decomposition(b,400,fx))

    def test_future_fx_never_changes_past_signal(self):
        fx=fx_fixture();b=bars();first=decomposition(b,400,fx)
        fx.times.append(b[400][0]+100);fx.rates.append(.4)
        self.assertEqual(first,decomposition(b,400,fx))

    def test_delayed_placebo_only_uses_older_fx(self):
        b=bars();fx=fx_fixture()
        normal=decomposition(b,400,fx)
        placebo=decomposition(b,400,fx,delay_days=7)
        self.assertLess(placebo['latest_fx_assumed_available_ts'],
                        normal['latest_fx_assumed_available_ts'])
        with self.assertRaises(ValueError):
            decomposition(b,400,fx,delay_days=-7)

    def test_no_future_bar_or_insufficient_warmup(self):
        with self.assertRaises(ValueError):
            decomposition(bars(),PERIOD,fx_fixture())
        with self.assertRaises(ValueError):
            decomposition(bars(),600,fx_fixture())

    def test_missing_fx_fails_closed_for_new_entries(self):
        fx=SimpleNamespace(times=[START],rates=[.7])
        self.assertIsNone(decomposition(bars(),400,fx))
        self.assertTrue(entry_veto(None,'h80_fx_driven'))
        self.assertFalse(entry_veto(None,'h80_base'))

    def test_fx_only_rally_and_usd_momentum_gate(self):
        f={'btc_aud_log30':math.log(1.08),'implied_btc_usd_log30':math.log(.98)}
        for n in ('h80_fx_driven','h80_usd_momentum','h80_fx_placebo7d'):
            self.assertTrue(entry_veto(f,n))
        f['implied_btc_usd_log30']=math.log(1.07)
        self.assertFalse(entry_veto(f,'h80_fx_driven'))
        self.assertFalse(entry_veto(f,'h80_usd_momentum'))
        with self.assertRaises(ValueError):entry_veto(f,'invented')

    def test_fx_staleness_and_validity(self):
        fx=fx_fixture()
        self.assertIsNone(rate_asof(fx,START-1))
        self.assertIsNone(rate_asof(fx,START+200*86400))
        with self.assertRaises(ValueError):
            rate_asof(SimpleNamespace(times=[START],rates=[-1.]),START)

    def test_gap_rejected(self):
        b=bars();b[399]=(b[399][0]+STEP,*b[399][1:])
        with self.assertRaises(ValueError):
            decomposition(b,400,fx_fixture())

    def test_selection_uses_only_train_validation(self):
        bad={'trades':0,'net_aud':0.}
        tr={n:bad for n in CANDIDATES};val={n:bad for n in CANDIDATES}
        self.assertEqual(select(tr,val),'HOLD')
        tr['h80_fx_driven']={'trades':3,'net_aud':4.}
        val['h80_fx_driven']={'trades':2,'net_aud':2.}
        self.assertEqual(select(tr,val),'h80_fx_driven')
        val['h80_fx_driven']={'trades':2,'net_aud':-1.}
        self.assertEqual(select(tr,val),'HOLD')

if __name__=='__main__':unittest.main()

"""V34 synthetic tests: DST, as-of publication, exit safety, fee audit and gap isolation."""
import math, unittest
from datetime import datetime, timezone
from research.v34_rba_systematic import (
    load_calendar, veto_factory, fold, evaluate, LATENCY_HOURS)
from research.v31_hysteresis import replay
from research.v29_point_in_time import STEP

def synthetic(n=1300, offset=0):
    out=[]
    for i in range(n):
        p=30000+12*i+300*math.sin(i/60)
        out.append((1609459200+(offset+i)*STEP,p,p*1.01,p*.99,p*1.001,1.))
    return out

class V34Tests(unittest.TestCase):
    def test_full_non_selected_calendar_and_provenance(self):
        e,p=load_calendar()
        self.assertEqual(len(e),61)
        self.assertIn("NOT_FIRST_OBSERVED",p["provenance"])
        self.assertTrue(all(x["sentiment"]==0 for x in e))
        self.assertEqual(len({x["id"] for x in e}),61)

    def test_sydney_dst_and_24h_assumed_latency(self):
        e,_=load_calendar()
        x={r["id"]:r for r in e}
        self.assertEqual(datetime.fromtimestamp(x["rba_2024-02-06"]["release_ts"],
            timezone.utc).isoformat(),"2024-02-06T03:30:00+00:00")
        self.assertEqual(datetime.fromtimestamp(x["rba_2024-06-18"]["release_ts"],
            timezone.utc).isoformat(),"2024-06-18T04:30:00+00:00")
        for row in e:
            self.assertEqual(row["available_ts"]-row["release_ts"],LATENCY_HOURS*3600)

    def test_no_future_news_and_delayed_placebo(self):
        e,_=load_calendar()
        at=e[15]["available_ts"]
        v=veto_factory(e,48)
        placebo=veto_factory(e,48,7*24)
        self.assertFalse(v(at-1))
        self.assertTrue(v(at))
        self.assertTrue(v(at+47*3600))
        self.assertFalse(v(at+48*3600))
        self.assertFalse(placebo(at))
        self.assertTrue(placebo(at+7*86400))

    def test_veto_suppresses_entry_but_not_sell(self):
        bars=synthetic()
        normal=replay(bars,305,len(bars),"h50_200")
        blocked=replay(bars,305,len(bars),"h50_200",entry_veto=lambda _:True)
        self.assertGreater(normal["trades"],0)
        self.assertEqual(blocked["trades"],0)
        # Late veto must not block a pre-existing position's exit.
        cut=800
        late=replay(bars,305,len(bars),"h50_200",entry_veto=lambda t:t>=bars[cut][0])
        self.assertLessEqual(late["trades"],normal["trades"])

    def test_gross_cost_net_reconciliation(self):
        bars=synthetic()
        events,_=load_calendar()
        result=fold(bars,events)
        for item in result["strategies"].values():
            self.assertAlmostEqual(item["net_aud"],
                item["gross_aud"]-item["fees_aud"]-
                item["spread_aud"]-item["slippage_aud"],places=4)
            self.assertEqual(item["trades"],len(item["trade_audit"]))
        self.assertEqual(result["embargo_bars"],20)

    def test_aud50_vs_aud100_inclusive_entry_audit(self):
        bars=synthetic()
        for cap in (50,100):
            out=replay(bars,305,len(bars),"h50_200",
                max_entry_debit=cap,audit=True)
            self.assertGreater(out["trades"],0)
            for trade in out["trade_audit"]:
                self.assertLessEqual(trade["entry_debit_aud"],cap+1e-8)
                self.assertLessEqual(trade["entry_debit_aud"],
                    trade["cash_before_entry_aud"]*.1+1e-8)
                self.assertAlmostEqual(trade["net"],
                    trade["gross"]-trade["fees"]-trade["spread"]-
                    trade["slippage"],places=6)
        with self.assertRaises(ValueError):
            replay(bars,305,len(bars),"h50_200",max_entry_debit=100.01)

    def test_gap_isolation_and_no_promotion(self):
        events,provenance=load_calendar()
        bars=synthetic()+synthetic(offset=1302)
        report=evaluate(bars,{"source":"SYNTHETIC"},events,provenance)
        self.assertEqual(report["eligible_segments"],2)
        self.assertEqual(report["segment_bar_counts"],[1300,1300])
        self.assertEqual(report["selected_android_policy"],"HOLD")
        self.assertEqual(report["max_inclusive_entry_debit_aud"],100)
        self.assertEqual(set(report["aggregate_position_sensitivity_aud50_vs_aud100"]),{"50","100"})

if __name__=="__main__":unittest.main()

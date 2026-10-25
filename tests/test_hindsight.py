"""Roadmap 5: net-fee opportunity analysis and chronological data firewall."""
from dataclasses import replace
from pathlib import Path
import math
import tempfile
import unittest

from backtester import BacktestParameters, compare_costs, run_backtest
from backtester.engine import checked_candles
from data_layer.storage import Candle
from examples.backtest_demo import make_bars
from hindsight import HindsightParameters, chronological_folds, analyze_hindsight, simulate_hindsight_trade
from hindsight.walkforward import validate_walk_forward
from trading_costs import load_settings, FeeSettings


class HindsightTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory()
        self.root=Path(self.directory.name)
        self.bars=make_bars()

    def tearDown(self):self.directory.cleanup()

    def test_net_below_gross_and_fee_off_better(self):
        a=simulate_hindsight_trade(self.bars,250,280,settings=load_settings(),stake_quote=50)
        b=simulate_hindsight_trade(self.bars,250,280,settings=FeeSettings.zero(),stake_quote=50)
        self.assertAlmostEqual(a['net_pnl_quote'],a['gross_pnl_quote']-a['fees_quote']-
                               a['spread_quote']-a['slippage_quote'],places=6)
        self.assertGreater(a['fees_quote'],0)
        self.assertGreater(b['net_return_on_outlay_pct'],a['net_return_on_outlay_pct'])

    def test_refuse_same_bar_and_time_reversal(self):
        for x,y in ((10,10),(11,10),(0,3),(-1,5),(600,800)):
            with self.assertRaises(ValueError):
                simulate_hindsight_trade(self.bars,x,y,settings=FeeSettings.zero(),stake_quote=50)

    def test_hindsight_never_uses_future_high_as_fill(self):
        orig=simulate_hindsight_trade(self.bars,240,250,settings=load_settings(),stake_quote=50)
        edited=list(self.bars)
        z=edited[249]
        edited[249]=Candle(z.ts,z.open,z.high*3,z.low,z.close,z.volume)
        after=simulate_hindsight_trade(edited,240,250,settings=load_settings(),stake_quote=50)
        self.assertAlmostEqual(orig['net_pnl_quote'],after['net_pnl_quote'],places=8)

    def test_only_completed_trades_reconciled_to_v8(self):
        result=compare_costs(self.bars,self.root/'wallet')['fee_on']
        report=analyze_hindsight(self.bars,result)
        self.assertEqual(result['completed_trades'],1)
        self.assertEqual(report['completed_trades_scored'],1)
        row=report['trade_exit_diagnostics'][0]
        self.assertAlmostEqual(row['actual_net_quote'],result['trades'][0]['net_pnl_quote'])
        self.assertGreater(row['best_next_open_fees_quote'],0)
        self.assertGreater(row['best_next_open_exit_ts'],row['entry_ts'])
        self.assertGreaterEqual(row['best_delayed_entry_ts'],row['entry_ts'])
        self.assertLess(row['best_delayed_entry_ts'],row['best_delayed_exit_ts'])
        self.assertGreater(row['best_delayed_fees_quote'],0)
        self.assertTrue(report['historical_future_used_for_diagnostics'])
        self.assertFalse(report['future_used_for_decisions'])
        self.assertTrue(report['paper_only'])

    def test_no_exaggerated_cumulative_earning_from_unmatched_signals(self):
        report=analyze_hindsight(self.bars,compare_costs(self.bars,self.root/'wallet')['fee_on'])
        self.assertGreater(report['unmatched_signals_scored'],0)
        self.assertEqual(report['unmatched_signals_scored'],len(report['unmatched_signal_diagnostics']))
        for row in report['unmatched_signal_diagnostics']:
            self.assertEqual(row['execution_status'],'unmatched_completed_trade')
            self.assertIn('not attainable cumulative profit',row['warning'])
            self.assertLess(row['signal_ts'],row['hypothetical_best_entry_ts'])
            self.assertLess(row['hypothetical_best_entry_ts'],row['hypothetical_best_exit_ts'])

    def test_fee_assumptions_change_hindsight_net(self):
        actual=compare_costs(self.bars,self.root/'wallet')['fee_on']
        a=analyze_hindsight(self.bars,actual,settings=load_settings())
        b=analyze_hindsight(self.bars,actual,settings=FeeSettings.zero())
        self.assertNotAlmostEqual(a['trade_exit_diagnostics'][0]['best_next_open_net_quote'],
                                  b['trade_exit_diagnostics'][0]['best_next_open_net_quote'])

    def test_purge_prevents_looking_past_scoring_end(self):
        actual=compare_costs(self.bars,self.root/'wallet')['fee_on']
        hp=HindsightParameters(holding_bars=60,entry_delay_bars=6)
        report=analyze_hindsight(self.bars,actual,hindsight_params=hp,
                                  score_start_idx=0,score_end_idx=280)
        for row in report['trade_exit_diagnostics']:
            self.assertLess(row['best_next_open_exit_ts'],self.bars[280].ts)
        for row in report['unmatched_signal_diagnostics']:
            self.assertLess(row['hypothetical_best_exit_ts'],self.bars[280].ts)
        # All windows that require prices beyond 280 are omitted entirely.
        short=analyze_hindsight(self.bars,actual,hindsight_params=hp,
                                 score_start_idx=270,score_end_idx=280)
        self.assertEqual(short['completed_trades_scored'],0)
        self.assertEqual(short['unmatched_signals_scored'],0)

    def test_missing_realized_trade_timestamp_rejected(self):
        actual=compare_costs(self.bars,self.root/'wallet')['fee_on']
        actual['trades'][0]['entry_ts']=-1
        with self.assertRaisesRegex(ValueError,'missing in candle history'):
            analyze_hindsight(self.bars,actual)

    def test_negative_market_can_still_have_negative_best_hindsight(self):
        from datetime import datetime,timezone
        base=int(datetime(2024,1,1,tzinfo=timezone.utc).timestamp())
        down=[Candle(base+i*14400,100-i*.5,100-i*.5+.01,
                     100-i*.5-.01,100-i*.5,10.) for i in range(20)]
        outcome=simulate_hindsight_trade(down,3,4,settings=load_settings(),stake_quote=50)
        self.assertLess(outcome['net_pnl_quote'],0)

    def test_expanding_nonoverlapping_folds_embargo(self):
        f=chronological_folds(1000,min_train_bars=360,test_bars=120,purge_bars=70)
        self.assertGreater(len(f),1)
        for index,z in enumerate(f):
            self.assertEqual(z['test_start_idx']-z['train_end_exclusive'],70)
            self.assertLess(z['test_start_idx'],z['test_end_exclusive'])
            if index:self.assertGreaterEqual(z['test_start_idx'],f[index-1]['test_end_exclusive'])

    def test_bad_horizons_fail_closed(self):
        for hp in [(-1,60),(1,0),(101,20)]:
            with self.assertRaises(ValueError):HindsightParameters(entry_delay_bars=hp[0],holding_bars=hp[1])
        with self.assertRaises(ValueError):chronological_folds(0)

    def test_trade_after_ts_allows_warmup_without_trades(self):
        params=BacktestParameters()
        result=run_backtest(self.bars,self.root/'late.sqlite',params=params,
                            trade_after_ts=self.bars[-2].ts)
        self.assertEqual(result['completed_trades'],0)
        self.assertEqual(result['account_final_liquidation_quote'],1000.)

    def test_walkforward_has_train_only_selection_and_embargo(self):
        a=BacktestParameters(breakout_bars=30,exit_low_bars=15,fast_ema_bars=10,slow_ema_bars=30)
        b=replace(a,breakout_bars=60)
        out=validate_walk_forward(self.bars,candidates=(a,b),
            min_train_bars=300,test_bars=110,purge_bars=70,
            hindsight_params=HindsightParameters(holding_bars=10,entry_delay_bars=2))
        self.assertTrue(out['historical_oracle_not_used_for_parameter_selection'])
        self.assertGreater(len(out['folds']),1)
        for z in out['folds']:
            self.assertEqual(len(z['train_candidate_net_returns']),2)
            self.assertGreater(z['test_start_ts'],z['train_end_ts'])
            self.assertLessEqual(z['selected_candidate_index_FROM_TRAIN_ONLY'],1)
            self.assertTrue(math.isfinite(z['test_net_return_pct']))

    def test_walkforward_short_data_and_too_small_purge_refused(self):
        a=BacktestParameters()
        with self.assertRaisesRegex(ValueError,'Purge shorter'):
            validate_walk_forward(self.bars,candidates=(a,),purge_bars=1)
        with self.assertRaisesRegex(ValueError,'Not enough candles'):
            validate_walk_forward(self.bars,candidates=(a,),min_train_bars=700,
                                  test_bars=100,purge_bars=100)


if __name__=='__main__':unittest.main()


class HindsightCliIntegrationTests(unittest.TestCase):
    """Exercise the entire offline CLI with interval override and empty-cache refusal."""

    def test_cli_60_minute_override_preserves_interval_and_output(self):
        from contextlib import redirect_stdout
        from io import StringIO
        from data_layer.storage import CandleStore
        from hindsight.cli import main
        from examples.backtest_demo import make_bars

        with tempfile.TemporaryDirectory() as work:
            work = Path(work)
            fixture = make_bars()
            hourly = [Candle(1704067200+i*3600,
                             c.open,c.high,c.low,c.close,c.volume)
                      for i,c in enumerate(fixture)]
            db = work/'synthetic_fixture.sqlite'
            with CandleStore(db) as store:
                store.upsert('kraken','BTC/AUD',60,hourly,
                             source='SYNTHETIC_UNIT_TEST_NOT_REAL_KRAKEN')
            out = work/'cli_output'
            with redirect_stdout(StringIO()):
                main(['--market-db',str(db),'--out',str(out),
                      '--interval','60','--entry-delay','2','--holding-bars','10'])
            import json
            data = json.loads((out/'hindsight.json').read_text())
            self.assertEqual(data['provenance']['interval_minutes'],60)
            self.assertFalse(data['provenance']['verified_exchange_provenance'])
            self.assertIn('SYNTHETIC_UNIT_TEST',
                          str(data['provenance']['sources_in_database']))
            self.assertTrue((out/'backtest'/'costs_on.sqlite').is_file())

    def test_cli_rejects_empty_database_without_creating_output(self):
        from contextlib import redirect_stderr
        from io import StringIO
        from data_layer.storage import CandleStore
        from hindsight.cli import main
        with tempfile.TemporaryDirectory() as work:
            work=Path(work)
            db=work/'empty.sqlite'
            with CandleStore(db): pass
            out=work/'should_not_exist'
            with redirect_stderr(StringIO()):
                with self.assertRaises(SystemExit) as context:
                    main(['--market-db',str(db),'--out',str(out)])
            self.assertEqual(context.exception.code,2)
            self.assertFalse(out.exists())


class WalkForwardLeakageRegressionTests(unittest.TestCase):
    def test_mutating_future_test_prices_cannot_change_train_only_selection(self):
        from examples.backtest_demo import make_bars
        bars = make_bars()[:480]
        shifted = list(bars)
        # Train ends at bar 299 and bars 300-369 are embargoed. Altering
        # test bars 370-479 must not influence fold-1 candidate selection.
        for i in range(370,len(shifted)):
            c=shifted[i]
            shifted[i]=Candle(c.ts,c.open*1.4,c.high*1.4,
                              c.low*1.4,c.close*1.4,c.volume)
        p=BacktestParameters(breakout_bars=30,exit_low_bars=15,
                             fast_ema_bars=10,slow_ema_bars=30)
        kwargs=dict(candidates=(p,replace(p,breakout_bars=60)),
                    min_train_bars=300,test_bars=110,purge_bars=70,
                    hindsight_params=HindsightParameters(holding_bars=10,entry_delay_bars=2))
        baseline=validate_walk_forward(bars,**kwargs)['folds'][0]
        modified=validate_walk_forward(shifted,**kwargs)['folds'][0]
        self.assertEqual(baseline['train_candidate_net_returns'],
                         modified['train_candidate_net_returns'])
        self.assertEqual(baseline['selected_candidate_index_FROM_TRAIN_ONLY'],
                         modified['selected_candidate_index_FROM_TRAIN_ONLY'])

"""Roadmap 4 integration: *the exact V7 PaperEngine* is used on both sides."""
import json
import math
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from contextlib import closing

from backtester import (BacktestParameters, DonchianBreakout, compare_costs,
                        run_backtest, metrics_from_wallet)
from backtester.engine import candles_from_store
from data_layer.storage import Candle, CandleStore
from examples.backtest_demo import make_bars
from paper_engine import RiskLimits, PaperEngine
from trading_costs import FeeSettings

STEP=240*60
BASE=1704067200  # 2024-01-01, 4h aligned


def flat(n=220):
    return [Candle(BASE+STEP*i,100,100.1,99.9,100,10) for i in range(n)]


class BacktesterTests(unittest.TestCase):
    def setUp(self):
        self.dir=tempfile.TemporaryDirectory()
        self.root=Path(self.dir.name)

    def tearDown(self):self.dir.cleanup()

    def test_identical_bars_fee_on_off_and_wallet_reconciliation(self):
        result=compare_costs(make_bars(),self.root/'out')
        paid,free=result['fee_on'],result['fee_off']
        self.assertGreater(paid['completed_trades'],0)
        self.assertEqual(paid['completed_trades'],free['completed_trades'])
        self.assertLess(paid['total_return_net_pct'],free['total_return_net_pct'])
        self.assertGreater(paid['total_trading_fees_quote'],0)
        self.assertEqual(free['total_trading_fees_quote'],0)
        self.assertEqual(free['total_spread_quote'],0)
        self.assertEqual(free['total_slippage_quote'],0)
        self.assertTrue(paid['verification']['ok'])
        self.assertEqual(len(paid['equity_curve']),len(make_bars()))
        self.assertAlmostEqual(paid['realized_net_pnl_quote']+paid['unrealized_liquidation_pnl_quote'],
                               paid['account_final_liquidation_quote']-paid['account_initial_quote'],places=6)

    def test_every_trade_is_gross_minus_all_costs(self):
        active=compare_costs(make_bars(),self.root/'out')['fee_on']
        for t in active['trades']:
            self.assertAlmostEqual(t['net_pnl_quote'],t['gross_pnl_quote']-t['total_costs_quote'],places=7)
            self.assertIn('entry_fee_quote',t)
            self.assertIn('exit_fee_quote',t)
            self.assertIn('slippage_quote',t)
        self.assertAlmostEqual(active['realized_net_pnl_quote'],sum(t['net_pnl_quote'] for t in active['trades']))
        with closing(sqlite3.connect(self.root/'out'/'costs_on.sqlite')) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM trades').fetchone()[0],active['completed_trades'])

    def test_flat_market_means_no_trades_no_false_profits_or_sharpe(self):
        result=compare_costs(flat(),self.root/'out')
        a=result['fee_on']
        self.assertEqual(a['completed_trades'],0)
        self.assertIsNone(a['net_win_rate_pct'])
        self.assertIsNone(a['net_profit_factor'])
        self.assertIsNone(a['annualized_sharpe_zero_riskfree'])
        self.assertEqual(a['account_final_liquidation_quote'],1000)
        self.assertEqual(a['fees_pct_of_gross_winning_trade_profit'],None)

    def test_refuses_gaps_even_on_zero_volume(self):
        bars=flat(12)
        del bars[4]
        with self.assertRaisesRegex(ValueError,'Non-contiguous'):
            compare_costs(bars,self.root/'out')
        self.assertFalse((self.root/'out').exists())

    def test_refuses_unsorted_duplicate_and_invalid_ohlc(self):
        bars=flat(10)
        with self.assertRaisesRegex(ValueError,'Non-contiguous'):
            compare_costs(bars+[bars[-1]],self.root/'a')
        bars[3]=Candle(bars[3].ts,100,99,98,100,10)
        with self.assertRaises(ValueError):compare_costs(bars,self.root/'b')

    def test_no_wallet_overwrite(self):
        result=compare_costs(flat(),self.root/'x')
        self.assertTrue((self.root/'x'/'costs_on.sqlite').is_file())
        with self.assertRaisesRegex(FileExistsError,'already exists'):
            compare_costs(flat(),self.root/'x')

    def test_causal_indicator_prior_high_does_not_include_current(self):
        params=BacktestParameters(breakout_bars=3,exit_low_bars=2,fast_ema_bars=2,slow_ema_bars=3)
        s=DonchianBreakout(params)
        candles=[Candle(BASE+i*STEP,c,c+0.01,c-0.01,c,10) for i,c in enumerate([100,100,100,100,110])]
        outcomes=[s.observe(c)[0] for c in candles]
        self.assertEqual(outcomes,[False,False,False,False,True])

    def test_next_open_only_and_zero_future_leak(self):
        params=BacktestParameters(breakout_bars=3,exit_low_bars=2,fast_ema_bars=2,slow_ema_bars=3)
        data=[Candle(BASE+i*STEP,*prices,volume=10) for i,prices in enumerate([
            (100,100.01,99.99,100),(100,100.01,99.99,100),
            (100,100.01,99.99,100),(100,100.01,99.99,100),
            (100,110,100,109),(109,110,109,109),(109,112,108,110),
            (110,111,101,103),(103,104,100,101),(101,102,99,100)])]
        result=run_backtest(data,self.root/'a.sqlite',params=params)
        with closing(sqlite3.connect(self.root/'a.sqlite')) as db:
            # The entry signal occurs at candle 4 close: its next executable open is candle 5.
            ts=db.execute("SELECT filled_ts FROM orders WHERE side='buy' AND status='filled' ORDER BY id LIMIT 1").fetchone()
        self.assertEqual(ts[0],BASE+5*STEP)
        edited=data[:6]+[Candle(c.ts,c.open,c.high+10,c.low,c.close,c.volume) for c in data[6:]]
        run_backtest(edited,self.root/'b.sqlite',params=params)
        with closing(sqlite3.connect(self.root/'b.sqlite')) as db:
            second=db.execute("SELECT filled_ts FROM orders WHERE side='buy' AND status='filled' ORDER BY id LIMIT 1").fetchone()
        self.assertEqual(second[0],ts[0])

    def test_empty_market_database_errors_and_carries_provenance(self):
        with CandleStore(self.root/'market.sqlite') as s:
            self.assertEqual(s.coverage()['n'],0)
            s.upsert('kraken','BTC/AUD',240,flat(5),'SYNTHETIC_TEST_FIXTURE')
        bars,source=candles_from_store(self.root/'market.sqlite',240)
        self.assertFalse(source['verified_exchange_provenance'])
        self.assertIn('SYNTHETIC_TEST_FIXTURE',source['sources_in_database'])
        self.assertEqual(len(bars),5)
        with self.assertRaisesRegex(ValueError,'No OHLCV'):
            compare_costs([],self.root/'no')

    def test_metrics_risk_treatment_cost_and_drawdown_bounded(self):
        result=compare_costs(make_bars(),self.root/'out')
        a=result['fee_on']
        self.assertLessEqual(a['max_drawdown_pct'],0)
        self.assertTrue(math.isfinite(a['annualized_sharpe_zero_riskfree']))
        self.assertEqual(a['net_win_rate_pct'],100*a['wins_net']/a['completed_trades'])
        self.assertAlmostEqual(a['total_explicit_and_implicit_costs_quote'],
                               a['total_trading_fees_quote']+a['total_spread_quote']+a['total_slippage_quote'])
        self.assertGreater(a['fees_pct_of_gross_winning_trade_profit'],0)

    def test_fee_off_replay_is_not_modified_fee_profile(self):
        zero=FeeSettings.zero()
        self.assertEqual(zero.rate('taker'),0)
        paid=compare_costs(make_bars(),self.root/'out')
        with PaperEngine(self.root/'out'/'costs_on.sqlite') as w:
            self.assertGreater(w.settings.rate('taker'),0)
        with PaperEngine(self.root/'out'/'costs_off.sqlite') as w:
            self.assertEqual(w.settings.rate('taker'),0)

    def test_cli_fails_empty_real_data_without_creating_trades(self):
        with CandleStore(self.root/'empty.sqlite'):pass
        p=subprocess.run([sys.executable,'-m','backtester.cli','--market-db',
                          str(self.root/'empty.sqlite'),'--out',str(self.root/'none')],
                          cwd=Path(__file__).resolve().parents[1],text=True,capture_output=True)
        self.assertNotEqual(p.returncode,0)
        self.assertIn('No OHLCV candles',p.stderr)
        self.assertFalse((self.root/'none'/'costs_on.sqlite').exists())

if __name__=='__main__':unittest.main()

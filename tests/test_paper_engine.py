"""Persistent paper wallet: fee-included cash, exactly-once candles and failsafes."""
import math
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from data_layer.storage import Candle
from paper_engine import PaperEngine, RiskLimits
from trading_costs import FeeSettings

BASE=240*60*100
STEP=240*60


def candle(k, o=100, h=None, l=None, c=None):
    c=o if c is None else c
    return Candle(BASE+k*STEP,o,max(o,c) if h is None else h,
                  min(o,c) if l is None else l,c,10)


class PaperEngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.db=Path(self.tmp.name)/'test.sqlite'
        self.p=PaperEngine(self.db)
        self.p.on_candle(candle(0))

    def tearDown(self):
        self.p.close();self.tmp.cleanup()

    def test_market_buy_sell_with_full_fee_reconciliation(self):
        ident=self.p.place_buy(50,client_id='a')
        self.assertEqual(self.p.place_buy(50,client_id='a'),ident)
        self.assertEqual(len(self.p.status()['pending']),1)
        self.assertTrue(self.p.on_candle(candle(1))['opened'])
        self.assertAlmostEqual(self.p.status()['cash_quote'],950,places=7)
        self.assertAlmostEqual(self.p.status()['position']['entry_outlay'],50,places=7)
        oid=self.p.place_sell()
        self.assertTrue(self.p.on_candle(candle(2,105,106,104,105))['exited'])
        trade=self.p.trades()[0]
        self.assertGreater(trade['net_pnl_quote'],0)
        self.assertLess(trade['net_pnl_quote'],trade['gross_pnl_quote'])
        self.assertAlmostEqual(self.p.status()['cash_quote'],1000+trade['net_pnl_quote'],places=8)
        self.assertAlmostEqual(trade['gross_pnl_quote']-trade['total_costs_quote'],trade['net_pnl_quote'],places=9)
        self.assertEqual(self.p.verify()['fills'],2)
        self.assertEqual(self.p.verify()['closed_trades'],1)
        self.assertTrue(any(x['id']==oid and x['status']=='filled' for x in self.p.orders()))

    def test_no_entry_fill_before_next_closed_bar(self):
        self.p.place_buy(50)
        self.assertEqual(self.p.status()['cash_quote'],1000)
        self.assertEqual(self.p.status()['position'],None)
        self.assertTrue(self.p.on_candle(candle(1))['opened'])

    def test_stop_wins_same_bar_collision(self):
        self.p.place_buy(50,stop_pct=.045,target_pct=.075)
        result=self.p.on_candle(candle(1,100,110,90,102))
        self.assertTrue(result['opened'])
        self.assertTrue(result['exited'])
        trade=self.p.trades()[0]
        self.assertEqual(trade['reason'],'stop_intrabar')
        self.assertLess(trade['net_pnl_quote'],0)
        self.assertEqual(self.p.verify()['fills'],2)

    def test_gap_below_stop_fills_at_worse_open(self):
        self.p.place_buy(50)
        self.p.on_candle(candle(1,100,101,99,100))
        self.p.on_candle(candle(2,87,88,80,81))
        trade=self.p.trades()[0]
        self.assertEqual(trade['reason'],'stop_gap')
        self.assertLess(trade['net_pnl_quote'],-5)

    def test_limit_uses_resting_maker_only_after_trade_through(self):
        oid=self.p.place_buy(50,kind='limit',limit_mid=98)
        self.p.on_candle(candle(1,100,101,99,100))
        self.assertEqual(len(self.p.status()['pending']),1)
        # Limit order not filled just by touching exact price (requires trade-through).
        self.p.on_candle(candle(2,100,101,98,100))
        self.assertEqual(len(self.p.status()['pending']),1)
        self.p.on_candle(candle(3,100,120,96,100))
        self.assertIsNotNone(self.p.status()['position'])
        self.assertEqual(self.p.trades(),[])
        exe=self.p.db.execute('SELECT execution_json FROM fills WHERE order_id=?',(oid,)).fetchone()
        self.assertIn('"liquidity":"maker"',exe['execution_json'])
        # Same-bar limit target is not credited when path is unknown.
        self.p.on_candle(candle(4,92,93,85,89))
        self.assertEqual(self.p.trades()[0]['reason'],'stop_gap')

    def test_limit_entry_ambiguous_stop_conservatively_exits(self):
        self.p.place_buy(50,kind='limit',limit_mid=98)
        outcome=self.p.on_candle(candle(1,100,120,90,101))
        self.assertTrue(outcome['opened'])
        self.assertTrue(outcome['exited'])
        self.assertEqual(self.p.trades()[0]['reason'],'stop_intrabar')

    def test_duplicate_client_id_conflicting_order_rejected(self):
        self.p.place_buy(50,client_id='unique')
        with self.assertRaisesRegex(ValueError,'reused'):
            self.p.place_buy(45,client_id='unique')
        with self.assertRaisesRegex(ValueError,'reused'):
            self.p.place_sell(client_id='unique')

    def test_halted_wallet_allows_existing_position_to_close(self):
        self.p.close()
        db=Path(self.tmp.name)/'halt-open.sqlite'
        risk=RiskLimits(max_order_quote=500,max_position_fraction=.5,
                        daily_loss_limit=.01,peak_drawdown_limit=.04)
        self.p=PaperEngine(db,risk=risk)
        self.p.on_candle(candle(0))
        self.p.place_buy(500,stop_pct=.2)
        self.p.on_candle(candle(1,100,100,99,99))
        self.assertIsNotNone(self.p.status()['position'])
        # A mild adverse move breaches the account daily limit without
        # touching the wide protective stop.
        self.p.on_candle(candle(2,98,99,97.5,98))
        self.assertEqual(self.p.status()['halt_reason'],'daily_loss')
        self.assertIsNotNone(self.p.status()['position'])
        with self.assertRaises(ValueError):self.p.place_buy(50)
        self.p.place_sell()
        self.p.on_candle(candle(3,98,98.5,97.9,98))
        self.assertIsNone(self.p.status()['position'])
        self.assertEqual(len(self.p.trades()),1)
        self.assertTrue(self.p.verify()['ok'])

    def test_status_uses_same_volatility_as_equity_snapshot(self):
        self.p.place_buy(50)
        snapshot=self.p.on_candle(candle(1),volatility_frac=.04)
        persisted=self.p.db.execute('SELECT equity_net FROM equity_snapshots WHERE ts=?',(BASE+STEP,)).fetchone()[0]
        self.assertAlmostEqual(snapshot['equity_net_quote'],persisted,places=8)
        self.p.close(); self.p=PaperEngine(self.db)
        self.assertAlmostEqual(self.p.status()['equity_net_quote'],persisted,places=8)

    def test_market_exit_after_open_and_protective_exit_priority(self):
        self.p.place_buy(50);self.p.on_candle(candle(1))
        pending_sell=self.p.place_sell()
        self.p.on_candle(candle(2,80,105,78,99))
        self.assertEqual(self.p.trades()[0]['reason'],'stop_gap')
        self.assertTrue(any(o['id']==pending_sell and o['status']=='cancelled' for o in self.p.orders()))

    def test_limit_sell_when_passed_and_fee_maker(self):
        self.p.place_buy(50,target_pct=.90)
        self.p.on_candle(candle(1))
        self.p.place_sell(kind='limit',limit_mid=104)
        self.p.on_candle(candle(2,102,104,102,103))
        self.assertEqual(self.p.trades(),[])
        self.p.on_candle(candle(3,102,105,101,103))
        self.assertEqual(self.p.trades()[0]['exit_order_type'],'maker')

    def test_cancel_order_does_not_modify_cash(self):
        oid=self.p.place_buy(50)
        self.p.cancel(oid)
        self.p.on_candle(candle(1))
        self.assertEqual(self.p.status()['cash_quote'],1000)
        self.assertIsNone(self.p.status()['position'])
        with self.assertRaises(ValueError):self.p.cancel(oid)

    def test_reopen_preserves_ledger_and_pending_orders(self):
        self.p.place_buy(50,client_id='first')
        self.p.close()
        self.p=PaperEngine(self.db)
        self.assertEqual(len(self.p.status()['pending']),1)
        self.p.on_candle(candle(1))
        self.p.close()
        self.p=PaperEngine(self.db)
        self.assertIsNotNone(self.p.status()['position'])
        self.p.place_sell(client_id='close')
        self.p.on_candle(candle(2,104,105,103,104))
        self.assertEqual(len(self.p.trades()),1)
        self.assertTrue(self.p.verify()['ok'])
        self.assertEqual(len(self.p.orders()),2)

    def test_cost_config_immutable_after_restart(self):
        self.p.close()
        with self.assertRaises(ValueError): PaperEngine(self.db,settings=FeeSettings.zero())
        self.p=PaperEngine(self.db)

    def test_repeated_identical_candle_is_noop(self):
        self.p.place_buy(50)
        original=self.p.on_candle(candle(1))
        self.assertTrue(original['opened'])
        repeat=self.p.on_candle(candle(1))
        self.assertTrue(repeat['duplicate'])
        self.assertEqual(self.p.verify()['fills'],1)
        with self.assertRaises(ValueError):self.p.on_candle(candle(1,102,103,101,102))
        self.assertEqual(self.p.verify()['fills'],1)

    def test_out_of_order_gap_and_bad_candle_rejected(self):
        with self.assertRaises(ValueError):self.p.on_candle(candle(2))
        self.assertEqual(self.p.status()['last_ts'],BASE)
        with self.assertRaises(ValueError):self.p.on_candle(Candle(BASE+STEP,-1,1,-2,-1,1))
        self.p.on_candle(candle(2),allow_gap=True)
        self.assertEqual(self.p.status()['last_ts'],BASE+2*STEP)

    def test_reject_oversize_pending_duplicate_and_missing_position(self):
        with self.assertRaises(ValueError):self.p.place_buy(60)
        with self.assertRaises(ValueError):self.p.place_buy(1)
        with self.assertRaises(ValueError):self.p.place_sell()
        self.p.place_buy(50)
        with self.assertRaises(ValueError):self.p.place_buy(20)

    def test_fee_free_comparison_is_more_profitable(self):
        with tempfile.TemporaryDirectory() as d:
            no=PaperEngine(Path(d)/'zero.sqlite',settings=FeeSettings.zero())
            no.on_candle(candle(0))
            no.place_buy(50);no.on_candle(candle(1))
            no.place_sell();no.on_candle(candle(2,105,106,104,105))
            net0=no.trades()[0]['net_pnl_quote'];no.close()
        self.p.place_buy(50);self.p.on_candle(candle(1))
        self.p.place_sell();self.p.on_candle(candle(2,105,106,104,105))
        net=self.p.trades()[0]['net_pnl_quote']
        self.assertAlmostEqual(net0,2.5,places=8)
        self.assertGreater(net0,net)

    def test_risk_halt_survives_restart_and_exits_remain_allowed(self):
        self.p.close()
        db=Path(self.tmp.name)/'risk.sqlite'
        limits=RiskLimits(max_order_quote=500,max_position_fraction=.5,
                          daily_loss_limit=.01,peak_drawdown_limit=.04)
        self.p=PaperEngine(db,risk=limits)
        self.p.on_candle(candle(0))
        self.p.place_buy(500)
        self.p.on_candle(candle(1))
        # Stop loss after a gap; account loss passes 1% and permanent risk halt.
        self.p.on_candle(candle(2,90,92,88,90))
        self.assertEqual(self.p.status()['halt_reason'],'daily_loss')
        self.assertLess(self.p.status()['equity_net_quote'],990)
        with self.assertRaises(ValueError):self.p.place_buy(20)
        self.p.close();self.p=PaperEngine(db)
        self.assertEqual(self.p.status()['halt_reason'],'daily_loss')
        self.assertTrue(self.p.verify()['ok'])

    def test_atomic_transaction_rollback(self):
        self.p.place_buy(50)
        self.p.on_candle(candle(1))
        cash=self.p.status()['cash_quote']
        orig=self.p._assert_reconciled
        def fault():raise ArithmeticError('Injected failure for atomicity test')
        self.p._assert_reconciled=fault
        with self.assertRaisesRegex(ArithmeticError,'Injected'):
            self.p.on_candle(candle(2,105,106,104,105))
        self.p._assert_reconciled=orig
        self.assertEqual(self.p.status()['last_ts'],BASE+STEP)
        self.assertEqual(self.p.status()['cash_quote'],cash)
        self.assertEqual(self.p.trades(),[])
        self.assertTrue(self.p.verify()['ok'])

    def test_invalid_client_fill_non_numeric_rejected(self):
        with self.assertRaises(ValueError):self.p.place_buy(float('nan'))
        with self.assertRaises(ValueError):self.p.place_buy(50,stop_pct=-.01)
        with self.assertRaises(ValueError):self.p.place_buy(50,kind='limit')
        with self.assertRaises(ValueError):self.p.on_candle(candle(1),volatility_frac=float('nan'))

    def test_cli_offline_initialize_and_status(self):
        db=Path(self.tmp.name)/'cli.sqlite'
        for cmd in ('init','status','verify'):
            p=subprocess.run([sys.executable,'-m','paper_engine.cli','--db',str(db),cmd],
                             text=True,capture_output=True,check=True)
            self.assertTrue(p.stdout.strip())
            self.assertNotIn('Traceback',p.stderr)


if __name__=='__main__':unittest.main()

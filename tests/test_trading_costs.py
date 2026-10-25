"""All costs must reconcile to actual estimated quote cashflows, incl off baseline."""
import math
import unittest
from dataclasses import replace
from trading_costs import (
    FeeTier, FeeSettings, load_settings, estimate_execution, settle_trade,
    quantity_for_quote_budget, minimum_break_even_move, expected_trade_edge,
    ledger_to_log
)

class UnifiedFeeModelTests(unittest.TestCase):
    def setUp(self):
        self.cfg=load_settings()

    def test_default_kraken_retail_tier(self):
        self.assertEqual(self.cfg.exchange,'kraken')
        self.assertEqual(self.cfg.rate('maker'),0.004)
        self.assertEqual(self.cfg.rate('taker'),0.008)

    def test_fee_volume_tier_in_usd_not_aud(self):
        self.assertEqual(self.cfg.rate('taker',2499),.008)
        self.assertEqual(self.cfg.rate('taker',2500),.006)
        self.assertEqual(self.cfg.rate('maker',10000),.0022)

    def test_trade_ledger_reconciles_gross_to_net(self):
        qty=quantity_for_quote_budget(100000,50,self.cfg,volatility_frac=.02)
        t=settle_trade(100000,104000,qty,self.cfg,volatility_frac=.02)
        self.assertAlmostEqual(t.gross_pnl_quote-t.total_costs_quote,t.net_pnl_quote,places=9)
        self.assertAlmostEqual(t.entry_total_outlay_quote,50,places=9)
        self.assertAlmostEqual(t.net_pnl_quote,1.029338338878766,places=5)
        self.assertAlmostEqual(t.trading_fees_quote, t.entry.fee_quote+t.exit.fee_quote)
        self.assertAlmostEqual(t.exit_total_received_quote-t.entry_total_outlay_quote,t.net_pnl_quote)

    def test_costless_trade_has_exact_midpoint_profit(self):
        cfg=FeeSettings.zero()
        x=settle_trade(100,110,2,cfg)
        self.assertAlmostEqual(x.gross_pnl_quote,20)
        self.assertAlmostEqual(x.net_pnl_quote,20)
        self.assertAlmostEqual(x.total_costs_quote,0)
        self.assertAlmostEqual(quantity_for_quote_budget(100,50,cfg),.5)

    def test_both_fees_even_on_flat_market(self):
        x=settle_trade(100,100,1,self.cfg)
        self.assertGreater(x.entry.fee_quote,0)
        self.assertGreater(x.exit.fee_quote,0)
        self.assertLess(x.net_pnl_quote,0)

    def test_maker_is_cheaper_assuming_fill(self):
        tk=settle_trade(100,102,1,self.cfg)
        mk=settle_trade(100,102,1,self.cfg,entry_liquidity='maker',exit_liquidity='maker')
        self.assertGreater(mk.net_pnl_quote,tk.net_pnl_quote)
        self.assertLess(mk.trading_fees_quote,tk.trading_fees_quote)
        self.assertLess(mk.spread_quote,0)  # passive bid/ask improvement only if filled

    def test_higher_volatility_and_order_size_cost_more(self):
        a=estimate_execution(100,1,'buy','taker',self.cfg,volatility_frac=0)
        b=estimate_execution(100,1,'buy','taker',self.cfg,volatility_frac=.05)
        c=estimate_execution(100,20,'buy','taker',self.cfg,volatility_frac=.05)
        self.assertGreater(b.slippage_rate,a.slippage_rate)
        self.assertGreater(c.slippage_rate,b.slippage_rate)

    def test_slippage_capped(self):
        x=estimate_execution(100,10000,'sell','taker',self.cfg,volatility_frac=3)
        self.assertLessEqual(x.slippage_rate,self.cfg.max_slippage_bps/10000)

    def test_spot_cannot_have_funding(self):
        with self.assertRaises(ValueError):replace(self.cfg,funding_rate_per_8h=.001)

    def test_perpetual_funding_signed(self):
        c=replace(self.cfg,instrument='perpetual',funding_rate_per_8h=.0001)
        t=settle_trade(100,110,2,c,holding_hours=16)
        self.assertAlmostEqual(t.funding_quote,.04)
        b=settle_trade(100,110,2,replace(c,funding_rate_per_8h=-.0001),holding_hours=16)
        self.assertAlmostEqual(b.funding_quote,-.04)
        self.assertGreater(b.net_pnl_quote,t.net_pnl_quote)

    def test_transfer_charges_opt_in_not_per_trade(self):
        c=replace(self.cfg,withdrawal_fee_quote=1,network_fee_quote=.2)
        no=settle_trade(100,105,1,c)
        yes=settle_trade(100,105,1,c,include_transfer_fees=True)
        self.assertAlmostEqual(no.net_pnl_quote-yes.net_pnl_quote,1.2)

    def test_break_even_and_decision_use_same_model(self):
        thr=minimum_break_even_move(100000,50,self.cfg,volatility_frac=.02)
        self.assertTrue(.018<thr<.021)
        approved,trade=expected_trade_edge(100000,100000*(1+thr),50,self.cfg,
                                        minimum_net_return=0,volatility_frac=.02)
        self.assertTrue(approved)
        self.assertAlmostEqual(trade.net_pnl_quote,0,places=8)
        declined,_=expected_trade_edge(100000,100000*(1+thr-.002),50,self.cfg,
                                        minimum_net_return=0,volatility_frac=.02)
        self.assertFalse(declined)
        edge=minimum_break_even_move(100000,50,self.cfg,volatility_frac=.02,
                                      min_net_edge=.012)
        self.assertGreater(edge,thr)

    def test_invalid_rates_and_prices_rejected(self):
        with self.assertRaises(ValueError):FeeTier(0,.4,1.8)
        with self.assertRaises(ValueError):settle_trade(0,100,1,self.cfg)
        with self.assertRaises(ValueError):settle_trade(100,100,float('nan'),self.cfg)
        with self.assertRaises(ValueError):self.cfg.rate('taker',-1)
        with self.assertRaises(ValueError):FeeSettings(tiers=(FeeTier(0,.004,.008),FeeTier(0,.003,.006)))

    def test_logs_have_all_required_columns(self):
        log=ledger_to_log(settle_trade(100,105,1,self.cfg))
        for name in ('gross_pnl_quote','entry_fee_quote','exit_fee_quote',
                     'total_trading_fees_quote','spread_quote','slippage_quote',
                     'net_pnl_quote','net_return_pct','entry_execution_price',
                     'exit_execution_price'):
            self.assertIn(name,log)
        self.assertAlmostEqual(log['gross_pnl_quote']-log['total_costs_quote'],log['net_pnl_quote'])

    def test_zero_cost_comparison_is_higher_pnl(self):
        a=settle_trade(100,110,1,self.cfg)
        b=settle_trade(100,110,1,FeeSettings.zero())
        self.assertGreater(b.net_pnl_quote,a.net_pnl_quote)
        self.assertAlmostEqual(b.net_pnl_quote,10)

if __name__=='__main__':unittest.main()

"""Example self-contained fee cost calculator, entirely offline."""
import argparse
import json
from .model import (load_settings, settle_trade, quantity_for_quote_budget,
                    minimum_break_even_move, ledger_to_log)

def main():
    p=argparse.ArgumentParser(description='Paper-only fee-aware trade calculation')
    p.add_argument('--buy',type=float,required=True,help='Mid-market entry price AUD/BTC')
    p.add_argument('--sell',type=float,required=True,help='Mid-market exit price AUD/BTC')
    p.add_argument('--budget',type=float,default=50,help='Max total entry outlay in AUD')
    p.add_argument('--volatility',type=float,default=.02,help='ATR as a fraction, e.g. 0.02')
    p.add_argument('--maker-entry',action='store_true')
    p.add_argument('--maker-exit',action='store_true')
    p.add_argument('--volume-usd',type=float,default=0)
    p.add_argument('--hold-hours',type=float,default=48)
    p.add_argument('--profile',type=str,default=None)
    a=p.parse_args();cfg=load_settings(a.profile)
    enter='maker' if a.maker_entry else 'taker';leave='maker' if a.maker_exit else 'taker'
    qty=quantity_for_quote_budget(a.buy,a.budget,cfg,liquidity=enter,
                                  volatility_frac=a.volatility,
                                  rolling_volume_usd=a.volume_usd)
    leg=settle_trade(a.buy,a.sell,qty,cfg,entry_liquidity=enter,
        exit_liquidity=leave,volatility_frac=a.volatility,
        rolling_volume_usd=a.volume_usd,holding_hours=a.hold_hours)
    breakeven=minimum_break_even_move(a.buy,a.budget,cfg,
        entry_liquidity=enter,exit_liquidity=leave,
        volatility_frac=a.volatility,rolling_volume_usd=a.volume_usd,
        holding_hours=a.hold_hours)
    print(json.dumps({'venue':cfg.exchange,'instrument':cfg.instrument,
        'qty_btc':qty,'budget_aud':a.budget,'break_even_price_move_pct':100*breakeven,
        'paper_only':True,'ledger':ledger_to_log(leg)},indent=2))

if __name__=='__main__':main()

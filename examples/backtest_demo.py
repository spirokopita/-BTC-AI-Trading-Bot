"""Strictly SYNTHETIC market demonstration of Roadmap 4 accounting."""
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import math

from backtester import compare_costs
from data_layer.storage import Candle


def make_bars():
    base=int(datetime(2024,1,1,tzinfo=timezone.utc).timestamp())
    output=[]
    last=100.
    for i in range(700):
        if i<220: price=100.+.025*i
        elif i<285: price=105.5+(i-220)*.36
        elif i<365: price=128.9-(i-285)*.27
        elif i<490: price=107.3+(i-365)*.02
        elif i<600: price=109.8+(i-490)*.28
        else: price=140.6-(i-600)*.31
        op=last
        high=max(op,price)*1.003
        low=min(op,price)*.997
        output.append(Candle(base+14400*i,op,high,low,price,volume=10.))
        last=price
    return output


def main():
    with tempfile.TemporaryDirectory(prefix='paper_backtest_demo_') as tmp:
        result=compare_costs(make_bars(),Path(tmp)/'results')
        active,control=result['fee_on'],result['fee_off']
        brief={'label':'SYNTHETIC SOFTWARE DEMO, NOT HISTORICAL BITCOIN RETURNS',
               'initial_quote_units':active['account_initial_quote'],
               'net_account_return_pct':active['total_return_net_pct'],
               'fee_free_account_return_pct':control['total_return_net_pct'],
               'closed_trades':active['completed_trades'],
               'fees_quote':active['total_trading_fees_quote'],
               'spread_quote':active['total_spread_quote'],
               'slippage_quote':active['total_slippage_quote'],
               'wallet_verified':active['verification']}
        path=Path(__file__).resolve().parents[1]/'reports'/'backtester_synthetic_demo.json'
        path.write_text(json.dumps(brief,indent=2),encoding='utf-8')
        print(json.dumps(brief,indent=2))

if __name__=='__main__':main()

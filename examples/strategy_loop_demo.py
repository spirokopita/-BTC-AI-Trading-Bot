"""All prices below are SYNTHETIC. Nothing here measures Bitcoin performance."""
import json
from pathlib import Path
import tempfile
from data_layer.storage import CandleStore
from examples.backtest_demo import make_bars
from strategy_loop.engine import PaperStrategyLoop


def main():
    bars=make_bars()
    now=bars[-1].ts+240*60+60
    with tempfile.TemporaryDirectory(prefix='paper_loop_demo_') as root:
        base=Path(root)
        with CandleStore(base/'prices.sqlite') as s:
            s.upsert('kraken','BTC/AUD',240,bars,'kraken_csv:SYNTHETIC_EXAMPLE_ONLY')
        loop=PaperStrategyLoop(base/'prices.sqlite',base/'news.sqlite',base/'wallet.sqlite',base/'journal.sqlite')
        first=loop.once(now=now)
        second=loop.once(now=now)
        output={'label':'SYNTHETIC DATA ONLY — not genuine Kraken prices or trading returns',
                'first_run_processed':first['processed_new_candles'],
                'second_run_processed':second['processed_new_candles'],
                'new_simulated_orders':first['new_orders']+second['new_orders'],
                'ending_equity_quote':second['status']['equity_net_quote'],
                'realized_net_profit_quote':0.,
                'wallet_verified':second['audit']}
        dest=Path(__file__).resolve().parents[1]/'reports'/'strategy_loop_synthetic_demo.json'
        dest.write_text(json.dumps(output,indent=2),encoding='utf-8')
        print(json.dumps(output,indent=2))


if __name__=='__main__':main()

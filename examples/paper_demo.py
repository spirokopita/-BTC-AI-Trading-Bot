"""Deterministic synthetic sample for testing paper ledger. NOT REAL BTC DATA."""
import json
from pathlib import Path
import tempfile
from data_layer.storage import Candle
from paper_engine import PaperEngine

BASE=240*60*10000
STEP=240*60

def c(k,o,h,l,close):
    return Candle(BASE+STEP*k,o,h,l,close,volume=10.0)


def main():
    with tempfile.TemporaryDirectory() as temp:
        db=Path(temp)/'paper.sqlite'
        with PaperEngine(db) as sim:
            sim.on_candle(c(0,100,101,99,100))
            sim.place_buy(50,client_id='first-buy')
            sim.on_candle(c(1,100,103,99,102))
            sim.on_candle(c(2,104,105,103,104))
            sim.on_candle(c(3,106,109,105,108)) # target intrabar
            sim.place_buy(50,client_id='second-buy')
            sim.on_candle(c(4,109,110,108,109))
            sim.on_candle(c(5,101,102,100,101)) # gap down, stop worse than stop-mid
            trades=sim.trades()
            result={
                'label':'SYNTHETIC TEST ONLY — no real Kraken BTC/AUD performance',
                'starting_cash_quote':1000.0,
                'ending_cash_quote':sim.status()['cash_quote'],
                'net_pnl_quote':sum(t['net_pnl_quote'] for t in trades),
                'gross_pnl_quote':sum(t['gross_pnl_quote'] for t in trades),
                'total_fees_quote':sum(t['total_trading_fees_quote'] for t in trades),
                'spread_quote':sum(t['spread_quote'] for t in trades),
                'slippage_quote':sum(t['slippage_quote'] for t in trades),
                'trades':trades,'audit':sim.verify(),
            }
            assert len(trades)==2
            assert abs(result['ending_cash_quote']-(1000+result['net_pnl_quote']))<1e-8
            assert result['total_fees_quote']>0
            out=Path(__file__).resolve().parents[1]/'reports'/'paper_demo.json'
            out.parent.mkdir(parents=True,exist_ok=True)
            out.write_text(json.dumps(result,indent=2))
            print(json.dumps({k:v for k,v in result.items() if k!='trades'},indent=2))

if __name__=='__main__':main()

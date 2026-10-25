"""Synthetic dashboard feed smoke check. Zero market performance inference."""
from pathlib import Path
import json
import tempfile
from dashboard import DashboardSources, read_snapshot
from paper_engine import PaperEngine
from data_layer.storage import Candle

STEP=4*3600
BASE=STEP*10000

def main():
    with tempfile.TemporaryDirectory() as temp:
        path=Path(temp)
        sources=DashboardSources(path/'market.sqlite',path/'wallet.sqlite',path/'news.sqlite',path/'journal.sqlite')
        with PaperEngine(sources.wallet) as engine:
            engine.on_candle(Candle(BASE,100,101,99,100,10))
            engine.place_buy(50,client_id='synthetic_dashboard_buy')
            engine.on_candle(Candle(BASE+STEP,100,103,99,101,10))
            engine.place_sell(client_id='synthetic_dashboard_sell')
            engine.on_candle(Candle(BASE+2*STEP,105,106,104,105,10))
        state=read_snapshot(sources,now=BASE+3*STEP)
        a=state['account']
        assert a['closed_trades']==1 and a['mode']=='PAPER_ONLY'
        assert abs(a['realized_net_quote']-(a['realized_gross_quote']-a['total_costs_quote']))<1e-7
        report={'label':'SYNTHETIC ACCOUNTING DEMONSTRATION ONLY; NOT REAL BTC/AUD DATA',
                'paper_only':True,'net_realized_quote':a['realized_net_quote'],
                'gross_realized_quote':a['realized_gross_quote'],
                'trading_fees_quote':a['trading_fees_quote'],
                'spread_quote':a['spread_quote'],'slippage_quote':a['slippage_quote'],
                'closed_trades':a['closed_trades'],'warnings':state['warnings']}
        out=Path(__file__).resolve().parents[1]/'reports'/'dashboard_synthetic_demo.json'
        out.write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report,indent=2))

if __name__=='__main__':main()

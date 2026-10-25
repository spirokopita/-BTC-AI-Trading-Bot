'use strict';
// No actions, forms, credentials, third-party scripts, or network calls except same-origin GET.
const $=id=>document.getElementById(id);
const amount=n=>n===null||n===undefined||!Number.isFinite(n)?'—':new Intl.NumberFormat('en-AU',{minimumFractionDigits:2,maximumFractionDigits:2}).format(n);
const money=n=>n===null||n===undefined||!Number.isFinite(n)?'—':'A$'+amount(n);
const when=n=>n===null||n===undefined?'—':new Date(n*1000).toLocaleString('en-AU',{dateStyle:'short',timeStyle:'short'});
const txt=(tag,text,cls)=>{const node=document.createElement(tag);node.textContent=String(text);if(cls)node.className=cls;return node;};
const empty=(target,message)=>{target.replaceChildren(txt('div',message,'empty'));};
function items(target,values,make){target.replaceChildren();if(!values?.length){empty(target,'No observations available');return;}values.forEach(x=>target.append(make(x)));}
function line(a,b){const row=txt('div','','detail');row.append(txt('span',a),txt('strong',b));return row;}
function rows(id,data,make,colspan){const node=$(id);node.replaceChildren();if(!data?.length){const row=document.createElement('tr'),cell=document.createElement('td');cell.colSpan=colspan;cell.textContent='No recorded entries';row.append(cell);node.append(row);return;}data.forEach(r=>{const tr=document.createElement('tr');make(r).forEach(v=>tr.append(txt('td',v)));node.append(tr);});}
function graph(data){const svg=$('equityGraph');svg.replaceChildren();$('curveStatus').textContent=data?.length?`${data.length} most recent completed-candle snapshots • no intrabar view`:'No priced equity observations';if(!data||data.length<2)return;const vals=data.map(x=>x.equity_net).filter(Number.isFinite);if(vals.length<2)return;const lo=Math.min(...vals),hi=Math.max(...vals),span=Math.max(hi-lo,0.01);const points=vals.map((v,i)=>`${(i*630/(vals.length-1)+5).toFixed(1)},${(178-(v-lo)/span*160).toFixed(1)}`).join(' ');const path=document.createElementNS('http://www.w3.org/2000/svg','polyline');path.setAttribute('points',points);path.setAttribute('fill','none');path.setAttribute('stroke','#d1e4e2');path.setAttribute('stroke-width','2.4');path.setAttribute('vector-effect','non-scaling-stroke');svg.append(path);}
function render(data){
 $('lastrefresh').textContent='Snapshot '+when(data.generated_at_utc);$('updated').textContent='Updated '+when(data.generated_at_utc);
 items($('warnings'),data.warnings||[],x=>txt('div',x,'warning'));
 const a=data.account;
 $('pnl').textContent=a?money(a.total_estimated_net_quote):'UNKNOWN';$('pnl').className='value '+(a?.total_estimated_net_quote<0?'negative':a?.total_estimated_net_quote>0?'positive':'');
 $('equity').textContent=a?`Net equity ${money(a.equity_net_quote)} · Cash ${money(a.cash_quote)}`:'No initialized paper wallet';
 $('realized').textContent=a?money(a.realized_net_quote):'—';$('tradesCount').textContent=a?`${a.closed_trades} closed trades · ${a.win_rate_pct===null?'—':amount(a.win_rate_pct)+'%'} net winners`:'No ledger';
 $('fees').textContent=a?money(a.trading_fees_quote):'—';$('othercosts').textContent=a?`Spread ${money(a.spread_quote)} · Slippage ${money(a.slippage_quote)}`:'No costs';
 const h=data.journal?.health?.[0];const stale=!h||data.generated_at_utc-h.observed_at>1800;
 $('health').textContent=!h?'UNKNOWN':stale?'STALE':h.status;$('heartbeat').textContent=h?`Last heartbeat ${when(h.observed_at)}`:'No heartbeat recorded';
 const pos=$('position');pos.replaceChildren();if(!a){empty(pos,'Wallet not initialised');}else if(!a.position){pos.append(line('Position','FLAT'),line('Risk lock',a.risk_halt||'None'),line('Latest marked BTC/AUD',money(a.last_mid_quote)),line('Last candle',when(a.last_candle_ts)));}else{const p=a.position;pos.append(line('Position','LONG BTC'),line('BTC quantity',p.quantity_btc.toFixed(8)),line('Entry midpoint',money(p.entry_mid_quote)),line('Current midpoint',money(a.last_mid_quote)),line('Estimated unrealized NET',money(p.estimated_unrealized_net_quote)),line('Protective stop',money(p.stop_mid_quote)),line('Target',money(p.target_mid_quote)),line('Risk lock',a.risk_halt||'None'),line('Last candle',when(a.last_candle_ts)));}
 graph(a?.equity_curve||[]);
 rows('tradeRows',a?.trades,x=>[when(x.exit_ts),x.exit_reason,money(x.gross_pnl_quote),money(x.fees_quote),money(x.net_pnl_quote)],5);
 rows('marketRows',data.market,x=>[x.interval+'m',String(x.candle_count),String(x.missing_interval_count),when(x.last_ts),x.latest_source_label||'—'],5);
 items($('decisions'),data.journal?.decisions,(x)=>{const div=txt('div','','item'),left=txt('div','');left.append(txt('div',x.decision+' · '+x.reason,'head'),txt('div',when(x.candle_ts)+(x.evidence?.predicted_net_return_pct===undefined?'':' · predicted net '+amount(x.evidence.predicted_net_return_pct)+'%') ,'meta'));div.append(left,txt('div',when(x.recorded_at),'rightmeta'));return div;});
 items($('news'),data.news?.articles,(x)=>{const div=txt('div','','item'),left=txt('div','');left.append(txt('div',x.headline,'head'),txt('div',x.source+' · first seen '+when(x.available_ts),'meta'));div.append(left,txt('div',x.polarity_label,'rightmeta'));return div;});
 items($('orders'),a?.orders,(x)=>{const div=txt('div','','item'),left=txt('div','');left.append(txt('div',`${x.side.toUpperCase()} ${x.kind.toUpperCase()} · ${x.status}`,'head'),txt('div',`#${x.id} · ${when(x.submitted_after_ts)}`,'meta'));div.append(left,txt('div',money(x.budget_quote),'rightmeta'));return div;});
 const feedRecords=[...(data.news?.feed_states||[]).map(x=>({title:x.feed,sub:x.last_error?'ERROR: '+x.last_error:'Last success: '+when(x.last_success_ts),time:x.last_attempt_ts})),...(data.journal?.health||[]).slice(0,4).map(x=>({title:'Bot '+x.status,sub:x.details,time:x.observed_at}))];
 items($('feeds'),feedRecords,x=>{const div=txt('div','','item'),left=txt('div','');left.append(txt('div',x.title,'head'),txt('div',x.sub,'meta'));div.append(left,txt('div',when(x.time),'rightmeta'));return div;});
}
async function refresh(){try{const response=await fetch('/api/status',{method:'GET',cache:'no-store'});if(!response.ok)throw new Error('Status endpoint '+response.status);render(await response.json());}catch(error){$('lastrefresh').textContent='Connection unavailable';items($('warnings'),['Dashboard read failed; figures may be stale. '+error.message],x=>txt('div',x,'warning'));}}
refresh();setInterval(refresh,15000);

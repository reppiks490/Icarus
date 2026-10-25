/* Persisted paper performance. Each URL binds one ledger; never a profit forecast. */
'use strict';
(() => {
  const mounted=new WeakMap();
  function mount(parent,client,id=client?.context?.id) {
  if(!parent||!['main','cc1','cc2','cc3','cc4'].includes(id))throw new Error('An explicit performance workspace is required');
  if(mounted.has(parent))return mounted.get(parent);
  const section = document.createElement('section');
  section.id = 'workspace-performance'; section.className = 'card c12';
  section.setAttribute('aria-label','Selected portfolio performance');
  section.innerHTML = `<style>
    #workspace-performance{box-sizing:border-box;max-width:100%;min-width:0;overflow:hidden;background:var(--panel,#101d2b);color:var(--text,#e6edf5);border:1px solid var(--line,#293d50);border-radius:12px;padding:20px;margin-top:20px;font:14px/1.5 system-ui,sans-serif}
    #workspace-performance .perf-top{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}
    #workspace-performance .perf-tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(145px,1fr));gap:16px;margin:20px 0}
    #workspace-performance .perf-tile span{display:block;font-size:12px;color:var(--muted,#a5b6c7)}
    #workspace-performance .perf-tile strong{font:500 24px/1.7 ui-monospace,monospace;font-variant-numeric:tabular-nums}
    #workspace-performance .perf-charts{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,320px),1fr));gap:20px}
    #workspace-performance canvas{display:block;width:100%;height:230px;max-width:100%}
    #workspace-performance .perf-scroll{overflow:auto;max-width:100%;max-height:430px}
    #workspace-performance table{border-collapse:collapse;min-width:750px;width:100%;font-size:12px}
    #workspace-performance td,#workspace-performance th{padding:10px 8px;border-bottom:1px solid var(--line,#293d50);text-align:left;white-space:nowrap}
    #workspace-performance p{color:var(--muted,#a5b6c7);font-size:12px;overflow-wrap:anywhere}
    #workspace-performance select,#workspace-performance button{font:inherit;background:#16283a;color:inherit;border:1px solid #496176;border-radius:7px;padding:8px;max-width:100%}
  </style><div class="perf-top"><h2 id="performance-title">${id.toUpperCase()} · Portfolio performance</h2><label>Switch portfolio <select id="performance-switch" aria-label="Switch portfolio"></select></label><button type="button" id="performance-refresh">Refresh performance</button></div>
  <p id="performance-status" role="status" aria-live="polite">Loading persisted paper trades…</p>
  <div class="perf-tiles"><div class="perf-tile"><span>Persisted closed paper P&amp;L</span><strong id="performance-realized">Unavailable</strong></div><div class="perf-tile"><span>Closure pieces</span><strong id="performance-count">Unavailable</strong></div><div class="perf-tile"><span>Sharpe · realized daily proxy</span><strong id="performance-sharpe">Unavailable</strong></div><div class="perf-tile"><span>Sortino · realized daily proxy</span><strong id="performance-sortino">Unavailable</strong></div></div>
  <p id="performance-ratio-note"></p><div class="perf-charts"><div><h3>Realized paper equity curve</h3><canvas id="performance-equity" width="900" height="280" role="img" aria-label="Cumulative persisted realized paper P&L over time"></canvas><p id="performance-equity-note"></p></div><div><h3>Trades over time · closure pieces by UTC day</h3><canvas id="performance-activity" width="900" height="280" role="img" aria-label="Persisted closure activity by UTC date"></canvas><p id="performance-activity-note"></p></div></div>
  <h3>Historical outcomes · potential is unproven</h3><p id="performance-history"></p><p>These descriptive results do not predict future profits. Fees and broker balances are not reconciled. This curve excludes open marks; the combined four-ledger accounting remains above the workspace.</p>
  <h3>Persisted paper trade history</h3><p id="performance-trade-note"></p><div class="perf-scroll"><table><thead><tr><th>Asset</th><th>Entry UTC</th><th>Exit UTC</th><th>Side</th><th>Quantity</th><th>Entry price</th><th>Exit price</th><th>P&amp;L</th><th>Exit</th></tr></thead><tbody id="performance-trades"></tbody></table></div>`;
  parent.insertBefore(section,parent.children[1] || null);
  const $ = name => section.querySelector('#performance-'+name);
  const finite = value => typeof value === 'number' && Number.isFinite(value);
  const amount = value => finite(value) ? value.toLocaleString(undefined,{style:'currency',currency:'USD'}) : 'Unavailable';
  const ratio = value => finite(value) ? value.toFixed(3) : 'Unavailable';
  const utc = ts => finite(ts) ? new Date(ts*1000).toISOString().replace('T',' ').slice(0,19) : 'Unavailable';
  let sequence=0,lastSnapshot=null,active=true,pending=null;
  for(const key of (client?['main','cc1','cc2','cc3','cc4']:['cc1','cc2','cc3','cc4'])){const option=document.createElement('option');option.value=key;option.textContent=key.toUpperCase();$('switch').append(option);}
  $('switch').value=id;
  $('switch').addEventListener('change',()=>{location.href=$('switch').value==='main'?'/':'/dashboards/'+$('switch').value;});
  function clear(reason) {
    lastSnapshot=null;
    for(const key of ['realized','count','sharpe','sortino'])$(key).textContent='Unavailable';
    for(const key of ['ratio-note','history','equity-note','activity-note','trade-note'])$(key).textContent='';
    $('trades').replaceChildren();
    for(const key of ['equity','activity']){const canvas=$(key);canvas.getContext('2d')?.clearRect(0,0,canvas.width,canvas.height);}
    $('status').textContent='Performance unavailable: '+reason;
  }
  function chart(key, rows, valueKey, bars=false) {
    const canvas=$(key),ctx=canvas.getContext('2d'),w=canvas.width,h=canvas.height,pad=42;
    if(!ctx)return;
    ctx.clearRect(0,0,w,h);
    if(!rows.length)return;
    const values=rows.map(row=>row[valueKey]);
    if(!values.every(finite)||!rows.every(row=>finite(row.ts)))return;
    const low=Math.min(0,...values),high=Math.max(0,...values),range=high-low||1;
    const start=rows[0].ts,end=rows.at(-1).ts;
    const x=ts=>pad+(end===start?.5:(ts-start)/(end-start))*(w-2*pad);
    const y=value=>h-pad-(value-low)/range*(h-2*pad);
    ctx.strokeStyle='#496176';ctx.beginPath();ctx.moveTo(pad,y(0));ctx.lineTo(w-pad,y(0));ctx.stroke();
    ctx.fillStyle='#a5b6c7';ctx.font='16px system-ui';
    ctx.fillText(bars?'Daily closures':amount(high),pad,22);
    ctx.fillText(utc(start).slice(0,10),pad,h-8);ctx.fillText(utc(end).slice(0,10),w-pad-100,h-8);
    ctx.strokeStyle='#72e4ca';ctx.fillStyle='#72e4ca';ctx.lineWidth=2;ctx.beginPath();
    rows.forEach((row,index)=>{
      if(bars){const width=Math.max(1,Math.min(20,(w-2*pad)/rows.length*.75));ctx.fillRect(x(row.ts)-width/2,y(row[valueKey]),width,Math.max(0,y(0)-y(row[valueKey])));}
      else if(index)ctx.lineTo(x(row.ts),y(row[valueKey]));else ctx.moveTo(x(row.ts),y(row[valueKey]));
    });
    if(!bars){ctx.stroke();if(rows.length===1){ctx.beginPath();ctx.arc(x(start),y(values[0]),4,0,2*Math.PI);ctx.fill();}}
  }
  function render(data) {
    const r=data.ratios||{},history=data.historical||{},display=data.display||{};
    $('realized').textContent=amount(data.realized_pnl);$('count').textContent=String(data.closed_pieces);
    $('sharpe').textContent=ratio(r.sharpe);$('sortino').textContent=ratio(r.sortino);
    $('status').textContent=`${id.toUpperCase()} · ${data.closed_pieces} persisted paper closure pieces · observed ${utc(data.as_of_ts)} UTC. Warmup/replay is excluded; history survives restarts.`;
    $('ratio-note').textContent=`${r.sample_days??0} complete UTC calendar days; minimum ${r.minimum_days??20}. ${r.reason||'Unavailable'}. ${r.basis||''}. Annualization: √${r.annualization_days??365}. ${r.capital_basis||''} These are realized-return proxies, not account NAV Sharpe or Sortino.`;
    chart('equity',data.equity_curve,'realized_pnl');chart('activity',data.daily_activity,'closed_pieces',true);
    $('equity-note').textContent=data.equity_curve.length?`Cumulative USD closure P&L, starting at zero; not broker equity.${display.equity_sampled?' Display downsampled; metrics use all closures.':''}`:'No persisted paper closures yet; no equity curve is fabricated.';
    $('activity-note').textContent=data.daily_activity.length?`Observed closure range ${data.daily_activity[0].date} to ${data.daily_activity.at(-1).date}; the current day is partial.${display.daily_sampled?' Display downsampled.':''}`:'No closure activity recorded yet.';
    $('history').textContent=`Win rate: ${finite(history.win_rate)?(history.win_rate*100).toFixed(1)+'%':'Unavailable'} · Mean closure P&L: ${amount(history.mean_closure_pnl)} · Maximum realized drawdown: ${amount(history.max_realized_drawdown)}. Partial exits are separate closure pieces.`;
    $('trade-note').textContent=`${data.trades.length} ${display.trades_truncated?'most recent':'recorded'} closure pieces, shown chronologically. All saved runs and previously selected assets remain included.`;
    const body=$('trades');body.replaceChildren();
    for(const trade of data.trades){const row=document.createElement('tr');for(const value of [trade.symbol,utc(trade.entry_ts),utc(trade.exit_ts),trade.direction===1?'Long':'Short',trade.qty,trade.entry_price,trade.exit_price,amount(trade.profit),trade.exit_comment]){const cell=document.createElement('td');cell.textContent=String(value??'');row.append(cell);}body.append(row);}
  }
  async function refresh() {
    if(!active||!section.isConnected)return;
    const current=++sequence;pending?.abort();
    const abort=new AbortController(),timer=setTimeout(()=>abort.abort(),10000);pending=abort;
    try {
      let data;
      if(client)data=await client.read('performance',{signal:abort.signal});
      else {
        const reply=await fetch(`/api/command-centers/${id}/performance`,{cache:'no-store',signal:abort.signal});
        if(!reply.ok)throw Error('HTTP '+reply.status);data=await reply.json();
      }
      if(!active||!section.isConnected||current!==sequence)return;
      if(data.workspace_id!==id||data.schema_version!==1||data.paper_only!==true||data.execution_authorized!==false)throw Error('Ledger identity or contract mismatch');
      if(!finite(data.as_of_ts)||Date.now()/1000-data.as_of_ts>90||data.as_of_ts>Date.now()/1000+5)throw Error('Snapshot expired');
      if(data.available!==true)throw Error(data.reason||'Ledger not available');
      if(![data.trades,data.equity_curve,data.daily_activity].every(rows=>Array.isArray(rows)&&rows.length<=10000))throw Error('Invalid history bounds');
      lastSnapshot=data;render(data);
    }catch(error){if(active&&section.isConnected&&current===sequence)clear(error.name==='AbortError'?'Request timed out':error.message);}
    finally{clearTimeout(timer);if(pending===abort)pending=null;}
  }
  $('refresh').addEventListener('click',refresh);
  const poll=setInterval(()=>{if(!document.hidden)refresh();},15000);
  const expiry=setInterval(()=>{if(!section.isConnected)return dispose();if(lastSnapshot&&Date.now()/1000-lastSnapshot.as_of_ts>90)clear('Snapshot expired');},1000);
  function dispose(){if(!active)return;active=false;sequence++;pending?.abort();pending=null;clearInterval(poll);clearInterval(expiry);globalThis.removeEventListener('pagehide',dispose);mounted.delete(parent);}
  globalThis.addEventListener('pagehide',dispose);
  const component=Object.freeze({refresh,dispose});mounted.set(parent,component);void refresh();return component;
  }
  globalThis.IcarusWorkspacePerformance=Object.freeze({mount:(parent,client)=>{
    if(!client?.context)throw new Error('An explicit page client is required');return mount(parent,client);
  }});
  if(!globalThis.IcarusClient){
    const id=location.pathname.split('/').pop(),parent=document.querySelector('#workspace-panel');
    if(parent&&['cc1','cc2','cc3','cc4'].includes(id))mount(parent,null,id);
  }
})();

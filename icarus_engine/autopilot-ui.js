/* ICARUS Tactical Autopilot — autonomous shadow research UI. */
let autopilotLoading=false, autopilotLast=null, autopilotTimer=null;

function apFmt(v,d=3){return(v==null||!Number.isFinite(Number(v)))?'—':Number(v).toLocaleString(undefined,{maximumFractionDigits:d});}
function apBadge(v){const s=String(v||'unknown').toLowerCase(),c=(s==='complete'||s==='running'||s==='backtest')?'b':s==='error'?'r':'w';return '<span class="chip '+c+'">'+esc(String(v||'unknown').toUpperCase())+'</span>';}
function apDelta(d){if(!d)return'—';if(d.kind==='baseline')return'<span class="muted">baseline benchmark</span>';return '<b>'+esc(d.name||'')+'</b> <span class="muted">'+esc(String(d.from??'—'))+'</span> → <b>'+esc(String(d.to??'—'))+'</b>';}
function apInputs(candidate,champion){
  const vals=(candidate&&candidate.inputs)||{},ch=(champion&&champion.inputs)||{};
  return Object.keys(vals).sort().map(k=>{
    const changed=ch[k]!==undefined&&ch[k]!==vals[k];
    return '<tr class="'+(changed?'new':'')+'"><td><code>'+esc(k)+'</code></td><td class="tnum"><b>'+esc(String(vals[k]))+'</b></td><td class="tnum muted">'+(ch[k]===undefined?'—':esc(String(ch[k])))+'</td></tr>';
  }).join('')||'<tr><td colspan="3" class="empty">No candidate inputs yet.</td></tr>';
}
function autopilotHtml(A){
  const opts=(A||[]).map(a=>'<option value="'+esc(a.symbol)+'">'+esc(a.continuous_symbol||a.symbol)+'</option>').join('');
  return '<section class="card c12">'+
    '<h2>Tactical Autopilot <span class="sub">Autonomous shadow optimizer · real-price replay · live input search</span></h2>'+
    '<div class="callout" style="border-color:var(--s1)"><div><b>Autonomous research plane</b><span class="small muted">Continuously searches bounded inputs and chart/session context on frozen cached data. It does not alter broker/live or canonical paper inputs. Winners flow upward through the qualified activation path.</span></div></div>'+
    '<div class="toolbar" style="margin-top:12px"><button class="primary" id="apStart">Start autonomous loop</button><button id="apStop">Stop</button><button id="apStep">Run one cycle now</button><button id="apRefresh">Refresh</button>'+
    '<label class="small">Cadence <input id="apCadence" type="number" min="5" max="3600" value="15" style="width:84px"> sec</label>'+
    '<label class="small">Asset <select id="apAsset"><option value="">all / round-robin</option>'+opts+'</select></label><span id="apStatus" class="small muted">loading…</span></div>'+
    '<div class="tiles" id="apSummary"></div></section>'+
    '<section class="card c6"><h2>Current candidate <span class="sub" id="apCandidateStage">—</span></h2><div id="apCurrent" class="small"></div>'+
    '<div class="scroll" style="max-height:430px;margin-top:10px"><table><thead><tr><th>Input</th><th>Candidate</th><th>Champion</th></tr></thead><tbody id="apInputRows"></tbody></table></div></section>'+
    '<section class="card c6"><h2>Best observed champion <span class="sub">within tested search space</span></h2><div id="apChampion"></div><h2 style="margin-top:18px">Score decomposition</h2><div class="tiles" id="apMetrics"></div></section>'+
    '<section class="card c12"><h2>Leaderboard <span class="sub">highest robust shadow scores</span></h2><div class="scroll"><table><thead><tr><th>#</th><th>Asset</th><th>Score</th><th>P&amp;L</th><th>Max DD</th><th>Return/DD</th><th>Win rate</th><th>PF</th><th>Trades</th><th>Mutation</th></tr></thead><tbody id="apLeaderboard"></tbody></table></div></section>'+
    '<section class="card c12"><h2>Autonomous trial stream <span class="sub">every tested mutation is retained</span></h2><div class="scroll" style="max-height:520px"><table><thead><tr><th>Time</th><th>Asset</th><th>Result</th><th>Score</th><th>Mutation</th><th>Chart</th><th>Session</th><th>Candidate ID</th></tr></thead><tbody id="apHistory"></tbody></table></div></section>';
}
function apMetricTiles(m){m=m||{};return[
 ['score',apFmt(m.score,5)],['P&L',m.pnl==null?'—':fmt$(m.pnl,0)],['max drawdown',m.max_drawdown==null?'—':fmt$(m.max_drawdown,0)],
 ['return / DD',apFmt(m.return_to_drawdown,4)],['win rate',m.win_rate==null?'—':(Number(m.win_rate)*100).toFixed(1)+'%'],
 ['profit factor',apFmt(m.profit_factor,3)],['trades',m.trades??'—'],['bars',m.bars??'—']
].map(x=>'<div class="tile"><div class="k">'+esc(x[0])+'</div><div class="v">'+esc(String(x[1]))+'</div></div>').join('');}
async function loadAutopilot(){
  if(autopilotLoading||view!=='autopilot')return;autopilotLoading=true;
  try{
    const tok=localStorage.getItem('icarus-engine-token')||'';
    const r=await fetch('/api/autopilot',{cache:'no-store',headers:{Authorization:'Bearer '+tok}});
    const d=await r.json();if(!r.ok)throw new Error(d.detail||('HTTP '+r.status));if(view!=='autopilot')return;
    autopilotLast=d;const cfg=d.config||{},active=d.active||{},cand=active.candidate||null,champion=cand?(d.champions||{})[cand.asset]:null;
    $('#apStatus').innerHTML=(d.running?'<span class="pos">RUNNING</span>':'<span class="muted">STOPPED</span>')+' · cycle '+esc(String(d.cursor||0))+' · '+esc(d.mode||'');
    if($('#apCadence'))$('#apCadence').value=cfg.cadence_seconds||15;
    $('#apSummary').innerHTML=
      '<div class="tile"><div class="k">Loop</div><div class="v '+(d.running?'pos':'')+'">'+(d.running?'AUTONOMOUS':'STOPPED')+'</div></div>'+
      '<div class="tile"><div class="k">Trials</div><div class="v">'+(d.history||[]).length+'</div></div>'+
      '<div class="tile"><div class="k">Champions</div><div class="v">'+Object.keys(d.champions||{}).length+'</div></div>'+
      '<div class="tile"><div class="k">Live mutation</div><div class="v pos">DISABLED</div></div>'+
      '<div class="tile"><div class="k">Broker control</div><div class="v pos">DISABLED</div></div>'+
      '<div class="tile"><div class="k">Search fill</div><div class="v">REAL PRICE</div></div>';
    $('#apCandidateStage').innerHTML=apBadge(active.stage||'idle');
    $('#apCurrent').innerHTML=cand?'<div class="tiles">'+
      '<div class="tile"><div class="k">Asset</div><div class="v">'+esc(cand.asset)+'</div></div>'+
      '<div class="tile"><div class="k">Mutation</div><div class="v" style="font-size:13px">'+apDelta(cand.delta)+'</div></div>'+
      '<div class="tile"><div class="k">Chart</div><div class="v">'+esc(cand.chart_type||'engine')+'</div></div>'+
      '<div class="tile"><div class="k">Session</div><div class="v">'+esc(cand.session||'engine')+'</div></div>'+
      '<div class="tile"><div class="k">Candidate</div><div class="v" style="font-size:12px"><code>'+esc(cand.id||'')+'</code></div></div></div>'+
      '<div class="small muted" style="margin-top:8px">'+esc(cand.reason||'')+'</div>':'<div class="empty">Waiting for the first autonomous cycle.</div>';
    $('#apInputRows').innerHTML=apInputs(cand,champion);
    if(champion){
      $('#apChampion').innerHTML='<div class="tiles"><div class="tile"><div class="k">Asset</div><div class="v">'+esc(champion.asset)+'</div></div>'+
        '<div class="tile"><div class="k">Score</div><div class="v pos">'+apFmt(champion.metrics&&champion.metrics.score,5)+'</div></div>'+
        '<div class="tile"><div class="k">Winning mutation</div><div class="v" style="font-size:13px">'+apDelta(champion.delta)+'</div></div>'+
        '<div class="tile"><div class="k">Candidate</div><div class="v" style="font-size:12px"><code>'+esc(champion.id)+'</code></div></div></div>';
      $('#apMetrics').innerHTML=apMetricTiles(champion.metrics);
    }else{$('#apChampion').innerHTML='<div class="empty">No champion yet.</div>';$('#apMetrics').innerHTML='';}
    $('#apLeaderboard').innerHTML=(d.leaderboard||[]).map((x,i)=>{const m=x.metrics||{};return '<tr><td>'+(i+1)+'</td><td><b>'+esc(x.asset)+'</b></td><td class="tnum '+(x.champion?'pos':'')+'">'+apFmt(m.score,5)+'</td><td class="tnum">'+(m.pnl==null?'—':fmt$(m.pnl,0))+'</td><td class="tnum">'+(m.max_drawdown==null?'—':fmt$(m.max_drawdown,0))+'</td><td>'+apFmt(m.return_to_drawdown,3)+'</td><td>'+(m.win_rate==null?'—':(100*m.win_rate).toFixed(1)+'%')+'</td><td>'+apFmt(m.profit_factor,2)+'</td><td>'+(m.trades??'—')+'</td><td>'+apDelta(x.delta)+'</td></tr>';}).join('')||'<tr><td colspan="10" class="empty">No completed trials.</td></tr>';
    $('#apHistory').innerHTML=(d.history||[]).slice().reverse().map(x=>'<tr><td class="tnum">'+(x.tested_at?new Date(x.tested_at*1000).toLocaleTimeString():'—')+'</td><td><b>'+esc(x.asset)+'</b></td><td>'+(x.champion?'<span class="chip b">NEW CHAMPION</span>':'<span class="chip">tested</span>')+'</td><td class="tnum">'+apFmt(x.metrics&&x.metrics.score,5)+'</td><td>'+apDelta(x.delta)+'</td><td>'+esc(x.chart_type||'engine')+'</td><td>'+esc(x.session||'engine')+'</td><td><code>'+esc(x.id||'')+'</code></td></tr>').join('')||'<tr><td colspan="8" class="empty">No autonomous trials yet.</td></tr>';
    if(d.last_error)$('#apStatus').innerHTML+=' · <span class="neg">'+esc(d.last_error.detail||d.last_error.type||'error')+'</span>';
  }catch(e){if($('#apStatus'))$('#apStatus').innerHTML='<span class="neg">'+esc(e.message||String(e))+'</span>';}finally{autopilotLoading=false;}
}
function wireAutopilot(){
  clearInterval(autopilotTimer);
  $('#apRefresh')&&$('#apRefresh').addEventListener('click',loadAutopilot);
  $('#apStart')&&$('#apStart').addEventListener('click',async()=>{await admin('/admin/autopilot/start',{});loadAutopilot();});
  $('#apStop')&&$('#apStop').addEventListener('click',async()=>{await admin('/admin/autopilot/stop',{});loadAutopilot();});
  $('#apStep')&&$('#apStep').addEventListener('click',async()=>{await admin('/admin/autopilot/step',{},true);loadAutopilot();});
  $('#apCadence')&&$('#apCadence').addEventListener('change',async e=>{await admin('/admin/autopilot/config',{cadence_seconds:Number(e.target.value)},true);loadAutopilot();});
  $('#apAsset')&&$('#apAsset').addEventListener('change',async e=>{await admin('/admin/autopilot/config',{assets:e.target.value?[e.target.value]:[]},true);loadAutopilot();});
  loadAutopilot();autopilotTimer=setInterval(loadAutopilot,1200);
}

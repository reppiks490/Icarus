/* ICARUS Tactical Autopilot — autonomous shadow research UI. */
let autopilotLoading=false, autopilotPendingLoad=false, autopilotMutationBusy=false, autopilotLast=null, autopilotTimer=null;

function apFmt(v,d=3){return(v==null||!Number.isFinite(Number(v)))?'—':Number(v).toLocaleString(undefined,{maximumFractionDigits:d});}
function apBadge(v){const s=String(v||'unknown').toLowerCase(),c=(s==='complete'||s==='running'||s==='backtest')?'b':s==='error'?'r':'w';return '<span class="chip '+c+'">'+esc(String(v||'unknown').toUpperCase())+'</span>';}
function apDelta(d){if(!d)return'—';if(d.kind==='baseline')return'<span class="muted">baseline benchmark</span>';return '<b>'+esc(d.name||'')+'</b> <span class="muted">'+esc(String(d.from??'—'))+'</span> → <b>'+esc(String(d.to??'—'))+'</b>';}
function apInputs(candidate,champion){
  const vals=(candidate&&candidate.inputs)||{},ch=(champion&&champion.inputs)||{};
  return Object.keys(vals).sort().map(k=>{
    const changed=(candidate&&candidate.delta&&candidate.delta.name===k)||(ch[k]!==undefined&&ch[k]!==vals[k]);
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
    '<label class="small">Robustness <select id="apWindows"><option value="1">1 window</option><option value="2">2 windows</option><option value="3">3 windows</option></select></label>'+
    '<label class="small">Asset <select id="apAsset"><option value="">all / round-robin</option>'+opts+'</select></label><span id="apStatus" class="small muted">loading…</span></div>'+
    '<div class="tiles" id="apSummary"></div></section>'+
    '<section class="card c12"><h2>Champion market context <span class="sub">live Ψ, order flow, depth, and dated public events · context only, not historical replay inputs</span></h2><div id="apMarketContext" class="small muted">Waiting for the first context receipt.</div></section>'+
    '<section class="card c6"><h2>Current candidate <span class="sub" id="apCandidateStage">—</span></h2><div id="apCurrent" class="small"></div>'+
    '<div class="scroll" style="max-height:430px;margin-top:10px"><table><thead><tr><th>Input</th><th>Candidate</th><th>Champion</th></tr></thead><tbody id="apInputRows"></tbody></table></div></section>'+
    '<section class="card c6"><h2>Best observed champion <span class="sub">within tested search space</span></h2><div id="apChampion"></div><h2 style="margin-top:18px">Score decomposition</h2><div class="tiles" id="apMetrics"></div></section>'+
    '<section class="card c12"><h2>Champion qualification handoff <span class="sub">send a shadow champion through fresh holdout research and independent review</span></h2><div id="apChampionHandoffs" class="tiles"></div><p class="small muted">Starting qualification does not apply an overlay. A candidate must pass the normal after cost research gates, specialist review, proposal checks, and paper runtime activation boundary.</p></section>'+
    '<section class="card c12"><h2>Tactical learning map <span class="sub">dimensions the optimizer is learning to revisit</span></h2><div class="scroll"><table><thead><tr><th>Dimension</th><th>Trials</th><th>Champion wins</th><th>Avg improvement</th><th>Best improvement</th><th>Last score</th></tr></thead><tbody id="apDimensions"></tbody></table></div></section>'+
    '<section class="card c12"><h2>Leaderboard <span class="sub">highest robust shadow scores</span></h2><div class="scroll"><table><thead><tr><th>#</th><th>Asset</th><th>Score</th><th>P&amp;L</th><th>Max DD</th><th>Return/DD</th><th>Win rate</th><th>PF</th><th>Trades</th><th>Mutation</th></tr></thead><tbody id="apLeaderboard"></tbody></table></div></section>'+
    '<section class="card c12"><h2>Autonomous trial stream <span class="sub">every tested mutation is retained</span></h2><div class="scroll" style="max-height:520px"><table><thead><tr><th>Time</th><th>Asset</th><th>Result</th><th>Score</th><th>Mutation</th><th>Regime</th><th>Chart</th><th>Session</th><th>Candidate ID</th></tr></thead><tbody id="apHistory"></tbody></table></div></section>';
}
function apMetricTiles(m){m=m||{};return[
 ['score',apFmt(m.score,5)],['P&L',m.pnl==null?'—':fmt$(m.pnl,0)],['max drawdown',m.max_drawdown==null?'—':fmt$(m.max_drawdown,0)],
 ['return / DD',apFmt(m.return_to_drawdown,4)],['win rate',m.win_rate==null?'—':(Number(m.win_rate)*100).toFixed(1)+'%'],
 ['profit factor',apFmt(m.profit_factor,3)],['trades',m.trades??'—'],['bars',m.bars??'—'],
 ['full score',apFmt(m.full_score,5)],['worst window',apFmt(m.worst_window_score,5)],
 ['score dispersion',apFmt(m.score_dispersion,5)],['robust windows',m.robustness_windows??'—']
].map(x=>'<div class="tile"><div class="k">'+esc(x[0])+'</div><div class="v">'+esc(String(x[1]))+'</div></div>').join('');}
async function loadAutopilot(){
  if(view!=='autopilot')return;
  if(autopilotLoading){autopilotPendingLoad=true;return;}
  autopilotLoading=true;autopilotPendingLoad=false;
  try{
    const tok=IcarusClient.getToken();
    const r=await IcarusClient.request('/api/autopilot',{cache:'no-store',headers:{Authorization:'Bearer '+tok}});
    const d=await r.json();if(!r.ok)throw new Error(d.detail||('HTTP '+r.status));if(view!=='autopilot')return;
    autopilotLast=d;const cfg=d.config||{},active=d.active||{},cand=active.candidate||null,champion=cand?(d.champions||{})[cand.asset]:null;
    $('#apStatus').innerHTML=(d.running?'<span class="pos">RUNNING</span>':'<span class="muted">STOPPED</span>')+' · cycle '+esc(String(d.cursor||0))+' · '+esc(d.mode||'');
    if($('#apCadence'))$('#apCadence').value=cfg.cadence_seconds||15;
    if($('#apWindows'))$('#apWindows').value=String(cfg.robustness_windows||1);
    $('#apSummary').innerHTML=
      '<div class="tile"><div class="k">Loop</div><div class="v '+(d.running?'pos':'')+'">'+(d.running?'AUTONOMOUS':'STOPPED')+'</div></div>'+
      '<div class="tile"><div class="k">Trials</div><div class="v">'+(d.history||[]).length+'</div></div>'+
      '<div class="tile"><div class="k">Champions</div><div class="v">'+Object.keys(d.champions||{}).length+'</div></div>'+
      '<div class="tile"><div class="k">Live mutation</div><div class="v pos">DISABLED</div></div>'+
      '<div class="tile"><div class="k">Broker control</div><div class="v pos">DISABLED</div></div>'+
      '<div class="tile"><div class="k">Search fill</div><div class="v">REAL PRICE</div></div>'+
      '<div class="tile"><div class="k">Robustness</div><div class="v">'+esc(String(cfg.robustness_windows||1))+' WINDOWS</div></div>';
    const marketContext=(cand&&cand.market_context)||((d.champions||{})[cand&&cand.asset]||{}).market_context||null;
    if(marketContext){
      const psi=marketContext.possibility||{},features=psi.features||{},health=(psi.data_health||{}).microstructure||{},events=marketContext.public_events||[];
      const featureRows=Object.entries(features).map(([name,f])=>'<tr><td><code>'+esc(name)+'</code></td><td>'+esc(String(f.available?'available':'missing'))+'</td><td class="tnum">'+apFmt(f.value,4)+'</td><td class="tnum">'+apFmt(f.confidence,3)+'</td><td>'+esc(f.source||'—')+'</td></tr>').join('');
      const eventRows=events.map(e=>'<li><b>'+esc(e.source||'source')+'</b> · '+esc(e.event_type||'event')+' · '+esc(e.observed_at||'time unavailable')+(e.text?' — '+esc(e.text):'')+'</li>').join('');
      $('#apMarketContext').innerHTML='<div class="tiles"><div class="tile"><div class="k">Captured</div><div class="v">'+esc(marketContext.captured_at||'—')+'</div></div><div class="tile"><div class="k">Ψ coverage</div><div class="v">'+apFmt(psi.evidence_coverage,3)+'</div></div><div class="tile"><div class="k">Order book</div><div class="v">'+(health.depth?'<span class="pos">LIVE</span>':'<span class="muted">UNAVAILABLE</span>')+'</div></div><div class="tile"><div class="k">Trade tape</div><div class="v">'+(health.ticks?'<span class="pos">LIVE</span>':'<span class="muted">UNAVAILABLE</span>')+'</div></div><div class="tile"><div class="k">Public events</div><div class="v">'+events.length+'</div></div><div class="tile"><div class="k">Replay score inputs</div><div class="v">NO</div></div></div><div class="scroll" style="max-height:260px;margin-top:10px"><table><thead><tr><th>Feature</th><th>Coverage</th><th>Value</th><th>Confidence</th><th>Source</th></tr></thead><tbody>'+featureRows+'</tbody></table></div><ul>'+eventRows+'</ul>';
    }else $('#apMarketContext').textContent='No market context receipt yet; it is attached automatically to the next candidate cycle.';
    $('#apCandidateStage').innerHTML=apBadge(active.stage||'idle')+(active.robustness_label?' · '+esc(active.robustness_label)+' '+esc(String(active.robustness_index||''))+'/'+esc(String(active.robustness_total||'')):'');
    $('#apCurrent').innerHTML=cand?'<div class="tiles">'+
      '<div class="tile"><div class="k">Asset</div><div class="v">'+esc(cand.asset)+'</div></div>'+
      '<div class="tile"><div class="k">Mutation</div><div class="v" style="font-size:13px">'+apDelta(cand.delta)+'</div></div>'+
      '<div class="tile"><div class="k">Chart</div><div class="v">'+esc(cand.chart_type||'engine')+'</div></div>'+
      '<div class="tile"><div class="k">Session</div><div class="v">'+esc(cand.session||'engine')+'</div></div>'+
      '<div class="tile"><div class="k">Search mode</div><div class="v">'+esc(String(cand.search_mode||'baseline').toUpperCase())+'</div></div>'+
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
    const scopedChampions=Object.values(d.regime_champions||{});
    const champions=scopedChampions.length?scopedChampions:Object.values(d.champions||{});
    $('#apChampionHandoffs').innerHTML=champions.map(ch=>'<div class="tile"><div class="k">'+esc(ch.asset)+' · champion '+esc(ch.id||'')+'</div><div class="v">'+apFmt(ch.metrics&&ch.metrics.win_rate*100,1)+'% replay win rate</div><button class="apQualifyChampion" data-asset="'+esc(ch.asset)+'" data-id="'+esc(ch.id||'')+'">Start fresh qualification</button><div class="small muted">Regime: '+esc(ch.regime_context&&ch.regime_context.label||'unknown')+'</div></div>').join('')||'<div class="empty">No champions recorded yet.</div>';
    document.querySelectorAll('.apQualifyChampion').forEach(button=>button.addEventListener('click',()=>promoteAutopilotChampion(button)));
    const dimRows=Object.entries(d.dimension_stats||{}).map(([key,row])=>{
      const trials=Number(row.trials||0),wins=Number(row.champion_wins||0);
      const avg=trials?Number(row.improvement_sum||0)/trials:0;
      return {key,trials,wins,avg,best:row.best_improvement,last:row.last_score};
    }).sort((a,b)=>(b.avg+0.1*(b.wins/Math.max(1,b.trials)))-(a.avg+0.1*(a.wins/Math.max(1,a.trials))));
    $('#apDimensions').innerHTML=dimRows.slice(0,40).map(x=>'<tr><td><code>'+esc(x.key)+'</code></td><td>'+x.trials+'</td><td>'+x.wins+'</td><td class="tnum '+(x.avg>0?'pos':x.avg<0?'neg':'')+'">'+apFmt(x.avg,5)+'</td><td class="tnum">'+apFmt(x.best,5)+'</td><td class="tnum">'+apFmt(x.last,5)+'</td></tr>').join('')||'<tr><td colspan="6" class="empty">Learning begins after the first non-baseline mutation.</td></tr>';
    $('#apLeaderboard').innerHTML=(d.leaderboard||[]).map((x,i)=>{const m=x.metrics||{};return '<tr><td>'+(i+1)+'</td><td><b>'+esc(x.asset)+'</b></td><td class="tnum '+(x.champion||x.regime_champion?'pos':'')+'">'+apFmt(m.score,5)+'</td><td class="tnum">'+(m.pnl==null?'—':fmt$(m.pnl,0))+'</td><td class="tnum">'+(m.max_drawdown==null?'—':fmt$(m.max_drawdown,0))+'</td><td>'+apFmt(m.return_to_drawdown,3)+'</td><td>'+(m.win_rate==null?'—':(100*m.win_rate).toFixed(1)+'%')+'</td><td>'+apFmt(m.profit_factor,2)+'</td><td>'+(m.trades??'—')+'</td><td>'+apDelta(x.delta)+'</td></tr>';}).join('')||'<tr><td colspan="10" class="empty">No completed trials.</td></tr>';
    $('#apHistory').innerHTML=(d.history||[]).slice().reverse().map(x=>'<tr><td class="tnum">'+(x.tested_at?new Date(x.tested_at*1000).toLocaleTimeString():'—')+'</td><td><b>'+esc(x.asset)+'</b></td><td>'+(x.champion?'<span class="chip b">NEW ASSET CHAMPION</span>':x.regime_champion?'<span class="chip b">NEW REGIME CHAMPION</span>':'<span class="chip">tested</span>')+'</td><td class="tnum">'+apFmt(x.metrics&&x.metrics.score,5)+'</td><td>'+apDelta(x.delta)+'</td><td>'+esc(x.regime_context&&x.regime_context.label||'unknown')+'</td><td>'+esc(x.chart_type||'engine')+'</td><td>'+esc(x.session||'engine')+'</td><td><code>'+esc(x.id||'')+'</code></td></tr>').join('')||'<tr><td colspan="9" class="empty">No autonomous trials yet.</td></tr>';
    if(d.last_error)$('#apStatus').innerHTML+=' · <span class="neg">'+esc(d.last_error.detail||d.last_error.type||'error')+'</span>';
  }catch(e){if($('#apStatus'))$('#apStatus').innerHTML='<span class="neg">'+esc(e.message||String(e))+'</span>';}finally{
    autopilotLoading=false;
    if(autopilotPendingLoad&&view==='autopilot'){autopilotPendingLoad=false;setTimeout(loadAutopilot,0);}
  }
}
async function promoteAutopilotChampion(button){
  button.disabled=true;
  try{
    const result=await admin('/admin/research/champion-study',{asset:button.dataset.asset,champion_id:button.dataset.id},true);
    if(result&&result.job){sessionStorage.setItem('icarus-champion-study-job',result.job);toast('Champion qualification started · study '+result.job);}
    else toast('Champion qualification could not start; see the reported gate or request error.',true);
    loadAutopilot();
  }catch(e){toast(e.message||String(e),true);}
  finally{if(button.isConnected)button.disabled=false;}
}
async function runAutopilotMutation(control,path,body){
  if(autopilotMutationBusy){if(typeof toast==='function')toast('Autopilot control already running',true);return;}
  autopilotMutationBusy=true;
  if(control)control.disabled=true;
  try{await admin(path,body||{});}
  finally{
    autopilotMutationBusy=false;
    if(control&&control.isConnected)control.disabled=false;
    loadAutopilot();
  }
}
function wireAutopilot(){
  clearInterval(autopilotTimer);
  $('#apRefresh')&&$('#apRefresh').addEventListener('click',loadAutopilot);
  $('#apStart')&&$('#apStart').addEventListener('click',e=>runAutopilotMutation(e.currentTarget,'/admin/autopilot/start',{}));
  $('#apStop')&&$('#apStop').addEventListener('click',e=>runAutopilotMutation(e.currentTarget,'/admin/autopilot/stop',{}));
  $('#apStep')&&$('#apStep').addEventListener('click',e=>runAutopilotMutation(e.currentTarget,'/admin/autopilot/step',{}));
  $('#apCadence')&&$('#apCadence').addEventListener('change',e=>runAutopilotMutation(e.currentTarget,'/admin/autopilot/config',{cadence_seconds:Number(e.target.value)}));
  $('#apWindows')&&$('#apWindows').addEventListener('change',e=>runAutopilotMutation(e.currentTarget,'/admin/autopilot/config',{robustness_windows:Number(e.target.value)}));
  $('#apAsset')&&$('#apAsset').addEventListener('change',e=>runAutopilotMutation(e.currentTarget,'/admin/autopilot/config',{assets:e.target.value?[e.target.value]:[]}));
  loadAutopilot();autopilotTimer=setInterval(loadAutopilot,1200);
}

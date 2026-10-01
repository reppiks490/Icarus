/* ICARUS Engine Control — authenticated registered application controls. */
let engineControlLoading=false, engineControlLast=null;

function ecChip(value){
  const s=String(value??'unknown'), u=s.toUpperCase();
  const cls=/ERROR|FAILED|BLOCKED|DEGRADED/.test(u)?'r':/WARN|UNKNOWN|STOPPED|PAUSED/.test(u)?'w':/OK|GREEN|RUNNING|ACTIVE|SUCCESS|VERIFIED/.test(u)?'b':'';
  return '<span class="chip '+cls+'">'+esc(s)+'</span>';
}

function engineControlHtml(){
  return '<section class="card c12">'+
    '<h2>ICARUS Engine Control <span class="sub">authenticated operator plane · registered actions only</span></h2>'+
    '<div id="ecSummary" class="tiles"></div>'+
    '<div class="toolbar" style="margin-top:12px"><button id="ecRefresh">Refresh</button><button id="ecSyncAll" class="primary">Sync all intelligence</button><span id="ecStatus" class="small muted">Loading…</span></div>'+
    '<div class="small muted">Full registered application control. Arbitrary shell/filesystem access, secret export, and broker arming are intentionally not exposed.</div>'+
  '</section>'+
  '<section class="card c12"><h2>Engine &amp; asset controls</h2><div id="ecCore"></div></section>'+
  '<section class="card c12"><h2>Specialized control surfaces <span class="sub">deep configuration and subsystem-specific operations</span></h2>'+
    '<div class="toolbar" id="ecSurfaces">'+
      '<button data-ec-view="inputs">Inputs / chart config</button>'+
      '<button data-ec-view="research">Research</button>'+
      '<button data-ec-view="autopilot">Tactical Autopilot</button>'+
      '<button data-ec-view="brain">Adaptive Brain</button>'+
      '<button data-ec-view="evolution">MCP Evolution</button>'+
      '<button data-ec-view="parallax">PARALLAX / DREAMSTATE</button>'+
      '<button data-ec-view="possibility">ICARUS Ψ</button>'+
      '<button data-ec-view="integrity">Data Integrity</button>'+
      '<button data-ec-view="system">System Intelligence</button>'+
      '<button data-ec-view="commands">Commands</button>'+
    '</div></section>'+
  '<section class="card c7"><h2>Subsystem controls</h2><div id="ecSubsystemActions"></div></section>'+
  '<section class="card c5"><h2>Subsystem health</h2><div id="ecSubsystems"></div></section>'+
  '<section class="card c12"><h2>MCP / audit mirror <span class="sub">important repair, audit, evolution, integration and control receipts</span></h2><div id="ecEvents" class="scroll" style="max-height:560px"></div></section>'+
  '<section class="card c12"><details><summary>Raw control snapshot</summary><pre id="ecRaw" class="log" style="max-height:520px"></pre></details></section>';
}

function ecTargetControl(action,data){
  if(action.target==='none') return '';
  if(action.target==='asset'){
    const assets=((((data||{}).subsystems||{}).portfolio||{}).data||{}).assets||[];
    if(action.id==='asset.add') return '<input data-ec-target="'+esc(action.id)+'" placeholder="symbol (NQ, GC, BTC…)" style="width:170px">';
    const opts=assets.map(a=>'<option value="'+esc(a.symbol)+'">'+esc(a.continuous_symbol||a.symbol)+'</option>').join('');
    return '<select data-ec-target="'+esc(action.id)+'">'+opts+'</select>';
  }
  if(action.target==='job') return '<input data-ec-target="'+esc(action.id)+'" placeholder="research job id" style="width:190px">';
  return '';
}

function ecActionRow(action,data){
  const args = action.id==='asset.add'
    ? '<input data-ec-args="'+esc(action.id)+'" placeholder=\'{"tf":"20"}\' style="width:180px">'
    : action.id==='asset.apply_config'
    ? '<input data-ec-args="'+esc(action.id)+'" placeholder=\'{"values":{},"chart":{}}\' style="width:240px">'
    : action.id==='autopilot.configure'
    ? '<input data-ec-args="'+esc(action.id)+'" placeholder=\'{"cadence_seconds":15,"robustness_windows":3}\' style="width:300px">'
    : action.id==='dreamstate.refresh'
    ? '<input data-ec-args="'+esc(action.id)+'" placeholder=\'{"min_samples":5}\' style="width:180px">'
    : '';
  return '<div class="cmd">'+
    '<div><b>'+esc(action.title)+'</b><div class="small muted">'+esc(action.group)+'</div></div>'+
    '<span class="desc">'+esc(action.description)+'</span>'+
    '<span style="display:flex;gap:6px;align-items:center;flex-wrap:wrap">'+ecTargetControl(action,data)+args+'</span>'+
    '<button class="sm '+(action.danger?'danger':'')+'" data-ec-run="'+esc(action.id)+'">Run</button>'+
  '</div>';
}

function ecSubsystemTable(data){
  const rows=Object.entries((data&&data.subsystems)||{}).map(([name,row])=>{
    const d=row&&row.data||{}, stat=row&&row.status||'unknown';
    const hint=d.status||d.state||d.phase||d.enabled;
    return '<tr><td><b>'+esc(name.replace(/_/g,' '))+'</b></td><td>'+ecChip(stat)+'</td><td class="small">'+
      (hint==null?'—':esc(typeof hint==='object'?JSON.stringify(hint):String(hint)))+
      (row&&row.error?'<div class="neg">'+esc(row.error)+'</div>':'')+'</td></tr>';
  }).join('');
  return '<div class="scroll" style="max-height:520px"><table><thead><tr><th>Subsystem</th><th>Snapshot</th><th>State</th></tr></thead><tbody>'+
    (rows||'<tr><td colspan=3 class="empty">No subsystem state.</td></tr>')+'</tbody></table></div>';
}

function ecEventTable(data){
  const sys=(data.important_events||[]).map(x=>({...x,source:'system'}));
  const integrity=((((data.subsystems||{}).integrity||{}).data||{}).events||[]).map(x=>({
    id:x.id,kind:x.kind,severity:x.status,title:x.area||x.summary,detail:x.summary,
    recorded_at:x.recorded_at,repository:x.source_repo,ref:x.source_commit,source:'integrity'
  }));
  const rows=[...sys,...integrity].sort((a,b)=>String(b.recorded_at||'').localeCompare(String(a.recorded_at||''))).slice(0,120);
  return '<table><thead><tr><th>Time</th><th>Source</th><th>Kind</th><th>Event</th><th>Ref</th></tr></thead><tbody>'+
    (rows.map(x=>'<tr><td class="tnum">'+esc(x.recorded_at||'—')+'</td><td>'+ecChip(x.source)+'</td><td>'+ecChip(x.kind||x.severity||'event')+
      '</td><td><b>'+esc(x.title||'')+'</b><div class="small muted" style="white-space:normal">'+esc(x.detail||'')+
      '</div></td><td class="tnum">'+esc(String(x.ref||'—').slice(0,16))+'</td></tr>').join('')||
      '<tr><td colspan=5 class="empty">No MCP/audit events recorded.</td></tr>')+'</tbody></table>';
}

function engineControlRender(data){
  engineControlLast=data;
  const sum=data.summary||{}, auth=data.authority||{};
  const summary=document.querySelector('#ecSummary');
  if(summary) summary.innerHTML=[
    ['Registered actions',sum.registered_actions],
    ['Subsystems',sum.subsystems],
    ['Subsystem errors',sum.subsystem_errors],
    ['Important events',sum.important_events],
    ['Application control',auth.application_control?'ENABLED':'NO'],
    ['Broker arming',auth.broker_arming?'EXPOSED':'NOT EXPOSED']
  ].map(x=>'<div class="tile"><div class="k">'+esc(x[0])+'</div><div class="v" style="font-size:16px">'+esc(x[1]??'—')+'</div></div>').join('');
  const status=document.querySelector('#ecStatus');
  if(status) status.textContent='snapshot '+(data.generated_at||'—')+' · admin auth '+(auth.admin_auth_required?'required':'invalid');
  const actions=data.actions||[];
  const core=actions.filter(a=>['Engine','Assets'].includes(a.group));
  const subs=actions.filter(a=>!['Engine','Assets'].includes(a.group));
  const coreEl=document.querySelector('#ecCore'); if(coreEl) coreEl.innerHTML=core.map(a=>ecActionRow(a,data)).join('');
  const actionEl=document.querySelector('#ecSubsystemActions'); if(actionEl) actionEl.innerHTML=subs.map(a=>ecActionRow(a,data)).join('');
  document.querySelectorAll('[data-ec-run]').forEach(b=>{b.onclick=()=>ecRun(b.dataset.ecRun);});
  const subEl=document.querySelector('#ecSubsystems'); if(subEl) subEl.innerHTML=ecSubsystemTable(data);
  const ev=document.querySelector('#ecEvents'); if(ev) ev.innerHTML=ecEventTable(data);
  const raw=document.querySelector('#ecRaw'); if(raw) raw.textContent=JSON.stringify(data,null,2);
}

async function loadEngineControl(){
  if(engineControlLoading||view!=='engine-control') return;
  engineControlLoading=true;
  try{
    const token=localStorage.getItem('icarus-engine-token')||'';
    const r=await fetch('/api/engine-control',{cache:'no-store',headers:{'Authorization':'Bearer '+token}});
    const data=await r.json().catch(()=>({}));
    if(!r.ok) throw new Error(data.detail||data.error||('HTTP '+r.status));
    if(view==='engine-control') engineControlRender(data);
  }catch(e){
    const el=document.querySelector('#ecStatus');
    if(el) el.textContent='Engine Control unavailable: '+e.message;
  }finally{engineControlLoading=false;}
}

async function ecRun(actionId){
  const data=engineControlLast||{}, action=(data.actions||[]).find(a=>a.id===actionId);
  if(!action) return toast('unknown control action',true);
  const targetEl=document.querySelector('[data-ec-target="'+CSS.escape(actionId)+'"]');
  const argsEl=document.querySelector('[data-ec-args="'+CSS.escape(actionId)+'"]');
  const body={action:actionId,reason:'ICARUS Engine Control panel'};
  if(action.target!=='none'){
    body.target=(targetEl&&targetEl.value||'').trim();
    if(!body.target) return toast(action.title+': target required',true);
  }
  if(argsEl&&argsEl.value.trim()){
    try{body.args=JSON.parse(argsEl.value);}catch(e){return toast(action.title+': args must be JSON',true);}
  }
  if(action.confirmation){
    const supplied=prompt('Destructive action. Type exactly:\n\n'+action.confirmation);
    if(supplied!==action.confirmation) return toast('confirmation did not match',true);
    body.confirm=supplied;
  }
  const result=await admin('/admin/engine-control',body,false);
  if(result){
    if(result.audit_recorded===false){
      toast(action.title+': state changed but final audit receipt failed — '+(result.audit_error||'unknown audit error'),true);
    }
    await loadEngineControl();
    if(typeof refresh==='function') refresh();
    if(typeof refreshAudit==='function') refreshAudit();
  }
}

function wireEngineControl(){
  const refresh=document.querySelector('#ecRefresh');
  if(refresh) refresh.onclick=loadEngineControl;
  const sync=document.querySelector('#ecSyncAll');
  if(sync) sync.onclick=()=>ecRun('sync.all');
  document.querySelectorAll('[data-ec-view]').forEach(b=>{
    b.onclick=()=>setView(b.dataset.ecView);
  });
  loadEngineControl();
}

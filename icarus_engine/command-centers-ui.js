/* Four independent, concurrent simulated-paper command centers. */
let paperWorkspaces = null;
let paperWorkspaceActive = 'cc1';
const paperWorkspaceDrafts = {};
let paperRequestSequence = 0;
const paperPendingActions = new Set();

function paperValue(x) { return x == null || x === '' || !Number.isFinite(Number(x)) ? null : Number(x); }
function paperSigned(x) { const n=paperValue(x); return n==null?'—':(n>0?'+':'')+paperMoney(n); }
function paperTone(x) { const n=paperValue(x); return n==null?'':n<0?'neg':'pos'; }
function paperCurrentPnl(realized,open) { const closed=paperValue(realized),mark=paperValue(open);if(closed==null||mark==null)return null;const total=closed+mark;return Number.isFinite(total)?total:null; }
function paperRealized(pnl,fallback) { return pnl?.realized_pnl??pnl?.paper_pnl??fallback; }
function paperConfigSignature(profile) { return JSON.stringify([profile.effective_inputs||{},profile.chart||{}]); }
function paperStateTone(x) {
  const s=String(x||'').toLowerCase();
  return /error|down|stale|fail|degraded|disconnected|unavailable|offline/.test(s)?'is-bad':/ready|healthy|connected|active|running/.test(s)?'is-good':'is-warn';
}

function paperWorkspacesHtml() {
  return `<section class="card c12 paper-deck" aria-label="Concurrent paper command centers">
    <header class="paper-deck-head"><div><p class="paper-kicker">ICARUS / SIMULATION DECK</p><h2>Four independent paper portfolios</h2><p>Separate strategy runners, positions, journals and paper P&amp;L. Shared market data, isolated controls.</p></div>
      <div class="paper-deck-actions"><span class="paper-mode">SIMULATED PAPER ONLY</span><button type="button" class="sm" data-paper-refresh>Refresh state</button></div></header>
    <p id="paperSnapshotNotice" class="small muted" role="status">Loading paper ledger state…</p>
    <div id="paperAggregate" class="paper-aggregate"></div>
    <div id="paperWorkspaceTabs" class="paper-workspace-grid" role="group" aria-label="Select a paper portfolio"></div>
    <div id="paperConnections" class="paper-connections"></div>
    <div id="paperWorkspaceBody"><div class="empty">Loading paper workspaces…</div></div>
  </section>`;
}

function paperEsc(x) { return String(x ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
function paperMoney(x) { const n=paperValue(x); return n==null?'—':n.toLocaleString(undefined,{style:'currency',currency:'USD',minimumFractionDigits:2,maximumFractionDigits:2}); }

function paperSetHeader(data) {
  const el=document.querySelector('#combinedPaperPnl'); if(!el)return;
  const profiles=data?.profiles;
  const value=data?.mode==='concurrent_paper'&&Array.isArray(profiles)&&profiles.length===4?paperCurrentPnl(paperRealized(data.aggregate),data.aggregate?.open_pnl):null;
  el.textContent=paperMoney(value);el.className='value '+paperTone(value);
  el.title=value==null?'Four paper ledger results unavailable.':`Closed live paper results plus current open marks across ${profiles.length} separate simulated ledgers. Open marks may include warmup-origin positions; replay-inclusive synthetic net is shown below.`;
}

async function loadPaperWorkspaces(full=false) {
  const sequence=++paperRequestSequence;
  const notice=document.querySelector('#paperSnapshotNotice');
  try {
    const response = await fetch('/api/command-centers', {cache:'no-store'});
    const data = await response.json().catch(()=>({}));
    if (!response.ok) throw new Error(data.detail||('HTTP '+response.status));
    if(sequence!==paperRequestSequence)return;
    if(data.mode!=='concurrent_paper'||data.profiles?.length!==4) throw new Error('four paper portfolios are unavailable');
    paperWorkspaces = data;
    if (!paperWorkspaces.profiles.some(p=>p.id===paperWorkspaceActive)) paperWorkspaceActive=paperWorkspaces.profiles[0].id;
    paperSetHeader(data);
    if(notice)notice.textContent='Latest engine snapshot · four isolated simulated ledgers';
    if(document.querySelector('#paperWorkspaceBody')) {
      const active=paperWorkspaces.profiles.find(p=>p.id===paperWorkspaceActive),draft=paperWorkspaceDrafts[paperWorkspaceActive];
      const cleanConfigChanged=!!(active&&draft&&!draft.dirty&&draft.baselineSignature!==paperConfigSignature(active));
      if(full||cleanConfigChanged||!document.querySelector('#paperWorkspaceRuntime'))renderPaperWorkspaces();
      else renderPaperLiveSections();
    }
  } catch (e) {
    if(sequence!==paperRequestSequence)return;
    paperSetHeader(null);
    if(notice)notice.textContent='Paper state unavailable: '+(e?.message||String(e));
    const target=document.querySelector('#paperWorkspaceBody');
    if(target&&!paperWorkspaces)target.innerHTML=`<div class="empty neg">Paper workspaces unavailable: ${paperEsc(e?.message||String(e))}</div>`;
  }
}

function paperAggregateHtml(data) {
  const a=data.aggregate||{},realized=paperRealized(a),current=paperCurrentPnl(realized,a.open_pnl);
  return `<div class="paper-aggregate-main"><span class="paper-metric-label">COMBINED PAPER P&amp;L · CLOSED + OPEN</span><strong class="tnum ${paperTone(current)}">${paperSigned(current)}</strong><span>Sum of all four current paper portfolios</span></div>
    <div class="paper-aggregate-side"><div><span>Persistent closed P&amp;L</span><b class="tnum ${paperTone(realized)}">${paperSigned(realized)}</b></div><div><span>Current open mark</span><b class="tnum ${paperTone(a.open_pnl)}">${paperSigned(a.open_pnl)}</b></div><div><span>Replay inclusive net</span><b class="tnum ${paperTone(a.net)}">${paperSigned(a.net)}</b></div></div>
    <p class="paper-basis">${current==null?'Aggregate ledger fields require the updated engine server.':`${paperEsc(a.open_positions??'—')} open positions. Closed P&L comes from persisted live paper trades; open marks may include warmup-origin positions. Replay-inclusive net and equity use synthetic per-asset capital.`}</p>`;
}

function paperProfileHtml(p) {
  const s=p.status||{},realized=paperRealized(p.pnl,s.paper_pnl),feed=p.feed||{},current=paperCurrentPnl(realized,p.pnl?.open_pnl??s.open_profit);
  const state=s.paused?'Entries paused':s.all_warm?'Runners ready':'Warming';
  return `<button type="button" class="paper-portfolio ${p.id===paperWorkspaceActive?'is-selected':''}" data-paper-profile="${paperEsc(p.id)}" aria-pressed="${p.id===paperWorkspaceActive}"><span class="paper-profile-top"><b>${paperEsc(p.id).toUpperCase()}</b><span class="paper-ledger-status ${s.paused?'is-warn':s.all_warm?'is-good':'is-warn'}">${state}</span></span><strong>${paperEsc(p.name)}</strong><em class="tnum ${paperTone(current)}">${paperSigned(current)}</em><span class="paper-profile-foot"><span>Closed + open P&amp;L</span><span>${paperEsc(s.positions??'—')} positions</span></span><small class="paper-feed-state ${paperStateTone(feed.status)}">Persistent closed ${paperSigned(realized)} · Feed ${paperEsc(feed.status||'unknown')}${feed.total_assets!=null?` ${paperEsc(feed.healthy_assets??0)}/${paperEsc(feed.total_assets)}`:''}</small></button>`;
}

function paperConnectionsHtml(data) {
  const connections=data.connections||{},feeds=Array.isArray(connections.feeds)?connections.feeds:[],adapters=Array.isArray(connections.adapters)?connections.adapters:[];
  const rows=(items,adapter)=>items.map(item=>{
    const state=adapter?(item.configured===false?'Not configured':item.connected===true?'Connected':item.connected===false?'Disconnected':item.configured===true?'Configured · unverified':'Unknown'):(item.status||'unknown');
    const tone=paperStateTone(state);
    return `<div class="paper-connection-row"><i class="${tone}" aria-hidden="true"></i><div><b>${paperEsc(item.label||item.id||'Connection')}</b><small>${paperEsc(item.detail||'No observation detail')}</small></div><span class="${tone}">${paperEsc(state)}</span></div>`;
  }).join('');
  return `<div class="paper-connection-panel"><div class="paper-section-head"><div><span class="paper-metric-label">DATA PATH</span><h3>Feed observations</h3></div><button type="button" class="sm" data-paper-market-data>Market data diagnostics ↗</button></div>${rows(feeds,false)||'<p class="empty">Feed observations unavailable from this engine snapshot.</p>'}</div>
    <div class="paper-connection-panel"><div class="paper-section-head"><div><span class="paper-metric-label">EXECUTION PATH</span><h3>Adapter inventory</h3></div><span class="paper-read-only">Read only · no live arming</span></div>${rows(adapters,true)||'<p class="empty">Adapter inventory unavailable from this engine snapshot.</p>'}</div>`;
}

function paperRuntimeHtml(p) {
  const s=p.status||{},pnl=p.pnl||{},assets=Array.isArray(s.assets)?s.assets:[];
  const realized=paperRealized(pnl,s.paper_pnl),current=paperCurrentPnl(realized,pnl.open_pnl??s.open_profit);
  const rows=assets.map(a=>`<tr><td><b>${paperEsc(a.symbol)}</b></td><td>${paperEsc(a.feed_provider||a.feed||'—')}</td><td>${a.warm?'Ready':'Warming'}</td><td>${a.paused?'Paused':'Running'}</td><td class="tnum">${paperEsc(a.position??0)}</td><td class="tnum ${paperTone(a.open_profit)}">${paperMoney(a.open_profit)}</td><td class="tnum ${paperTone(a.live_profit)}">${paperMoney(a.live_profit)}</td><td>${paperEsc(a.last_error||'—')}</td></tr>`).join('');
  return `<div class="paper-workspace-heading"><div><span class="paper-kicker">SELECTED LEDGER / ${paperEsc(p.id).toUpperCase()}</span><h3>${paperEsc(p.name)}</h3><p>${paperEsc(p.description||'')}</p></div><span class="paper-mode">PAPER ONLY</span></div>
    <div class="paper-runtime-tiles"><div><span>Current paper P&amp;L</span><b class="tnum ${paperTone(current)}">${paperSigned(current)}</b></div><div><span>Persistent closed P&amp;L</span><b class="tnum ${paperTone(realized)}">${paperSigned(realized)}</b></div><div><span>Open mark</span><b class="tnum ${paperTone(pnl.open_pnl??s.open_profit)}">${paperSigned(pnl.open_pnl??s.open_profit)}</b></div><div><span>Replay inclusive net</span><b class="tnum ${paperTone(pnl.replay_inclusive_net??s.net)}">${paperSigned(pnl.replay_inclusive_net??s.net)}</b></div></div>
    <div class="paper-workspace-controls"><span class="paper-ledger-status ${s.paused?'is-warn':s.all_warm?'is-good':'is-warn'}">${s.paused?'Entries paused':s.all_warm?'Runners ready':'Warming'}</span><span class="small muted">${assets.length} asset runners · ${paperEsc(s.positions??0)} open positions</span><div class="paper-workspace-actions"><button type="button" class="sm" data-paper-pause="${paperEsc(p.id)}" data-paused="${!!s.paused}">${s.paused?'Resume entries':'Pause entries'}</button><button type="button" class="sm danger" data-paper-flatten="${paperEsc(p.id)}">Flatten this ledger</button></div></div>
    <div class="paper-section-head"><h3>Independent paper runners</h3><span>Runner states from current engine snapshot</span></div><div class="scroll paper-runner-scroll"><table><thead><tr><th>Asset</th><th>Feed</th><th>Warmth</th><th>Entries</th><th>Position</th><th>Open mark</th><th>Live realized</th><th>Issue</th></tr></thead><tbody>${rows||'<tr><td colspan="8" class="empty">No paper runners configured.</td></tr>'}</tbody></table></div>`;
}

function paperControl(meta, value) {
  const name = paperEsc(meta.name), v = value ?? meta.default;
  if (meta.kind === 'bool') return `<label><input type="checkbox" data-paper-input="${name}" ${v?'checked':''}> <span class="small muted">${v?'on':'off'}</span></label>`;
  if (Array.isArray(meta.options)) return `<select data-paper-input="${name}">${meta.options.map(x=>`<option value="${paperEsc(x)}" ${String(x)===String(v)?'selected':''}>${paperEsc(x)}</option>`).join('')}</select>`;
  if (meta.kind === 'timeframe') return `<input type="text" data-paper-input="${name}" value="${paperEsc(v)}" style="width:90px">`;
  if (meta.kind === 'session') return `<input type="text" data-paper-input="${name}" value="${paperEsc(v)}" placeholder="HHMM-HHMM" style="width:120px">`;
  if (meta.kind === 'int' || meta.kind === 'float') return `<input type="number" data-paper-input="${name}" value="${paperEsc(v)}" ${meta.minval!=null?`min="${meta.minval}"`:''} ${meta.maxval!=null?`max="${meta.maxval}"`:''} step="${meta.step??(meta.kind==='int'?1:'any')}">`;
  return `<input type="text" data-paper-input="${name}" value="${paperEsc(v)}">`;
}

function paperWorkspaceDraft(profile) {
  if (!paperWorkspaceDrafts[profile.id] || !paperWorkspaceDrafts[profile.id].dirty) {
    paperWorkspaceDrafts[profile.id] = {
      inputs:{...(profile.effective_inputs||{})},
      chart:{...(profile.chart||{})},
      baselineSignature:paperConfigSignature(profile),
      dirty:false,
    };
  }
  return paperWorkspaceDrafts[profile.id];
}

function paperDraftConflict(profile,draft) { return !!(profile&&draft?.dirty&&draft.baselineSignature!==paperConfigSignature(profile)); }
function paperUpdateDraftState(profile) {
  const draft=profile&&paperWorkspaceDrafts[profile.id],state=document.querySelector('#paperDraftState');
  if(!draft||!state)return;
  const conflict=paperDraftConflict(profile,draft);
  state.textContent=conflict?'Settings changed elsewhere. Discard edits to load the latest settings.':draft.dirty?'Unsaved edits':'No pending edits';
  const apply=document.querySelector('[data-paper-apply]'),discard=document.querySelector('[data-paper-discard]');
  if(apply)apply.disabled=!draft.dirty||conflict||paperPendingActions.has(profile.id);
  if(discard)discard.disabled=!draft.dirty||paperPendingActions.has(profile.id);
}

function renderPaperLiveSections() {
  if (!paperWorkspaces) return;
  const aggregate=document.querySelector('#paperAggregate'),tabs=document.querySelector('#paperWorkspaceTabs'),connections=document.querySelector('#paperConnections');
  const focused=document.activeElement,focusAttr=['data-paper-profile','data-paper-market-data','data-paper-pause','data-paper-flatten'].find(attr=>focused?.hasAttribute(attr)),focusValue=focusAttr?focused.getAttribute(focusAttr):null;
  if(aggregate)aggregate.innerHTML=paperAggregateHtml(paperWorkspaces);
  if(tabs)tabs.innerHTML=paperWorkspaces.profiles.map(paperProfileHtml).join('');
  if(connections)connections.innerHTML=paperConnectionsHtml(paperWorkspaces);
  const active=paperWorkspaces.profiles.find(p=>p.id===paperWorkspaceActive),runtime=document.querySelector('#paperWorkspaceRuntime');
  const replaceRuntime=!!(runtime&&active&&!paperPendingActions.has(active.id));
  if(replaceRuntime)runtime.innerHTML=paperRuntimeHtml(active);
  tabs?.querySelectorAll('[data-paper-profile]').forEach(button=>button.addEventListener('click',()=>{paperWorkspaceActive=button.dataset.paperProfile;renderPaperWorkspaces();}));
  connections?.querySelector('[data-paper-market-data]')?.addEventListener('click',()=>setView('market-data'));
  if(replaceRuntime) {
    runtime.querySelector('[data-paper-pause]')?.addEventListener('click',paperPause);
    runtime.querySelector('[data-paper-flatten]')?.addEventListener('click',paperFlatten);
  }
  paperUpdateDraftState(active);
  if(focusAttr&&document.activeElement!==focused)Array.from(document.querySelectorAll(`[${focusAttr}]`)).find(el=>el.getAttribute(focusAttr)===focusValue)?.focus({preventScroll:true});
}

function renderPaperWorkspaces() {
  if(!paperWorkspaces)return;
  const body=document.querySelector('#paperWorkspaceBody'),p=paperWorkspaces.profiles.find(x=>x.id===paperWorkspaceActive);
  if(!body||!p)return;
  const draft=paperWorkspaceDraft(p),meta=paperWorkspaces.input_meta||[],groups={};
  meta.forEach(m=>(groups[m.group||'Other']=groups[m.group||'Other']||[]).push(m));
  const groupsHtml=Object.entries(groups).map(([group,items])=>`<details class="group"><summary>${paperEsc(group)}<span class="cnt">${items.length} inputs</span></summary>${items.map(m=>`<div class="irow"><div class="lbl"><span>${paperEsc(m.label)}</span><small>${paperEsc(m.name)}${m.tooltip?' · '+paperEsc(m.tooltip).slice(0,120):''}</small></div><div>${paperControl(m,draft.inputs[m.name])}</div><div class="ov">paper config</div><div class="small muted">default ${paperEsc(m.default)}</div></div>`).join('')}</details>`).join('');
  body.innerHTML=`<div id="paperWorkspaceRuntime"></div><div class="paper-config"><div class="paper-section-head"><div><span class="paper-metric-label">PROFILE CONFIGURATION</span><h3>Strategy inputs for ${paperEsc(p.name)}</h3></div><span id="paperDraftState" class="paper-draft-state">${draft.dirty?'Unsaved edits':'No pending edits'}</span></div>
    <p class="small muted">Each profile has its own chart and strategy settings. Applying changes re-warms only this paper workspace and requires its positions to be flat.</p>
    <div class="paper-chart-controls"><label>Chart timeframe <select data-paper-chart="timeframe">${['1','2','3','5','10','15','20','30','45','60','120','180','240','D','W'].map(tf=>`<option value="${tf}" ${String(draft.chart.timeframe||'20')===tf?'selected':''}>${tf}</option>`).join('')}</select></label>
      <label>Strategy chart <select data-paper-chart="chart_type"><option value="heikin_ashi" ${draft.chart.chart_type==='heikin_ashi'?'selected':''}>Heikin Ashi</option><option value="real" ${draft.chart.chart_type==='real'?'selected':''}>Standard OHLC</option></select></label>
      <label>Fill prices <select data-paper-chart="fill_on"><option value="real" ${draft.chart.fill_on==='real'?'selected':''}>Real OHLC</option><option value="chart" ${draft.chart.fill_on==='chart'?'selected':''}>Chart synthetic</option></select></label>
      <label>HTF/LTF source <select data-paper-chart="security_source"><option value="chart" ${draft.chart.security_source==='chart'?'selected':''}>Selected chart</option><option value="standard" ${draft.chart.security_source==='standard'?'selected':''}>Standard OHLC</option></select></label></div>
    <div class="paper-config-actions"><button type="button" class="primary" data-paper-apply="${paperEsc(p.id)}">Apply to this paper portfolio</button><button type="button" class="sm" data-paper-discard="${paperEsc(p.id)}">Discard edits</button><span class="small muted">Inputs stay in this portfolio until applied.</span></div>${groupsHtml||'<p class="empty">Strategy input metadata unavailable.</p>'}</div>`;
  body.querySelectorAll('[data-paper-input]').forEach(el=>el.addEventListener(el.tagName==='INPUT'&&el.type!=='checkbox'?'input':'change',()=>{
    const name=el.dataset.paperInput,item=meta.find(x=>x.name===name);let value=el.type==='checkbox'?el.checked:el.value;
    if(item?.kind==='int')value=parseInt(value,10);else if(item?.kind==='float')value=parseFloat(value);
    draft.inputs[name]=value;draft.dirty=true;paperUpdateDraftState(p);
  }));
  body.querySelectorAll('[data-paper-chart]').forEach(el=>el.addEventListener('change',()=>{draft.chart[el.dataset.paperChart]=el.value;draft.dirty=true;paperUpdateDraftState(p);}));
  body.querySelector('[data-paper-apply]')?.addEventListener('click',paperApply);
  body.querySelector('[data-paper-discard]')?.addEventListener('click',()=>{delete paperWorkspaceDrafts[p.id];renderPaperWorkspaces();});
  renderPaperLiveSections();
}

async function paperPause(event) {
  const button=event.currentTarget,id=button.dataset.paperPause,paused=button.dataset.paused!=='true';
  if(paperPendingActions.has(id))return;
  paperPendingActions.add(id);
  document.querySelectorAll('[data-paper-pause],[data-paper-flatten]').forEach(el=>el.disabled=true);
  try {
    const result=await admin(`/admin/command-centers/${encodeURIComponent(id)}/pause`,{paused});
    if(result)await loadPaperWorkspaces();
  } finally {paperPendingActions.delete(id);renderPaperLiveSections();}
}
async function paperFlatten(event) {
  const button=event.currentTarget,id=button.dataset.paperFlatten;
  if(!confirm(`Flatten every open simulated paper position in ${id.toUpperCase()} now?`))return;
  if(paperPendingActions.has(id))return;
  paperPendingActions.add(id);
  document.querySelectorAll('[data-paper-pause],[data-paper-flatten]').forEach(el=>el.disabled=true);
  try {
    await admin(`/admin/command-centers/${encodeURIComponent(id)}/flatten`,{confirm:true});
    await loadPaperWorkspaces();
  } finally {paperPendingActions.delete(id);renderPaperLiveSections();}
}
async function paperApply(event) {
  const button=event.currentTarget,id=button.dataset.paperApply,draft=paperWorkspaceDrafts[id];
  const profile=paperWorkspaces?.profiles?.find(p=>p.id===id);
  if(!draft?.dirty||!profile||paperDraftConflict(profile,draft)||paperPendingActions.has(id))return;
  paperPendingActions.add(id);paperUpdateDraftState(profile);
  try {
    // The update API accepts a full input set, so recheck the baseline before posting it.
    const response=await fetch('/api/command-centers',{cache:'no-store'});
    if(!response.ok)throw new Error('Could not verify the latest paper settings');
    const latest=await response.json(),current=latest.profiles?.find(p=>p.id===id);
    if(!current)throw new Error('Selected paper portfolio is unavailable');
    if(draft.baselineSignature!==paperConfigSignature(current)) {
      paperWorkspaces=latest;paperSetHeader(latest);renderPaperLiveSections();
      throw new Error('Settings changed elsewhere. Discard edits to load the latest settings');
    }
    const result=await admin(`/admin/command-centers/${encodeURIComponent(id)}`,{chart:draft.chart,inputs:draft.inputs});
    if(result){delete paperWorkspaceDrafts[id];await loadPaperWorkspaces(true);}
  } catch(e) {
    const notice=document.querySelector('#paperSnapshotNotice');
    if(notice)notice.textContent='Configuration not applied: '+(e?.message||String(e));
  } finally {
    paperPendingActions.delete(id);
    renderPaperLiveSections();
  }
}

document.addEventListener('click',event=>{
  if(event.target.closest?.('[data-paper-refresh]'))loadPaperWorkspaces();
});

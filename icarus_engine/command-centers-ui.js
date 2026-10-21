/* Four independent, concurrent simulated-paper command centers. */
let paperWorkspaces = null;
let paperRequestSequence = 0;
const paperPendingActions = new Set();

function paperValue(x) { return IcarusPaperPnl.amount(x) ? x : null; }
function paperSigned(x) { const n=paperValue(x); return n==null?'—':(n>0?'+':'')+paperMoney(n); }
function paperTone(x) { const n=paperValue(x); return n==null?'':n<0?'neg':'pos'; }
function paperCurrentPnl(realized,open) { const closed=paperValue(realized),mark=paperValue(open);if(closed==null||mark==null)return null;const total=closed+mark;return Number.isFinite(total)?total:null; }
function paperRealized(pnl) { return pnl?.realized_pnl; }
function paperLedger(id) { return IcarusPaperPnl.read(paperWorkspaces)?.profiles.find(row=>row.id===id)||{}; }
function paperSelectedWorkspace() {
  const id=globalThis.IcarusClient?.context?.id;
  return ['cc1','cc2','cc3','cc4'].includes(id)?id:null;
}
function paperStateTone(x) {
  const s=String(x||'').toLowerCase();
  return /error|down|stale|fail|degraded|disconnected|unavailable|offline/.test(s)?'is-bad':/ready|healthy|connected|active|running/.test(s)?'is-good':'is-warn';
}

function paperWorkspacesHtml() {
  return `<section class="card c12 paper-deck" aria-label="Concurrent paper command centers">
    <header class="paper-deck-head"><div><p class="paper-kicker">ICARUS / SHARED SIMULATION OVERVIEW</p><h2>Four independent paper portfolios</h2><p>Shared overview of separate runners, positions, journals and paper P&amp;L. Open a ledger dashboard for its controls and Inputs.</p></div>
      <div class="paper-deck-actions"><span class="paper-mode">SIMULATED PAPER ONLY</span><button type="button" class="sm" data-paper-refresh>Refresh state</button></div></header>
    <p id="paperSnapshotNotice" class="small muted" role="status">Loading paper ledger state…</p>
    <nav aria-label="Separate dashboards">${['cc1','cc2','cc3','cc4'].map(id=>`<a href="/dashboards/${id}">${id.toUpperCase()} dashboard ↗</a>`).join(' · ')} · <a href="/dashboards/connections">Connections ↗</a></nav>
    <div id="paperAggregate" class="paper-aggregate"></div>
    <div id="paperWorkspaceTabs" class="paper-workspace-grid" role="group" aria-label="Open a paper portfolio dashboard"></div>
    <div id="paperConnections" class="paper-connections"></div>
    <div id="paperWorkspaceBody"><div class="empty">Loading paper workspaces…</div></div>
  </section>`;
}

function paperEsc(x) { return String(x ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
function paperMoney(x) { const n=paperValue(x); return n==null?'—':n.toLocaleString(undefined,{style:'currency',currency:'USD',minimumFractionDigits:2,maximumFractionDigits:2}); }

function paperSetHeader(data) {
  const el=document.querySelector('#combinedPaperPnl'); if(!el)return;
  const accounting=IcarusPaperPnl.read(data),value=accounting?.aggregate.total_pnl??null;
  el.textContent=paperMoney(value);el.className='value '+paperTone(value);
  el.title='Four isolated USD paper ledgers; persisted closures plus fresh open marks. Fees unverified; no broker reconciliation. '+(value==null?'Current total unavailable.':'');
}

function paperExpireObservations() {
  if(paperWorkspaces&&!IcarusPaperPnl.read(paperWorkspaces)) {
    paperSetHeader(null);
    renderPaperLiveSections();
  }
}
setInterval(paperExpireObservations,1000);

async function loadPaperWorkspaces(full=false) {
  const sequence=++paperRequestSequence;
  const notice=document.querySelector('#paperSnapshotNotice');
  try {
    const client=globalThis.IcarusClient;
    const data = client?await client.shared('/api/command-centers'):await IcarusPaperPnl.fetchJson('/api/command-centers');
    if(sequence!==paperRequestSequence)return;
    if(data.mode!=='concurrent_paper'||data.profiles?.length!==4||new Set(data.profiles.map(p=>p.id)).size!==4||!data.profiles.every(p=>['cc1','cc2','cc3','cc4'].includes(p.id))) throw new Error('four paper portfolios are unavailable');
    paperWorkspaces = data;
    paperSetHeader(data);
    if(notice)notice.textContent='Shared cross-ledger snapshot · four isolated simulated ledgers';
    if(document.querySelector('#paperWorkspaceBody')) {
      if(full||!document.querySelector('#paperWorkspaceRuntime'))renderPaperWorkspaces();
      else renderPaperLiveSections();
    }
  } catch (e) {
    if(sequence!==paperRequestSequence)return;
    paperSetHeader(null);
    paperWorkspaces=null;
    for(const selector of ['#paperAggregate','#paperWorkspaceTabs','#paperConnections','#paperWorkspaceRuntime']){const el=document.querySelector(selector);if(el)el.innerHTML='<p class="empty">Current observations unavailable.</p>';}
    if(notice)notice.textContent='Paper state unavailable: '+(e?.message||String(e));
    const target=document.querySelector('#paperWorkspaceBody');
    if(target&&!document.querySelector('#paperWorkspaceRuntime'))target.innerHTML=`<div class="empty neg">Paper workspaces unavailable: ${paperEsc(e?.message||String(e))}</div>`;
  }
}

function paperAggregateHtml(data) {
  const a=IcarusPaperPnl.read(data)?.aggregate||{},complete=a.accounting_complete===true,realized=a.realized_pnl,current=a.total_pnl;
  return `<div class="paper-aggregate-main"><span class="paper-metric-label">COMBINED PAPER P&amp;L · CLOSED + OPEN</span><strong class="tnum ${paperTone(current)}">${paperSigned(current)}</strong><span>Sum of all four current paper portfolios</span></div>
    <div class="paper-aggregate-side"><div><span>Persistent closed P&amp;L</span><b class="tnum ${paperTone(realized)}">${paperSigned(realized)}</b></div><div><span>Current open mark</span><b class="tnum ${paperTone(a.open_pnl)}">${paperSigned(a.open_pnl)}</b></div><div><span>Broker reconciliation</span><b class="tnum ${paperTone(a.net)}">—</b></div></div>
    <p class="paper-basis">${current==null?'Aggregate ledger fields require the updated engine server.':`${paperEsc(a.open_positions??'—')} open positions. Closed P&L comes from persisted live paper trades; open marks may include warmup-origin positions. Replay-inclusive net and equity use synthetic per-asset capital.`}</p>`;
}

function paperProfileHtml(p) {
  const s=p.status||{},ledger=paperLedger(p.id),realized=ledger.realized_pnl,feed=p.feed||{},current=ledger.total_pnl;
  const observed=!!IcarusPaperPnl.read(paperWorkspaces)&&p.runtime_available===true&&!s.snapshot_unavailable&&!s.view_stale;
  const state=!observed?'Runtime unavailable':s.paused?'Entries paused':s.all_warm?'Runners ready':'Warming';
  return `<a href="/dashboards/${paperEsc(p.id)}" class="paper-portfolio ${p.id===paperSelectedWorkspace()?'is-selected':''}" data-paper-profile="${paperEsc(p.id)}" ${p.id===paperSelectedWorkspace()?'aria-current="page"':''}><span class="paper-profile-top"><b>${paperEsc(p.id).toUpperCase()}</b><span class="paper-ledger-status ${!observed?'is-bad':s.paused?'is-warn':s.all_warm?'is-good':'is-warn'}">${state}</span></span><strong>${paperEsc(p.name)}</strong><em class="tnum ${paperTone(current)}">${paperSigned(current)}</em><span class="paper-profile-foot"><span>Closed + open P&amp;L</span><span>${paperEsc(observed?s.positions??'—':'—')} positions</span></span><small class="paper-feed-state ${paperStateTone(observed?feed.status:'unavailable')}">Persistent closed ${paperSigned(realized)} · Feed ${paperEsc(observed?feed.status||'unknown':'unavailable')}${observed&&feed.total_assets!=null?` ${paperEsc(feed.healthy_assets??0)}/${paperEsc(feed.total_assets)}`:''}</small></a>`;
}

function paperConnectionsHtml(data) {
  const fresh=!!IcarusPaperPnl.read(data),connections=data.connections||{},feeds=fresh&&Array.isArray(connections.feeds)?connections.feeds:[],adapters=fresh&&Array.isArray(connections.adapters)?connections.adapters:[];
  const rows=(items,adapter)=>items.map(item=>{
    const state=adapter?(item.configured===false?'Not configured':item.connected===true?'Connected':item.connected===false?'Disconnected':item.configured===true?'Configured · unverified':'Unknown'):(item.status||'unknown');
    const tone=paperStateTone(state);
    return `<div class="paper-connection-row"><i class="${tone}" aria-hidden="true"></i><div><b>${paperEsc(item.label||item.id||'Connection')}</b><small>${paperEsc(item.detail||'No observation detail')}</small></div><span class="${tone}">${paperEsc(state)}</span></div>`;
  }).join('');
  return `<div class="paper-connection-panel"><div class="paper-section-head"><div><span class="paper-metric-label">SHARED DATA PATH</span><h3>Feed observations</h3></div><button type="button" class="sm" data-paper-market-data>Market data diagnostics ↗</button></div>${rows(feeds,false)||'<p class="empty">Feed observations unavailable from this engine snapshot.</p>'}</div>
    <div class="paper-connection-panel"><div class="paper-section-head"><div><span class="paper-metric-label">SHARED EXECUTION INVENTORY</span><h3>Adapter inventory</h3></div><span class="paper-read-only">Read only · no live arming</span></div>${rows(adapters,true)||'<p class="empty">Adapter inventory unavailable from this engine snapshot.</p>'}</div>`;
}

function paperRuntimeHtml(p) {
  const s=p.status||{},pnl=paperLedger(p.id),assets=Array.isArray(s.assets)?s.assets:[];
  if(!IcarusPaperPnl.read(paperWorkspaces)||p.runtime_available!==true||s.snapshot_unavailable||s.view_stale)
    return `<p class="empty">Current runner observations for ${paperEsc(p.id).toUpperCase()} are unavailable from the shared snapshot.</p>`;
  const realized=pnl.realized_pnl,current=pnl.total_pnl;
  const controls=p.id===paperSelectedWorkspace()?`<button type="button" class="sm" data-paper-pause="${paperEsc(p.id)}" data-paused="${!!s.paused}">${s.paused?'Resume entries':'Pause entries'}</button><button type="button" class="sm danger" data-paper-flatten="${paperEsc(p.id)}">Flatten this ledger</button>`:`<a href="/dashboards/${paperEsc(p.id)}">Open ledger controls ↗</a>`;
  const rows=assets.map(a=>`<tr><td><b>${paperEsc(a.symbol)}</b></td><td>${paperEsc(a.feed_provider||a.feed||'—')}</td><td>${a.warm?'Ready':'Warming'}</td><td>${a.paused?'Paused':'Running'}</td><td class="tnum">${paperEsc(a.position??0)}</td><td class="tnum ${paperTone(a.open_profit)}">${paperMoney(pnl.open_pnl!=null&&paperValue(a.price_age)!=null&&a.price_age>=0&&a.price_age<=90?a.open_profit:null)}</td><td class="tnum ${paperTone(a.live_profit)}">${paperMoney(pnl.realized_pnl!=null?a.live_profit:null)}</td><td>${paperEsc(a.last_error||'—')}</td></tr>`).join('');
  return `<div class="paper-workspace-heading"><div><span class="paper-kicker">SHARED SNAPSHOT / ${paperEsc(p.id).toUpperCase()}</span><h3>${paperEsc(p.name)}</h3><p>${paperEsc(p.description||'')}</p></div><span class="paper-mode">PAPER ONLY</span></div>
    <div class="paper-runtime-tiles"><div><span>Current paper P&amp;L</span><b class="tnum ${paperTone(current)}">${paperSigned(current)}</b></div><div><span>Persistent closed P&amp;L</span><b class="tnum ${paperTone(realized)}">${paperSigned(realized)}</b></div><div><span>Open mark</span><b class="tnum ${paperTone(pnl.open_pnl)}">${paperSigned(pnl.open_pnl)}</b></div><div><span>Broker reconciliation</span><b class="tnum ${paperTone(null)}">${paperSigned(null)}</b></div></div>
    <div class="paper-workspace-controls"><span class="paper-ledger-status ${s.paused?'is-warn':s.all_warm?'is-good':'is-warn'}">${s.paused?'Entries paused':s.all_warm?'Runners ready':'Warming'}</span><span class="small muted">${assets.length} asset runners · ${paperEsc(s.positions??0)} open positions</span><div class="paper-workspace-actions">${controls}</div></div>
    <div class="paper-section-head"><h3>Independent paper runners</h3><span>Runner states from current engine snapshot</span></div><div class="scroll paper-runner-scroll"><table><thead><tr><th>Asset</th><th>Feed</th><th>Warmth</th><th>Entries</th><th>Position</th><th>Open mark</th><th>Live realized</th><th>Issue</th></tr></thead><tbody>${rows||'<tr><td colspan="8" class="empty">No paper runners configured.</td></tr>'}</tbody></table></div>`;
}

function renderPaperLiveSections() {
  if (!paperWorkspaces) return;
  const aggregate=document.querySelector('#paperAggregate'),tabs=document.querySelector('#paperWorkspaceTabs'),connections=document.querySelector('#paperConnections');
  const focused=document.activeElement,focusAttr=['data-paper-profile','data-paper-market-data','data-paper-pause','data-paper-flatten','data-paper-inputs'].find(attr=>focused?.hasAttribute(attr)),focusValue=focusAttr?focused.getAttribute(focusAttr):null;
  if(aggregate)aggregate.innerHTML=paperAggregateHtml(paperWorkspaces);
  if(tabs)tabs.innerHTML=paperWorkspaces.profiles.map(paperProfileHtml).join('');
  if(connections)connections.innerHTML=paperConnectionsHtml(paperWorkspaces);
  const active=paperWorkspaces.profiles.find(p=>p.id===paperSelectedWorkspace()),runtime=document.querySelector('#paperWorkspaceRuntime');
  if(runtime&&active&&!paperPendingActions.has(active.id)) {
    runtime.innerHTML=paperRuntimeHtml(active);
    runtime.querySelector('[data-paper-pause]')?.addEventListener('click',paperPause);
    runtime.querySelector('[data-paper-flatten]')?.addEventListener('click',paperFlatten);
  }
  connections?.querySelector('[data-paper-market-data]')?.addEventListener('click',()=>setView('market-data'));
  if(typeof applyWritePermissions==='function')applyWritePermissions();
  if(focusAttr&&document.activeElement!==focused)Array.from(document.querySelectorAll(`[${focusAttr}]`)).find(el=>el.getAttribute(focusAttr)===focusValue)?.focus({preventScroll:true});
}

function renderPaperWorkspaces() {
  if(!paperWorkspaces)return;
  const body=document.querySelector('#paperWorkspaceBody'),id=paperSelectedWorkspace();
  if(!body)return;
  const selected=paperWorkspaces.profiles.find(p=>p.id===id);
  body.innerHTML=selected?`<div id="paperWorkspaceRuntime"></div><div class="paper-config"><div class="paper-section-head"><h3>Inputs for ${paperEsc(selected.name)}</h3><button type="button" class="sm" data-paper-inputs>Open Inputs</button></div><p class="small muted">Use this dashboard's Inputs tab to edit individual assets or the workspace defaults with a saved configuration revision.</p></div>`:
    '<p class="empty">Open a ledger dashboard above to inspect its runners, edit Inputs or use its paper controls. This shared overview does not select an operating ledger.</p>';
  body.querySelector('[data-paper-inputs]')?.addEventListener('click',()=>setView('inputs'));
  renderPaperLiveSections();
}

async function paperRunControl(id,action) {
  const client=globalThis.IcarusClient,selected=paperSelectedWorkspace();
  if(!selected||id!==selected||!client||paperPendingActions.has(id))return;
  paperPendingActions.add(id);
  document.querySelectorAll('[data-paper-pause],[data-paper-flatten]').forEach(el=>el.disabled=true);
  try {
    await client.control(action);
    await loadPaperWorkspaces();
  } catch(error) {
    const receipt=error?.receipt,message='Paper control: '+(error?.message||String(error))+
      (receipt?.partial===true?` · ${receipt.flattened_positions??'—'} positions closed; ${receipt.positions_remain_open===true?'positions remain open':receipt.positions_remain_open===false?'no positions remain open':'open position state unavailable'}`:'');
    const notice=document.querySelector('#paperSnapshotNotice');
    if(notice)notice.textContent=message;
    await loadPaperWorkspaces();
    const refreshedNotice=document.querySelector('#paperSnapshotNotice');
    if(refreshedNotice)refreshedNotice.textContent=message;
  } finally {paperPendingActions.delete(id);renderPaperLiveSections();}
}
async function paperPause(event) {
  const button=event.currentTarget,id=button.dataset.paperPause;
  return paperRunControl(id,button.dataset.paused==='true'?'resume':'pause');
}
async function paperFlatten(event) {
  const id=event.currentTarget.dataset.paperFlatten;
  if(!paperSelectedWorkspace()||id!==paperSelectedWorkspace()||paperPendingActions.has(id))return;
  if(!confirm(`Flatten every open simulated paper position in ${id.toUpperCase()} now?`))return;
  return paperRunControl(id,'flatten');
}

document.addEventListener('click',event=>{
  if(event.target.closest?.('[data-paper-refresh]'))loadPaperWorkspaces();
});

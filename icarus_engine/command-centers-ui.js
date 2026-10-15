/* Four independent, concurrent simulated-paper command centers. */
let paperWorkspaces = null;
let paperWorkspaceActive = 'cc1';
const paperWorkspaceDrafts = {};

function paperWorkspacesHtml() {
  return `<section class="card c12">
    <h2>Concurrent Paper Command Centers <span class="sub">four independent strategy instances · separate positions, journals, and paper equity</span></h2>
    <div class="callout" style="margin:10px 0"><b>SIMULATED PAPER ONLY</b><span class="small"> These workspaces do not connect to a broker or place live orders. Market data is shared; paper positions and P&amp;L are isolated by workspace.</span></div>
    <div id="paperWorkspaceTabs" class="toolbar"></div>
    <div id="paperWorkspaceBody"><div class="empty">Loading paper workspaces…</div></div>
  </section>`;
}

function paperEsc(x) { return String(x ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
function paperMoney(x) { return Number.isFinite(Number(x)) ? Number(x).toLocaleString(undefined,{style:'currency',currency:'USD',maximumFractionDigits:2}) : '—'; }

async function loadPaperWorkspaces() {
  const target = document.querySelector('#paperWorkspaceBody');
  if (!target) return;
  target.innerHTML = '<div class="empty">Loading concurrent paper profiles…</div>';
  try {
    const response = await fetch('/api/command-centers', {cache:'no-store'});
    const data = await response.json().catch(()=>({}));
    if (!response.ok) throw new Error(data.detail||('HTTP '+response.status));
    paperWorkspaces = data;
    if (!paperWorkspaces.profiles?.length) throw new Error('no paper profiles are available');
    if (!paperWorkspaces.profiles.some(p=>p.id===paperWorkspaceActive)) paperWorkspaceActive=paperWorkspaces.profiles[0].id;
    renderPaperWorkspaces();
  } catch (e) {
    target.innerHTML = `<div class="empty neg">Paper workspaces unavailable: ${paperEsc(e?.message||String(e))}</div>`;
  }
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
  if (!paperWorkspaceDrafts[profile.id]) {
    paperWorkspaceDrafts[profile.id] = {
      inputs:{...(profile.effective_inputs||{})},
      chart:{...(profile.chart||{})},
      baseline:{...(profile.effective_inputs||{})},
      dirty:false,
    };
  }
  return paperWorkspaceDrafts[profile.id];
}

function renderPaperWorkspaces() {
  if (!paperWorkspaces) return;
  const tabs = document.querySelector('#paperWorkspaceTabs');
  const body = document.querySelector('#paperWorkspaceBody');
  if (!tabs || !body) return;
  tabs.innerHTML = paperWorkspaces.profiles.map(p=>`<button type="button" class="sm ${p.id===paperWorkspaceActive?'primary':''}" data-paper-profile="${paperEsc(p.id)}">${paperEsc(p.name)}</button>`).join('');
  const p = paperWorkspaces.profiles.find(x=>x.id===paperWorkspaceActive);
  if (!p) return;
  const draft = paperWorkspaceDraft(p);
  const s = p.status||{}, assets = s.assets||[];
  const rows = assets.map(a=>`<tr><td><b>${paperEsc(a.symbol)}</b></td><td>${paperEsc(a.status||'—')}</td><td>${a.warm?'Ready':'Warming'}</td><td>${a.paused?'Paused':'Running'}</td><td class="tnum">${Number(a.position||0)}</td><td class="tnum">${paperMoney(a.open_profit)}</td><td class="tnum">${paperMoney(a.live_profit)}</td><td>${paperEsc(a.last_error||'')}</td></tr>`).join('');
  const meta = paperWorkspaces.input_meta||[];
  const groups = {};
  meta.forEach(m=>(groups[m.group]=groups[m.group]||[]).push(m));
  const groupsHtml = Object.entries(groups).map(([group,items])=>`<details class="group"><summary>${paperEsc(group)}<span class="cnt">${items.length} inputs</span></summary>${items.map(m=>`<div class="irow"><div class="lbl"><span>${paperEsc(m.label)}</span><small>${paperEsc(m.name)}${m.tooltip?' · '+paperEsc(m.tooltip).slice(0,120):''}</small></div><div>${paperControl(m,draft.inputs[m.name])}</div><div class="ov">${draft.dirty?'draft':'paper config'}</div><div class="small muted">default ${paperEsc(m.default)}</div></div>`).join('')}</details>`).join('');
  body.innerHTML = `<div class="tiles">
      <div class="tile"><div class="k">Paper equity</div><div class="v">${paperMoney(s.equity)}</div></div>
      <div class="tile"><div class="k">Paper net</div><div class="v ${Number(s.net)>=0?'pos':'neg'}">${paperMoney(s.net)}</div></div>
      <div class="tile"><div class="k">Open positions</div><div class="v">${s.positions??0}</div></div>
      <div class="tile"><div class="k">Runtime</div><div class="v">${s.all_warm?'WARM':'STARTING'}</div></div>
    </div>
    <p class="small muted">${paperEsc(p.description)} · ${assets.length} separately simulated assets · profile changes re-warm only this workspace. Profile 2 starts at half the default TP values and double the default contract count as an editable paper assumption. The current strategy has no dedicated scalp switch.</p>
    <div class="toolbar"><label>Chart timeframe <select data-paper-chart="timeframe">${['1','2','3','5','10','15','20','30','45','60','120','180','240','D','W'].map(tf=>`<option value="${tf}" ${String(draft.chart.timeframe||'20')===tf?'selected':''}>${tf}</option>`).join('')}</select></label>
      <label>Strategy chart <select data-paper-chart="chart_type"><option value="heikin_ashi" ${draft.chart.chart_type==='heikin_ashi'?'selected':''}>Heikin Ashi</option><option value="real" ${draft.chart.chart_type==='real'?'selected':''}>Standard OHLC</option></select></label>
      <label>Fill prices <select data-paper-chart="fill_on"><option value="real" ${draft.chart.fill_on==='real'?'selected':''}>Real OHLC</option><option value="chart" ${draft.chart.fill_on==='chart'?'selected':''}>Chart synthetic</option></select></label>
      <label>HTF/LTF source <select data-paper-chart="security_source"><option value="chart" ${draft.chart.security_source==='chart'?'selected':''}>Selected chart</option><option value="standard" ${draft.chart.security_source==='standard'?'selected':''}>Standard OHLC</option></select></label>
      <button class="sm" data-paper-refresh>Refresh</button><span style="margin-left:auto"><button class="sm" data-paper-pause="${paperEsc(p.id)}" data-paused="${!!s.paused}">${s.paused?'Resume entries':'Pause entries'}</button> <button class="sm danger" data-paper-flatten="${paperEsc(p.id)}">Flatten this workspace</button> <button class="primary" data-paper-apply="${paperEsc(p.id)}">Apply to this paper workspace</button></span></div>
    <h3>Independent paper runners</h3><div class="scroll" style="max-height:300px"><table><thead><tr><th>Asset</th><th>Engine</th><th>Warmth</th><th>Entries</th><th>Position</th><th>Open P&amp;L</th><th>Realized P&amp;L</th><th>Issue</th></tr></thead><tbody>${rows||'<tr><td colspan="8" class="empty">No paper runners configured.</td></tr>'}</tbody></table></div>
    <h3>Inputs for ${paperEsc(p.name)}</h3><p class="small muted">Edits stay in this profile until you apply. Applying requires flat positions in this workspace so re-warm cannot rewrite an open paper trade.</p>${groupsHtml}`;
  body.querySelectorAll('[data-paper-input]').forEach(el=>el.addEventListener('change',()=>{
    const name=el.dataset.paperInput, item=meta.find(x=>x.name===name); let value=el.type==='checkbox'?el.checked:el.value;
    if (item?.kind==='int') value=parseInt(value,10); else if (item?.kind==='float') value=parseFloat(value);
    draft.inputs[name]=value; draft.dirty=true;
  }));
  body.querySelectorAll('[data-paper-chart]').forEach(el=>el.addEventListener('change',()=>{draft.chart[el.dataset.paperChart]=el.value;draft.dirty=true;}));
  tabs.querySelectorAll('[data-paper-profile]').forEach(el=>el.addEventListener('click',()=>{paperWorkspaceActive=el.dataset.paperProfile;renderPaperWorkspaces();}));
  body.querySelector('[data-paper-refresh]')?.addEventListener('click',loadPaperWorkspaces);
  body.querySelector('[data-paper-pause]')?.addEventListener('click',async ev=>{
    const button=ev.currentTarget, id=button.dataset.paperPause, paused=button.dataset.paused!=='true';
    try { const result=await admin(`/admin/command-centers/${id}/pause`,{paused}); if(!result)return; await loadPaperWorkspaces(); }
    catch(e){toast(e?.message||String(e),true);}
  });
  body.querySelector('[data-paper-flatten]')?.addEventListener('click',async ev=>{
    const button=ev.currentTarget,id=button.dataset.paperFlatten;
    if(!confirm('Flatten every open paper position in this workspace now?'))return;
    try { const result=await admin(`/admin/command-centers/${id}/flatten`,{confirm:true}); if(!result)return; await loadPaperWorkspaces(); }
    catch(e){toast(e?.message||String(e),true);}
  });
  body.querySelector('[data-paper-apply]')?.addEventListener('click',async ev=>{
    const button=ev.currentTarget; button.disabled=true;
    try {
      const result=await admin(`/admin/command-centers/${button.dataset.paperApply}`,{chart:draft.chart,inputs:draft.inputs});
      if(!result){button.disabled=false;return;}
      draft.dirty=false; toast('paper workspace re-warmed independently'); await loadPaperWorkspaces();
    } catch(e){toast(e?.message||String(e),true);button.disabled=false;}
  });
}

/* ICARUS Ψ latent-pressure + possibility panel. Research-only; never authorizes execution. */
(() => {
  let timer = null;
  let loading = false;
  let pendingLoad = false;
  let selected = '';
  let assetNames = [];
  const evidenceFeatures = [
    ['gamma_pressure','Gamma pressure'],
    ['basis_pressure','Basis pressure'],
    ['cta_pressure','CTA pressure'],
    ['liquidation_pressure','Liquidation pressure'],
    ['rebalance_pressure','Rebalance pressure'],
  ];
  const evidenceDraft = {source:'ui:operator', ttl_seconds:300, values:{}};
  let ledgerIncludeExpired = false;
  let lastEvidenceMessage = '';
  let lastEvidenceKind = '';
  const quickCache = new Map();
  const quickInflight = new Map();
  const QUICK_TTL_MS = 4000;

  const h = value => String(value ?? '').replace(/[&<>"]/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[ch]));
  const n = (value, digits=2) => (value == null || Number.isNaN(Number(value))) ? '—' : Number(value).toLocaleString(undefined,{maximumFractionDigits:digits,minimumFractionDigits:digits});
  const pct = value => (value == null || Number.isNaN(Number(value))) ? '—' : (Number(value)*100).toFixed(1)+'%';
  const score = value => (value == null || Number.isNaN(Number(value))) ? '—' : Number(value).toFixed(1);

  function chip(state) {
    const s = String(state || 'UNKNOWN').toUpperCase();
    const cls = s.includes('LONG') || s.includes('UP') || s.includes('OBSERVED') || s.includes('ACTIVE') ? 'b'
      : s.includes('SHORT') || s.includes('DOWN') || s.includes('BLOCK') || s.includes('ERROR') ? 'r' : 'w';
    return '<span class="chip '+cls+'">'+h(s)+'</span>';
  }

  function meter(value, signed=false) {
    if (value == null || Number.isNaN(Number(value))) return '<div class="psi-meter"><i style="width:0"></i><span>unavailable</span></div>';
    const raw = Number(value);
    const v = signed ? Math.max(-1,Math.min(1,raw)) : Math.max(0,Math.min(1,raw));
    const width = signed ? Math.abs(v)*50 : v*100;
    const left = signed && v < 0 ? 50-width : (signed ? 50 : 0);
    const cls = signed ? (v>0?'posbar':v<0?'negbar':'') : '';
    return '<div class="psi-meter signed-'+(signed?'1':'0')+'"><i class="'+cls+'" style="left:'+left+'%;width:'+width+'%"></i><span>'+(signed?(v>=0?'+':'')+v.toFixed(2):pct(v))+'</span></div>';
  }

  function evidenceConsoleHtml() {
    const rows = evidenceFeatures.map(([key,label]) => {
      const draft = evidenceDraft.values[key] || {};
      const value = draft.value == null ? '' : draft.value;
      const confidence = draft.confidence == null ? 1 : draft.confidence;
      return '<div class="psi-evidence-row"><div><b>'+h(label)+'</b><div class="small muted">'+h(key)+' · -1 bearish / +1 bullish</div></div>'+
        '<input class="psi-evidence-input" data-psi-value="'+h(key)+'" type="number" min="-1" max="1" step="0.01" placeholder="optional" value="'+h(value)+'">'+
        '<input class="psi-evidence-input" data-psi-confidence="'+h(key)+'" type="number" min="0" max="1" step="0.01" value="'+h(confidence)+'"></div>';
    }).join('');
    const msgCls = lastEvidenceKind === 'ok' ? 'pos' : lastEvidenceKind === 'error' ? 'neg' : 'muted';
    return '<section class="card c12" style="margin-top:12px"><h2>Research evidence console <span class="sub">operator-supplied Ψ force evidence · durable causal ledger · no execution authority</span></h2>'+
      '<div class="psi-evidence-toolbar"><label>Source <input id="psiEvidenceSource" type="text" maxlength="180" value="'+h(evidenceDraft.source)+'" placeholder="ui:operator"></label>'+
      '<label>TTL seconds <input id="psiEvidenceTtl" type="number" min="1" max="86400" step="1" value="'+h(evidenceDraft.ttl_seconds)+'"></label>'+
      '<label class="small"><input id="psiIncludeExpired" type="checkbox" '+(ledgerIncludeExpired?'checked':'')+'> include expired history</label>'+
      '<button class="primary" id="psiEvidenceSubmit">Submit evidence</button><button id="psiEvidenceClear">Clear form</button><button id="psiEvidenceRefresh">Refresh ledger</button></div>'+
      '<div class="small muted" style="margin:6px 0 10px">Only non-empty force values are submitted. Values must be within [-1,1], confidence within [0,1]. The current asset is <b>'+h(selected||'—')+'</b>.</div>'+
      '<div class="psi-evidence-head"><div>Force</div><div>Value</div><div>Confidence</div></div>'+rows+
      '<div id="psiEvidenceMessage" class="small '+msgCls+'" style="margin-top:8px">'+h(lastEvidenceMessage)+'</div>'+
      '<div id="psiEvidenceLedger" style="margin-top:12px"><div class="empty">loading evidence ledger…</div></div></section>';
  }

  function evidenceLedgerHtml(ledger) {
    if (!ledger || ledger.error) return '<div class="empty">evidence ledger unavailable: '+h((ledger&&ledger.error)||'unknown error')+'</div>';
    const active = Object.entries(ledger.active||{}).map(([feature,row]) => '<tr><td><b>'+h(feature)+'</b></td><td class="tnum">'+n(row.value,3)+'</td><td class="tnum">'+pct(row.confidence)+'</td><td>'+h(row.source||'—')+'</td><td class="tnum">'+h(row.observed_at||'—')+'</td><td class="tnum">'+h(String(row.evidence_id||'').slice(0,16))+'</td></tr>').join('');
    const history = (ledger.history||[]).map(row => '<tr><td>'+h(row.feature||'—')+'</td><td class="tnum">'+n(row.value,3)+'</td><td class="tnum">'+pct(row.confidence)+'</td><td>'+h(row.source||'—')+'</td><td class="tnum">'+h(row.observed_at||'—')+'</td><td class="tnum">'+h(row.created_at||'—')+'</td><td class="tnum">'+h(String(row.evidence_id||'').slice(0,16))+'</td></tr>').join('');
    const integrity = ledger.integrity || {};
    return '<div class="tiles" style="margin-top:0"><div class="tile"><div class="k">Active receipts</div><div class="v">'+h(ledger.active_count||0)+'</div></div><div class="tile"><div class="k">Causal history</div><div class="v">'+h(ledger.total_history_count||0)+'</div></div><div class="tile"><div class="k">Storage</div><div class="v">'+h(integrity.storage|| (ledger.durable?'sqlite':'memory'))+'</div></div><div class="tile"><div class="k">Integrity</div><div class="v">'+(integrity.ok===false?'FAILED':'VERIFIED')+'</div><div class="small muted">'+h(integrity.quick_check||'')+'</div></div></div>'+
      '<h3 style="margin:12px 0 6px;font-size:11px;text-transform:uppercase;letter-spacing:.09em;color:var(--muted)">Active evidence</h3><div class="scroll"><table><thead><tr><th>Feature</th><th>Value</th><th>Confidence</th><th>Source</th><th>Observed</th><th>Receipt</th></tr></thead><tbody>'+(active||'<tr><td colspan="6" class="empty">no active external evidence for this asset</td></tr>')+'</tbody></table></div>'+
      '<h3 style="margin:12px 0 6px;font-size:11px;text-transform:uppercase;letter-spacing:.09em;color:var(--muted)">Evidence history</h3><div class="scroll"><table><thead><tr><th>Feature</th><th>Value</th><th>Confidence</th><th>Source</th><th>Observed</th><th>Created</th><th>Receipt</th></tr></thead><tbody>'+(history||'<tr><td colspan="7" class="empty">no evidence receipts in the selected causal window</td></tr>')+'</tbody></table></div>';
  }

  function possibilityHtml(A) {
    const assets = (A||[]).map(a=>String(a.symbol||'')).filter(Boolean);
    assetNames = assets.slice();
    if (!selected || !assets.includes(selected)) selected = assets.includes('NQ') ? 'NQ' : (assets[0] || '');
    const options = assets.map(x=>'<option value="'+h(x)+'" '+(x===selected?'selected':'')+'>'+h(x)+'</option>').join('');
    return '<style>'+
      '.psi-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:10px}.psi-box{border:1px solid var(--ring);background:var(--surface-2);border-radius:12px;padding:11px}.psi-box h3{font-size:11px;text-transform:uppercase;letter-spacing:.09em;color:var(--muted);margin:0 0 7px}.psi-meter{height:24px;border:1px solid var(--ring);border-radius:7px;position:relative;overflow:hidden;background:var(--surface);margin-top:5px}.psi-meter:before{content:"";position:absolute;left:50%;top:0;bottom:0;width:1px;background:var(--ring)}.psi-meter i{position:absolute;top:0;bottom:0;background:var(--s1);opacity:.7}.psi-meter i.posbar{background:var(--good)}.psi-meter i.negbar{background:var(--crit)}.psi-meter span{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:600}.psi-kv{display:grid;grid-template-columns:minmax(120px,1fr) minmax(90px,auto);gap:6px 12px;font-size:12px}.psi-kv div:nth-child(odd){color:var(--muted)}.psi-force{display:grid;grid-template-columns:minmax(145px,1fr) 1fr 72px;gap:8px;align-items:center;padding:6px 0;border-bottom:1px solid var(--grid);font-size:12px}.psi-force:last-child{border-bottom:0}.psi-hero{font-size:34px;font-weight:700;letter-spacing:-.03em}.psi-hero.pos{color:var(--good)}.psi-hero.neg{color:var(--crit)}.psi-hero.neutral{color:var(--warn)}.psi-evidence-toolbar{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.psi-evidence-toolbar label{display:flex;gap:6px;align-items:center}.psi-evidence-toolbar input[type=text]{width:180px}.psi-evidence-head,.psi-evidence-row{display:grid;grid-template-columns:minmax(210px,1fr) 130px 130px;gap:10px;align-items:center;padding:7px 0;border-bottom:1px solid var(--grid)}.psi-evidence-head{font-size:10px;text-transform:uppercase;letter-spacing:.08em;color:var(--muted)}.psi-evidence-input{width:100%!important}@media(max-width:760px){.psi-evidence-head,.psi-evidence-row{grid-template-columns:1fr 1fr}.psi-evidence-head div:first-child,.psi-evidence-row div:first-child{grid-column:span 2}}'+
      '</style>'+
      '<section class="card c12" id="possibilityPanel"><h2>ICARUS Ψ · LATENT PRESSURE <span class="sub">latent pressure · causal leadership · counterfactual price · future-space collapse · interactive research console</span></h2>'+
      '<div class="toolbar"><label class="small muted">Asset <select id="possAsset">'+options+'</select></label><button id="possRefresh">Refresh</button><span class="small muted">Research diagnostics only. Missing evidence stays unavailable; execution_authorized=false.</span></div>'+
      '<div class="empty">loading possibility engine…</div></section>';
  }

  function componentRows(components) {
    return Object.entries(components||{}).map(([name,row]) => {
      const available = !!row.available;
      return '<div class="psi-force"><div><b>'+h(name.replaceAll('_',' '))+'</b><div class="small muted">'+h(row.source||'')+'</div><div class="small muted">'+h(row.detail||'')+'</div></div>'+
        meter(available?row.value:null,true)+
        '<div class="small tnum">'+(available?pct(row.confidence):'OFF')+'</div></div>';
    }).join('');
  }

  function renderPossibility(data, evidenceLedger) {
    const el = document.querySelector('#possibilityPanel');
    if (!el) return;
    const latent = data.latent_pressure_engine || {}, wave = data.information_wave || {}, poss = data.possibility || {}, cf = data.counterfactual || {};
    const phase = data.phase_transition || {}, fc = data.forced_consensus || {}, leaders = data.causal_leadership || {};
    const edge = data.edge_state || {state:'NO_EDGE'}, health = data.data_health || {};
    const lp = latent.latent_pressure;
    const lpClass = lp == null ? 'neutral' : lp > 0 ? 'pos' : lp < 0 ? 'neg' : 'neutral';
    const blockers = (edge.blockers||[]).map(x=>'<li>'+h(x)+'</li>').join('');
    const clusters = (poss.clusters||[]).map(x=>'<tr><td><b>'+h(x.name)+'</b></td><td class="tnum">'+n(x.share*100,1)+'%</td><td class="tnum">'+n(x.weight,2)+'</td></tr>').join('');
    const leaderRows = (leaders.leaders||[]).map((x,i)=>'<tr><td>'+(i+1)+'</td><td><b>'+h(x.asset)+'</b></td><td class="tnum">'+n(x.lag1_correlation,3)+'</td><td class="tnum">'+n(x.directional_pressure,3)+'</td><td class="tnum">'+pct(x.lead_strength)+'</td><td class="tnum">'+pct(x.stability)+'</td><td class="tnum">'+n(x.latest_peer_z,3)+'</td><td class="tnum">'+h(x.samples)+'</td></tr>').join('');
    const shadows = (data.market_shadows||[]).map(x=>'<tr><td><b>'+h(x.removed_force.replaceAll('_',' '))+'</b></td><td class="tnum">'+n(x.force_contribution,4)+'</td><td class="tnum">'+n(x.counterfactual_price,4)+'</td><td class="tnum">'+n(x.distance_from_actual,4)+'</td></tr>').join('');
    const hidden = latent.hidden_state || {};
    const hypotheses = (hidden.hypotheses||[]).map(x=>'<div class="psi-box"><h3>'+h(x.state)+'</h3><div class="psi-hero '+(x.state.includes('BUYER')||x.state.includes('OFFER')?'pos':x.state.includes('SELLER')||x.state.includes('BID')?'neg':'neutral')+'" style="font-size:20px">'+pct(x.strength)+'</div><div class="small muted">'+h((x.evidence||[]).join(' · '))+'</div></div>').join('');
    const mechanisms = (fc.mechanisms||[]).map(x=>'<span class="chip '+(x.sign>0?'b':'r')+'">'+h(x.name)+' '+(x.sign>0?'↑':'↓')+'</span>').join(' ');
    const micro = health.microstructure || {};
    const ledger = health.evidence_ledger || {};
    const history = health.history || {};
    const auth = data.authority || {};

    el.innerHTML =
      '<h2>ICARUS Ψ · LATENT PRESSURE <span class="sub">market possibility engine · '+h(data.asset||'—')+' · '+h(data.generated_at||'')+'</span></h2>'+
      '<div class="toolbar"><label class="small muted">Asset <select id="possAsset"></select></label><button id="possRefresh">Refresh</button>'+
        '<span>'+chip(edge.state)+'</span><span class="small muted">confidence '+pct(edge.confidence)+' · production '+(auth.production_decision_authorized?'ENABLED':'DISABLED')+' · execution '+(auth.execution_authorized?'ENABLED':'DISABLED')+'</span></div>'+
      '<div class="tiles" style="margin-top:0">'+
        '<div class="tile"><div class="k">Latent pressure</div><div class="psi-hero '+lpClass+'">'+(lp==null?'—':(lp>=0?'+':'')+score(latent.latent_pressure_score))+'</div>'+meter(lp,true)+'</div>'+
        '<div class="tile"><div class="k">Evidence coverage</div><div class="v">'+pct(latent.evidence_coverage)+'</div>'+meter(latent.evidence_coverage)+'</div>'+
        '<div class="tile"><div class="k">Future entropy</div><div class="v">'+(poss.future_entropy==null?'—':n(poss.future_entropy,1))+'</div><div class="small muted">0 constrained · 100 diffuse</div></div>'+
        '<div class="tile"><div class="k">Future-space collapse</div><div class="v">'+(poss.future_space_collapse==null?'—':n(poss.future_space_collapse,1))+'</div>'+meter(poss.future_space_collapse==null?null:poss.future_space_collapse/100)+'</div>'+
        '<div class="tile"><div class="k">Effective scenarios</div><div class="v">'+n(poss.effective_scenarios,1)+'</div><div class="small muted">'+pct(poss.effective_sample_ratio)+' of generated mass</div></div>'+
        '<div class="tile"><div class="k">Lattice reliability</div><div class="v">'+pct(poss.reliability)+'</div>'+meter(poss.reliability)+'</div>'+
        '<div class="tile"><div class="k">Endpoint band</div><div class="v">'+(poss.endpoint_return_p50==null?'—':n(poss.endpoint_return_p50*100,2)+'%')+'</div><div class="small muted">P10 '+(poss.endpoint_return_p10==null?'—':n(poss.endpoint_return_p10*100,2)+'%')+' · P90 '+(poss.endpoint_return_p90==null?'—':n(poss.endpoint_return_p90*100,2)+'%')+'</div></div>'+
        '<div class="tile"><div class="k">Synthetic price</div><div class="v tnum">'+n(cf.synthetic_price,4)+'</div><div class="small muted">actual '+n(data.price,4)+' · gap '+n(cf.dislocation,4)+'</div></div>'+
        '<div class="tile"><div class="k">Unexplained residual</div><div class="v tnum">'+(cf.unexplained_dislocation_available?n(cf.unexplained_dislocation,4):'UNIDENTIFIED')+'</div><div class="small muted">not independently identifiable from the same force snapshot</div></div>'+
        '<div class="tile"><div class="k">Phase boundary</div><div class="v tnum">'+n(phase.phase_boundary,4)+'</div><div class="small muted">'+h(phase.direction||'—')+' · horizon '+n(phase.event_horizon,4)+'</div></div>'+
        '<div class="tile"><div class="k">Forced consensus</div><div class="v">'+(fc.active?'ACTIVE':'INACTIVE')+'</div><div class="small muted">'+h(fc.direction||'—')+' · alignment '+pct(fc.alignment)+'</div></div>'+
        '<div class="tile"><div class="k">Information wave</div><div class="v">'+h(wave.status||'WARMING')+'</div><div class="small muted">novelty '+(wave.score==null?'—':n(wave.score,1))+' · '+h(wave.direction||'—')+' · '+(wave.causal_leading?'POST-BAR CAUSAL WINDOW':'NOT CAUSALLY ORDERED')+' · source unidentified</div></div>'+
      '</div>'+
      '<div class="psi-grid" style="margin-top:12px">'+
        '<div class="psi-box"><h3>Edge gate</h3><div class="psi-hero '+(String(edge.state).includes('LONG')?'pos':String(edge.state).includes('SHORT')?'neg':'neutral')+'" style="font-size:24px">'+h(edge.state||'NO_EDGE')+'</div>'+
          (blockers?'<ul class="small muted" style="padding-left:18px;margin:8px 0 0">'+blockers+'</ul>':'<div class="small pos">All research gates currently satisfied.</div>')+'</div>'+
        '<div class="psi-box"><h3>Pressure / price elasticity</h3><div class="psi-hero '+(String((latent.pressure_price_elasticity||{}).state).includes('BUYER')||String((latent.pressure_price_elasticity||{}).state).includes('OFFER')?'pos':String((latent.pressure_price_elasticity||{}).state).includes('SELLER')||String((latent.pressure_price_elasticity||{}).state).includes('BID')?'neg':'neutral')+'" style="font-size:21px">'+h((latent.pressure_price_elasticity||{}).state||'UNAVAILABLE')+'</div>'+
          '<div class="small muted">elasticity '+n((latent.pressure_price_elasticity||{}).value,8)+' · flow '+n((latent.pressure_price_elasticity||{}).flow_imbalance,3)+' · displacement '+n((latent.pressure_price_elasticity||{}).price_displacement,6)+' · '+h((latent.pressure_price_elasticity||{}).normalization||'—')+' · response z '+n((latent.pressure_price_elasticity||{}).response_z,2)+'</div></div>'+
        '<div class="psi-box"><h3>Inverse hidden-state inference</h3><div class="psi-hero neutral" style="font-size:21px">'+h(hidden.primary||'UNRESOLVED')+'</div><div class="small muted">Ranked explanation hypotheses; not participant-identity claims.</div></div>'+
        '<div class="psi-box"><h3>Evidence health</h3><div class="psi-kv"><div>History observations</div><div class="tnum">'+h(health.market_history_observations||0)+'</div><div>History source</div><div>'+h(history.source||'—')+'</div><div>Chart cadence</div><div class="tnum">'+(history.chart_minutes==null?'—':h(history.chart_minutes)+'m')+'</div><div>Price basis</div><div>'+h(history.price_basis||'—')+'</div><div>Gap returns skipped</div><div class="tnum">'+h(history.gap_returns_skipped||0)+'</div><div>Poll independent</div><div>'+chip(history.poll_independent?'YES':'NO')+'</div><div>Leader alignment</div><div>'+chip(history.timestamp_aligned_leaders?'EXACT':'FALLBACK')+'</div><div>Tick tape</div><div>'+chip(micro.ticks?'OBSERVED':'UNAVAILABLE')+'</div><div>Order-book depth</div><div>'+chip(micro.depth?'OBSERVED':'UNAVAILABLE')+'</div><div>Provider</div><div>'+h(micro.provider||'—')+'</div><div>Depth age</div><div class="tnum">'+(micro.depth_age_seconds==null?'—':n(micro.depth_age_seconds,2)+'s')+'</div><div>Evidence ledger</div><div>'+chip(ledger.durable?'DURABLE':'MEMORY')+'</div><div>Ledger integrity</div><div>'+chip(ledger.storage_integrity_ok?'VERIFIED':'FAILED')+'</div><div>Invalid receipts</div><div class="tnum">'+h(ledger.invalid_receipt_count||0)+'</div><div>Ledger digest</div><div class="tnum">'+h((ledger.ledger_digest_sha256||'—').slice(0,12))+'</div><div>Source conflicts</div><div>'+chip((ledger.conflicting_feature_count||0)>0?'CONFLICT':'CLEAR')+' '+h(ledger.conflicting_feature_count||0)+'</div><div>Active evidence</div><div class="tnum">'+h(ledger.active_count||0)+'</div><div>Evidence history</div><div class="tnum">'+h(ledger.total_history_count||0)+'</div></div></div>'+
      '</div>'+
      evidenceConsoleHtml()+
      '<section class="card c12" style="margin-top:12px"><h2>Latent force decomposition</h2>'+componentRows(latent.components||{})+'</section>'+
      '<div class="psi-grid" style="margin-top:12px">'+(hypotheses || '<div class="psi-box"><h3>Hidden state</h3><div class="small muted">No sufficiently strong hidden-state hypothesis yet.</div></div>')+'</div>'+
      '<section class="card c12" style="margin-top:12px"><h2>Future-space clusters <span class="sub">'+h(poss.viable_futures||0)+' viable / '+h(poss.scenarios_generated||0)+' generated · dominant '+h(poss.dominant_cluster||'—')+'</span></h2>'+
        '<div class="scroll"><table><thead><tr><th>Cluster</th><th>Share</th><th>Weight</th></tr></thead><tbody>'+(clusters||'<tr><td colspan="3" class="empty">scenario engine warming</td></tr>')+'</tbody></table></div>'+
        '<div class="small muted" style="margin-top:8px">'+h(poss.model_note||'')+'</div></section>'+
      '<section class="card c12" style="margin-top:12px"><h2>Dynamic causal leadership <span class="sub">lagged association · '+h(leaders.alignment_mode||'warming')+' · '+(leaders.chart_minutes==null?'cadence —':h(leaders.chart_minutes)+'m')+' · not proof of structural causality</span></h2>'+
        '<div class="scroll"><table><thead><tr><th>#</th><th>Leader</th><th>Lag-1 corr</th><th>Pressure</th><th>Lead strength</th><th>Stability</th><th>Peer z</th><th>Samples</th></tr></thead><tbody>'+(leaderRows||'<tr><td colspan="8" class="empty">leader graph warming</td></tr>')+'</tbody></table></div></section>'+
      '<section class="card c12" style="margin-top:12px"><h2>Forced consensus</h2><div>'+mechanisms+'</div><div class="small muted" style="margin-top:8px">Active only when at least three observed mechanisms align strongly enough.</div></section>'+
      '<section class="card c12" style="margin-top:12px"><h2>Market shadows <span class="sub">counterfactual removal of one observed force at a time</span></h2>'+
        '<div class="scroll"><table><thead><tr><th>Removed force</th><th>Contribution</th><th>Counterfactual price</th><th>Distance from actual</th></tr></thead><tbody>'+(shadows||'<tr><td colspan="4" class="empty">counterfactual force attribution unavailable</td></tr>')+'</tbody></table></div></section>'+
      '<div class="small muted" style="margin-top:12px"><b>Truth contract:</b> scenario shares are not calibrated probabilities; dynamic leader scores do not prove causality; missing evidence is never imputed; the engine has no broker or production-decision authority.</div>';

    const sel = el.querySelector('#possAsset');
    sel.innerHTML = assetNames.map(x=>'<option value="'+h(x)+'" '+(x===data.asset?'selected':'')+'>'+h(x)+'</option>').join('');
    selected = data.asset || selected;
    sel.onchange = () => { selected = sel.value; loadPossibility(); };
    el.querySelector('#possRefresh').onclick = loadPossibility;
    const ledgerEl = el.querySelector('#psiEvidenceLedger');
    if (ledgerEl) ledgerEl.innerHTML = evidenceLedgerHtml(evidenceLedger);
    wireEvidenceControls();
  }

  function wireEvidenceControls() {
    const source = document.querySelector('#psiEvidenceSource');
    if (source) source.oninput = () => { evidenceDraft.source = source.value; };
    const ttl = document.querySelector('#psiEvidenceTtl');
    if (ttl) ttl.oninput = () => { evidenceDraft.ttl_seconds = ttl.value; };
    evidenceFeatures.forEach(([key]) => {
      const value = document.querySelector('[data-psi-value="'+key+'"]');
      const confidence = document.querySelector('[data-psi-confidence="'+key+'"]');
      if (value) value.oninput = () => { evidenceDraft.values[key] = evidenceDraft.values[key] || {}; evidenceDraft.values[key].value = value.value; };
      if (confidence) confidence.oninput = () => { evidenceDraft.values[key] = evidenceDraft.values[key] || {}; evidenceDraft.values[key].confidence = confidence.value; };
    });
    const expired = document.querySelector('#psiIncludeExpired');
    if (expired) expired.onchange = () => { ledgerIncludeExpired = !!expired.checked; loadPossibility(); };
    const submit = document.querySelector('#psiEvidenceSubmit');
    if (submit) submit.onclick = submitEvidence;
    const clear = document.querySelector('#psiEvidenceClear');
    if (clear) clear.onclick = () => { evidenceDraft.values = {}; lastEvidenceMessage = ''; lastEvidenceKind = ''; loadPossibility(); };
    const refresh = document.querySelector('#psiEvidenceRefresh');
    if (refresh) refresh.onclick = loadPossibility;
  }

  async function submitEvidence() {
    const button = document.querySelector('#psiEvidenceSubmit');
    if (button) button.disabled = true;
    try {
      const values = {};
      evidenceFeatures.forEach(([key]) => {
        const valueEl = document.querySelector('[data-psi-value="'+key+'"]');
        const confEl = document.querySelector('[data-psi-confidence="'+key+'"]');
        const raw = valueEl ? valueEl.value.trim() : '';
        if (raw === '') return;
        const value = Number(raw);
        const confidence = Number(confEl && confEl.value !== '' ? confEl.value : 1);
        if (!Number.isFinite(value) || value < -1 || value > 1) throw new Error(key+' value must be within [-1,1]');
        if (!Number.isFinite(confidence) || confidence < 0 || confidence > 1) throw new Error(key+' confidence must be within [0,1]');
        values[key] = {value, confidence};
      });
      if (!Object.keys(values).length) throw new Error('Enter at least one force value before submitting.');
      const sourceEl = document.querySelector('#psiEvidenceSource');
      const ttlEl = document.querySelector('#psiEvidenceTtl');
      const source = String(sourceEl ? sourceEl.value : evidenceDraft.source).trim();
      const ttl = Number(ttlEl ? ttlEl.value : evidenceDraft.ttl_seconds);
      if (!source) throw new Error('Evidence source is required.');
      if (!Number.isFinite(ttl) || ttl <= 0 || ttl > 86400) throw new Error('TTL must be within 1..86400 seconds.');
      evidenceDraft.source = source;
      evidenceDraft.ttl_seconds = ttl;
      const token = localStorage.getItem('icarus-engine-token') || 'icarus';
      const response = await fetch('/admin/possibility/evidence', {
        method:'POST', cache:'no-store', headers:{'Content-Type':'application/json','Authorization':'Bearer '+token},
        body:JSON.stringify({asset:selected, values, source, ttl_seconds:ttl}),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || data.error || ('HTTP '+response.status));
      lastEvidenceKind = 'ok';
      lastEvidenceMessage = 'Stored '+String(data.inserted ?? Object.keys(values).length)+' new receipt(s); '+String(data.idempotent_duplicates||0)+' idempotent duplicate(s).';
      evidenceDraft.values = {};
      await loadPossibility();
    } catch (err) {
      lastEvidenceKind = 'error';
      lastEvidenceMessage = String(err && err.message ? err.message : err);
      const message = document.querySelector('#psiEvidenceMessage');
      if (message) { message.className = 'small neg'; message.textContent = lastEvidenceMessage; }
    } finally {
      if (button) button.disabled = false;
    }
  }

  async function loadPossibility() {
    if (loading) { pendingLoad = true; return; }
    const panel = document.querySelector('#possibilityPanel');
    if (!panel) return;
    const requestAsset = selected;
    loading = true;
    pendingLoad = false;
    try {
      const token = localStorage.getItem('icarus-engine-token') || 'icarus';
      const query = selected ? '?asset='+encodeURIComponent(selected) : '';
      const ledgerQuery = '?asset='+encodeURIComponent(selected||'')+'&limit=100&include_expired='+(ledgerIncludeExpired?'true':'false');
      const [response, ledgerResponse] = await Promise.all([
        fetch('/api/possibility'+query,{cache:'no-store',headers:{'Authorization':'Bearer '+token}}),
        fetch('/api/possibility/evidence'+ledgerQuery,{cache:'no-store',headers:{'Authorization':'Bearer '+token}}),
      ]);
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || data.error || ('HTTP '+response.status));
      let ledger;
      try {
        ledger = await ledgerResponse.json();
        if (!ledgerResponse.ok) ledger = {error:ledger.detail || ledger.error || ('HTTP '+ledgerResponse.status)};
      } catch (e) { ledger = {error:String(e && e.message ? e.message : e)}; }
      if (requestAsset !== selected) { pendingLoad = true; return; }
      renderPossibility(data, ledger);
    } catch (err) {
      if (requestAsset === selected) panel.innerHTML = '<h2>ICARUS Ψ · LATENT PRESSURE</h2><div class="empty">possibility engine unavailable: '+h(err.message||err)+'</div>';
    } finally {
      loading = false;
      if (pendingLoad && (location.hash || '#overview').slice(1) === 'possibility') { pendingLoad = false; setTimeout(loadPossibility, 0); }
    }
  }

  function wirePossibility() {
    const sel = document.querySelector('#possAsset');
    if (sel) {
      selected = sel.value || selected;
      sel.onchange = () => { selected = sel.value; loadPossibility(); };
    }
    const btn = document.querySelector('#possRefresh');
    if (btn) btn.onclick = loadPossibility;
    loadPossibility();
    if (timer) clearInterval(timer);
    timer = setInterval(() => {
      if ((location.hash || '#overview').slice(1) !== 'possibility') return;
      const active = document.activeElement;
      if (active && active.closest && active.closest('#possibilityPanel') && /^(INPUT|SELECT)$/.test(active.tagName)) return;
      loadPossibility();
    }, 2500);
  }

  async function fetchQuickPossibility(asset, force=false) {
    const symbol = String(asset || '').trim().toUpperCase();
    if (!symbol) throw new Error('asset is required');
    const cached = quickCache.get(symbol);
    if (!force && cached && Date.now() - cached.at < QUICK_TTL_MS) return cached.data;
    if (quickInflight.has(symbol)) return quickInflight.get(symbol);
    const token = localStorage.getItem('icarus-engine-token') || 'icarus';
    const task = (async () => {
      const response = await fetch('/api/possibility?asset='+encodeURIComponent(symbol), {cache:'no-store', headers:{'Authorization':'Bearer '+token}});
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || data.error || ('HTTP '+response.status));
      quickCache.set(symbol, {at:Date.now(), data});
      return data;
    })();
    quickInflight.set(symbol, task);
    try { return await task; } finally { quickInflight.delete(symbol); }
  }

  function quickPossibilityBody(data) {
    const latent = data.latent_pressure_engine || {}, poss = data.possibility || {}, phase = data.phase_transition || {};
    const edge = data.edge_state || {state:'NO_EDGE'}, health = data.data_health || {}, hist = health.history || {}, micro = health.microstructure || {}, ledger = health.evidence_ledger || {};
    const lp = latent.latent_pressure;
    const lpText = lp == null ? '—' : (lp >= 0 ? '+' : '') + score(latent.latent_pressure_score);
    const blockers = (edge.blockers || []).slice(0,3).map(x=>h(x)).join(' · ');
    return '<div class="tiles" style="margin-top:0">'+
      '<div class="tile"><div class="k">Ψ edge gate</div><div class="v">'+chip(edge.state)+'</div><div class="small muted">confidence '+pct(edge.confidence)+'</div></div>'+
      '<div class="tile"><div class="k">Latent pressure</div><div class="v tnum '+(lp==null?'':lp>0?'pos':lp<0?'neg':'')+'">'+lpText+'</div><div class="small muted">coverage '+pct(latent.evidence_coverage)+'</div></div>'+
      '<div class="tile"><div class="k">Future collapse</div><div class="v tnum">'+(poss.future_space_collapse==null?'—':n(poss.future_space_collapse,1))+'</div><div class="small muted">reliability '+pct(poss.reliability)+'</div></div>'+
      '<div class="tile"><div class="k">Phase</div><div class="v">'+h(phase.direction||'—')+'</div><div class="small muted">boundary '+n(phase.phase_boundary,4)+'</div></div>'+
      '<div class="tile"><div class="k">Leader alignment</div><div class="v">'+h(hist.timestamp_aligned_leaders?'EXACT':(hist.source?'FALLBACK':'—'))+'</div><div class="small muted">'+h(hist.chart_minutes==null?'cadence —':hist.chart_minutes+'m · '+(hist.source||'unknown'))+'</div></div>'+
      '<div class="tile"><div class="k">Microstructure</div><div class="v">'+h(micro.provider||'—')+'</div><div class="small muted">ticks '+(micro.ticks?'yes':'no')+' · depth '+(micro.depth?'yes':'no')+'</div></div>'+
      '<div class="tile"><div class="k">Evidence ledger</div><div class="v">'+(ledger.storage_integrity_ok===false?'FAILED':ledger.durable?'VERIFIED':'MEMORY')+'</div><div class="small muted">active '+h(ledger.active_count||0)+' · history '+h(ledger.total_history_count||0)+'</div></div>'+
    '</div>'+
    (blockers?'<div class="small muted" style="margin-top:8px"><b>Current blockers:</b> '+blockers+'</div>':'<div class="small pos" style="margin-top:8px">All Ψ research gates currently satisfied.</div>')+
    '<div class="small muted" style="margin-top:6px">Research diagnostics only · execution_authorized=false · production_decision_authorized=false</div>';
  }

  function openPossibilityConsole(asset) {
    selected = String(asset || selected || '').trim().toUpperCase();
    if (typeof window.setView === 'function') window.setView('possibility');
    else location.hash = 'possibility';
  }

  function possibilityQuickOverviewHtml(A) {
    const assets = (A||[]).map(a=>String(a.symbol||'')).filter(Boolean);
    const current = selected && assets.includes(selected) ? selected : (assets.includes('NQ') ? 'NQ' : (assets[0] || ''));
    if (current) selected = current;
    const options = assets.map(x=>'<option value="'+h(x)+'" '+(x===current?'selected':'')+'>'+h(x)+'</option>').join('');
    return '<section class="card c12" id="psiOverviewCard"><h2>ICARUS Ψ · LIVE RESEARCH MONITOR <span class="sub">embedded in the trading overview</span></h2>'+
      '<div class="toolbar"><label class="small muted">Asset <select id="psiQuickOverviewAsset">'+options+'</select></label><button id="psiQuickOverviewRefresh">Refresh Ψ</button><button class="primary" id="psiQuickOverviewOpen">Open full Ψ console</button><span class="small muted">read-only monitor; evidence editing remains in the full console</span></div>'+
      '<div id="psiQuickOverviewBody" class="empty">loading ICARUS Ψ…</div></section>';
  }

  async function loadPossibilityQuickOverview(force=false) {
    const body = document.querySelector('#psiQuickOverviewBody');
    const sel = document.querySelector('#psiQuickOverviewAsset');
    if (!body || !sel || !sel.value) return;
    const asset = sel.value;
    try { body.innerHTML = quickPossibilityBody(await fetchQuickPossibility(asset, force)); }
    catch (err) { body.innerHTML = '<div class="empty">ICARUS Ψ unavailable: '+h(err.message||err)+'</div>'; }
  }

  function wirePossibilityQuickOverview(A) {
    const sel = document.querySelector('#psiQuickOverviewAsset');
    if (!sel) return;
    const assets = (A||[]).map(a=>String(a.symbol||'')).filter(Boolean);
    const preferred = assets.includes(sel.value) ? sel.value : (assets.includes(selected) ? selected : (assets.includes('NQ') ? 'NQ' : (assets[0] || '')));
    const existing = Array.from(sel.options).map(x=>x.value);
    if (existing.join('|') !== assets.join('|')) {
      sel.innerHTML = assets.map(x=>'<option value="'+h(x)+'" '+(x===preferred?'selected':'')+'>'+h(x)+'</option>').join('');
    } else if (preferred && sel.value !== preferred) {
      sel.value = preferred;
    }
    if (preferred) selected = preferred;
    sel.onchange = () => { selected = sel.value; loadPossibilityQuickOverview(true); };
    const refresh = document.querySelector('#psiQuickOverviewRefresh');
    if (refresh) refresh.onclick = () => loadPossibilityQuickOverview(true);
    const open = document.querySelector('#psiQuickOverviewOpen');
    if (open) open.onclick = () => openPossibilityConsole(sel.value);
    loadPossibilityQuickOverview(false);
  }

  function possibilityQuickAssetHtml(a) {
    const symbol = String((a&&a.symbol)||'').toUpperCase();
    return '<section class="card c12" id="psiAssetDock" data-psi-asset="'+h(symbol)+'"><h2>ICARUS Ψ · '+h(symbol)+' <span class="sub">research state beside the live asset workflow</span></h2>'+
      '<div class="toolbar"><button id="psiAssetRefresh">Refresh Ψ</button><button class="primary" id="psiAssetOpen">Open full Ψ console</button><span class="small muted">no broker authority; does not alter strategy execution</span></div>'+
      '<div id="psiAssetBody" class="empty">loading ICARUS Ψ…</div></section>';
  }

  async function loadPossibilityQuickAsset(asset, force=false) {
    const body = document.querySelector('#psiAssetBody');
    if (!body) return;
    try { body.innerHTML = quickPossibilityBody(await fetchQuickPossibility(asset, force)); }
    catch (err) { body.innerHTML = '<div class="empty">ICARUS Ψ unavailable: '+h(err.message||err)+'</div>'; }
  }

  function wirePossibilityQuickAsset(asset) {
    const symbol = String(asset||'').toUpperCase();
    const refresh = document.querySelector('#psiAssetRefresh');
    if (refresh) refresh.onclick = () => loadPossibilityQuickAsset(symbol, true);
    const open = document.querySelector('#psiAssetOpen');
    if (open) open.onclick = () => openPossibilityConsole(symbol);
    loadPossibilityQuickAsset(symbol, false);
  }

  window.possibilityHtml = possibilityHtml;
  window.wirePossibility = wirePossibility;
  window.loadPossibility = loadPossibility;
  window.possibilityQuickOverviewHtml = possibilityQuickOverviewHtml;
  window.wirePossibilityQuickOverview = wirePossibilityQuickOverview;
  window.loadPossibilityQuickOverview = loadPossibilityQuickOverview;
  window.possibilityQuickAssetHtml = possibilityQuickAssetHtml;
  window.wirePossibilityQuickAsset = wirePossibilityQuickAsset;
  window.loadPossibilityQuickAsset = loadPossibilityQuickAsset;
  window.openPossibilityConsole = openPossibilityConsole;
})();

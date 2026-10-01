/* ICARUS Ψ latent-pressure + possibility panel. Research-only; never authorizes execution. */
(() => {
  let timer = null;
  let loading = false;
  let selected = '';
  let assetNames = [];

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

  function possibilityHtml(A) {
    const assets = (A||[]).map(a=>String(a.symbol||'')).filter(Boolean);
    assetNames = assets.slice();
    if (!selected || !assets.includes(selected)) selected = assets.includes('NQ') ? 'NQ' : (assets[0] || '');
    const options = assets.map(x=>'<option value="'+h(x)+'" '+(x===selected?'selected':'')+'>'+h(x)+'</option>').join('');
    return '<style>'+
      '.psi-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:10px}.psi-box{border:1px solid var(--ring);background:var(--surface-2);border-radius:12px;padding:11px}.psi-box h3{font-size:11px;text-transform:uppercase;letter-spacing:.09em;color:var(--muted);margin:0 0 7px}.psi-meter{height:24px;border:1px solid var(--ring);border-radius:7px;position:relative;overflow:hidden;background:var(--surface);margin-top:5px}.psi-meter:before{content:"";position:absolute;left:50%;top:0;bottom:0;width:1px;background:var(--ring)}.psi-meter i{position:absolute;top:0;bottom:0;background:var(--s1);opacity:.7}.psi-meter i.posbar{background:var(--good)}.psi-meter i.negbar{background:var(--crit)}.psi-meter span{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:600}.psi-kv{display:grid;grid-template-columns:minmax(120px,1fr) minmax(90px,auto);gap:6px 12px;font-size:12px}.psi-kv div:nth-child(odd){color:var(--muted)}.psi-force{display:grid;grid-template-columns:minmax(145px,1fr) 1fr 72px;gap:8px;align-items:center;padding:6px 0;border-bottom:1px solid var(--grid);font-size:12px}.psi-force:last-child{border-bottom:0}.psi-hero{font-size:34px;font-weight:700;letter-spacing:-.03em}.psi-hero.pos{color:var(--good)}.psi-hero.neg{color:var(--crit)}.psi-hero.neutral{color:var(--warn)}'+
      '</style>'+
      '<section class="card c12" id="possibilityPanel"><h2>ICARUS Ψ · LATENT PRESSURE <span class="sub">latent pressure · causal leadership · counterfactual price · future-space collapse · read only</span></h2>'+
      '<div class="toolbar"><label class="small muted">Asset <select id="possAsset">'+options+'</select></label><button id="possRefresh">Refresh</button><span class="small muted">Research diagnostics only. Missing evidence stays unavailable; execution_authorized=false.</span></div>'+
      '<div class="empty">loading possibility engine…</div></section>';
  }

  function componentRows(components) {
    return Object.entries(components||{}).map(([name,row]) => {
      const available = !!row.available;
      return '<div class="psi-force"><div><b>'+h(name.replaceAll('_',' '))+'</b><div class="small muted">'+h(row.source||'')+'</div></div>'+
        meter(available?row.value:null,true)+
        '<div class="small tnum">'+(available?pct(row.confidence):'OFF')+'</div></div>';
    }).join('');
  }

  function renderPossibility(data) {
    const el = document.querySelector('#possibilityPanel');
    if (!el) return;
    const latent = data.latent_pressure_engine || {}, wave = data.information_wave || {}, poss = data.possibility || {}, cf = data.counterfactual || {};
    const phase = data.phase_transition || {}, fc = data.forced_consensus || {}, leaders = data.causal_leadership || {};
    const edge = data.edge_state || {state:'NO_EDGE'}, health = data.data_health || {};
    const lp = latent.latent_pressure;
    const lpClass = lp == null ? 'neutral' : lp > 0 ? 'pos' : lp < 0 ? 'neg' : 'neutral';
    const blockers = (edge.blockers||[]).map(x=>'<li>'+h(x)+'</li>').join('');
    const clusters = (poss.clusters||[]).map(x=>'<tr><td><b>'+h(x.name)+'</b></td><td class="tnum">'+n(x.share*100,1)+'%</td><td class="tnum">'+n(x.weight,2)+'</td></tr>').join('');
    const leaderRows = (leaders.leaders||[]).map((x,i)=>'<tr><td>'+(i+1)+'</td><td><b>'+h(x.asset)+'</b></td><td class="tnum">'+n(x.lag1_correlation,3)+'</td><td class="tnum">'+n(x.directional_pressure,3)+'</td><td class="tnum">'+pct(x.lead_strength)+'</td><td class="tnum">'+h(x.samples)+'</td></tr>').join('');
    const shadows = (data.market_shadows||[]).map(x=>'<tr><td><b>'+h(x.removed_force.replaceAll('_',' '))+'</b></td><td class="tnum">'+n(x.force_contribution,4)+'</td><td class="tnum">'+n(x.counterfactual_price,4)+'</td><td class="tnum">'+n(x.distance_from_actual,4)+'</td></tr>').join('');
    const hidden = latent.hidden_state || {};
    const hypotheses = (hidden.hypotheses||[]).map(x=>'<div class="psi-box"><h3>'+h(x.state)+'</h3><div class="psi-hero '+(x.state.includes('BUYER')||x.state.includes('OFFER')?'pos':x.state.includes('SELLER')||x.state.includes('BID')?'neg':'neutral')+'" style="font-size:20px">'+pct(x.strength)+'</div><div class="small muted">'+h((x.evidence||[]).join(' · '))+'</div></div>').join('');
    const mechanisms = (fc.mechanisms||[]).map(x=>'<span class="chip '+(x.sign>0?'b':'r')+'">'+h(x.name)+' '+(x.sign>0?'↑':'↓')+'</span>').join(' ');
    const micro = health.microstructure || {};
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
        '<div class="tile"><div class="k">Synthetic price</div><div class="v tnum">'+n(cf.synthetic_price,4)+'</div><div class="small muted">actual '+n(data.price,4)+' · gap '+n(cf.dislocation,4)+'</div></div>'+
        '<div class="tile"><div class="k">Unexplained gap</div><div class="v tnum">'+n(cf.unexplained_dislocation,4)+'</div><div class="small muted">after known force attribution</div></div>'+
        '<div class="tile"><div class="k">Phase boundary</div><div class="v tnum">'+n(phase.phase_boundary,4)+'</div><div class="small muted">'+h(phase.direction||'—')+' · horizon '+n(phase.event_horizon,4)+'</div></div>'+
        '<div class="tile"><div class="k">Forced consensus</div><div class="v">'+(fc.active?'ACTIVE':'INACTIVE')+'</div><div class="small muted">'+h(fc.direction||'—')+' · alignment '+pct(fc.alignment)+'</div></div>'+
        '<div class="tile"><div class="k">Information wave</div><div class="v">'+h(wave.status||'WARMING')+'</div><div class="small muted">novelty '+(wave.score==null?'—':n(wave.score,1))+' · '+h(wave.direction||'—')+' · source unidentified</div></div>'+
      '</div>'+
      '<div class="psi-grid" style="margin-top:12px">'+
        '<div class="psi-box"><h3>Edge gate</h3><div class="psi-hero '+(String(edge.state).includes('LONG')?'pos':String(edge.state).includes('SHORT')?'neg':'neutral')+'" style="font-size:24px">'+h(edge.state||'NO_EDGE')+'</div>'+
          (blockers?'<ul class="small muted" style="padding-left:18px;margin:8px 0 0">'+blockers+'</ul>':'<div class="small pos">All research gates currently satisfied.</div>')+'</div>'+
        '<div class="psi-box"><h3>Pressure / price elasticity</h3><div class="psi-hero '+(String((latent.pressure_price_elasticity||{}).state).includes('BUYER')||String((latent.pressure_price_elasticity||{}).state).includes('OFFER')?'pos':String((latent.pressure_price_elasticity||{}).state).includes('SELLER')||String((latent.pressure_price_elasticity||{}).state).includes('BID')?'neg':'neutral')+'" style="font-size:21px">'+h((latent.pressure_price_elasticity||{}).state||'UNAVAILABLE')+'</div>'+
          '<div class="small muted">elasticity '+n((latent.pressure_price_elasticity||{}).value,8)+' · flow '+n((latent.pressure_price_elasticity||{}).flow_imbalance,3)+' · displacement '+n((latent.pressure_price_elasticity||{}).price_displacement,6)+'</div></div>'+
        '<div class="psi-box"><h3>Inverse hidden-state inference</h3><div class="psi-hero neutral" style="font-size:21px">'+h(hidden.primary||'UNRESOLVED')+'</div><div class="small muted">Ranked explanation hypotheses; not participant-identity claims.</div></div>'+
        '<div class="psi-box"><h3>Evidence health</h3><div class="psi-kv"><div>History observations</div><div class="tnum">'+h(health.market_history_observations||0)+'</div><div>Tick tape</div><div>'+chip(micro.ticks?'OBSERVED':'UNAVAILABLE')+'</div><div>Order-book depth</div><div>'+chip(micro.depth?'OBSERVED':'UNAVAILABLE')+'</div><div>Provider</div><div>'+h(micro.provider||'—')+'</div></div></div>'+
      '</div>'+
      '<section class="card c12" style="margin-top:12px"><h2>Latent force decomposition</h2>'+componentRows(latent.components||{})+'</section>'+
      '<div class="psi-grid" style="margin-top:12px">'+(hypotheses || '<div class="psi-box"><h3>Hidden state</h3><div class="small muted">No sufficiently strong hidden-state hypothesis yet.</div></div>')+'</div>'+
      '<section class="card c12" style="margin-top:12px"><h2>Future-space clusters <span class="sub">'+h(poss.viable_futures||0)+' viable / '+h(poss.scenarios_generated||0)+' generated · dominant '+h(poss.dominant_cluster||'—')+'</span></h2>'+
        '<div class="scroll"><table><thead><tr><th>Cluster</th><th>Share</th><th>Weight</th></tr></thead><tbody>'+(clusters||'<tr><td colspan="3" class="empty">scenario engine warming</td></tr>')+'</tbody></table></div>'+
        '<div class="small muted" style="margin-top:8px">'+h(poss.model_note||'')+'</div></section>'+
      '<section class="card c12" style="margin-top:12px"><h2>Dynamic causal leadership <span class="sub">lagged association, not proof of structural causality</span></h2>'+
        '<div class="scroll"><table><thead><tr><th>#</th><th>Leader</th><th>Lag-1 corr</th><th>Pressure</th><th>Lead strength</th><th>Samples</th></tr></thead><tbody>'+(leaderRows||'<tr><td colspan="6" class="empty">leader graph warming</td></tr>')+'</tbody></table></div></section>'+
      '<section class="card c12" style="margin-top:12px"><h2>Forced consensus</h2><div>'+mechanisms+'</div><div class="small muted" style="margin-top:8px">Active only when at least three observed mechanisms align strongly enough.</div></section>'+
      '<section class="card c12" style="margin-top:12px"><h2>Market shadows <span class="sub">counterfactual removal of one observed force at a time</span></h2>'+
        '<div class="scroll"><table><thead><tr><th>Removed force</th><th>Contribution</th><th>Counterfactual price</th><th>Distance from actual</th></tr></thead><tbody>'+(shadows||'<tr><td colspan="4" class="empty">counterfactual force attribution unavailable</td></tr>')+'</tbody></table></div></section>'+
      '<div class="small muted" style="margin-top:12px"><b>Truth contract:</b> scenario shares are not calibrated probabilities; dynamic leader scores do not prove causality; missing evidence is never imputed; the engine has no broker or production-decision authority.</div>';

    const sel = el.querySelector('#possAsset');
    sel.innerHTML = assetNames.map(x=>'<option value="'+h(x)+'" '+(x===data.asset?'selected':'')+'>'+h(x)+'</option>').join('');
    selected = data.asset || selected;
    sel.onchange = () => { selected = sel.value; loadPossibility(); };
    el.querySelector('#possRefresh').onclick = loadPossibility;
  }

  async function loadPossibility() {
    if (loading) return;
    const panel = document.querySelector('#possibilityPanel');
    if (!panel) return;
    loading = true;
    try {
      const token = localStorage.getItem('icarus-engine-token') || 'icarus';
      const query = selected ? '?asset='+encodeURIComponent(selected) : '';
      const response = await fetch('/api/possibility'+query,{cache:'no-store',headers:{'Authorization':'Bearer '+token}});
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || data.error || ('HTTP '+response.status));
      renderPossibility(data);
    } catch (err) {
      panel.innerHTML = '<h2>ICARUS Ψ · LATENT PRESSURE</h2><div class="empty">possibility engine unavailable: '+h(err.message||err)+'</div>';
    } finally {
      loading = false;
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
      if ((location.hash || '#overview').slice(1) === 'possibility') loadPossibility();
    }, 2500);
  }

  window.possibilityHtml = possibilityHtml;
  window.wirePossibility = wirePossibility;
  window.loadPossibility = loadPossibility;
})();

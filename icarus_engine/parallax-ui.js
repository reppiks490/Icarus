(() => {
  let timer = null;
  const h = value => String(value ?? '').replace(/[&<>"]/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[ch]));
  const num = (v, d=3) => (typeof v === 'number' && Number.isFinite(v)) ? v.toFixed(d) : '—';
  const cls = value => {
    const s = String(value || '').toUpperCase();
    if (s.includes('QUALIFIED') || s.includes('VALIDATED') || s === 'GREEN') return 'b';
    if (s.includes('REJECT') || s.includes('RETIRED') || s.includes('ERROR') || s.includes('BLOCK')) return 'r';
    return 'w';
  };

  function parallaxHtml() {
    return '<section class="card c12" id="parallaxPanel"><h2>PARALLAX / DREAMSTATE <span class="sub">counterfactual twins · regret · ablation · policy incubation · shadow only</span></h2><div class="empty">loading counterfactual research state…</div></section>';
  }

  function attributionRows(rows) {
    return (rows || []).slice(0, 24).map(r => '<tr>' +
      '<td><b>'+h(String(r.subsystem || '').toUpperCase())+'</b></td>' +
      '<td class="tnum">'+h(r.n ?? 0)+'</td>' +
      '<td class="tnum">'+num(r.mean_delta)+'</td>' +
      '<td class="tnum">'+num(r.ci95_low)+' → '+num(r.ci95_high)+'</td>' +
      '</tr>').join('');
  }

  function signalRows(rows) {
    return (rows || []).slice(0, 30).map(r => '<tr>' +
      '<td><b>'+h(r.asset || '')+'</b></td><td>'+h(r.regime || '')+'</td>' +
      '<td><span class="chip">'+h(r.branch_label || '')+'</span></td>' +
      '<td class="tnum">'+h(r.n ?? 0)+'</td><td class="tnum">'+num(r.mean_delta)+'</td>' +
      '<td class="tnum">'+num(r.ci95_low)+'</td></tr>').join('');
  }

  function candidateRows(rows, gates) {
    return (rows || []).slice(0, 60).map(c => {
      const passed = (gates || []).filter(g => c.validation && c.validation[g] === true).length;
      const failed = (gates || []).filter(g => c.validation && c.validation[g] === false).length;
      return '<tr>' +
        '<td class="tnum">'+h(c.candidate_id || '')+'<div class="small muted">'+h(c.family_id || '')+' · trial '+h(c.trial_index ?? '—')+'</div></td>' +
        '<td><b>'+h(c.asset || '')+'</b><div class="small muted">'+h(c.regime || '')+'</div></td>' +
        '<td><span class="chip '+cls(c.stage)+'">'+h(String(c.stage || '').toUpperCase())+'</span></td>' +
        '<td>'+h(c.hypothesis || '')+'<div class="small muted tnum">'+h(JSON.stringify(c.mutation || {}))+'</div></td>' +
        '<td class="tnum">'+h(passed)+'/'+h((gates || []).length)+(failed ? '<div class="small neg">'+h(failed)+' failed</div>' : '')+'</td>' +
        '<td class="tnum">'+h(String(c.source_commit || '').slice(0,16))+'</td>' +
      '</tr>';
    }).join('');
  }

  function decisionRows(rows) {
    return (rows || []).slice(0, 40).map(d => {
      const a = d.analysis || {};
      return '<tr><td class="tnum">'+h(d.observed_at || '')+'</td><td><b>'+h(d.asset || '')+'</b></td>' +
        '<td>'+h(String(d.action || '').toUpperCase())+'</td><td>'+h(d.regime || '')+'</td>' +
        '<td class="tnum">'+num(a.actual_utility)+'</td><td class="tnum">'+num(a.regret)+'</td>' +
        '<td>'+h(a.best_observed_branch || '—')+'</td><td class="tnum">'+h(a.observed_branch_count ?? 0)+'/'+h((d.branches || []).length)+'</td></tr>';
    }).join('');
  }

  function render(px, ds) {
    const el = document.querySelector('#parallaxPanel');
    if (!el) return;
    const counts = px.counts || {};
    const regret = px.regret || {};
    const stages = ds.stages || {};
    const gates = ds.required_gates || [];
    const qualified = stages.qualified_shadow || 0;
    const proposed = stages.proposed || 0;
    const validated = stages.validated || 0;
    const rejected = stages.rejected || 0;

    el.innerHTML = '<style>' +
      '.px-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:10px}' +
      '.px-box{border:1px solid var(--ring);border-radius:12px;padding:10px;background:var(--surface-2)}' +
      '</style>' +
      '<h2>PARALLAX / DREAMSTATE <span class="sub">observed counterfactual twins · conservative policy incubation · execution_authorized=false</span></h2>' +
      '<div class="tiles" style="margin-top:0">' +
        '<div class="tile"><div class="k">Twin decisions</div><div class="v tnum">'+h(counts.decisions ?? 0)+'</div><div class="small muted">'+h(counts.observed_outcomes ?? 0)+' observed branch outcomes</div></div>' +
        '<div class="tile"><div class="k">Mean observed regret</div><div class="v tnum">'+num(regret.mean_delta)+'</div><div class="small muted">n='+h(regret.n ?? 0)+' · only scored branches</div></div>' +
        '<div class="tile"><div class="k">DREAMSTATE candidates</div><div class="v tnum">'+h((ds.candidates || []).length)+'</div><div class="small muted">'+h(proposed)+' proposed · '+h(validated)+' validated</div></div>' +
        '<div class="tile"><div class="k">Qualified shadow</div><div class="v tnum">'+h(qualified)+'</div><div class="small muted">maximum authority stage</div></div>' +
        '<div class="tile"><div class="k">Rejected</div><div class="v tnum '+(rejected ? 'neg' : '')+'">'+h(rejected)+'</div><div class="small muted">failed gates are immutable</div></div>' +
        '<div class="tile"><div class="k">Authority</div><div class="v">SHADOW ONLY</div><div class="small muted">no broker · no production promotion</div></div>' +
      '</div>' +

      '<div class="px-grid" style="margin-top:12px">' +
        '<div class="px-box"><b>PARALLAX truth contract</b><div class="small muted" style="margin-top:6px">Unobserved counterfactuals are never scored. Ablation deltas are paired attribution, not standalone proof of causality. All alternate outcomes must be supplied by replay/shadow observation.</div></div>' +
        '<div class="px-box"><b>DREAMSTATE truth contract</b><div class="small muted" style="margin-top:6px">Counterfactual advantage creates a hypothesis only. Protected holdout, multiple-testing, latency/cost, calibration, OOD/drift, deterministic replay and independent verification gates remain mandatory.</div></div>' +
      '</div>' +

      '<h3 class="small" style="margin:16px 0 8px">Paired subsystem ablation attribution</h3>' +
      '<div class="scroll" style="max-height:300px"><table><thead><tr><th>Subsystem</th><th>N</th><th>Mean contribution</th><th>95% interval</th></tr></thead><tbody>' +
      (attributionRows(px.paired_ablation_attribution) || '<tr><td colspan="4" class="empty">No paired ablation outcomes yet.</td></tr>') + '</tbody></table></div>' +

      '<h3 class="small" style="margin:16px 0 8px">Statistically conservative mutation signals</h3>' +
      '<div class="scroll" style="max-height:320px"><table><thead><tr><th>Asset</th><th>Regime</th><th>Branch</th><th>N</th><th>Mean Δ</th><th>95% lower</th></tr></thead><tbody>' +
      (signalRows(px.mutation_signals) || '<tr><td colspan="6" class="empty">No branch has cleared the minimum paired evidence + positive 95% lower-bound screen.</td></tr>') + '</tbody></table></div>' +

      '<h3 class="small" style="margin:16px 0 8px">DREAMSTATE candidate population</h3>' +
      '<div class="scroll" style="max-height:440px"><table><thead><tr><th>Candidate</th><th>Scope</th><th>Stage</th><th>Hypothesis / mutation</th><th>Gates</th><th>Source</th></tr></thead><tbody>' +
      (candidateRows(ds.candidates, gates) || '<tr><td colspan="6" class="empty">No DREAMSTATE candidates yet. Candidates appear only after PARALLAX evidence clears its conservative screen.</td></tr>') + '</tbody></table></div>' +

      '<h3 class="small" style="margin:16px 0 8px">Recent twin decisions</h3>' +
      '<div class="scroll" style="max-height:420px"><table><thead><tr><th>Observed</th><th>Asset</th><th>Action</th><th>Regime</th><th>Actual utility</th><th>Regret</th><th>Best observed</th><th>Coverage</th></tr></thead><tbody>' +
      (decisionRows(px.decisions) || '<tr><td colspan="8" class="empty">No PARALLAX decisions recorded yet.</td></tr>') + '</tbody></table></div>' +

      '<div class="small muted" style="margin-top:12px">PARALLAX and DREAMSTATE are research/shadow systems. A qualified-shadow candidate is not a live trading rule and cannot authorize orders, sizing, broker actions, or production promotion.</div>';
  }

  async function loadParallax() {
    const el = document.querySelector('#parallaxPanel');
    if (!el) return;
    try {
      const tok = localStorage.getItem('icarus-engine-token') || 'icarus';
      const headers = {'Authorization':'Bearer '+tok};
      const [pr, dr] = await Promise.all([
        fetch('/api/parallax', {cache:'no-store', headers}),
        fetch('/api/dreamstate', {cache:'no-store', headers})
      ]);
      const px = await pr.json();
      const ds = await dr.json();
      if (!pr.ok) throw new Error(px.detail || ('PARALLAX HTTP '+pr.status));
      if (!dr.ok) throw new Error(ds.detail || ('DREAMSTATE HTTP '+dr.status));
      render(px, ds);
    } catch (err) {
      el.innerHTML = '<h2>PARALLAX / DREAMSTATE</h2><div class="empty">counterfactual research state unavailable: '+h(err.message || err)+'</div>';
    }
  }

  function wireParallax() {
    loadParallax();
    if (timer) clearInterval(timer);
    timer = setInterval(() => {
      if ((location.hash || '#overview').slice(1) === 'parallax') loadParallax();
    }, 5000);
  }

  window.parallaxHtml = parallaxHtml;
  window.wireParallax = wireParallax;
  window.loadParallax = loadParallax;
})();

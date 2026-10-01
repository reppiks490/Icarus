(() => {
  let timer = null;
  const h = value => String(value ?? '').replace(/[&<>"]/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[ch]));
  const num = (v, d=3) => (typeof v === 'number' && Number.isFinite(v)) ? v.toFixed(d) : '—';
  const pct = v => (typeof v === 'number' && Number.isFinite(v)) ? (100 * v).toFixed(0) + '%' : '—';
  const short = (v, n=12) => String(v || '').slice(0, n);
  const cls = value => {
    const s = String(value || '').toUpperCase();
    if (s.includes('QUALIFIED') || s.includes('VALIDATED') || s === 'GREEN' || s === 'READY') return 'b';
    if (s.includes('REJECT') || s.includes('RETIRED') || s.includes('ERROR') || s.includes('BLOCK')) return 'r';
    return 'w';
  };

  function parallaxHtml() {
    return '<section class="card c12" id="parallaxPanel"><h2>PARALLAX / DREAMSTATE <span class="sub">counterfactual twins · FDR · temporal stability · parameter basins · bounded policy incubation · shadow only</span></h2><div class="empty">loading counterfactual research state…</div></section>';
  }

  function attributionRows(rows) {
    return (rows || []).slice(0, 30).map(r => '<tr>' +
      '<td><b>'+h(String(r.subsystem || '').toUpperCase())+'</b></td>' +
      '<td>'+h(r.asset || '')+'<div class="small muted">'+h(r.regime || '')+'</div></td>' +
      '<td class="tnum">'+h(r.n ?? 0)+'</td>' +
      '<td class="tnum">'+num(r.mean_delta)+'</td>' +
      '<td class="tnum">'+num(r.ci95_low)+' → '+num(r.ci95_high)+'</td>' +
      '<td class="tnum">'+h(short(r.source_commit, 10))+'</td>' +
      '</tr>').join('');
  }

  function signalRows(rows) {
    return (rows || []).slice(0, 40).map(r => '<tr>' +
      '<td><b>'+h(r.asset || '')+'</b><div class="small muted">'+h(r.regime || '')+'</div></td>' +
      '<td><span class="chip">'+h(r.branch_label || '')+'</span><div class="small muted">'+h(r.kind || '')+'</div></td>' +
      '<td class="tnum">'+h(r.evidence_pair_count ?? r.n ?? 0)+'</td>' +
      '<td class="tnum">'+pct(r.evidence_pair_coverage)+'</td>' +
      '<td class="tnum">'+num(r.mean_delta)+'</td>' +
      '<td class="tnum">'+num(r.ci95_low)+'</td>' +
      '<td class="tnum">'+num(r.q_value, 4)+'</td>' +
      '<td><span class="chip '+(((r.temporal_stability||{}).evaluable)?(((r.temporal_stability||{}).stable)?'b':'r'):'w')+'">'+(((r.temporal_stability||{}).evaluable)?(((r.temporal_stability||{}).stable)?'STABLE':'UNSTABLE'):'EARLY')+'</span><div class="small muted">worst '+num((r.temporal_stability||{}).worst_fold_mean)+'</div></td>' +
      '<td><span class="chip '+(((r.parameter_basin||{}).isolated_spike||(r.parameter_basin||{}).local_support_missing)?'r':((r.parameter_basin||{}).evaluable?'b':'w'))+'">'+((r.parameter_basin||{}).isolated_spike?'SPIKE':((r.parameter_basin||{}).local_support_missing?'SPARSE':((r.parameter_basin||{}).evaluable?'BASIN':'EARLY')))+'</span><div class="small muted">support '+h((r.parameter_basin||{}).basin_support_count ?? 0)+' · family '+h((r.parameter_basin||{}).family_evaluable_point_count ?? 0)+'</div></td>' +
      '<td class="tnum">'+h(r.strata_count ?? 0)+'</td>' +
      '<td><span class="chip '+(r.comparison_contract_complete?'b':'r')+'">'+(r.comparison_contract_complete?'READY':'INCOMPLETE')+'</span><div class="small muted tnum">'+h(short(r.comparison_contract_hash, 10))+'</div></td>' +
      '</tr>').join('');
  }

  function blockedRows(rows) {
    return (rows || []).filter(r => !r.robust_candidate_eligible).slice(0, 40).map(r => {
      const blockers = [...(r.screen_blockers || []), ...(r.robustness_blockers || [])];
      return '<tr>' +
        '<td><b>'+h(r.asset || '')+'</b><div class="small muted">'+h(r.regime || '')+'</div></td>' +
        '<td>'+h(r.branch_label || '')+'</td>' +
        '<td class="tnum">'+h(r.evidence_pair_count ?? 0)+'</td>' +
        '<td class="tnum">'+num(r.q_value, 4)+'</td>' +
        '<td>'+h(blockers.join(', '))+'</td>' +
        '<td class="tnum">'+h(short(r.source_commit, 10))+'</td>' +
        '</tr>';
    }).join('');
  }

  function candidateRows(rows, gates) {
    return (rows || []).slice(0, 80).map(c => {
      const passed = (gates || []).filter(g => c.validation && c.validation[g] === true).length;
      const failed = (gates || []).filter(g => c.validation && c.validation[g] === false).length;
      const acct = c.search_accounting || {};
      const pc = c.policy_contract || {};
      const scope = pc.scope || {};
      return '<tr>' +
        '<td class="tnum">'+h(c.candidate_id || '')+'<div class="small muted">'+h(c.family_id || '')+' · trial '+h(c.trial_index ?? '—')+'</div></td>' +
        '<td><b>'+h(c.asset || '')+'</b><div class="small muted">'+h(c.regime || '')+'</div><div class="small muted tnum">'+h(short(scope.comparison_contract_hash, 10))+'</div></td>' +
        '<td><span class="chip '+cls(c.stage)+'">'+h(String(c.stage || '').toUpperCase())+'</span></td>' +
        '<td>'+h(c.hypothesis || '')+'<div class="small muted tnum">'+h(JSON.stringify(c.mutation || {}))+'</div></td>' +
        '<td class="tnum">'+num(acct.source_q_value, 4)+'<div class="small muted">n='+h(acct.source_evidence_pairs ?? '—')+'</div><div class="small muted">'+(acct.source_temporal_evaluable?(acct.source_temporal_stable?'time stable':'time unstable'):'time early')+' · '+(acct.source_isolated_parameter_spike?'spike':(acct.source_parameter_local_support_missing?'sparse':(acct.source_parameter_basin_evaluable?'basin '+h(acct.source_parameter_basin_support_count ?? 0):'basin early')))+'</div></td>' +
        '<td class="tnum">'+h(acct.family_trial_budget_remaining ?? '—')+'<div class="small muted">remaining</div></td>' +
        '<td class="tnum">'+h(passed)+'/'+h((gates || []).length)+(failed ? '<div class="small neg">'+h(failed)+' failed</div>' : '')+'</td>' +
        '<td class="tnum">'+h(short(c.source_commit, 10))+'</td>' +
      '</tr>';
    }).join('');
  }

  function familyRows(rows) {
    return (rows || []).slice(0, 40).map(f => '<tr>' +
      '<td class="tnum">'+h(f.family_id || '')+'</td>' +
      '<td><b>'+h(f.asset || '')+'</b><div class="small muted">'+h(f.regime || '')+'</div></td>' +
      '<td class="tnum">'+h(f.trials ?? 0)+'/'+h(f.trial_budget ?? '—')+'</td>' +
      '<td>'+h(f.active_candidate || '—')+'</td>' +
      '<td>'+Object.entries(f.stages || {}).map(([k,v])=>'<span class="chip '+cls(k)+'">'+h(k)+':'+h(v)+'</span>').join(' ')+'</td>' +
      '<td class="tnum">'+h(short(f.source_commit, 10))+'</td>' +
      '</tr>').join('');
  }

  function decisionRows(rows) {
    return (rows || []).slice(0, 50).map(d => {
      const a = d.analysis || {};
      return '<tr>' +
        '<td class="tnum">'+h(d.observed_at || '')+'</td>' +
        '<td><b>'+h(d.asset || '')+'</b><div class="small muted">'+h(d.regime || '')+'</div></td>' +
        '<td>'+h(String(d.action || '').toUpperCase())+'</td>' +
        '<td><span class="chip '+(d.comparison_contract_complete?'b':'r')+'">'+(d.comparison_contract_complete?'READY':'INCOMPLETE')+'</span><div class="small muted">'+h((d.comparison_contract || {}).utility_metric || '')+'</div></td>' +
        '<td class="tnum">'+pct(a.branch_coverage_ratio)+'</td>' +
        '<td class="tnum">'+pct(a.evidence_coverage_ratio)+'</td>' +
        '<td class="tnum">'+num(a.regret)+'</td>' +
        '<td>'+h(a.best_observed_branch || '—')+'</td>' +
        '<td class="tnum">'+h(short(d.source_commit, 10))+'</td>' +
      '</tr>';
    }).join('');
  }

  function kindCoverageRows(kinds) {
    return Object.entries(kinds || {}).map(([kind,row]) => '<tr>' +
      '<td>'+h(kind)+'</td><td class="tnum">'+h(row.total ?? 0)+'</td>' +
      '<td class="tnum">'+h(row.observed ?? 0)+'</td>' +
      '<td class="tnum">'+h(row.with_evidence ?? 0)+'</td>' +
      '<td class="tnum">'+pct((row.total||0) ? (row.with_evidence||0)/(row.total||1) : 0)+'</td></tr>').join('');
  }

  function render(px, ds) {
    const el = document.querySelector('#parallaxPanel');
    if (!el) return;
    const counts = px.counts || {};
    const coverage = px.coverage || {};
    const regret = px.regret || {};
    const screening = px.screening || {};
    const stages = ds.stages || {};
    const search = ds.search || {};
    const gates = ds.required_gates || [];
    const qualified = stages.qualified_shadow || 0;
    const rejected = stages.rejected || 0;
    const contractReady = coverage.recent_decisions_with_complete_comparison_contract || 0;
    const recentN = coverage.recent_decision_count || 0;

    el.innerHTML = '<style>' +
      '.px-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:10px}' +
      '.px-box{border:1px solid var(--ring);border-radius:12px;padding:10px;background:var(--surface-2)}' +
      '</style>' +
      '<h2>PARALLAX / DREAMSTATE <span class="sub">observed twins · BH-FDR · temporal folds · parameter basins · bounded policy incubation · execution_authorized=false</span></h2>' +
      '<div class="tiles" style="margin-top:0">' +
        '<div class="tile"><div class="k">Twin decisions</div><div class="v tnum">'+h(counts.decisions ?? 0)+'</div><div class="small muted">'+h(counts.observed_outcomes ?? 0)+' observed outcomes</div></div>' +
        '<div class="tile"><div class="k">Contract-ready recent</div><div class="v tnum">'+h(contractReady)+'/'+h(recentN)+'</div><div class="small muted">utility · horizon · dataset · costs · clock</div></div>' +
        '<div class="tile"><div class="k">Robust-ready signals</div><div class="v tnum">'+h(screening.robust_candidate_ready ?? 0)+'</div><div class="small muted">'+h(screening.candidate_ready ?? 0)+' statistical · '+h(screening.robustness_blocked ?? 0)+' robustness-blocked</div></div>' +
        '<div class="tile"><div class="k">Comparable mean regret</div><div class="v tnum">'+num(regret.mean_delta)+'</div><div class="small muted">'+(regret.comparable_globally ? 'single comparable evidence scope' : 'not pooled across incomparable scopes')+'</div></div>' +
        '<div class="tile"><div class="k">DREAMSTATE families</div><div class="v tnum">'+h(search.family_count ?? 0)+'</div><div class="small muted">'+h(search.active_family_count ?? 0)+' active · '+h(search.budget_exhausted_family_count ?? 0)+' exhausted</div></div>' +
        '<div class="tile"><div class="k">Qualified shadow</div><div class="v tnum">'+h(qualified)+'</div><div class="small muted">maximum authority stage</div></div>' +
        '<div class="tile"><div class="k">Rejected / retired</div><div class="v tnum '+(rejected ? 'neg' : '')+'">'+h(rejected)+' / '+h(stages.retired ?? 0)+'</div><div class="small muted">failures preserved as evidence</div></div>' +
        '<div class="tile"><div class="k">Authority</div><div class="v">SHADOW ONLY</div><div class="small muted">no broker · no automatic activation</div></div>' +
      '</div>' +

      '<div class="px-grid" style="margin-top:12px">' +
        '<div class="px-box"><b>PARALLAX V3 robustness contract</b><div class="small muted" style="margin-top:6px">Statistical candidates still require paired evidence, exact revision/contract identity, positive lower bound and BH-FDR. Once evidence is rich enough, robust-ready also requires positive chronological folds and rejects isolated parameter spikes when adjacent settings are evaluable.</div></div>' +
        '<div class="px-box"><b>DREAMSTATE V3 policy contract</b><div class="small muted" style="margin-top:6px">DREAMSTATE consumes only robust-ready PARALLAX sources when robustness is evaluable. Candidates retire if time stability collapses or a setting becomes an isolated spike. Families retain bounded trials, immutable failures, baseline fallback and zero production/broker authority.</div></div>' +
      '</div>' +

      '<h3 class="small" style="margin:16px 0 8px">Robust-ready PARALLAX signals</h3>' +
      '<div class="scroll" style="max-height:360px"><table><thead><tr><th>Scope</th><th>Branch</th><th>Evidence N</th><th>Pair coverage</th><th>Mean Δ</th><th>95% lower</th><th>FDR q</th><th>Time</th><th>Basin</th><th>Strata</th><th>Contract</th></tr></thead><tbody>' +
      (signalRows(px.mutation_signals) || '<tr><td colspan="11" class="empty">No counterfactual hypothesis currently clears every statistical and robustness screen.</td></tr>') + '</tbody></table></div>' +

      '<h3 class="small" style="margin:16px 0 8px">Blocked hypothesis diagnostics</h3>' +
      '<div class="scroll" style="max-height:300px"><table><thead><tr><th>Scope</th><th>Branch</th><th>Evidence N</th><th>FDR q</th><th>Blockers</th><th>Revision</th></tr></thead><tbody>' +
      (blockedRows(screening.hypotheses) || '<tr><td colspan="6" class="empty">No blocked observed hypotheses.</td></tr>') + '</tbody></table></div>' +

      '<h3 class="small" style="margin:16px 0 8px">Paired subsystem-ablation attribution</h3>' +
      '<div class="scroll" style="max-height:320px"><table><thead><tr><th>Subsystem</th><th>Scope</th><th>N</th><th>Mean contribution</th><th>95% interval</th><th>Revision</th></tr></thead><tbody>' +
      (attributionRows(px.paired_ablation_attribution) || '<tr><td colspan="6" class="empty">No evidence-complete paired ablation outcomes yet.</td></tr>') + '</tbody></table></div>' +

      '<h3 class="small" style="margin:16px 0 8px">Counterfactual branch coverage</h3>' +
      '<div class="scroll" style="max-height:300px"><table><thead><tr><th>Branch kind</th><th>Total</th><th>Observed</th><th>With evidence</th><th>Evidence coverage</th></tr></thead><tbody>' +
      (kindCoverageRows(coverage.branch_kinds) || '<tr><td colspan="5" class="empty">No branch coverage yet.</td></tr>') + '</tbody></table></div>' +

      '<h3 class="small" style="margin:16px 0 8px">DREAMSTATE candidate population</h3>' +
      '<div class="scroll" style="max-height:480px"><table><thead><tr><th>Candidate</th><th>Scope</th><th>Stage</th><th>Hypothesis / mutation</th><th>Source q</th><th>Trial budget</th><th>Gates</th><th>Revision</th></tr></thead><tbody>' +
      (candidateRows(ds.candidates, gates) || '<tr><td colspan="8" class="empty">No DREAMSTATE candidates. Candidates exist only after PARALLAX clears the comparison-contract, paired-evidence and FDR screens.</td></tr>') + '</tbody></table></div>' +

      '<h3 class="small" style="margin:16px 0 8px">DREAMSTATE family search accounting</h3>' +
      '<div class="scroll" style="max-height:320px"><table><thead><tr><th>Family</th><th>Scope</th><th>Trials</th><th>Active candidate</th><th>Stages</th><th>Revision</th></tr></thead><tbody>' +
      (familyRows(ds.families) || '<tr><td colspan="6" class="empty">No candidate families yet.</td></tr>') + '</tbody></table></div>' +

      '<h3 class="small" style="margin:16px 0 8px">Recent twin decisions</h3>' +
      '<div class="scroll" style="max-height:440px"><table><thead><tr><th>Observed</th><th>Scope</th><th>Action</th><th>Contract</th><th>Branch coverage</th><th>Evidence coverage</th><th>Regret</th><th>Best observed</th><th>Revision</th></tr></thead><tbody>' +
      (decisionRows(px.decisions) || '<tr><td colspan="9" class="empty">No PARALLAX decisions recorded yet.</td></tr>') + '</tbody></table></div>' +

      '<div class="small muted" style="margin-top:12px">PARALLAX and DREAMSTATE are research/shadow systems. Statistical and robustness screens prioritize hypotheses; they do not prove causality or expected profit. A qualified-shadow candidate cannot authorize orders, sizing, broker actions, or production promotion.</div>';
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

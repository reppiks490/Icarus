(() => {
  'use strict';

  let timer = null;
  let loadSeq = 0;

  const h = v => String(v == null ? '' : v).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
  const short = v => {
    const s = String(v == null ? '' : v);
    return s.length > 18 ? s.slice(0, 10) + '…' + s.slice(-6) : s;
  };
  const json = v => {
    if (v == null) return 'UNAVAILABLE';
    try { return JSON.stringify(v); } catch (_) { return 'UNAVAILABLE'; }
  };
  const count = v => (v == null ? 'UNMEASURED' : v);

  function statusClass(value) {
    const s = String(value || 'UNVERIFIED').toUpperCase();
    if (s.startsWith('VERIFIED') || s.startsWith('VALIDATED') || s.startsWith('COMPILED')) return 'pos';
    if (s.startsWith('BLOCKED') || s === 'REJECTED') return 'neg';
    return 'muted';
  }

  function ascendancyHtml() {
    return '<section class="card c12" id="ascendancyPanel">' +
      '<div class="row" style="justify-content:space-between;align-items:flex-start;gap:12px;flex-wrap:wrap">' +
        '<div><h2 style="margin-bottom:4px">ASCENDANCY · Capability Orchestrator</h2>' +
        '<div class="small muted">Capability truth plane + open-ended Architecture Genome laboratory · immutable evaluator contracts · research/shadow only</div></div>' +
        '<button id="ascendancyReload" type="button">Reload</button>' +
      '</div>' +
      '<div id="ascendancyBody" style="margin-top:12px"><div class="empty">loading ASCENDANCY state…</div></div>' +
    '</section>';
  }

  function renderCapabilities(d) {
    if (!d) {
      return '<section class="card"><h3>CAPABILITY TRUTH</h3><div class="empty">UNAVAILABLE — capability state did not load.</div></section>';
    }
    const rows = Array.isArray(d.providers) ? d.providers : [];
    const body = rows.map(r => {
      const allowed = Array.isArray(r.claims_allowed) ? r.claims_allowed : [];
      const forbidden = Array.isArray(r.claims_forbidden) ? r.claims_forbidden : [];
      return '<tr>' +
        '<td><b>' + h(r.id || 'UNAVAILABLE') + '</b><div class="small muted">' + h(r.category || 'UNAVAILABLE') + '</div></td>' +
        '<td class="' + statusClass(r.observed_status) + '"><b>' + h(r.observed_status || 'UNVERIFIED') + '</b><div class="small muted">' + h(r.observed_detail || 'No probe evidence.') + '</div></td>' +
        '<td class="small">' + h(allowed.join(' · ') || 'NONE DECLARED') + '</td>' +
        '<td class="small">' + h(forbidden.join(' · ') || 'NONE DECLARED') + '</td>' +
        '<td>' + h(r.authority || 'research') + '</td>' +
      '</tr>';
    }).join('');

    return '<section class="card" style="margin-top:12px">' +
      '<h3>CAPABILITY TRUTH</h3>' +
      '<div class="tiles">' +
        '<div class="tile"><div class="k">PROVIDERS</div><div class="v tnum">' + h(count(d.provider_count)) + '</div></div>' +
        '<div class="tile"><div class="k">VERIFIED</div><div class="v pos tnum">' + h(count(d.verified_count)) + '</div></div>' +
        '<div class="tile"><div class="k">BLOCKED</div><div class="v neg tnum">' + h(count(d.blocked_count)) + '</div><div class="small muted">BLOCKED_SUBSCRIPTION / BLOCKED_NETWORK_POLICY remain explicit</div></div>' +
        '<div class="tile"><div class="k">UNPROBED</div><div class="v tnum">' + h(count(d.unprobed_count)) + '</div></div>' +
        '<div class="tile"><div class="k">AUTHORITY</div><div class="v">RESEARCH ONLY</div><div class="small muted">execution_authorized=false · production_decision_authorized=false</div></div>' +
      '</div>' +
      '<div class="small muted" style="margin:10px 0">Audit ' + h(d.audit_observed_at || 'UNAVAILABLE') + ' · ' + h(d.audit_rule || '') + '</div>' +
      '<div class="scroll" style="max-height:42vh"><table><thead><tr>' +
        '<th>Capability</th><th>Observed state</th><th>claims_allowed</th><th>claims_forbidden</th><th>Authority domain</th>' +
      '</tr></thead><tbody>' + (body || '<tr><td colspan="5" class="empty">UNAVAILABLE — no capability contracts loaded.</td></tr>') +
      '</tbody></table></div>' +
      '<div class="small muted" style="margin-top:10px">Tool presence never becomes market truth; unavailable evidence never becomes a zero-valued observation.</div>' +
    '</section>';
  }

  function genomeRows(archive) {
    const rows = Array.isArray(archive.genomes) ? archive.genomes : [];
    return rows.map(g => {
      const parents = Array.isArray(g.parent_genome_ids) ? g.parent_genome_ids : [];
      const b = g.resource_budget || {};
      return '<tr>' +
        '<td><code title="' + h(g.genome_id || '') + '">' + h(short(g.genome_id || 'UNAVAILABLE')) + '</code></td>' +
        '<td class="' + statusClass(g.state) + '"><b>' + h(g.state || 'UNAVAILABLE') + '</b></td>' +
        '<td><code>' + h(short(g.source_commit || 'UNAVAILABLE')) + '</code></td>' +
        '<td>' + h((g.nodes || []).length) + ' / ' + h((g.edges || []).length) + '</td>' +
        '<td class="small">' + h(parents.map(short).join(' · ') || 'ROOT') + '</td>' +
        '<td class="small">' + h((g.mutation || {}).operator || 'UNAVAILABLE') + ' → ' + h((g.mutation || {}).target || 'UNAVAILABLE') + '</td>' +
        '<td class="small">eval=' + h(count(b.max_evaluations)) + ' · wall=' + h(count(b.max_wall_seconds)) + 's · cost=' + h(count(b.max_cost_units)) + '</td>' +
      '</tr>';
    }).join('');
  }

  function contractRows(frontier) {
    const groups = Array.isArray(frontier.contracts) ? frontier.contracts : [];
    return groups.map(group => {
      const objectives = (group.objectives || []).map(o => String(o.name || '?') + ':' + String(o.direction || '?')).join(' · ');
      const current = (group.pareto_genome_ids || []).map(short).join(' · ') || 'UNMEASURED';
      return '<tr>' +
        '<td><code title="' + h(group.evaluation_contract_hash || '') + '">' + h(short(group.evaluation_contract_hash || 'UNAVAILABLE')) + '</code></td>' +
        '<td class="small">' + h(objectives || 'UNAVAILABLE') + '</td>' +
        '<td class="small">' + h((group.descriptor_keys || []).join(' · ') || 'NONE') + '</td>' +
        '<td>' + h(count(group.active_candidate_count)) + '</td>' +
        '<td class="small">' + h(current) + '</td>' +
      '</tr>';
    }).join('');
  }

  function nicheRows(frontier) {
    const out = [];
    (frontier.contracts || []).forEach(group => {
      (group.niches || []).forEach(n => {
        out.push('<tr>' +
          '<td><code>' + h(short(group.evaluation_contract_hash || 'UNAVAILABLE')) + '</code></td>' +
          '<td><code>' + h(short(n.niche_id || 'UNAVAILABLE')) + '</code></td>' +
          '<td class="small">' + h(json(n.descriptor_values)) + '</td>' +
          '<td>' + h(count(n.candidate_count)) + '</td>' +
          '<td class="small">' + h((n.elite_genome_ids || []).map(short).join(' · ') || 'UNMEASURED') + '</td>' +
        '</tr>');
      });
    });
    return out.join('');
  }

  function candidateRows(frontier) {
    const out = [];
    (frontier.contracts || []).forEach(group => {
      (group.candidates || []).forEach(row => {
        out.push('<tr>' +
          '<td><code>' + h(short(row.genome_id || 'UNAVAILABLE')) + '</code></td>' +
          '<td>' + h(row.genome_state || 'UNAVAILABLE') + '</td>' +
          '<td class="small">' + h(json(row.metrics)) + '</td>' +
          '<td class="small">' + h(json(row.descriptors)) + '</td>' +
          '<td class="tnum">' + h(row.novelty_score == null ? 'UNMEASURED' : Number(row.novelty_score).toFixed(3)) + '</td>' +
          '<td><code>' + h(short(row.niche_id || 'UNAVAILABLE')) + '</code></td>' +
        '</tr>');
      });
    });
    return out.join('');
  }

  function lineageRows(archive) {
    return (archive.lineage || []).map(row =>
      '<tr><td><code>' + h(short(row.parent_genome_id || 'UNAVAILABLE')) + '</code></td>' +
      '<td>→</td><td><code>' + h(short(row.child_genome_id || 'UNAVAILABLE')) + '</code></td></tr>'
    ).join('');
  }

  function steppingStoneRows(frontier) {
    return (frontier.stepping_stones || []).map(row =>
      '<tr><td><code>' + h(short(row.genome_id || 'UNAVAILABLE')) + '</code></td>' +
      '<td>' + h(row.state || 'UNAVAILABLE') + '</td>' +
      '<td class="small">' + h((row.descendant_genome_ids || []).map(short).join(' · ') || 'NONE') + '</td>' +
      '<td class="small">' + h((row.active_frontier_descendant_ids || []).map(short).join(' · ') || 'NONE') + '</td>' +
      '<td>' + h(row.informative_even_if_dominated === true ? 'YES' : 'NO') + '</td></tr>'
    ).join('');
  }

  function compileRows(archive) {
    return (archive.compile_receipts || []).map(row =>
      '<tr><td><code>' + h(short(row.genome_id || 'UNAVAILABLE')) + '</code></td>' +
      '<td class="' + statusClass(row.status) + '">' + h(row.status || 'UNAVAILABLE') + '</td>' +
      '<td><code>' + h(short(row.runtime_hash || 'UNAVAILABLE')) + '</code></td>' +
      '<td>' + h(count(row.node_count)) + ' / ' + h(count(row.edge_count)) + '</td>' +
      '<td class="small">' + h(row.recorded_at || 'UNAVAILABLE') + '</td></tr>'
    ).join('');
  }

  function renderGenomeLab(state) {
    if (!state) {
      return '<section class="card"><h3>ARCHITECTURE GENOME</h3><div class="empty">UNAVAILABLE — genome laboratory state did not load.</div></section>';
    }
    const archive = state.archive || {};
    const frontier = state.frontier || {};
    const compiledIds = new Set((archive.compile_receipts || []).map(x => x.genome_id));
    const blockers = (archive.genomes || []).filter(g => !compiledIds.has(g.genome_id));
    const blockersHtml = blockers.map(g =>
      '<tr><td><code>' + h(short(g.genome_id || 'UNAVAILABLE')) + '</code></td>' +
      '<td>' + h(g.state || 'UNAVAILABLE') + '</td><td>UNAVAILABLE — no compile receipt</td></tr>'
    ).join('');

    return '<section class="card" style="margin-top:12px">' +
      '<h3>ARCHITECTURE GENOME</h3>' +
      '<div class="small muted">Architecture itself is a bounded research object. Novelty is not predictive edge. RETIRED and REJECTED lineages remain evidence; no genome has execution authority.</div>' +
      '<div class="tiles" style="margin-top:10px">' +
        '<div class="tile"><div class="k">GENOMES</div><div class="v tnum">' + h(count(archive.genome_count)) + '</div></div>' +
        '<div class="tile"><div class="k">COMPILE RECEIPTS</div><div class="v tnum">' + h(count(archive.compile_count)) + '</div></div>' +
        '<div class="tile"><div class="k">EVALUATIONS</div><div class="v tnum">' + h(count(archive.evaluation_count)) + '</div></div>' +
        '<div class="tile"><div class="k">RETIRED</div><div class="v tnum">' + h(count(archive.retired_count)) + '</div></div>' +
        '<div class="tile"><div class="k">EVALUATOR CONTRACTS</div><div class="v tnum">' + h(count(frontier.contract_count)) + '</div></div>' +
        '<div class="tile"><div class="k">AUTHORITY</div><div class="v">RESEARCH ONLY</div><div class="small muted">execution_authorized=false · production_decision_authorized=false</div></div>' +
      '</div>' +

      '<h3 style="margin-top:16px">RESOURCE BUDGET · PARENT / CHILD ANCESTRY</h3>' +
      '<div class="scroll"><table><thead><tr><th>Genome</th><th>State</th><th>Source commit</th><th>Nodes / edges</th><th>Parents</th><th>Mutation</th><th>RESOURCE BUDGET</th></tr></thead><tbody>' +
        (genomeRows(archive) || '<tr><td colspan="7" class="empty">UNAVAILABLE — no architecture genomes registered.</td></tr>') +
      '</tbody></table></div>' +

      '<h3 style="margin-top:16px">SEARCH FRONTIER · CURRENT FRONTIER · EVALUATOR CONTRACT</h3>' +
      '<div class="small muted">Selection policy: ' + h(frontier.selection_policy || 'latest_evaluation_per_genome_per_contract') +
      ' · comparisons never cross evaluator-contract identity.</div>' +
      '<div class="scroll"><table><thead><tr><th>Contract</th><th>EVALUATOR CONTRACT objectives</th><th>Descriptors</th><th>Active</th><th>CURRENT FRONTIER</th></tr></thead><tbody>' +
        (contractRows(frontier) || '<tr><td colspan="5" class="empty">UNMEASURED — no contract-bound evaluations yet.</td></tr>') +
      '</tbody></table></div>' +

      '<h3 style="margin-top:16px">DIVERSITY / NICHES</h3>' +
      '<div class="scroll"><table><thead><tr><th>Contract</th><th>Niche</th><th>Descriptor values</th><th>Candidates</th><th>Local elites</th></tr></thead><tbody>' +
        (nicheRows(frontier) || '<tr><td colspan="5" class="empty">UNMEASURED — no evaluated niches yet.</td></tr>') +
      '</tbody></table></div>' +

      '<div class="scroll" style="margin-top:8px"><table><thead><tr><th>Genome</th><th>State</th><th>Metrics</th><th>Descriptors</th><th>novelty_score</th><th>Niche</th></tr></thead><tbody>' +
        (candidateRows(frontier) || '<tr><td colspan="6" class="empty">UNMEASURED — no evaluated genome candidates.</td></tr>') +
      '</tbody></table></div>' +

      '<h3 style="margin-top:16px">EVOLUTION LINEAGE · PARENT / CHILD ANCESTRY</h3>' +
      '<div class="scroll"><table><thead><tr><th>Parent</th><th></th><th>Child</th></tr></thead><tbody>' +
        (lineageRows(archive) || '<tr><td colspan="3" class="empty">UNAVAILABLE — no parent/child edges recorded.</td></tr>') +
      '</tbody></table></div>' +

      '<h3 style="margin-top:16px">STEPPING STONES</h3>' +
      '<div class="small muted">A dominated or RETIRED ancestor is preserved when it leads to descendants; stepping-stone status is historical lineage, not proof of edge.</div>' +
      '<div class="scroll"><table><thead><tr><th>Genome</th><th>State</th><th>Descendants</th><th>Frontier descendants</th><th>Informative despite domination</th></tr></thead><tbody>' +
        (steppingStoneRows(frontier) || '<tr><td colspan="5" class="empty">UNMEASURED — no stepping-stone lineage yet.</td></tr>') +
      '</tbody></table></div>' +

      '<h3 style="margin-top:16px">COMPILE RECEIPTS · COMPILE BLOCKERS</h3>' +
      '<div class="scroll"><table><thead><tr><th>Genome</th><th>Compile state</th><th>Runtime hash</th><th>Nodes / edges</th><th>Recorded</th></tr></thead><tbody>' +
        (compileRows(archive) || '<tr><td colspan="5" class="empty">UNAVAILABLE — no successful compile receipts.</td></tr>') +
      '</tbody></table></div>' +
      '<div class="scroll" style="margin-top:8px"><table><thead><tr><th>Genome</th><th>State</th><th>COMPILE BLOCKERS</th></tr></thead><tbody>' +
        (blockersHtml || '<tr><td colspan="3" class="small muted">No registered genome is missing a compile receipt.</td></tr>') +
      '</tbody></table></div>' +

      '<div class="small muted" style="margin-top:12px">latest_evaluation_per_genome_per_contract prevents best-print cherry-picking. REJECTED / RETIRED / stepping-stone state remains visible. Missing measurements render UNMEASURED or UNAVAILABLE, never zero.</div>' +
    '</section>';
  }

  function renderFoundry(foundry) {
    if (!foundry) {
      return '<section class="card" style="margin-top:12px"><h3>EDGE FOUNDRY</h3><div class="empty">UNAVAILABLE — candidate foundry state did not load.</div></section>';
    }
    const candidates = Array.isArray(foundry.candidates) ? foundry.candidates : [];
    const stages = foundry.stage_counts || {};
    const rows = candidates.map(row => {
      const observations = (row.required_observations || []).map(o =>
        String(o.name || 'UNAVAILABLE') + ':' + String(o.evidence_class || 'UNAVAILABLE') +
        (o.usable_for_confirmation === false ? ':NO_CONFIRMATION' : '')
      );
      const parents = Array.isArray(row.parent_candidate_ids) ? row.parent_candidate_ids : [];
      const budget = row.resource_budget || {};
      return '<tr>' +
        '<td><code title="' + h(row.candidate_id || '') + '">' + h(short(row.candidate_id || 'UNAVAILABLE')) + '</code></td>' +
        '<td class="' + statusClass(row.stage) + '"><b>' + h(row.stage || 'UNAVAILABLE') + '</b></td>' +
        '<td>' + h(row.origin || 'UNAVAILABLE') + '</td>' +
        '<td class="small">' + h(row.hypothesis || 'UNAVAILABLE') + '</td>' +
        '<td class="small">' + h(json(row.mechanism)) + '</td>' +
        '<td class="small">' + h(json(row.expected_advantage)) + '</td>' +
        '<td class="small">' + h(observations.join(' · ') || 'UNAVAILABLE') + '</td>' +
        '<td class="small">' + h((row.falsifiers || []).join(' · ') || 'UNAVAILABLE') + '</td>' +
        '<td class="small">' + h(parents.map(short).join(' · ') || 'ROOT') + '</td>' +
        '<td class="small">eval=' + h(count(budget.max_evaluations)) + ' · wall=' + h(count(budget.max_wall_seconds)) + 's · cost=' + h(count(budget.max_cost_units)) + '</td>' +
      '</tr>';
    }).join('');

    const lineage = (foundry.lineage || []).map(edge =>
      '<tr><td><code>' + h(short(edge.parent_candidate_id || 'UNAVAILABLE')) + '</code></td>' +
      '<td>→</td><td><code>' + h(short(edge.child_candidate_id || 'UNAVAILABLE')) + '</code></td></tr>'
    ).join('');

    const contracts = foundry.contracts || {};
    return '<section class="card" style="margin-top:12px">' +
      '<h3>EDGE FOUNDRY</h3>' +
      '<div class="small muted">Falsifiable candidate intake across native failures, foreign lenses, public research, generated mathematics and architecture mutations. Candidate creation is not qualification.</div>' +
      '<div class="tiles" style="margin-top:10px">' +
        '<div class="tile"><div class="k">CANDIDATES</div><div class="v tnum">' + h(count(foundry.candidate_count)) + '</div></div>' +
        '<div class="tile"><div class="k">PROPOSED</div><div class="v tnum">' + h(count(stages.PROPOSED)) + '</div></div>' +
        '<div class="tile"><div class="k">TESTING</div><div class="v tnum">' + h(count(stages.TESTING)) + '</div></div>' +
        '<div class="tile"><div class="k">VALIDATED RESEARCH</div><div class="v tnum">' + h(count(stages.VALIDATED_RESEARCH)) + '</div></div>' +
        '<div class="tile"><div class="k">REJECTED / RETIRED</div><div class="v tnum">' + h((stages.REJECTED || 0) + (stages.RETIRED || 0)) + '</div></div>' +
        '<div class="tile"><div class="k">AUTHORITY</div><div class="v">RESEARCH ONLY</div><div class="small muted">execution_authorized=false · production_decision_authorized=false</div></div>' +
      '</div>' +
      '<div class="small muted" style="margin:10px 0">qualified_shadow_reserved_for_protected_qualification=' +
        h(contracts.qualified_shadow_reserved_for_protected_qualification === true ? 'true' : 'UNAVAILABLE') +
        ' · unavailable_observations_cannot_confirm=' +
        h(contracts.unavailable_observations_cannot_confirm === true ? 'true' : 'UNAVAILABLE') +
      '</div>' +
      '<div class="scroll" style="max-height:58vh"><table><thead><tr>' +
        '<th>Candidate</th><th>Stage</th><th>ORIGIN</th><th>HYPOTHESIS</th><th>MECHANISM</th><th>EXPECTED ADVANTAGE</th><th>REQUIRED OBSERVATIONS</th><th>FALSIFIERS</th><th>PARENT CANDIDATES</th><th>RESOURCE BUDGET</th>' +
      '</tr></thead><tbody>' +
        (rows || '<tr><td colspan="10" class="empty">UNAVAILABLE — no candidates have entered the Foundry.</td></tr>') +
      '</tbody></table></div>' +
      '<h3 style="margin-top:16px">CANDIDATE LINEAGE</h3>' +
      '<div class="scroll"><table><thead><tr><th>Parent</th><th></th><th>Child</th></tr></thead><tbody>' +
        (lineage || '<tr><td colspan="3" class="empty">UNAVAILABLE — no candidate parent/child edges recorded.</td></tr>') +
      '</tbody></table></div>' +
      '<div class="small muted" style="margin-top:10px">PROPOSED → INCUBATING → TESTING → VALIDATED_RESEARCH. The Foundry cannot mint QUALIFIED_SHADOW; protected qualification remains independent.</div>' +
    '</section>';
  }

  function renderUnknowns(unknowns) {
    if (!unknowns) {
      return '<section class="card" style="margin-top:12px"><h3>UNKNOWN UNKNOWNS</h3><div class="empty">UNAVAILABLE — unexplained-phenomenon state did not load.</div></section>';
    }
    const phenomena = Array.isArray(unknowns.phenomena) ? unknowns.phenomena : [];
    const rows = phenomena.map(row => {
      const cause = row.cause == null ? 'UNEXPLAINED' : String(row.cause);
      return '<tr>' +
        '<td><code title="' + h(row.phenomenon_signature || '') + '">' + h(row.phenomenon_id || short(row.phenomenon_signature || 'UNAVAILABLE')) + '</code></td>' +
        '<td class="' + statusClass(row.status) + '"><b>' + h(row.status || 'UNAVAILABLE') + '</b></td>' +
        '<td class="small"><b>' + h(row.structured_vs_noise_status || 'UNMEASURED') + '</b></td>' +
        '<td class="small">' + h(count(row.independent_episode_count)) + ' / ' + h(count(row.independent_episode_threshold)) + '</td>' +
        '<td class="small">' + h((row.source_engines || []).join(' · ') || 'UNAVAILABLE') + '</td>' +
        '<td class="small">' + h((row.failed_systems || []).join(' · ') || 'UNAVAILABLE') + '</td>' +
        '<td class="small">' + h((row.assets || []).join(' · ') || 'UNAVAILABLE') + '</td>' +
        '<td class="small">' + h((row.regimes || []).join(' · ') || 'UNAVAILABLE') + '</td>' +
        '<td class="small">' + h(cause) + '</td>' +
        '<td class="small">' + h((row.failed_explanations || []).join(' · ') || 'NONE RECORDED') + '</td>' +
        '<td class="small">' + h((row.candidate_ids || []).map(short).join(' · ') || 'NONE') + '</td>' +
        '<td class="small">' + h(row.next_stage || 'UNAVAILABLE') + '</td>' +
      '</tr>';
    }).join('');

    const contracts = unknowns.contracts || {};
    return '<section class="card" style="margin-top:12px">' +
      '<h3>UNKNOWN UNKNOWNS</h3>' +
      '<div class="small muted">Cross-engine residual replication and ontology-gap escalation. This does not duplicate NULLSPACE, EX NIHILO, APEX unknown-force, or reality-gap diagnostics; it persists and tests whether their unexplained failures recur independently.</div>' +
      '<div class="tiles" style="margin-top:10px">' +
        '<div class="tile"><div class="k">EVENTS</div><div class="v tnum">' + h(count(unknowns.event_count)) + '</div></div>' +
        '<div class="tile"><div class="k">PHENOMENA</div><div class="v tnum">' + h(count(unknowns.phenomenon_count)) + '</div></div>' +
        '<div class="tile"><div class="k">REPLICATED</div><div class="v tnum">' + h(count(unknowns.replicated_count)) + '</div></div>' +
        '<div class="tile"><div class="k">STRUCTURED CANDIDATES</div><div class="v tnum">' + h(count(unknowns.structured_candidate_count)) + '</div></div>' +
        '<div class="tile"><div class="k">UNMEASURED</div><div class="v tnum">' + h(count(unknowns.unmeasured_count)) + '</div></div>' +
        '<div class="tile"><div class="k">CAUSE POLICY</div><div class="v">UNEXPLAINED</div><div class="small muted">cause=None until separate validation</div></div>' +
      '</div>' +
      '<div class="small muted" style="margin:10px 0">' +
        'cause_remains_null_until_separate_validation=' + h(contracts.cause_remains_null_until_separate_validation === true ? 'true' : 'UNAVAILABLE') +
        ' · independent_episodes_required_for_replication=' + h(contracts.independent_episodes_required_for_replication === true ? 'true' : 'UNAVAILABLE') +
        ' · unavailable_evidence_cannot_confirm=' + h(contracts.unavailable_evidence_cannot_confirm === true ? 'true' : 'UNAVAILABLE') +
      '</div>' +
      '<div class="scroll" style="max-height:58vh"><table><thead><tr>' +
        '<th>Phenomenon</th><th>Status</th><th>STRUCTURED VS NOISE</th><th>INDEPENDENT EPISODES</th><th>Source engines</th><th>FAILED SYSTEMS</th><th>Assets</th><th>Regimes</th><th>Cause</th><th>FAILED EXPLANATIONS</th><th>CANDIDATE LINKS</th><th>Next stage</th>' +
      '</tr></thead><tbody>' +
        (rows || '<tr><td colspan="12" class="empty">UNAVAILABLE — no unexplained phenomena have been recorded.</td></tr>') +
      '</tbody></table></div>' +
      '<div class="small muted" style="margin-top:10px">EARLY → STRUCTURED_CANDIDATE → REPLICATED is based on independent episodes, not repeated messages from the same episode. A linked candidate is still only research.</div>' +
    '</section>';
  }

  function renderAscendancy(capabilities, genomes, foundry, unknowns, errors) {
    const el = document.querySelector('#ascendancyBody');
    if (!el) return;
    const warning = errors.length
      ? '<div class="empty" style="margin-bottom:10px">DEGRADED: ' + h(errors.join(' · ')) + '</div>'
      : '';
    el.innerHTML = warning + renderCapabilities(capabilities) + renderUnknowns(unknowns) + renderFoundry(foundry) + renderGenomeLab(genomes);
  }

  async function fetchJson(url, token) {
    const response = await fetch(url, {
      cache:'no-store',
      headers:{'Authorization':'Bearer ' + token}
    });
    let data = {};
    try { data = await response.json(); } catch (_) {}
    if (!response.ok) throw new Error(data.detail || ('ASCENDANCY HTTP ' + response.status + ' ' + url));
    return data;
  }

  async function loadAscendancy() {
    const seq = ++loadSeq;
    const el = document.querySelector('#ascendancyBody');
    if (!el) return;
    try {
      const token = localStorage.getItem('icarus-engine-token') || 'icarus';
      const settled = await Promise.allSettled([
        fetchJson('/api/ascendancy/capabilities', token),
        fetchJson('/api/ascendancy/genomes', token),
        fetchJson('/api/ascendancy/candidates', token),
        fetchJson('/api/ascendancy/unknowns', token)
      ]);
      if (seq !== loadSeq) return;
      const capabilities = settled[0].status === 'fulfilled' ? settled[0].value : null;
      const genomes = settled[1].status === 'fulfilled' ? settled[1].value : null;
      const foundry = settled[2].status === 'fulfilled' ? settled[2].value : null;
      const unknowns = settled[3].status === 'fulfilled' ? settled[3].value : null;
      const errors = settled
        .filter(x => x.status === 'rejected')
        .map(x => x.reason && x.reason.message ? x.reason.message : String(x.reason || 'UNAVAILABLE'));
      renderAscendancy(capabilities, genomes, foundry, unknowns, errors);
    } catch (err) {
      if (seq !== loadSeq) return;
      el.innerHTML = '<div class="empty">ASCENDANCY state UNAVAILABLE: ' + h(err && err.message ? err.message : err) + '</div>';
    }
  }

  function wireAscendancy() {
    const reload = document.querySelector('#ascendancyReload');
    if (reload) reload.addEventListener('click', loadAscendancy);
    loadAscendancy();
    if (timer) clearInterval(timer);
    timer = setInterval(() => {
      if ((location.hash || '#overview').slice(1) === 'ascendancy') loadAscendancy();
    }, 10000);
  }

  window.ascendancyHtml = ascendancyHtml;
  window.wireAscendancy = wireAscendancy;
  window.loadAscendancy = loadAscendancy;
})();

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
      return '<section class="card" style="margin-top:12px"><h3>ASCENDANCY UNKNOWN-UNKNOWN LAB</h3><div class="empty">UNAVAILABLE — unexplained-phenomenon state did not load.</div></section>';
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
      '<h3>ASCENDANCY UNKNOWN-UNKNOWN LAB</h3>' +
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

  function renderMechanisms(mechanisms) {
    if (!mechanisms) {
      return '<section class="card" style="margin-top:12px"><h3>MECHANISM LABORATORY</h3><div class="empty">UNAVAILABLE — mechanism extraction state did not load.</div></section>';
    }
    const rows = Array.isArray(mechanisms.mechanisms) ? mechanisms.mechanisms : [];
    const counts = {DIRECT_CONTRIBUTOR:0, INTERACTION_DEPENDENT:0, HARMFUL_LOOKING:0, UNRESOLVED:0};
    rows.forEach(row => {
      const key = String(row.classification || 'UNRESOLVED');
      counts[key] = (counts[key] || 0) + 1;
    });
    const body = rows.map(row => {
      const groups = (row.groups || []).map(g => {
        const ci = g.ci95_low == null || g.ci95_high == null
          ? 'UNMEASURED'
          : '[' + Number(g.ci95_low).toFixed(6) + ', ' + Number(g.ci95_high).toFixed(6) + ']';
        return String(g.experiment_kind || 'UNAVAILABLE') +
          ' · n=' + count(g.n) +
          ' · mean=' + (g.mean_effect == null ? 'UNMEASURED' : Number(g.mean_effect).toFixed(6)) +
          ' · CI95=' + ci +
          ' · sign=' + (g.sign_agreement == null ? 'UNMEASURED' : Number(g.sign_agreement).toFixed(3)) +
          ' · contract=' + short(g.evaluation_contract_hash || 'UNAVAILABLE') +
          ' · context=' + json(g.context || {});
      }).join(' | ');
      return '<tr>' +
        '<td><b>' + h(row.mechanism_key || 'UNAVAILABLE') + '</b></td>' +
        '<td class="' + statusClass(row.classification) + '"><b>' + h(row.classification || 'UNRESOLVED') + '</b></td>' +
        '<td><code>' + h(short(row.candidate_id || 'UNAVAILABLE')) + '</code></td>' +
        '<td class="small">' + h((row.related_mechanisms || []).join(' · ') || 'NONE') + '</td>' +
        '<td class="small">' + h(groups || 'UNMEASURED') + '</td>' +
        '<td class="small">causal_proof=false</td>' +
      '</tr>';
    }).join('');
    const truth = mechanisms.truth_contract || {};
    return '<section class="card" style="margin-top:12px">' +
      '<h3>MECHANISM LABORATORY</h3>' +
      '<div class="small muted">Paired ablation and interaction decomposition. Positive contribution is not structural causal proof.</div>' +
      '<div class="tiles" style="margin-top:10px">' +
        '<div class="tile"><div class="k">EXPERIMENTS</div><div class="v tnum">' + h(count(mechanisms.experiment_count)) + '</div></div>' +
        '<div class="tile"><div class="k">DIRECT_CONTRIBUTOR</div><div class="v tnum">' + h(count(counts.DIRECT_CONTRIBUTOR)) + '</div></div>' +
        '<div class="tile"><div class="k">INTERACTION_DEPENDENT</div><div class="v tnum">' + h(count(counts.INTERACTION_DEPENDENT)) + '</div></div>' +
        '<div class="tile"><div class="k">HARMFUL_LOOKING</div><div class="v tnum">' + h(count(counts.HARMFUL_LOOKING)) + '</div></div>' +
        '<div class="tile"><div class="k">UNRESOLVED</div><div class="v tnum">' + h(count(counts.UNRESOLVED)) + '</div></div>' +
        '<div class="tile"><div class="k">AUTHORITY</div><div class="v">RESEARCH ONLY</div><div class="small muted">execution_authorized=false · production_decision_authorized=false</div></div>' +
      '</div>' +
      '<div class="small muted" style="margin:10px 0">' +
        'mechanism_attribution_is_not_causal_proof=' + h(truth.mechanism_attribution_is_not_causal_proof === true ? 'true' : 'UNAVAILABLE') +
        ' · contracts_and_contexts_are_never_pooled=' + h(truth.contracts_and_contexts_are_never_pooled === true ? 'true' : 'UNAVAILABLE') +
        ' · independent_episode_identity_prevents_duplicate_counting=' + h(truth.independent_episode_identity_prevents_duplicate_counting === true ? 'true' : 'UNAVAILABLE') +
      '</div>' +
      '<div class="scroll" style="max-height:58vh"><table><thead><tr>' +
        '<th>Mechanism</th><th>Classification</th><th>Candidate</th><th>Related mechanisms</th><th>Paired evidence groups</th><th>Causal status</th>' +
      '</tr></thead><tbody>' +
        (body || '<tr><td colspan="6" class="empty">UNMEASURED — no paired mechanism experiments recorded.</td></tr>') +
      '</tbody></table></div>' +
    '</section>';
  }

  function renderInventions(inventions) {
    if (!inventions) {
      return '<section class="card" style="margin-top:12px"><h3>INVENTION ENGINE</h3><div class="empty">UNAVAILABLE — invention state did not load.</div></section>';
    }
    const blueprints = Array.isArray(inventions.blueprints) ? inventions.blueprints : [];
    const truth = inventions.truth_contract || {};
    const rows = blueprints.map(row => {
      const families = Array.isArray(row.primitive_families) ? row.primitive_families : [];
      const primitives = Array.isArray(row.primitive_ids) ? row.primitive_ids : [];
      const falsifiers = Array.isArray(row.falsifiers) ? row.falsifiers : [];
      return '<tr>' +
        '<td><code title="' + h(row.blueprint_id || '') + '">' + h(short(row.blueprint_id || 'UNAVAILABLE')) + '</code></td>' +
        '<td class="w"><b>' + h(row.status || 'UNTESTED_HYPOTHESIS') + '</b></td>' +
        '<td>' + h(row.target_role || 'UNAVAILABLE') + '</td>' +
        '<td class="small">' + h(primitives.join(' → ') || 'UNAVAILABLE') + '</td>' +
        '<td class="small">' + h(families.join(' · ') || 'UNAVAILABLE') + '</td>' +
        '<td class="small">depth=' + h(count(row.depth)) + ' · cost=' + h(count(row.estimated_cost_units)) + '</td>' +
        '<td class="small">' + h(row.hypothesis || 'UNAVAILABLE') + '</td>' +
        '<td class="small">' + h(falsifiers.join(' · ') || 'UNAVAILABLE') + '</td>' +
        '<td class="small">edge_claim_established=false</td>' +
      '</tr>';
    }).join('');

    const familyCounts = inventions.family_counts || {};
    const familySummary = Object.keys(familyCounts).sort().map(k => k + '=' + familyCounts[k]).join(' · ');
    return '<section class="card" style="margin-top:12px">' +
      '<h3>INVENTION ENGINE</h3>' +
      '<div class="small muted">Bounded typed mathematical search creates reproducible hypotheses; it does not execute arbitrary generated code and it does not establish edge.</div>' +
      '<div class="tiles" style="margin-top:10px">' +
        '<div class="tile"><div class="k">BLUEPRINTS</div><div class="v tnum">' + h(count(inventions.blueprint_count)) + '</div></div>' +
        '<div class="tile"><div class="k">PRIMITIVES</div><div class="v tnum">' + h(count((inventions.primitive_catalog || []).length)) + '</div></div>' +
        '<div class="tile"><div class="k">STATUS</div><div class="v">UNTESTED_HYPOTHESIS</div></div>' +
        '<div class="tile"><div class="k">EDGE CLAIM</div><div class="v">FALSE</div><div class="small muted">edge_claim_established=false</div></div>' +
        '<div class="tile"><div class="k">CODE EXECUTION</div><div class="v">DISABLED</div><div class="small muted">arbitrary_source_code_execution=false</div></div>' +
        '<div class="tile"><div class="k">AUTHORITY</div><div class="v">RESEARCH ONLY</div><div class="small muted">execution_authorized=false · production_decision_authorized=false</div></div>' +
      '</div>' +
      '<div class="small muted" style="margin:10px 0">' +
        'generated_blueprint_is_not_validated_edge=' + h(truth.generated_blueprint_is_not_validated_edge === true ? 'true' : 'UNAVAILABLE') +
        ' · unavailable_observations_cannot_seed_transformations=' + h(truth.unavailable_observations_cannot_seed_transformations === true ? 'true' : 'UNAVAILABLE') +
        ' · search_is_bounded_by_depth_candidate_count_and_cost=' + h(truth.search_is_bounded_by_depth_candidate_count_and_cost === true ? 'true' : 'UNAVAILABLE') +
        ' · arbitrary_source_code_execution=false' +
      '</div>' +
      '<div class="small muted">primitive_families: ' + h(familySummary || 'UNMEASURED') + '</div>' +
      '<div class="scroll" style="max-height:58vh;margin-top:10px"><table><thead><tr>' +
        '<th>Blueprint</th><th>Status</th><th>Target role</th><th>Primitive chain</th><th>primitive_families</th><th>Depth / cost</th><th>Hypothesis</th><th>Falsifiers</th><th>Edge</th>' +
      '</tr></thead><tbody>' +
        (rows || '<tr><td colspan="9" class="empty">UNMEASURED — no invention blueprints generated.</td></tr>') +
      '</tbody></table></div>' +
    '</section>';
  }

  function renderContributions(contributions) {
    if (!contributions) {
      return '<section class="card" style="margin-top:12px"><h3>INFORMATION CONTRIBUTION MATRIX</h3><div class="empty">UNAVAILABLE — conditional contribution state did not load.</div></section>';
    }
    const groups = Array.isArray(contributions.groups) ? contributions.groups : [];
    const counts = {
      SUPPORTED_INCREMENTAL: 0,
      SUPPORTED_HARMFUL_OR_REDUNDANT: 0,
      UNRESOLVED: 0,
      INSUFFICIENT_EVIDENCE: 0
    };
    groups.forEach(row => {
      const key = String(row.classification || 'UNRESOLVED');
      counts[key] = (counts[key] || 0) + 1;
    });
    const rows = groups.map(row => {
      const ci = row.ci95_low == null || row.ci95_high == null
        ? 'UNMEASURED'
        : '[' + Number(row.ci95_low).toFixed(6) + ', ' + Number(row.ci95_high).toFixed(6) + ']';
      const mean = row.mean_information_gain_nats == null
        ? 'UNMEASURED'
        : Number(row.mean_information_gain_nats).toFixed(6);
      const bits = row.bits_per_observation == null
        ? 'UNMEASURED'
        : Number(row.bits_per_observation).toFixed(6);
      const positive = row.positive_fraction == null
        ? 'UNMEASURED'
        : Number(row.positive_fraction).toFixed(3);
      return '<tr>' +
        '<td><code title="' + h(row.contributor_id || '') + '">' + h(short(row.contributor_id || 'UNAVAILABLE')) + '</code><div class="small muted">' + h(row.contributor_kind || 'UNAVAILABLE') + '</div></td>' +
        '<td class="' + statusClass(row.classification) + '"><b>' + h(row.classification || 'UNRESOLVED') + '</b></td>' +
        '<td class="small">' + h((row.conditioning_set || []).join(' · ') || 'UNAVAILABLE') + '</td>' +
        '<td class="small">' + h(row.target_key || 'UNAVAILABLE') + ' · ' + h(count(row.horizon_seconds)) + 's · ' + h(row.target_kind || 'UNAVAILABLE') + '</td>' +
        '<td class="small">' + h(json(row.context || {})) + '</td>' +
        '<td class="tnum">' + h(count(row.n)) + '</td>' +
        '<td class="tnum">' + h(mean) + '</td>' +
        '<td class="tnum">' + h(bits) + '</td>' +
        '<td class="small">' + h(ci) + '</td>' +
        '<td class="tnum">' + h(positive) + '</td>' +
        '<td class="small">' + h(row.estimator || 'paired_predictive_log_score_gain') + '<br><span class="muted">exact_conditional_mutual_information=false · causal_proof=false</span></td>' +
      '</tr>';
    }).join('');
    const truth = contributions.truth_contract || {};
    return '<section class="card" style="margin-top:12px">' +
      '<h3>INFORMATION CONTRIBUTION MATRIX</h3>' +
      '<div class="small muted">Measures whether a contributor improves paired predictive log score after conditioning on an explicit ICARUS baseline. Structural novelty and standalone performance do not count as incremental information.</div>' +
      '<div class="tiles" style="margin-top:10px">' +
        '<div class="tile"><div class="k">OBSERVATIONS</div><div class="v tnum">' + h(count(contributions.observation_count)) + '</div></div>' +
        '<div class="tile"><div class="k">COMPARISON GROUPS</div><div class="v tnum">' + h(count(contributions.group_count)) + '</div></div>' +
        '<div class="tile"><div class="k">SUPPORTED INCREMENTAL</div><div class="v tnum">' + h(count(counts.SUPPORTED_INCREMENTAL)) + '</div></div>' +
        '<div class="tile"><div class="k">HARMFUL / REDUNDANT</div><div class="v tnum">' + h(count(counts.SUPPORTED_HARMFUL_OR_REDUNDANT)) + '</div></div>' +
        '<div class="tile"><div class="k">UNRESOLVED / INSUFFICIENT</div><div class="v tnum">' + h(count((counts.UNRESOLVED || 0) + (counts.INSUFFICIENT_EVIDENCE || 0))) + '</div></div>' +
        '<div class="tile"><div class="k">AUTHORITY</div><div class="v">RESEARCH ONLY</div><div class="small muted">execution_authorized=false · production_decision_authorized=false</div></div>' +
      '</div>' +
      '<div class="small muted" style="margin:10px 0">' +
        'estimator=' + h(truth.estimator || 'paired_predictive_log_score_gain') +
        ' · exact_conditional_mutual_information=' + h(truth.exact_conditional_mutual_information === false ? 'false' : 'UNAVAILABLE') +
        ' · standalone_performance_is_not_incremental_information=' + h(truth.standalone_performance_is_not_incremental_information === true ? 'true' : 'UNAVAILABLE') +
        ' · contracts_contexts_horizons_and_conditioning_sets_are_never_pooled=' + h(truth.contracts_contexts_horizons_and_conditioning_sets_are_never_pooled === true ? 'true' : 'UNAVAILABLE') +
      '</div>' +
      '<div class="scroll" style="max-height:58vh"><table><thead><tr>' +
        '<th>Contributor</th><th>Classification</th><th>CONDITIONING SET</th><th>Target / horizon</th><th>Context</th><th>N</th><th>MEAN GAIN (NATS)</th><th>BITS / OBS</th><th>CI95</th><th>Positive fraction</th><th>Estimator / truth</th>' +
      '</tr></thead><tbody>' +
        (rows || '<tr><td colspan="11" class="empty">UNMEASURED — no paired conditional-contribution observations recorded.</td></tr>') +
      '</tbody></table></div>' +
    '</section>';
  }

  function renderPeers(brain) {
    const sync = brain && brain.remote_sync ? brain.remote_sync : null;
    if (!sync) {
      return '<section class="card" style="margin-top:12px"><h3>FEDERATED ICARUS-ENGINE CONTEXT</h3><div class="empty">UNAVAILABLE — Adaptive Brain remote federation state did not load.</div></section>';
    }
    const lanes = Array.isArray(sync.peer_lanes) ? sync.peer_lanes : [];
    const historical = Array.isArray(sync.historical_context_sources) ? sync.historical_context_sources : [];
    const laneRows = lanes.map(row => '<tr>' +
      '<td><b>' + h(row.name || 'UNAVAILABLE') + '</b><div class="small muted">' + h(row.worker_repository || 'UNAVAILABLE') + '</div></td>' +
      '<td class="' + statusClass(row.evidence_status) + '"><b>' + h(row.evidence_status || 'UNMEASURED') + '</b></td>' +
      '<td class="small">' + h(row.run_id || 'UNAVAILABLE') + '<br>' + h(row.run_status || 'UNAVAILABLE') + '</td>' +
      '<td class="small">worker_execution_observed=' + h(row.worker_execution_observed === true ? 'true' : row.worker_execution_observed === false ? 'false' : 'UNMEASURED') +
        '<br>substantive_research_evidence=' + h(row.substantive_research_evidence === true ? 'true' : 'false') + '</td>' +
    '</tr>').join('');

    const historyRows = historical.map(row => {
      const summary = row.summary || {};
      const keys = Object.keys(summary);
      const summaryText = keys.map(key => key + '=' + JSON.stringify(summary[key])).join(' · ');
      return '<tr>' +
        '<td><b>' + h(row.id || 'UNAVAILABLE') + '</b><div class="small muted">' + h(row.path || '') + '</div></td>' +
        '<td><span class="chip ' + statusClass(row.evidence_status) + '">' + h(row.evidence_status || 'UNMEASURED') + '</span></td>' +
        '<td><code title="' + h(row.remote_blob_sha || '') + '">' + h(short(row.remote_blob_sha || 'UNAVAILABLE')) + '</code></td>' +
        '<td class="small">' + h(row.run_id || 'UNAVAILABLE') + '<br>' + h(row.run_status || 'UNAVAILABLE') + '</td>' +
        '<td class="small">' + h(summaryText || 'NO BOUNDED SUMMARY CLAIMS') + '</td>' +
        '<td class="small">research_context=true<br>candidate evidence=false<br>requires Foundry + Evaluator=true<br>foreign evidence only=true</td>' +
      '</tr>';
    }).join('');

    const truth = sync.truth_contract || {};
    return '<section class="card" style="margin-top:12px">' +
      '<h3>FEDERATED ICARUS-ENGINE CONTEXT</h3>' +
      '<div class="small muted">Canonical Adaptive Brain federation · current peer state + bounded historical research context · exact Git provenance · no authority transfer.</div>' +
      '<div class="tiles" style="margin-top:10px">' +
        '<div class="tile"><div class="k">FEDERATION</div><div class="v ' + statusClass(sync.status) + '">' + h(String(sync.status || 'UNMEASURED').toUpperCase()) + '</div></div>' +
        '<div class="tile"><div class="k">PEER PACKET</div><div class="v ' + statusClass(sync.peer_packet_status) + '">' + h(String(sync.peer_packet_status || 'UNMEASURED').toUpperCase()) + '</div><div class="small muted">fresh=' + h(sync.peer_packet_fresh === true ? 'true' : 'false') + ' · age ' + h(sync.peer_packet_age_seconds == null ? 'UNMEASURED' : sync.peer_packet_age_seconds) + 's</div></div>' +
        '<div class="tile"><div class="k">PEER SOURCE COMMIT</div><div class="v tnum">' + h(short(sync.peer_source_commit || 'UNAVAILABLE')) + '</div><div class="small muted">verified=' + h(sync.peer_source_commit_verified === true ? 'true' : 'false') + ' · ' + h(sync.peer_source_commit_relation || 'UNMEASURED') + '</div></div>' +
        '<div class="tile"><div class="k">SUBSTANTIVE LANES</div><div class="v tnum">' + h(count(sync.peer_substantive_lane_count)) + '</div><div class="small muted">durability-only ' + h(count(sync.peer_durability_only_lane_count)) + '</div></div>' +
        '<div class="tile"><div class="k">HISTORICAL CONTEXT</div><div class="v ' + statusClass(sync.historical_context_status) + '">' + h(String(sync.historical_context_status || 'UNMEASURED').toUpperCase()) + '</div><div class="small muted">sources ' + h(count(sync.historical_context_source_count)) + ' · ingested ' + h(count(sync.historical_context_ingested_total)) + '</div></div>' +
        '<div class="tile"><div class="k">HISTORICAL CANDIDATE EVIDENCE</div><div class="v tnum">' + h(count(sync.historical_candidate_evidence_count)) + '</div><div class="small muted">must remain 0; context cannot bypass Foundry/Evaluator</div></div>' +
        '<div class="tile"><div class="k">AUTHORITY</div><div class="v">RESEARCH OBSERVABILITY ONLY</div><div class="small muted">execution=false · production decision=false · automatic promotion=false</div></div>' +
      '</div>' +
      '<div class="small muted" style="margin:10px 0">' +
        'federation_schema=' + h(truth.federation_schema || 'UNAVAILABLE') +
        ' · durability_receipts_are_substantive_evidence=' + h(truth.durability_receipts_are_substantive_evidence === false ? 'false' : 'UNAVAILABLE') +
        ' · historical_context_never_bypasses_foundry=' + h(truth.historical_context_never_bypasses_foundry === true ? 'true' : 'UNAVAILABLE') +
        ' · historical_context_never_bypasses_evaluator=' + h(truth.historical_context_never_bypasses_evaluator === true ? 'true' : 'UNAVAILABLE') +
      '</div>' +
      '<h4 style="margin:12px 0 6px">CURRENT PEER LANES</h4>' +
      '<div class="scroll"><table><thead><tr><th>Lane</th><th>Evidence status</th><th>Run</th><th>Evidence boundary</th></tr></thead><tbody>' +
        (laneRows || '<tr><td colspan="4" class="empty">UNMEASURED — no current peer lane state.</td></tr>') +
      '</tbody></table></div>' +
      '<h4 style="margin:14px 0 6px">HISTORICAL RESEARCH CONTEXT</h4>' +
      '<div class="scroll" style="max-height:44vh"><table><thead><tr><th>Source</th><th>Evidence class</th><th>Git blob</th><th>Run</th><th>Bounded context</th><th>Admission boundary</th></tr></thead><tbody>' +
        (historyRows || '<tr><td colspan="6" class="empty">UNMEASURED — no historical peer context.</td></tr>') +
      '</tbody></table></div>' +
    '</section>';
  }

  function renderFederatedIntake(intake) {
    if (!intake) {
      return '<section class="card" style="margin-top:12px"><h3>FEDERATED RESEARCH INTAKE</h3><div class="empty">UNAVAILABLE — federated intake state did not load.</div></section>';
    }
    const rows = Array.isArray(intake.proposals) ? intake.proposals : [];
    const kinds = intake.proposal_kind_counts || {};
    const body = rows.map(row =>
      '<tr>' +
        '<td><code title="' + h(row.proposal_id || '') + '">' + h(short(row.proposal_id || 'UNAVAILABLE')) + '</code></td>' +
        '<td><b>' + h(row.proposal_kind || 'UNAVAILABLE') + '</b><div class="small muted">' + h(row.source_id || 'UNAVAILABLE') + '</div></td>' +
        '<td class="small"><code>' + h(short(row.source_commit || 'UNAVAILABLE')) + '</code><br>blob <code>' + h(short(row.source_blob_sha || 'UNAVAILABLE')) + '</code></td>' +
        '<td class="small">' + h(row.research_question || 'UNAVAILABLE') + '</td>' +
        '<td class="small">' + h(row.claim_status || 'UNAVAILABLE') + '<br>' + h(row.source_evidence_status || 'UNAVAILABLE') + '</td>' +
        '<td class="small"><b>' + h(row.admission_state || 'RESEARCH_PROMPT_ONLY') + '</b><br>candidate evidence=false<br>automatic candidate creation=false<br>requires Foundry + Evaluator=true</td>' +
      '</tr>'
    ).join('');
    const kindText = Object.keys(kinds).sort().map(key => key + '=' + kinds[key]).join(' · ');

    return '<section class="card" style="margin-top:12px">' +
      '<h3>FEDERATED RESEARCH INTAKE</h3>' +
      '<div class="small muted">Verified Icarus-engine historical context becomes bounded replication targets and research questions. It does not become local truth, candidate evidence, or a Foundry candidate.</div>' +
      '<div class="tiles" style="margin-top:10px">' +
        '<div class="tile"><div class="k">RESEARCH PROMPTS</div><div class="v tnum">' + h(count(intake.proposal_count)) + '</div></div>' +
        '<div class="tile"><div class="k">PEER SOURCES</div><div class="v tnum">' + h(count(intake.source_repository_count)) + '</div></div>' +
        '<div class="tile"><div class="k">SOURCE REVISIONS</div><div class="v tnum">' + h(count((intake.source_commits || []).length)) + '</div></div>' +
        '<div class="tile"><div class="k">CANDIDATE EVIDENCE</div><div class="v tnum">' + h(count(intake.candidate_evidence_count)) + '</div><div class="small muted">must remain 0</div></div>' +
        '<div class="tile"><div class="k">ADMISSION</div><div class="v">RESEARCH_PROMPT_ONLY</div><div class="small muted">automatic candidate creation=false · automatic model promotion=false</div></div>' +
        '<div class="tile"><div class="k">AUTHORITY</div><div class="v">RESEARCH ONLY</div><div class="small muted">execution_authorized=false · production_decision_authorized=false</div></div>' +
      '</div>' +
      '<div class="small muted" style="margin:10px 0">' + h(kindText || 'No federated research prompts yet.') + '</div>' +
      '<div class="scroll" style="max-height:54vh"><table><thead><tr>' +
        '<th>Prompt</th><th>Investigation</th><th>Exact peer provenance</th><th>Research question</th><th>Claim status</th><th>Admission boundary</th>' +
      '</tr></thead><tbody>' +
        (body || '<tr><td colspan="6" class="empty">UNMEASURED — run ASCENDANCY federated intake after canonical peer synchronization.</td></tr>') +
      '</tbody></table></div>' +
    '</section>';
  }

  function renderEvaluator(evaluator) {
    if (!evaluator) {
      return '<section class="card" style="margin-top:12px"><h3>ASCENDANCY EVALUATOR CASCADE · RESOURCE ECONOMY</h3><div class="empty">UNAVAILABLE — staged evaluator state did not load.</div></section>';
    }
    const candidates = Array.isArray(evaluator.candidates) ? evaluator.candidates : [];
    const stages = Array.isArray(evaluator.stage_catalog) ? evaluator.stage_catalog : [];
    const exposures = Array.isArray(evaluator.holdout_exposures) ? evaluator.holdout_exposures : [];
    const stateCounts = evaluator.state_counts || {};
    const truth = evaluator.truth_contract || {};

    const candidateRows = candidates.map(row => {
      const used = row.resource_used || {};
      const remaining = row.resource_remaining || {};
      return '<tr>' +
        '<td><code title="' + h(row.candidate_id || '') + '">' + h(short(row.candidate_id || 'UNAVAILABLE')) + '</code></td>' +
        '<td class="' + statusClass(row.state) + '"><b>' + h(row.state || 'UNAVAILABLE') + '</b></td>' +
        '<td><b>' + h(row.next_stage || 'COMPLETE / HALTED') + '</b></td>' +
        '<td class="tnum">' + h(count(row.completed_stage_count)) + ' / ' + h(count(stages.length)) + '</td>' +
        '<td class="small">eval=' + h(count(used.evaluations)) + ' · wall=' + h(count(used.wall_seconds)) + 's · cost=' + h(count(used.cost_units)) + '</td>' +
        '<td class="small">eval=' + h(count(remaining.evaluations)) + ' · wall=' + h(count(remaining.wall_seconds)) + 's · cost=' + h(count(remaining.cost_units)) + '</td>' +
        '<td class="small">qualified_shadow=false · execution_authorized=false</td>' +
      '</tr>';
    }).join('');

    const stageRows = stages.map(row =>
      '<tr>' +
        '<td class="tnum">' + h(count(row.stage_index)) + '</td>' +
        '<td><b>' + h(row.id || 'UNAVAILABLE') + '</b></td>' +
        '<td>' + h(row.fidelity || 'UNAVAILABLE') + '</td>' +
        '<td class="small">' + h(row.purpose || 'UNAVAILABLE') + '</td>' +
        '<td class="small">grants_qualification=' + h(row.grants_qualification === false ? 'false' : 'UNAVAILABLE') + '</td>' +
      '</tr>'
    ).join('');

    const exposureRows = exposures.map(row =>
      '<tr>' +
        '<td><b>' + h(row.holdout_id || 'UNAVAILABLE') + '</b></td>' +
        '<td><code>' + h(short(row.evaluation_contract_hash || 'UNAVAILABLE')) + '</code></td>' +
        '<td><code>' + h(short(row.candidate_id || 'UNAVAILABLE')) + '</code></td>' +
        '<td class="small">' + h(row.observed_at || 'UNAVAILABLE') + '</td>' +
      '</tr>'
    ).join('');

    return '<section class="card" style="margin-top:12px">' +
      '<h3>ASCENDANCY EVALUATOR CASCADE · RESOURCE ECONOMY</h3>' +
      '<div class="small muted">Multi-fidelity elimination spends cheap evidence first, escalates only survivors, locks protected-holdout generations after exposure, and ends at QUALIFICATION_PREFLIGHT without self-qualification.</div>' +
      '<div class="tiles" style="margin-top:10px">' +
        '<div class="tile"><div class="k">ENROLLED</div><div class="v tnum">' + h(count(evaluator.candidate_count)) + '</div></div>' +
        '<div class="tile"><div class="k">EVALUATING</div><div class="v tnum">' + h(count(stateCounts.EVALUATING)) + '</div></div>' +
        '<div class="tile"><div class="k">HALTED FAILED</div><div class="v tnum">' + h(count(stateCounts.HALTED_FAILED)) + '</div></div>' +
        '<div class="tile"><div class="k">READY FOR QUALIFICATION</div><div class="v tnum">' + h(count(stateCounts.READY_FOR_PROTECTED_QUALIFICATION)) + '</div></div>' +
        '<div class="tile"><div class="k">PROTECTED HOLDOUT EXPOSURES</div><div class="v tnum">' + h(count(evaluator.holdout_exposure_count)) + '</div></div>' +
        '<div class="tile"><div class="k">AUTHORITY</div><div class="v">RESEARCH ONLY</div><div class="small muted">qualified_shadow=false · production_decision_authorized=false</div></div>' +
      '</div>' +
      '<div class="small muted" style="margin:10px 0">' +
        'cascade_cannot_mint_qualification=' + h(truth.cascade_cannot_mint_qualification === true ? 'true' : 'UNAVAILABLE') +
        ' · protected_holdout_exposure_is_consumable=' + h(truth.protected_holdout_exposure_is_consumable === true ? 'true' : 'UNAVAILABLE') +
        ' · research_priority_is_expected_information_gain_per_cost=' + h(truth.research_priority_is_expected_information_gain_per_cost === true ? 'true' : 'UNAVAILABLE') +
        ' · resource_budget_checked_before_receipt_commit=' + h(truth.resource_budget_checked_before_receipt_commit === true ? 'true' : 'UNAVAILABLE') +
      '</div>' +
      '<h3 style="margin-top:14px">CANDIDATE CASCADE STATE</h3>' +
      '<div class="scroll"><table><thead><tr><th>Candidate</th><th>State</th><th>NEXT STAGE</th><th>Stages passed</th><th>RESOURCE USED</th><th>RESOURCE REMAINING</th><th>Authority</th></tr></thead><tbody>' +
        (candidateRows || '<tr><td colspan="7" class="empty">UNMEASURED — no candidates enrolled in evaluator cascade.</td></tr>') +
      '</tbody></table></div>' +
      '<h3 style="margin-top:14px">MULTI-FIDELITY STAGE CATALOG</h3>' +
      '<div class="scroll"><table><thead><tr><th>#</th><th>Stage</th><th>Fidelity</th><th>Purpose</th><th>Qualification authority</th></tr></thead><tbody>' +
        (stageRows || '<tr><td colspan="5" class="empty">UNAVAILABLE — evaluator stage catalog missing.</td></tr>') +
      '</tbody></table></div>' +
      '<h3 style="margin-top:14px">HOLDOUT EXPOSURES</h3>' +
      '<div class="scroll"><table><thead><tr><th>PROTECTED HOLDOUT</th><th>Evaluator contract</th><th>Candidate</th><th>Observed</th></tr></thead><tbody>' +
        (exposureRows || '<tr><td colspan="4" class="small muted">No protected holdout generation has been exposed.</td></tr>') +
      '</tbody></table></div>' +
    '</section>';
  }

  function renderAscendancy(capabilities, genomes, foundry, unknowns, mechanisms, inventions, contributions, evaluator, peers, intake, errors) {
    const el = document.querySelector('#ascendancyBody');
    if (!el) return;
    const warning = errors.length
      ? '<div class="empty" style="margin-bottom:10px">DEGRADED: ' + h(errors.join(' · ')) + '</div>'
      : '';
    el.innerHTML = warning + renderCapabilities(capabilities) + renderPeers(peers) + renderFederatedIntake(intake) + renderUnknowns(unknowns) + renderInventions(inventions) + renderFoundry(foundry) + renderEvaluator(evaluator) + renderContributions(contributions) + renderMechanisms(mechanisms) + renderGenomeLab(genomes);
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
        fetchJson('/api/ascendancy/unknowns', token),
        fetchJson('/api/ascendancy/mechanisms', token),
        fetchJson('/api/ascendancy/inventions', token),
        fetchJson('/api/ascendancy/contributions', token),
        fetchJson('/api/ascendancy/evaluator', token),
        fetchJson('/api/brain', token),
        fetchJson('/api/ascendancy/federated-intake', token)
      ]);
      if (seq !== loadSeq) return;
      const capabilities = settled[0].status === 'fulfilled' ? settled[0].value : null;
      const genomes = settled[1].status === 'fulfilled' ? settled[1].value : null;
      const foundry = settled[2].status === 'fulfilled' ? settled[2].value : null;
      const unknowns = settled[3].status === 'fulfilled' ? settled[3].value : null;
      const mechanisms = settled[4].status === 'fulfilled' ? settled[4].value : null;
      const inventions = settled[5].status === 'fulfilled' ? settled[5].value : null;
      const contributions = settled[6].status === 'fulfilled' ? settled[6].value : null;
      const evaluator = settled[7].status === 'fulfilled' ? settled[7].value : null;
      const peers = settled[8].status === 'fulfilled' ? settled[8].value : null;
      const intake = settled[9].status === 'fulfilled' ? settled[9].value : null;
      const errors = settled
        .filter(x => x.status === 'rejected')
        .map(x => x.reason && x.reason.message ? x.reason.message : String(x.reason || 'UNAVAILABLE'));
      renderAscendancy(capabilities, genomes, foundry, unknowns, mechanisms, inventions, contributions, evaluator, peers, intake, errors);
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

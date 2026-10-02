(() => {
  let timer = null;

  const h = value => String(value ?? '').replace(/[&<>"]/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[ch]));
  const pct = value => (typeof value === 'number' && Number.isFinite(value)) ? (value * 100).toFixed(1) + '%' : 'UNMEASURED';
  const num = value => (typeof value === 'number' && Number.isFinite(value)) ? value.toLocaleString() : '—';

  function statusClass(value) {
    const s = String(value || '').toUpperCase();
    if (s.includes('VERIFIED') || s.includes('ACTIVE') || s.includes('RUN_PERSISTED') || s === 'QUALIFIED' || s === 'GREEN' || s === 'PERSISTED_WORKER_EVIDENCE') return 'brain-good';
    if (s.includes('BLOCK') || s.includes('REJECT') || s.includes('FAIL') || s.includes('ERROR')) return 'brain-bad';
    return 'brain-warn';
  }

  function brainHtml() {
    return `<section class="card c12 brain-shell" id="brainPanel">
      <style>
        .brain-shell{position:relative;overflow:hidden;min-height:520px;background:
          radial-gradient(circle at 50% 8%,rgba(86,225,255,.16),transparent 34%),
          radial-gradient(circle at 92% 42%,rgba(145,92,255,.12),transparent 32%),
          linear-gradient(145deg,var(--surface),rgba(20,34,44,.92));}
        .brain-shell:before{content:"";position:absolute;inset:0;pointer-events:none;background:
          linear-gradient(rgba(95,232,255,.035) 1px,transparent 1px),
          linear-gradient(90deg,rgba(95,232,255,.035) 1px,transparent 1px);background-size:28px 28px;mask-image:linear-gradient(to bottom,black,transparent 92%)}
        .brain-layer{position:relative;z-index:1}
        .brain-title{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin-bottom:12px}
        .brain-core{border:1px solid rgba(95,232,255,.35);box-shadow:0 0 40px rgba(95,232,255,.08) inset;border-radius:18px;padding:16px;background:rgba(8,18,25,.28)}
        .brain-orbit{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:10px}
        .brain-agent,.brain-sub,.brain-lane{border:1px solid var(--ring);background:rgba(255,255,255,.025);border-radius:12px;padding:10px}
        .brain-agent b,.brain-sub b{letter-spacing:.04em}
        .brain-good{color:var(--good-text);border-color:var(--good)!important}.brain-bad{color:var(--crit);border-color:var(--crit)!important}.brain-warn{color:var(--warn);border-color:var(--warn)!important}
        .brain-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:10px}
        .brain-gate{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:6px;margin-top:8px}
        .brain-gate span{font-size:11px;padding:5px 7px;border:1px solid var(--ring);border-radius:8px}
        .brain-pulse{width:11px;height:11px;border-radius:50%;background:#67e8f9;box-shadow:0 0 0 0 rgba(103,232,249,.65);animation:brainPulse 1.8s infinite}
        @keyframes brainPulse{70%{box-shadow:0 0 0 14px rgba(103,232,249,0)}100%{box-shadow:0 0 0 0 rgba(103,232,249,0)}}
        .brain-route{font:11px/1.5 ui-monospace,Consolas,monospace;background:rgba(0,0,0,.16);border-radius:8px;padding:8px;margin-top:6px;white-space:pre-wrap}
      </style>
      <div class="brain-layer"><h2>Adaptive Brain <span class="sub">multi-agent learning fabric · evidence-backed · router SHADOW_ONLY</span></h2><div class="empty">loading measured brain state…</div></div>
    </section>`;
  }

  function renderBrain(b) {
    const el = document.querySelector('#brainPanel');
    if (!el) return;
    const auth = b.authority || {}, learn = b.learning || {}, truth = b.truth_contract || {}, sync = b.remote_sync || {}, agentContract = sync.truth_contract || {}, inc = b.incubator || {}, researchSync = b.research_sync || {}, evidenceLab = b.evidence_lab_sync || {}, proof = b.performance_proof || {}, latency = b.latency_telemetry || {}, graph = b.evidence_graph || {}, reliability = b.source_reliability || {}, qualification = b.qualification_receipts || {};
    const agents = ((b.architecture || {}).agents || []);
    const subs = ((b.architecture || {}).subsystems || []);
    const lanes = ((b.architecture || {}).latency_tiers || []);
    const candidates = b.candidates || [];
    const routes = b.regime_routes || [];
    const regimes = ((b.market || {}).regimes || []);
    const tournaments = b.evidence_tournaments || [];
    const proofMetrics = proof.metrics || {}, proofClosed = proof.closed_sample || {}, proofReplay = proof.replay || {};
    const proofBacklog = proof.settlement_backlog || {};
    const hotLatency = latency.hot_path || {};
    const graphMetrics = graph.metrics || {};
    const reliabilityRows = reliability.sources || [];
    const measuredReliability = reliabilityRows.filter(r => r.measurement_status === "MEASURED").length;
    const qualificationRows = qualification.candidates || [];
    const peerLanes = sync.peer_lanes || [];
    const peerLaneRows = peerLanes.map(l => `<tr><td><b>${h(l.title||l.name||"")}</b><div class="small muted">${h(l.name||"")}</div></td><td><span class="chip ${statusClass(l.evidence_status)}">${h(l.evidence_status||"UNKNOWN")}</span></td><td>${h(l.run_id||"—")}</td><td>${l.worker_execution_observed===true?"OBSERVED":l.worker_execution_observed===false?"NOT OBSERVED":"UNMEASURED"}</td><td class="${l.source_witness_verified?"brain-good":l.source_witness_status==="REMOTE_PEER_UNREAD"?"muted":"brain-warn"}">${h(l.source_witness_status||"UNVERIFIED")}<div class="small muted">blobs ${num(l.source_witness_blob_count)}</div></td><td class="${l.substantive_research_evidence?"brain-good":"muted"}">${l.substantive_research_evidence?"YES":"NO"}</td></tr>`).join("");
    const historicalContext = sync.historical_context_sources || [];
    const historicalWitnesses = sync.historical_packet_witnesses || [];
    const historicalWitnessById = Object.fromEntries(
      historicalWitnesses.map(row => [String(row.id || ""), row])
    );
    const historicalContextRows = historicalContext.map(row => {
      const witness = historicalWitnessById[String(row.id || "")] || {};
      const summary = row.summary || {};
      const summaryParts = Object.entries(summary).slice(0, 12).map(([key, value]) => {
        const rendered = typeof value === "string" ? value : JSON.stringify(value);
        return '<div><b>' + h(key) + ':</b> ' + h(rendered == null ? "null" : String(rendered)) + '</div>';
      }).join("");
      return '<tr>' +
        '<td><b>' + h(row.id || "unknown") + '</b><div class="small muted">' + h(row.path || "") + '</div></td>' +
        '<td><span class="chip ' + statusClass(row.evidence_status) + '">' + h(row.evidence_status || "UNMEASURED") + '</span></td>' +
        '<td><code title="' + h(row.remote_blob_sha || "") + '">' + h(row.remote_blob_sha ? String(row.remote_blob_sha).slice(0, 12) : "—") + '</code></td>' +
        '<td><div class="' + (witness.source_artifact_blob_verified ? 'brain-good' : 'brain-warn') + '">' + (witness.source_artifact_blob_verified ? 'PACKET SOURCE VERIFIED' : 'PACKET SOURCE UNVERIFIED') + '</div><code title="' + h(witness.source_artifact_blob_sha || "") + '">' + h(witness.source_artifact_blob_sha ? String(witness.source_artifact_blob_sha).slice(0, 12) : "—") + '</code><div class="small muted">' + h(witness.current_main_relation || "UNMEASURED") + '</div></td>' +
        '<td>' + h(row.run_id || "—") + '<div class="small muted">' + h(row.run_status || "—") + '</div></td>' +
        '<td class="small">' + (summaryParts || '<span class="muted">No bounded summary fields present.</span>') + '</td>' +
        '<td class="small">candidate evidence=false<br><b>Foundry + Evaluator required</b><br>foreign evidence only</td>' +
      '</tr>';
    }).join("");

    const agentHtml = agents.map(a => `<div class="brain-agent ${statusClass(a.status)}"><div style="display:flex;justify-content:space-between;gap:8px"><b>${h(a.title)}</b><span class="chip">${h(a.status)}</span></div><div class="small muted" style="margin-top:5px">${h(a.job)}</div><div class="small" style="margin-top:7px"><b>Owns:</b> ${(a.owns||[]).map(x=>h(x)).join(' · ')}</div><div class="small muted" style="margin-top:5px">${h(a.detail||'')}</div></div>`).join('');

    const subHtml = subs.map(s => `<div class="brain-sub ${statusClass(s.status)}"><div style="display:flex;justify-content:space-between;gap:8px"><b>${h(s.title)}</b><span class="chip">${h(s.status)}</span></div><div class="small muted" style="margin-top:5px">${h(s.job)}</div><div class="small" style="margin-top:6px">owner <b>${h(s.owner)}</b></div></div>`).join('');

    const laneHtml = lanes.map(l => `<div class="brain-lane"><div style="display:flex;justify-content:space-between;gap:8px"><b>${h(l.title)}</b><span class="chip">${h(l.target)}</span></div><div class="small muted" style="margin-top:5px">${h(l.job)}</div><div class="small" style="margin-top:6px">training: <b>${h(String(l.training_allowed))}</b></div></div>`).join('');

    const candRows = candidates.map(c => {
      const gates = Object.entries(c.validation||{}).map(([k,v]) => `<span class="${v===true?'brain-good':v===false?'brain-bad':'brain-warn'}">${h(k)}: ${v===true?'PASS':v===false?'FAIL':'UNKNOWN'}</span>`).join('');
      const q = c.qualification_receipts || {};
      return `<tr><td><b>${h(c.candidate_id)}</b><div class="small muted">${h((c.regimes||[]).join(', '))}</div></td><td><span class="chip ${c.eligible_for_regime_swap?'brain-good':statusClass(c.stage)}">${h(c.stage)}</span></td><td>${c.metrics&&c.metrics.validation_score!=null?h(String(c.metrics.validation_score)):'—'}</td><td>${c.eligible_for_regime_swap?'SHADOW ELIGIBLE':'BLOCKED'}<div class="small muted">${h((c.gate_blockers||[]).join(' · '))}</div><div class="small ${q.qualification_ready?'brain-good':'muted'}">receipts: ${num(q.receipt_count)} · ${q.qualification_ready?'READY':'NOT READY'}</div><div class="brain-gate">${gates}</div></td></tr>`;
    }).join('');

    const routeHtml = routes.map(r => `<div class="brain-route"><b>${h(r.asset)} · ${h(r.regime||'UNKNOWN')}</b>\nselected: ${h(r.selected_candidate||'none')}\neligible: ${h((r.eligible_shadow_candidates||[]).map(x=>x.candidate_id).join(', ')||'none')}\nmode: ${h(r.selection_mode)}</div>`).join('');

    const regimeHtml = regimes.map(r => `<span class="chip ${r.paused?'r':r.warm?'b':'w'}">${h(r.asset)} · ${h(r.regime||'UNKNOWN')} · ${pct(r.confidence)}</span>`).join(' ');
    const tournamentRows = tournaments.map(t => `<tr><td><b>${h((t.scope||{}).asset||"—")}</b></td><td>${h((t.scope||{}).regime||"UNKNOWN")}</td><td><b>${h(t.shadow_champion||"none")}</b></td><td>${h(t.status||"")}</td><td>${h(t.decision||"")}</td></tr>`).join("");
    const incubatorRows = (inc.proposals||[]).map(p => {
      const rc = p.regime_context || {};
      return `<tr><td><b>${h(p.asset||'—')}</b><div class="small muted">${h(String(p.proposal_id||'').slice(0,18))}</div></td><td><span class="chip ${statusClass(p.state)}">${h(String(p.state||'unknown').toUpperCase())}</span><div class="small muted">${h(p.review_mode||'')}</div></td><td><b>${h(rc.label||'UNKNOWN')}</b><div class="small muted">${rc.regime_score==null?'score —':'score '+h(String(rc.regime_score))}</div></td><td class="tnum">${num(p.input_count)}</td><td class="tnum">${num(p.review_count)}</td><td>${p.review_required?'INDEPENDENT REVIEW REQUIRED':'—'}</td></tr>`;
    }).join('');

    el.innerHTML = `<style>
        .brain-shell{position:relative;overflow:hidden;min-height:520px;background:
          radial-gradient(circle at 50% 8%,rgba(86,225,255,.16),transparent 34%),
          radial-gradient(circle at 92% 42%,rgba(145,92,255,.12),transparent 32%),
          linear-gradient(145deg,var(--surface),rgba(20,34,44,.92));}
        .brain-shell:before{content:"";position:absolute;inset:0;pointer-events:none;background:linear-gradient(rgba(95,232,255,.035) 1px,transparent 1px),linear-gradient(90deg,rgba(95,232,255,.035) 1px,transparent 1px);background-size:28px 28px;mask-image:linear-gradient(to bottom,black,transparent 92%)}
        .brain-layer{position:relative;z-index:1}.brain-title{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin-bottom:12px}.brain-core{border:1px solid rgba(95,232,255,.35);box-shadow:0 0 40px rgba(95,232,255,.08) inset;border-radius:18px;padding:16px;background:rgba(8,18,25,.28)}.brain-orbit{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:10px}.brain-agent,.brain-sub,.brain-lane{border:1px solid var(--ring);background:rgba(255,255,255,.025);border-radius:12px;padding:10px}.brain-good{color:var(--good-text);border-color:var(--good)!important}.brain-bad{color:var(--crit);border-color:var(--crit)!important}.brain-warn{color:var(--warn);border-color:var(--warn)!important}.brain-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:10px}.brain-gate{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:6px;margin-top:8px}.brain-gate span{font-size:11px;padding:5px 7px;border:1px solid var(--ring);border-radius:8px}.brain-pulse{width:11px;height:11px;border-radius:50%;background:#67e8f9;box-shadow:0 0 0 0 rgba(103,232,249,.65);animation:brainPulse 1.8s infinite}@keyframes brainPulse{70%{box-shadow:0 0 0 14px rgba(103,232,249,0)}100%{box-shadow:0 0 0 0 rgba(103,232,249,0)}}.brain-route{font:11px/1.5 ui-monospace,Consolas,monospace;background:rgba(0,0,0,.16);border-radius:8px;padding:8px;margin-top:6px;white-space:pre-wrap}
      </style>
      <div class="brain-layer">
        <div class="brain-title"><span class="brain-pulse"></span><div><h2 style="margin:0">ICARUS Adaptive Brain <span class="sub">truthful continuous-learning control surface</span></h2><div class="small muted">generated ${h(b.generated_at)} · production decision authority: ${auth.production_decision_authorized?'YES':'NO'} · execution authority: ${auth.execution_authorized?'YES':'NO'}</div></div></div>
        <div class="brain-core">
          <div class="tiles" style="margin-top:0">
            <div class="tile"><div class="k">Custom agents</div><div class="v tnum">${num((b.architecture||{}).agent_count)}</div></div>
            <div class="tile"><div class="k">Subsystems</div><div class="v tnum">${num((b.architecture||{}).subsystem_count)}</div></div>
            <div class="tile"><div class="k">Brain events / hour</div><div class="v tnum">${num(learn.brain_events_last_hour)}</div></div>
            <div class="tile"><div class="k">Events / 24h</div><div class="v tnum">${num(learn.brain_events_last_24h)}</div></div>
            <div class="tile"><div class="k">Qualified shadow candidates</div><div class="v tnum">${num(learn.qualified_shadow_candidates)}</div></div>
            <div class="tile"><div class="k">Candidate qualification share</div><div class="v">${pct(learn.qualified_share_of_decided)}</div></div>
            <div class="tile"><div class="k">Observed success rate</div><div class="v">${pct(truth.success_rate)}</div><div class="small muted">${h(truth.success_rate_status)}</div></div>
            <div class="tile"><div class="k">Outcome coverage</div><div class="v">${pct(truth.outcome_coverage)}</div><div class="small muted">${num(proofMetrics.settled_forecasts)} / ${num(proofMetrics.matured_forecasts)} matured</div></div>
            <div class="tile"><div class="k">Matured unsettled</div><div class="v ${proofBacklog.count>0?'brain-warn':'brain-good'}">${num(proofBacklog.count)}</div><div class="small muted">${proofBacklog.oldest_matures_at?h("oldest "+proofBacklog.oldest_matures_at):"settlement backlog clear"}</div></div>
            <div class="tile"><div class="k">Brier score</div><div class="v">${proofMetrics.brier_score==null?"UNMEASURED":h(Number(proofMetrics.brier_score).toFixed(4))}</div><div class="small muted">lower is better</div></div>
            <div class="tile"><div class="k">Closed-sample 100%</div><div class="v ${proofClosed.historical_100_percent_established?"brain-good":"brain-warn"}">${proofClosed.historical_100_percent_established?"ESTABLISHED":"NOT ESTABLISHED"}</div><div class="small muted">${h(proofClosed.claim||"requires a closed fully-settled sample")}</div></div>
            <div class="tile"><div class="k">Replay determinism</div><div class="v">${pct(proofReplay.determinism_rate)}</div><div class="small muted">${proofReplay.historical_100_percent_established?"100% established for recorded replay sample":"not yet established"}</div></div>
            <div class="tile"><div class="k">Hot-path p99</div><div class="v">${hotLatency.p99_ms==null?"UNMEASURED":h(Number(hotLatency.p99_ms).toFixed(3))+" ms"}</div><div class="small muted">${h(hotLatency.budget_status||"awaiting instrumentation")}</div></div>
            <div class="tile"><div class="k">Evidence graph</div><div class="v">${num(graphMetrics.node_count)}</div><div class="small muted">${num(graphMetrics.edge_count)} edges · ${num(graphMetrics.source_revision_count)} exact revisions</div></div>
            <div class="tile"><div class="k">Independent corroboration</div><div class="v">${num(graphMetrics.independently_corroborated_evidence_count)}</div><div class="small muted">${num(graphMetrics.duplicate_evidence_count)} repeated evidence nodes tracked separately</div></div>
            <div class="tile"><div class="k">Source reliability</div><div class="v">${num(measuredReliability)} / ${num(reliability.source_stream_count)}</div><div class="small muted">${num(reliability.observation_count)} causal observations retained</div></div>
            <div class="tile"><div class="k">Qualification-ready revisions</div><div class="v">${num(qualification.qualification_ready_count)} / ${num(qualification.candidate_revision_count)}</div><div class="small muted">immutable gate-receipt state · shadow only</div></div>
            <div class="tile"><div class="k">Router</div><div class="v">${h(auth.candidate_router||'—')}</div></div>
            <div class="tile"><div class="k">Agent repo sync</div><div class="v ${statusClass(sync.status)}">${h(String(sync.status||'not configured').toUpperCase())}</div><div class="small muted">${h(sync.last_success_at?'last '+sync.last_success_at:'awaiting first verified ingest')}</div></div>
            <div class="tile"><div class="k">Agent federation contract</div><div class="v ${agentContract.federation_schema?'brain-good':'brain-warn'}">${h(agentContract.federation_schema||'UNVERIFIED')}</div><div class="small muted">${h(agentContract.event_records||'fail-closed')} · ${agentContract.strict_event_contract?'STRICT EVENT ENVELOPE':'EVENT CONTRACT UNVERIFIED'} · legacy exceptions ${num(agentContract.legacy_exception_count)} · execution ${agentContract.automatic_execution_authority===false?'DENIED':'UNVERIFIED'}</div></div>
            <div class="tile"><div class="k">Peer lane packet</div><div class="v ${statusClass(sync.peer_packet_status)}">${h(String(sync.peer_packet_status||'not started').toUpperCase())}</div><div class="small muted">${h(sync.peer_source_commit?String(sync.peer_source_commit).slice(0,12):'no verified source commit')} · source ${sync.peer_source_commit_verified?'VERIFIED '+h(sync.peer_source_commit_relation||''):'UNVERIFIED'} · ${h(agentContract.peer_packet_authority||'OBSERVE')}</div></div>
            <div class="tile"><div class="k">Peer freshness</div><div class="v ${sync.peer_packet_fresh?'brain-good':'brain-warn'}">${sync.peer_packet_fresh?'FRESH':'UNVERIFIED'}</div><div class="small muted">age ${sync.peer_packet_age_seconds==null?'—':h(String(sync.peer_packet_age_seconds))+'s'} · max ${num(agentContract.peer_packet_max_age_seconds)}s · future skew ${num(agentContract.peer_packet_max_future_skew_seconds)}s</div></div>
            <div class="tile"><div class="k">Peer substantive lanes</div><div class="v tnum">${num(sync.peer_substantive_lane_count)} / ${num(peerLanes.length)}</div><div class="small muted">durability-only ${num(sync.peer_durability_only_lane_count)} · foreign evidence only</div></div>
            <div class="tile"><div class="k">Peer lane provenance</div><div class="v ${Number(sync.peer_lane_witness_verified_count||0)>0?'brain-good':'brain-warn'}">${num(sync.peer_lane_witness_verified_count)} VERIFIED</div><div class="small muted">exact packet-source blobs · unavailable ${num(sync.peer_lane_witness_unavailable_count)}</div></div>
            <div class="tile"><div class="k">Peer source contracts</div><div class="v ${statusClass(sync.peer_source_contract_witness_status)}">${h(String(sync.peer_source_contract_witness_status||'not started').toUpperCase())}</div><div class="small muted">verified ${num(sync.peer_source_contract_witness_count)} / ${num(agentContract.peer_source_contract_blob_witness_keys&&agentContract.peer_source_contract_blob_witness_keys.length)} exact packet-source blobs</div></div>
            <div class="tile"><div class="k">Remote agent events</div><div class="v tnum">${num(sync.ingested_total)}</div><div class="small muted">poll ${num(sync.interval_seconds)}s · rejected ${num(sync.rejected_total)}</div></div>
            <div class="tile"><div class="k">Historical context</div><div class="v ${statusClass(sync.historical_context_status)}">${h(String(sync.historical_context_status||"not declared").toUpperCase())}</div><div class="small muted">sources ${num(sync.historical_context_source_count)} · ingested ${num(sync.historical_context_ingested_total)}</div></div>
            <div class="tile"><div class="k">Historical candidate evidence</div><div class="v ${Number(sync.historical_candidate_evidence_count||0)===0?"brain-good":"brain-bad"}">${num(sync.historical_candidate_evidence_count)}</div><div class="small muted">must remain 0 · context cannot bypass Foundry/Evaluator</div></div>
            <div class="tile"><div class="k">Historical packet provenance</div><div class="v ${statusClass(sync.historical_packet_witness_status)}">${h(String(sync.historical_packet_witness_status||"not started").toUpperCase())}</div><div class="small muted">verified ${num(sync.historical_packet_witness_count)} · same as live ${num(sync.historical_packet_same_as_live_count)} · live advanced ${num(sync.historical_packet_live_advanced_count)}</div></div>
            <div class="tile"><div class="k">CSV Evidence Lab</div><div class="v ${statusClass(evidenceLab.status)}">${h(String(evidenceLab.status||"not configured").toUpperCase())}</div><div class="small muted">${h(evidenceLab.current_run_id||"no run observed")} · ${h(evidenceLab.evidence_status||"evidence unknown")}</div></div>
            <div class="tile"><div class="k">CSV pointer coherence</div><div class="v ${evidenceLab.latest_pointer_matches_heartbeat===false?"brain-warn":"brain-good"}">${evidenceLab.latest_pointer_matches_heartbeat===false?"LAGGING":"COHERENT/UNSET"}</div><div class="small muted">RUN_PERSISTED is durability only · evidence authority stays EVIDENCE_STATUS</div></div>
            <div class="tile"><div class="k">Research → Brain</div><div class="v ${statusClass(researchSync.status)}">${h(String(researchSync.status||'not configured').toUpperCase())}</div><div class="small muted">candidates ${num(researchSync.candidates_recorded)} · negatives ${num(researchSync.negative_results_recorded)}</div></div>
            <div class="tile"><div class="k">Revision-blocked studies</div><div class="v tnum">${num(researchSync.blocked_revision_count)}</div><div class="small muted">candidate admission fails closed without exact clean source revision</div></div>
            <div class="tile"><div class="k">Local incubator</div><div class="v tnum">${num(inc.proposal_count)}</div><div class="small muted">review required ${num(inc.review_required)}</div></div>
            <div class="tile"><div class="k">Independently approved</div><div class="v tnum">${num(inc.approved)}</div><div class="small muted">paper activation still gated</div></div>
          </div>
          <div class="small muted" style="margin-top:9px">A 100% value is emitted only when the exact historical sample is closed, fully settled and actually proves 100%; it is never promoted into a future guarantee. Millisecond claims are backed by measured p50/p95/p99 telemetry rather than targets alone. Training, falsification and promotion stay off the hot path.</div>
        </div>

        <h3 class="small" style="margin:16px 0 8px">5 custom agents · distinct vital jobs</h3>
        <div class="brain-orbit">${agentHtml}</div>

        <h3 class="small" style="margin:16px 0 8px">Federated Icarus-engine lane state</h3>
        <div class="small muted" style="margin-bottom:7px">Revision-bound foreign evidence from the live peer packet. DURABILITY_ONLY never counts as substantive research evidence, and sibling-repository state is not inferred.</div>
        <div class="scroll" style="max-height:300px"><table><thead><tr><th>Lane</th><th>Evidence status</th><th>Run</th><th>Worker execution</th><th>Source proof</th><th>Substantive evidence</th></tr></thead><tbody>${peerLaneRows || '<tr><td colspan=6 class="empty">No verified Icarus-engine peer packet is currently available.</td></tr>'}</tbody></table></div>

        <h3 class="small" style="margin:16px 0 8px">Historical peer research context</h3>
        <div class="small muted" style="margin-bottom:7px">Bounded Git-blob-verified context from Icarus-engine. HISTORICAL_RESEARCH_EVIDENCE and HISTORICAL_COLLECTION_EVIDENCE are research context only; candidate evidence=false and Foundry + Evaluator required before any hypothesis can gain admission.</div>
        <div class="scroll" style="max-height:360px"><table><thead><tr><th>Source</th><th>Evidence status</th><th>Live Git blob</th><th>Packet-bound source proof</th><th>Historical run</th><th>Bounded preserved context</th><th>Admission boundary</th></tr></thead><tbody>${historicalContextRows || '<tr><td colspan=7 class="empty">No verified historical Icarus-engine context has been ingested.</td></tr>'}</tbody></table></div>

        <h3 class="small" style="margin:16px 0 8px">Subsystem fabric · ${subs.length} registered</h3>
        <div class="brain-grid">${subHtml}</div>

        <h3 class="small" style="margin:16px 0 8px">Latency architecture</h3>
        <div class="brain-grid">${laneHtml}</div>

        <h3 class="small" style="margin:16px 0 8px">Current market regimes</h3>
        <div>${regimeHtml || '<span class="muted small">No live market-regime state available.</span>'}</div>

        <h3 class="small" style="margin:16px 0 8px">Regime-specialist shadow router</h3>
        <div class="brain-grid">${routeHtml || '<div class="muted small">No eligible candidates. The router fails closed instead of inventing one.</div>'}</div>

        <h3 class="small" style="margin:16px 0 8px">Source reliability memory</h3>
        <div class="small muted" style="margin-bottom:7px">Freshness, completeness, independent agreement and revision stability are measured per source/stream with Beta smoothing; low samples never become fake certainty.</div>
        <div class="scroll" style="max-height:280px"><table><thead><tr><th>Source</th><th>Stream</th><th>N</th><th>Fresh</th><th>Complete</th><th>Agree</th><th>Revision</th><th>Posterior</th><th>Status</th></tr></thead><tbody>${reliabilityRows.map(r => `<tr><td><b>${h(r.source_id||"")}</b></td><td>${h(r.stream||"")}</td><td>${num(r.sample_count)}</td><td>${pct(r.fresh_rate)}</td><td>${pct(r.complete_rate)}</td><td>${pct(r.agreement_rate)}</td><td>${pct(r.revision_rate)}</td><td>${pct(r.reliability_posterior_mean)}</td><td>${h(r.measurement_status||"")}</td></tr>`).join("") || '<tr><td colspan=9 class="empty">No source-reliability observations have been recorded yet.</td></tr>'}</tbody></table></div>

        <h3 class="small" style="margin:16px 0 8px">Causal evidence graph</h3>
        <div class="small muted" style="margin-bottom:7px">Connects exact source revisions, recorded evidence, candidates, regimes and validation gates. Repeated evidence is not treated as independent corroboration unless it comes from distinct exact revisions.</div>
        <div class="scroll" style="max-height:260px"><table><thead><tr><th>Candidate</th><th>Events</th><th>Exact sources</th><th>Evidence</th><th>Regimes</th><th>Verified gates</th></tr></thead><tbody>${(graph.candidates||[]).map(c => `<tr><td><b>${h(c.candidate_id||"")}</b></td><td>${num(c.event_count)}</td><td>${num(c.source_revision_count)}</td><td>${num(c.evidence_count)}</td><td>${h((c.regimes||[]).join(", ")||"—")}</td><td class="small">${h((c.verified_gates||[]).join(", ")||"none")}</td></tr>`).join("") || '<tr><td colspan=6 class="empty">No candidate evidence graph has been recorded yet.</td></tr>'}</tbody></table></div>

        <h3 class="small" style="margin:16px 0 8px">Evidence champion / challenger tournaments</h3>
        <div class="small muted" style="margin-bottom:7px">Only fully-settled comparable samples enter these tournaments. Results remain EMPIRICAL_SHADOW_ONLY.</div>
        <div class="scroll" style="max-height:320px"><table><thead><tr><th>Asset</th><th>Regime</th><th>Shadow champion</th><th>Status</th><th>Decision</th></tr></thead><tbody>${tournamentRows || '<tr><td colspan=5 class="empty">No evidence tournament has enough comparable closed-sample data yet.</td></tr>'}</tbody></table></div>

        <h3 class="small" style="margin:16px 0 8px">Zero-cost local candidate incubator</h3>
        <div class="small muted" style="margin-bottom:7px">${h(inc.rule||'Local deterministic studies can preserve candidates without paid model calls; independent review remains mandatory before activation.')}</div>
        <div class="scroll" style="max-height:300px"><table><thead><tr><th>Asset / proposal</th><th>State / mode</th><th>Observed regime</th><th>Inputs</th><th>Reviews</th><th>Authority</th></tr></thead><tbody>${incubatorRows || '<tr><td colspan=6 class="empty">No locally incubated proposals yet.</td></tr>'}</tbody></table></div>

        <h3 class="small" style="margin:16px 0 8px">Immutable qualification receipts</h3>
        <div class="small muted" style="margin-bottom:7px">Each candidate revision must prove every configured gate. The last positive gate can create a qualified-shadow event; a later negative receipt removes shadow eligibility. Neither transition grants production or execution authority.</div>
        <div class="scroll" style="max-height:320px"><table><thead><tr><th>Candidate</th><th>Revision</th><th>Receipts</th><th>Gate state</th><th>Recommended stage</th><th>Blockers</th></tr></thead><tbody>${qualificationRows.map(q => { const vals=Object.values(q.validation||{}), passed=vals.filter(v=>v===true).length; return `<tr><td><b>${h(q.candidate_id||"")}</b></td><td class="small">${h(String(q.candidate_source_revision||"").slice(0,28))}</td><td>${num(q.receipt_count)}</td><td class="${q.qualification_ready?'brain-good':'brain-warn'}">${passed}/${vals.length} ${q.qualification_ready?'READY':'INCOMPLETE'}</td><td>${h(q.recommended_stage||"validated")}</td><td class="small muted">${h((q.blockers||[]).join(" · ")||"none")}</td></tr>`; }).join("") || '<tr><td colspan=6 class="empty">No qualification receipts recorded yet.</td></tr>'}</tbody></table></div>

        <h3 class="small" style="margin:16px 0 8px">Candidate lifecycle & rigorous gates</h3>
        <div class="scroll" style="max-height:520px"><table><thead><tr><th>Candidate</th><th>Stage</th><th>Validation score</th><th>Gate state</th></tr></thead><tbody>${candRows || '<tr><td colspan=4 class="empty">No candidate events recorded yet. Qualification remains empty/fail-closed.</td></tr>'}</tbody></table></div>

        <div class="small muted" style="margin-top:12px">Learning loop: ${h(((b.architecture||{}).learning_loop||[]).join(' → '))}. Local study-only incubation is zero-cost and never applies inputs. The brain can learn and route research/shadow candidates, but cannot silently mutate production strategy or place orders.</div>
      </div>`;
  }

  async function loadBrain() {
    const el = document.querySelector('#brainPanel');
    if (!el) return;
    try {
      const tok = localStorage.getItem('icarus-engine-token') || 'icarus';
      const r = await fetch('/api/brain', {cache:'no-store', headers:{'Authorization':'Bearer '+tok}});
      const b = await r.json();
      if (!r.ok) throw new Error(b.detail || ('HTTP '+r.status));
      renderBrain(b);
    } catch (err) {
      el.innerHTML = `<h2>Adaptive Brain</h2><div class="empty">brain state unavailable: ${h(err.message||err)}</div>`;
    }
  }

  function wireBrain() {
    loadBrain();
    if (timer) clearInterval(timer);
    timer = setInterval(() => {
      if ((location.hash || '#overview').slice(1) === 'brain') loadBrain();
    }, 5000);
  }

  window.brainHtml = brainHtml;
  window.wireBrain = wireBrain;
  window.loadBrain = loadBrain;
})();

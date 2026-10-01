(() => {
  let timer = null;

  const h = value => String(value ?? '').replace(/[&<>"]/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[ch]));
  const pct = value => (typeof value === 'number' && Number.isFinite(value)) ? (value * 100).toFixed(1) + '%' : 'UNMEASURED';
  const num = value => (typeof value === 'number' && Number.isFinite(value)) ? value.toLocaleString() : '—';

  function statusClass(value) {
    const s = String(value || '').toUpperCase();
    if (s.includes('VERIFIED') || s.includes('ACTIVE') || s.includes('RUN_PERSISTED') || s === 'QUALIFIED') return 'brain-good';
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
    const auth = b.authority || {}, learn = b.learning || {}, truth = b.truth_contract || {}, sync = b.remote_sync || {}, inc = b.incubator || {}, researchSync = b.research_sync || {}, proof = b.performance_proof || {}, latency = b.latency_telemetry || {};
    const agents = ((b.architecture || {}).agents || []);
    const subs = ((b.architecture || {}).subsystems || []);
    const lanes = ((b.architecture || {}).latency_tiers || []);
    const candidates = b.candidates || [];
    const routes = b.regime_routes || [];
    const regimes = ((b.market || {}).regimes || []);
    const tournaments = b.evidence_tournaments || [];
    const proofMetrics = proof.metrics || {}, proofClosed = proof.closed_sample || {}, proofReplay = proof.replay || {};
    const hotLatency = latency.hot_path || {};

    const agentHtml = agents.map(a => `<div class="brain-agent ${statusClass(a.status)}"><div style="display:flex;justify-content:space-between;gap:8px"><b>${h(a.title)}</b><span class="chip">${h(a.status)}</span></div><div class="small muted" style="margin-top:5px">${h(a.job)}</div><div class="small" style="margin-top:7px"><b>Owns:</b> ${(a.owns||[]).map(x=>h(x)).join(' · ')}</div><div class="small muted" style="margin-top:5px">${h(a.detail||'')}</div></div>`).join('');

    const subHtml = subs.map(s => `<div class="brain-sub ${statusClass(s.status)}"><div style="display:flex;justify-content:space-between;gap:8px"><b>${h(s.title)}</b><span class="chip">${h(s.status)}</span></div><div class="small muted" style="margin-top:5px">${h(s.job)}</div><div class="small" style="margin-top:6px">owner <b>${h(s.owner)}</b></div></div>`).join('');

    const laneHtml = lanes.map(l => `<div class="brain-lane"><div style="display:flex;justify-content:space-between;gap:8px"><b>${h(l.title)}</b><span class="chip">${h(l.target)}</span></div><div class="small muted" style="margin-top:5px">${h(l.job)}</div><div class="small" style="margin-top:6px">training: <b>${h(String(l.training_allowed))}</b></div></div>`).join('');

    const candRows = candidates.map(c => {
      const gates = Object.entries(c.validation||{}).map(([k,v]) => `<span class="${v===true?'brain-good':v===false?'brain-bad':'brain-warn'}">${h(k)}: ${v===true?'PASS':v===false?'FAIL':'UNKNOWN'}</span>`).join('');
      return `<tr><td><b>${h(c.candidate_id)}</b><div class="small muted">${h((c.regimes||[]).join(', '))}</div></td><td><span class="chip ${c.eligible_for_regime_swap?'brain-good':statusClass(c.stage)}">${h(c.stage)}</span></td><td>${c.metrics&&c.metrics.validation_score!=null?h(String(c.metrics.validation_score)):'—'}</td><td>${c.eligible_for_regime_swap?'SHADOW ELIGIBLE':'BLOCKED'}<div class="small muted">${h((c.gate_blockers||[]).join(' · '))}</div><div class="brain-gate">${gates}</div></td></tr>`;
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
            <div class="tile"><div class="k">Brier score</div><div class="v">${proofMetrics.brier_score==null?"UNMEASURED":h(Number(proofMetrics.brier_score).toFixed(4))}</div><div class="small muted">lower is better</div></div>
            <div class="tile"><div class="k">Closed-sample 100%</div><div class="v ${proofClosed.historical_100_percent_established?"brain-good":"brain-warn"}">${proofClosed.historical_100_percent_established?"ESTABLISHED":"NOT ESTABLISHED"}</div><div class="small muted">${h(proofClosed.claim||"requires a closed fully-settled sample")}</div></div>
            <div class="tile"><div class="k">Replay determinism</div><div class="v">${pct(proofReplay.determinism_rate)}</div><div class="small muted">${proofReplay.historical_100_percent_established?"100% established for recorded replay sample":"not yet established"}</div></div>
            <div class="tile"><div class="k">Hot-path p99</div><div class="v">${hotLatency.p99_ms==null?"UNMEASURED":h(Number(hotLatency.p99_ms).toFixed(3))+" ms"}</div><div class="small muted">${h(hotLatency.budget_status||"awaiting instrumentation")}</div></div>
            <div class="tile"><div class="k">Router</div><div class="v">${h(auth.candidate_router||'—')}</div></div>
            <div class="tile"><div class="k">Agent repo sync</div><div class="v ${statusClass(sync.status)}">${h(String(sync.status||'not configured').toUpperCase())}</div><div class="small muted">${h(sync.last_success_at?'last '+sync.last_success_at:'awaiting first verified ingest')}</div></div>
            <div class="tile"><div class="k">Remote agent events</div><div class="v tnum">${num(sync.ingested_total)}</div><div class="small muted">poll ${num(sync.interval_seconds)}s · rejected ${num(sync.rejected_total)}</div></div>
            <div class="tile"><div class="k">Research → Brain</div><div class="v ${statusClass(researchSync.status)}">${h(String(researchSync.status||'not configured').toUpperCase())}</div><div class="small muted">candidates ${num(researchSync.candidates_recorded)} · negatives ${num(researchSync.negative_results_recorded)}</div></div>
            <div class="tile"><div class="k">Revision-blocked studies</div><div class="v tnum">${num(researchSync.blocked_revision_count)}</div><div class="small muted">candidate admission fails closed without exact clean source revision</div></div>
            <div class="tile"><div class="k">Local incubator</div><div class="v tnum">${num(inc.proposal_count)}</div><div class="small muted">review required ${num(inc.review_required)}</div></div>
            <div class="tile"><div class="k">Independently approved</div><div class="v tnum">${num(inc.approved)}</div><div class="small muted">paper activation still gated</div></div>
          </div>
          <div class="small muted" style="margin-top:9px">A 100% value is emitted only when the exact historical sample is closed, fully settled and actually proves 100%; it is never promoted into a future guarantee. Millisecond claims are backed by measured p50/p95/p99 telemetry rather than targets alone. Training, falsification and promotion stay off the hot path.</div>
        </div>

        <h3 class="small" style="margin:16px 0 8px">5 custom agents · distinct vital jobs</h3>
        <div class="brain-orbit">${agentHtml}</div>

        <h3 class="small" style="margin:16px 0 8px">Subsystem fabric · ${subs.length} registered</h3>
        <div class="brain-grid">${subHtml}</div>

        <h3 class="small" style="margin:16px 0 8px">Latency architecture</h3>
        <div class="brain-grid">${laneHtml}</div>

        <h3 class="small" style="margin:16px 0 8px">Current market regimes</h3>
        <div>${regimeHtml || '<span class="muted small">No live market-regime state available.</span>'}</div>

        <h3 class="small" style="margin:16px 0 8px">Regime-specialist shadow router</h3>
        <div class="brain-grid">${routeHtml || '<div class="muted small">No eligible candidates. The router fails closed instead of inventing one.</div>'}</div>

        <h3 class="small" style="margin:16px 0 8px">Evidence champion / challenger tournaments</h3>
        <div class="small muted" style="margin-bottom:7px">Only fully-settled comparable samples enter these tournaments. Results remain EMPIRICAL_SHADOW_ONLY.</div>
        <div class="scroll" style="max-height:320px"><table><thead><tr><th>Asset</th><th>Regime</th><th>Shadow champion</th><th>Status</th><th>Decision</th></tr></thead><tbody>${tournamentRows || '<tr><td colspan=5 class="empty">No evidence tournament has enough comparable closed-sample data yet.</td></tr>'}</tbody></table></div>

        <h3 class="small" style="margin:16px 0 8px">Zero-cost local candidate incubator</h3>
        <div class="small muted" style="margin-bottom:7px">${h(inc.rule||'Local deterministic studies can preserve candidates without paid model calls; independent review remains mandatory before activation.')}</div>
        <div class="scroll" style="max-height:300px"><table><thead><tr><th>Asset / proposal</th><th>State / mode</th><th>Observed regime</th><th>Inputs</th><th>Reviews</th><th>Authority</th></tr></thead><tbody>${incubatorRows || '<tr><td colspan=6 class="empty">No locally incubated proposals yet.</td></tr>'}</tbody></table></div>

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

(function () {
  'use strict';

  let timer = null;
  let loadSeq = 0;
  let selectedAsset = 'NQ';

  function h(v) {
    return String(v == null ? '' : v).replace(/[&<>\"]/g, function (c) {
      return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];
    });
  }

  function available(v) {
    return !(v == null || (typeof v === 'number' && !Number.isFinite(v)));
  }

  function val(v, digits) {
    if (!available(v)) return 'UNAVAILABLE';
    if (typeof v === 'number') return v.toFixed(digits == null ? 3 : digits);
    return h(v);
  }

  function pct(v, digits) {
    if (!available(v)) return 'UNAVAILABLE';
    const n = Number(v);
    return Number.isFinite(n) ? (n * 100).toFixed(digits == null ? 1 : digits) + '%' : 'UNAVAILABLE';
  }

  function status(v) {
    const s = String(v == null ? 'UNAVAILABLE' : v).toUpperCase();
    const cls = /INVALID|VETO|DEGRADED|CONTRADICT/.test(s) ? 'b' : /WARN|OBJECT|DRIFT|METASTABLE|CRITICAL/.test(s) ? 'w' : '';
    return '<span class="chip ' + cls + '">' + h(s) + '</span>';
  }

  function table(headers, rows, empty) {
    return '<div class="scroll" style="max-height:320px"><table><thead><tr>' +
      headers.map(function (x) { return '<th>' + h(x) + '</th>'; }).join('') +
      '</tr></thead><tbody>' +
      (rows.length ? rows.join('') : '<tr><td colspan="' + headers.length + '" class="empty">' + h(empty || 'UNAVAILABLE') + '</td></tr>') +
      '</tbody></table></div>';
  }

  function macroRows(d) {
    const domains = (((d || {}).economic_world || {}).domains) || {};
    return Object.keys(domains).sort().map(function (name) {
      const r = domains[name] || {};
      return '<tr><td><b>' + h(name.toUpperCase()) + '</b></td><td>' + status(r.status) + '</td><td>' + h(r.state == null ? 'UNAVAILABLE' : r.state) + '</td><td>' + h(r.market_response == null ? 'UNAVAILABLE' : r.market_response) + '</td><td class="tnum">' + val((r.hypotheses || []).length, 0) + '</td></tr>';
    });
  }

  function participantRows(d) {
    return (((d || {}).participants || {}).classes || []).map(function (r) {
      return '<tr><td><b>' + h(r.participant_class || 'unknown') + '</b></td><td>' + status(r.evidence_integrity_ok === false ? 'CONTRADICTED' : 'SUPPORTED') +
        '</td><td class="tnum">' + val(r.nominal_evidence_count, 0) + '</td><td class="tnum">' + val(r.effective_independent_families, 0) +
        '</td><td class="tnum">' + pct(r.confidence) + '</td><td class="tnum">' + val(r.long_support, 0) + '</td><td class="tnum">' + val(r.short_support, 0) + '</td></tr>';
    });
  }

  function crowdRows(d) {
    return (((d || {}).crowdhunt || {}).cells || []).slice(0, 80).map(function (r) {
      return '<tr><td class="tnum">' + val(r.price, 2) + '</td><td>' + val(r.entry_long_density) + '</td><td>' + val(r.entry_short_density) +
        '</td><td>' + val(r.stop_density_below) + '</td><td>' + val(r.stop_density_above) + '</td><td>' + val(r.trapped_long_density) +
        '</td><td>' + val(r.trapped_short_density) + '</td><td>' + val(r.forced_exit_pressure) + '</td></tr>';
    });
  }

  function forceRows(d) {
    return (((d || {}).forces || {}).cells || []).slice(0, 80).map(function (r) {
      const names = (r.contributions || []).map(function (x) { return x.participant_class || x.mechanism || x.source || 'unknown'; }).join(', ');
      return '<tr><td class="tnum">' + val(r.price, 2) + '</td><td class="tnum">' + val(r.horizon_seconds, 0) + '</td><td>' + status(r.status) +
        '</td><td class="tnum">' + val(r.net_pressure) + '</td><td class="tnum">' + pct(r.confidence) + '</td><td class="small">' + h(names || 'UNAVAILABLE') + '</td></tr>';
    });
  }

  function liquidityRows(d) {
    return (((d || {}).liquidity || {}).cells || []).slice(0, 80).map(function (r) {
      const proxies = Object.keys(r.proxies || {}).map(function (k) { return k + '=' + val(r.proxies[k]); }).join(', ');
      return '<tr><td class="tnum">' + val(r.price, 2) + '</td><td class="tnum">' + val(r.depth) + '</td><td class="tnum">' + val(r.spread) + '</td><td class="small">' + h(proxies || 'UNAVAILABLE') + '</td></tr>';
    });
  }

  function edgeRows(container) {
    return (((container || {}).edges) || []).slice(0, 100).map(function (r) {
      return '<tr><td><b>' + h(r.source || 'UNAVAILABLE') + '</b> → <b>' + h(r.target || 'UNAVAILABLE') + '</b></td><td>' + status(r.status) +
        '</td><td class="tnum">' + val(r.horizon_seconds, 0) + '</td><td class="tnum">' + pct(r.confidence) + '</td><td class="small">' + h((r.contradictions || []).join('; ') || '—') + '</td></tr>';
    });
  }

  function worldRows(d) {
    return ((((d || {}).worlds || {}).states) || []).slice(0, 80).map(function (r) {
      return '<tr><td>' + h(r.world_id || r.world_record_id || 'UNAVAILABLE') + '</td><td class="tnum">' + pct(r.weight) + '</td><td class="small">' + h(JSON.stringify(r.state || {})) + '</td><td class="small">' + h((r.assumptions || []).join('; ') || '—') + '</td></tr>';
    });
  }

  function unknownRows(d) {
    return ((((d || {}).unknown_force || {}).events) || []).slice(0, 80).map(function (r) {
      return '<tr><td>' + status(r.state) + '</td><td class="tnum">' + pct(r.unexplained_fraction) + '</td><td>' + h(r.residual_signature || 'UNAVAILABLE') + '</td><td>' + h(r.cause == null ? 'UNINTERPRETED' : r.cause) + '</td></tr>';
    });
  }

  function modelRows(d) {
    const s = (d || {}).self || {};
    const health = (s.model_health || []).map(function (r) {
      return '<tr><td>' + h(r.model_id || 'UNAVAILABLE') + '</td><td>' + status(r.status) + '</td><td class="tnum">' + val(r.score) + '</td><td>credibility</td></tr>';
    });
    const gaps = (s.reality_gap || []).map(function (r) {
      return '<tr><td>' + h(r.model_id || 'UNAVAILABLE') + '</td><td>' + status(r.state) + '</td><td class="tnum">' + val(r.gap) + '</td><td>reality gap</td></tr>';
    });
    return health.concat(gaps);
  }

  function conscienceRows(d) {
    return ((((d || {}).conscience || {}).verdicts) || []).slice(0, 80).map(function (r) {
      const judges = Object.keys(r.judges || {}).map(function (k) { const j = r.judges[k] || {}; return k + ':' + (j.state || 'UNMEASURED'); }).join(', ');
      return '<tr><td>' + h(r.belief_id || 'UNAVAILABLE') + '</td><td>' + status(r.overall) + '</td><td class="small">' + h(judges || 'UNMEASURED') + '</td></tr>';
    });
  }

  function apexHtml() {
    return '<section class="card c12">' +
      '<div class="row" style="justify-content:space-between;align-items:flex-start;gap:12px;flex-wrap:wrap">' +
        '<div><h2 style="margin-bottom:4px">APEX Ω · World Dynamics Intelligence</h2><div class="small muted">Proof-carrying world model · participant/force reconstruction · causal disagreement · self-audit · research/shadow only</div></div>' +
        '<div class="row" style="gap:8px"><label class="small muted">Asset <input id="apexAsset" value="' + h(selectedAsset) + '" style="width:86px;text-transform:uppercase"></label><button id="apexLoad" type="button">Load</button></div>' +
      '</div><div id="apexPanel" style="margin-top:12px"><div class="empty">loading APEX Ω…</div></div></section>';
  }

  function render(d) {
    const el = document.querySelector('#apexPanel');
    if (!el) return;
    selectedAsset = d.asset || selectedAsset;
    const e = d.epistemics || {};
    const siblingCounts = (d.siblings || []).reduce(function (acc, x) { const k = String(x.status || 'UNAVAILABLE').toUpperCase(); acc[k] = (acc[k] || 0) + 1; return acc; }, {});
    const cstate = (d.conscience || {}).status || 'UNMEASURED';
    el.innerHTML =
      '<div class="tiles">' +
        '<div class="tile"><div class="k">WORLD</div><div class="v">' + status(d.status) + '</div><div class="small muted">asset ' + h(d.asset || 'UNAVAILABLE') + ' · as-of ' + h(d.as_of || 'UNAVAILABLE') + '</div></div>' +
        '<div class="tile"><div class="k">EPISTEMIC HEALTH</div><div class="v">' + status(e.status) + '</div><div class="small muted">evidence ' + val(e.evidence_count, 0) + ' · beliefs ' + val(e.belief_count, 0) + '</div></div>' +
        '<div class="tile"><div class="k">PARTICIPANTS</div><div class="v">' + status((d.participants || {}).status) + '</div><div class="small muted">' + val(((d.participants || {}).classes || []).length, 0) + ' reconstructed classes</div></div>' +
        '<div class="tile"><div class="k">FORCES</div><div class="v">' + status((d.forces || {}).status) + '</div><div class="small muted">opposing contributions remain separate</div></div>' +
        '<div class="tile"><div class="k">LIQUIDITY</div><div class="v">' + status((d.liquidity || {}).depth_status) + '</div><div class="small muted">proxy fields: ' + h(((d.liquidity || {}).proxy_fields || []).join(', ') || 'UNAVAILABLE') + '</div></div>' +
        '<div class="tile"><div class="k">CONSCIENCE</div><div class="v">' + status(cstate) + '</div><div class="small muted">independent Truth / Uncertainty / Risk / Consistency / Provenance / Authority judges</div></div>' +
        '<div class="tile"><div class="k">SIBLING FABRIC</div><div class="v">' + h(JSON.stringify(siblingCounts)) + '</div><div class="small muted">failures degrade locally, not globally</div></div>' +
        '<div class="tile"><div class="k">AUTHORITY</div><div class="v">RESEARCH ONLY</div><div class="small muted">execution_authorized=false · production_decision_authorized=false</div></div>' +
      '</div>' +
      '<h3 class="small" style="margin:16px 0 8px">WORLD</h3>' + table(['Domain','State','Hypothesis','Market response','Hypotheses'], macroRows(d), 'UNAVAILABLE — no causally eligible economic world evidence.') +
      '<h3 class="small" style="margin:16px 0 8px">PARTICIPANTS</h3>' + table(['Class','Integrity','Nominal evidence','Independent families','Confidence','Long','Short'], participantRows(d), 'UNAVAILABLE — no causally eligible participant evidence.') +
      '<h3 class="small" style="margin:16px 0 8px">CROWDHUNT</h3>' + table(['Price','Entry long','Entry short','Stops below','Stops above','Trapped long','Trapped short','Forced exit'], crowdRows(d), 'UNAVAILABLE — no reconstructed retail crowd topology.') +
      '<h3 class="small" style="margin:16px 0 8px">FORCES</h3>' + table(['Price','Horizon s','State','Net derived pressure','Confidence','Contributors'], forceRows(d), 'UNAVAILABLE — no pressure contributions.') +
      '<h3 class="small" style="margin:16px 0 8px">LIQUIDITY</h3>' + table(['Price','Observed depth','Spread','Proxies'], liquidityRows(d), 'UNAVAILABLE — no authenticated depth or liquidity proxy evidence.') +
      '<h3 class="small" style="margin:16px 0 8px">CASCADES</h3>' + table(['Edge','Status','Horizon s','Confidence','Contradictions'], edgeRows(d.cascades), 'UNAVAILABLE — no persisted cascade edges.') +
      '<h3 class="small" style="margin:16px 0 8px">CAUSAL GRAPH</h3>' + table(['Edge','Status','Horizon s','Confidence','Contradictions'], edgeRows(d.causality), 'UNAVAILABLE — no supported causal claims.') +
      '<h3 class="small" style="margin:16px 0 8px">COUNTERFACTUAL WORLDS</h3>' + table(['World','Weight','State','Assumptions'], worldRows(d), 'UNAVAILABLE — no durable counterfactual world states.') +
      '<h3 class="small" style="margin:16px 0 8px">UNKNOWN FORCE</h3>' + table(['State','Unexplained','Residual signature','Cause'], unknownRows(d), 'UNAVAILABLE — no residual event outside the current explanatory envelope.') +
      '<h3 class="small" style="margin:16px 0 8px">MODEL HEALTH</h3>' + table(['Model','State','Value','Measure'], modelRows(d), 'UNMEASURED — no model credibility or reality-gap history.') +
      '<h3 class="small" style="margin:16px 0 8px">CONSCIENCE</h3>' + table(['Belief','Overall','Judges'], conscienceRows(d), 'UNMEASURED — no persisted conscience verdicts.') +
      '<div class="small muted" style="margin-top:12px">APEX Ω distinguishes OBSERVED, DERIVED, RECONSTRUCTED, INFERRED and UNAVAILABLE evidence. It does not infer exact hidden account positions, manufacture depth/order flow/open interest/liquidations, or promote research confidence into execution authority.</div>';
  }

  async function loadApex() {
    const seq = ++loadSeq;
    const el = document.querySelector('#apexPanel');
    if (!el) return;
    try {
      const token = localStorage.getItem('icarus-engine-token') || 'icarus';
      const input = document.querySelector('#apexAsset');
      if (input && input.value.trim()) selectedAsset = input.value.trim().toUpperCase();
      const qs = selectedAsset ? '?asset=' + encodeURIComponent(selectedAsset) : '';
      const response = await fetch('/api/apex' + qs, {cache:'no-store', headers:{'Authorization':'Bearer ' + token}});
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || ('APEX HTTP ' + response.status));
      if (seq !== loadSeq) return;
      render(data);
    } catch (err) {
      if (seq !== loadSeq) return;
      el.innerHTML = '<div class="empty">APEX Ω state UNAVAILABLE: ' + h(err && err.message ? err.message : err) + '</div>';
    }
  }

  function wireApex() {
    const button = document.querySelector('#apexLoad');
    const input = document.querySelector('#apexAsset');
    if (button) button.addEventListener('click', loadApex);
    if (input) input.addEventListener('keydown', function (ev) { if (ev.key === 'Enter') loadApex(); });
    loadApex();
    if (timer) clearInterval(timer);
    timer = setInterval(function () {
      if ((location.hash || '#overview').slice(1) === 'apex') loadApex();
    }, 5000);
  }

  window.apexHtml = apexHtml;
  window.wireApex = wireApex;
  window.loadApex = loadApex;
})();
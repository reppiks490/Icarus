(function () {
  'use strict';

  let timer = null;
  let selectedAsset = '';

  function h(v) {
    return String(v == null ? '' : v).replace(/[&<>"]/g, function (c) {
      return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];
    });
  }

  function pct(v, digits) {
    if (v == null || Number.isNaN(Number(v))) return '—';
    return (Number(v) * 100).toFixed(digits == null ? 1 : digits) + '%';
  }

  function num(v, digits) {
    if (v == null || Number.isNaN(Number(v))) return '—';
    return Number(v).toFixed(digits == null ? 3 : digits);
  }

  function price(v) {
    if (v == null || Number.isNaN(Number(v))) return '—';
    return Number(v).toLocaleString(undefined, {maximumFractionDigits: 4});
  }

  function horizonLabel(seconds) {
    seconds = Number(seconds || 0);
    if (seconds < 60) return seconds + 's';
    if (seconds < 3600) return Math.round(seconds / 60) + 'm';
    if (seconds < 86400) return (seconds / 3600) + 'h';
    return (seconds / 86400) + 'd';
  }

  function clsForBasin(basin) {
    if (basin === 'up') return 'pos';
    if (basin === 'down') return 'neg';
    return '';
  }

  function stateChip(row) {
    if (!row) return '<span class="chip">UNAVAILABLE</span>';
    if (row.collapse_detected) return '<span class="chip b">FUTURE COLLAPSE</span>';
    if (Number(row.bifurcation_score || 0) >= 0.55) return '<span class="chip w">TEMPORAL FRACTURE</span>';
    return '<span class="chip">DISTRIBUTED</span>';
  }

  function horizonRows(rows) {
    return (rows || []).map(function (r) {
      var p = r.probabilities || {};
      var band = r.reachable_band || {};
      return '<tr>' +
        '<td class="tnum"><b>' + h(horizonLabel(r.horizon_seconds)) + '</b></td>' +
        '<td class="' + clsForBasin(r.dominant_basin) + '"><b>' + h(String(r.dominant_basin || '—').toUpperCase()) + '</b></td>' +
        '<td class="tnum">' + pct(p.up) + '</td>' +
        '<td class="tnum">' + pct(p.rotation) + '</td>' +
        '<td class="tnum">' + pct(p.down) + '</td>' +
        '<td class="tnum">' + pct(r.entropy) + '</td>' +
        '<td class="tnum">' + pct(r.convergence) + '</td>' +
        '<td class="tnum">' + pct(r.coverage) + '</td>' +
        '<td class="tnum">' + pct(r.collapse_score) + '</td>' +
        '<td class="tnum">' + pct(r.bifurcation_score) + '</td>' +
        '<td class="tnum">' + price(band.low) + ' — ' + price(band.high) + '</td>' +
        '</tr>';
    }).join('');
  }

  function levelRows(rows, label) {
    return (rows || []).map(function (r) {
      return '<tr>' +
        '<td><b>' + h(label) + '</b></td>' +
        '<td class="tnum">' + price(r.price) + '</td>' +
        '<td class="tnum">' + num(r.mass, 3) + '</td>' +
        '<td class="tnum">' + (r.distance_pct == null ? '—' : Number(r.distance_pct).toFixed(3) + '%') + '</td>' +
        '<td class="small">' + h((r.sources || []).join(', ')) + '</td>' +
        '</tr>';
    }).join('');
  }

  function calibrationRows(rows) {
    return (rows || []).map(function (r) {
      return '<tr>' +
        '<td class="tnum">' + h(horizonLabel(r.horizon_seconds)) + '</td>' +
        '<td class="tnum">' + h(r.n) + '</td>' +
        '<td class="tnum">' + num(r.mean_brier, 4) + '</td>' +
        '<td class="tnum">' + pct(r.dominant_hit_rate) + '</td>' +
        '<td class="tnum">' + pct(r.mean_dominant_confidence) + '</td>' +
        '</tr>';
    }).join('');
  }

  function forecastRows(rows) {
    return (rows || []).map(function (r) {
      return '<tr>' +
        '<td class="small tnum">' + h(String(r.observed_at || '').replace('T', ' ').replace('Z', '')) + '</td>' +
        '<td><span class="' + clsForBasin(r.dominant_basin) + '"><b>' + h(String(r.dominant_basin || '—').toUpperCase()) + '</b></span></td>' +
        '<td class="tnum">' + pct(r.collapse_score) + '</td>' +
        '<td>' + (r.collapse_detected ? '<span class="chip b">collapse</span>' : '<span class="chip">distributed</span>') + '</td>' +
        '<td class="small tnum">' + h(String(r.source_commit || '').slice(0, 12)) + '</td>' +
        '</tr>';
    }).join('');
  }

  function worldRows(forks) {
    return (((forks || {}).worlds) || []).map(function (w) {
      var states = (w.states || []).map(function (x) {
        return horizonLabel(x.horizon_seconds) + ':' + String(x.basin || '').toUpperCase();
      }).join(' → ');
      return '<tr>' +
        '<td class="tnum">' + h(w.rank) + '</td>' +
        '<td><b>' + h(w.signature || '—') + '</b></td>' +
        '<td class="tnum">' + pct(w.relative_weight) + '</td>' +
        '<td class="' + clsForBasin(w.terminal_basin) + '"><b>' + h(String(w.terminal_basin || '—').toUpperCase()) + '</b></td>' +
        '<td class="small">' + h(states) + '</td>' +
        '</tr>';
    }).join('');
  }

  function causalRows(rows) {
    return (rows || []).map(function (r) {
      return '<tr>' +
        '<td><b>' + h(r.from) + '</b> → <b>' + h(r.to) + '</b></td>' +
        '<td class="tnum">' + h(Math.round(Number(r.lag_ms || 0))) + ' ms</td>' +
        '<td>' + h(r.relation || 'reported') + '</td>' +
        '<td class="tnum">' + pct(r.confidence) + '</td>' +
        '<td class="small">' + h(r.publisher || '') + ' · ' + h(r.domain || '') + '</td>' +
        '</tr>';
    }).join('');
  }

  function forwardRows(rows) {
    return (rows || []).map(function (r) {
      return '<tr>' +
        '<td class="tnum"><b>' + h(horizonLabel(r.horizon_seconds)) + '</b></td>' +
        '<td class="tnum">' + pct(r.expected_return, 3) + '</td>' +
        '<td class="tnum">' + pct(r.implied_vol, 2) + '</td>' +
        '<td class="tnum">' + num(r.skew, 4) + '</td>' +
        '<td class="tnum">' + pct(r.tail_up, 1) + '</td>' +
        '<td class="tnum">' + pct(r.tail_down, 1) + '</td>' +
        '<td class="small">' + h((r.sources || []).join(', ')) + '</td>' +
        '</tr>';
    }).join('');
  }

  function sibylHtml() {
    return '<section class="card c12">' +
      '<div class="row" style="justify-content:space-between;align-items:flex-start;gap:12px;flex-wrap:wrap">' +
        '<div><h2 style="margin-bottom:4px">SIBYL Ω · Future Lightcone</h2>' +
        '<div class="small muted">Probabilistic reachable-state synthesis · calibrated research/shadow intelligence · never deterministic foresight</div></div>' +
        '<div class="row" style="gap:8px;flex-wrap:wrap">' +
          '<label class="small muted">Asset <input id="sibylAsset" value="' + h(selectedAsset) + '" placeholder="NQ" style="width:86px;text-transform:uppercase"></label>' +
          '<button id="sibylLoad" type="button">Load</button>' +
        '</div>' +
      '</div>' +
      '<div id="sibylPanel" style="margin-top:12px"><div class="empty">loading future-state synthesis…</div></div>' +
    '</section>';
  }

  function render(d) {
    var el = document.querySelector('#sibylPanel');
    if (!el) return;
    selectedAsset = d.asset || selectedAsset || '';
    var collapse = d.temporal_collapse || {};
    var fracture = d.temporal_fracture || {};
    var ev = d.evidence || {};
    var cal = d.calibration || {};
    var ctx = d.context || {};
    var levels = levelRows(d.attractors, 'Attractor') + levelRows(d.repulsion_or_invalidation, 'Invalidation');
    var gravity = d.liquidity_gravity_field || {};
    var p = collapse.probabilities || {};

    el.innerHTML =
      '<div class="tiles">' +
        '<div class="tile"><div class="k">Asset / price</div><div class="v">' + h(d.asset || '—') + '</div><div class="small muted tnum">' + price(d.current_price) + '</div></div>' +
        '<div class="tile"><div class="k">Lightcone state</div><div class="v">' + stateChip(collapse) + '</div><div class="small muted">strongest convergence horizon ' + h(horizonLabel(collapse.horizon_seconds)) + '</div></div>' +
        '<div class="tile"><div class="k">Dominant basin</div><div class="v ' + clsForBasin(collapse.dominant_basin) + '">' + h(String(collapse.dominant_basin || '—').toUpperCase()) + '</div><div class="small muted">up ' + pct(p.up) + ' · rotate ' + pct(p.rotation) + ' · down ' + pct(p.down) + '</div></div>' +
        '<div class="tile"><div class="k">Future convergence</div><div class="v tnum">' + pct(collapse.convergence) + '</div><div class="small muted">entropy ' + pct(collapse.entropy) + '</div></div>' +
        '<div class="tile"><div class="k">Collapse score</div><div class="v tnum">' + pct(collapse.collapse_score) + '</div><div class="small muted">' + h(collapse.domain_count || 0) + ' independent domains</div></div>' +
        '<div class="tile"><div class="k">Fracture score</div><div class="v tnum">' + pct(fracture.bifurcation_score) + '</div><div class="small muted">highest bifurcation horizon ' + h(horizonLabel(fracture.horizon_seconds)) + '</div></div>' +
        '<div class="tile"><div class="k">Evidence</div><div class="v tnum">' + h(ev.count || 0) + '</div><div class="small muted">' + h((ev.sources || []).length) + ' sources · ' + h(ev.distinct_domain_count || 0) + ' domains · ' + h(ev.ledger_count == null ? ev.count || 0 : ev.ledger_count) + ' ledger rows</div></div>' +
        '<div class="tile"><div class="k">Calibration</div><div class="v">' + h(String(cal.status || 'unmeasured').toUpperCase()) + '</div><div class="small muted">' + h(cal.outcome_count || 0) + ' realized forecast outcomes</div></div>' +
        '<div class="tile"><div class="k">Authority</div><div class="v">SHADOW ONLY</div><div class="small muted">no order routing · no production promotion</div></div>' +
      '</div>' +

      '<div class="px-grid" style="margin-top:12px">' +
        '<div class="px-box"><b>Correlation / revision guard</b><div class="small muted" style="margin-top:6px">' + h(ev.correlation_guard || '') + '<br>' + h(ev.revision_guard || '') + '</div></div>' +
        '<div class="px-box"><b>Integration contract</b><div class="small muted" style="margin-top:6px">' + h(ctx.integration_rule || '') + '</div></div>' +
      '</div>' +

      '<h3 class="small" style="margin:16px 0 8px">Multi-horizon reachable-state basins</h3>' +
      '<div class="scroll" style="max-height:360px"><table><thead><tr><th>Horizon</th><th>Basin</th><th>Up</th><th>Rotate</th><th>Down</th><th>Entropy</th><th>Convergence</th><th>Coverage</th><th>Collapse</th><th>Fracture</th><th>Reachable band</th></tr></thead><tbody>' +
      (horizonRows(d.horizons) || '<tr><td colspan="11" class="empty">No horizon synthesis available.</td></tr>') +
      '</tbody></table></div>' +

      '<h3 class="small" style="margin:16px 0 8px">Future world forks</h3>' +
      '<div class="scroll" style="max-height:320px"><table><thead><tr><th>Rank</th><th>Signature</th><th>Relative weight</th><th>Terminal</th><th>Path</th></tr></thead><tbody>' +
      (worldRows(d.future_world_forks) || '<tr><td colspan="5" class="empty">No coherent future-world paths available.</td></tr>') +
      '</tbody></table></div>' +

      '<h3 class="small" style="margin:16px 0 8px">Liquidity gravity / scenario field</h3>' +
      '<div class="px-grid" style="margin-bottom:8px">' +
        '<div class="px-box"><b>Local equilibrium</b><div class="small muted" style="margin-top:6px">' + price(gravity.equilibrium_price) + '</div></div>' +
        '<div class="px-box"><b>Gravity state</b><div class="small muted" style="margin-top:6px">' + h(gravity.available ? gravity.force_scale || 'available' : 'no target/invalidation evidence') + '</div></div>' +
      '</div>' +
      '<div class="scroll" style="max-height:260px"><table><thead><tr><th>Type</th><th>Level</th><th>Mass</th><th>Distance</th><th>Sources</th></tr></thead><tbody>' +
      (levels || '<tr><td colspan="5" class="empty">No target or invalidation levels have been published into the SIBYL evidence contract.</td></tr>') +
      '</tbody></table></div>' +

      '<h3 class="small" style="margin:16px 0 8px">Causal delay radar</h3>' +
      '<div class="scroll" style="max-height:260px"><table><thead><tr><th>Edge</th><th>Lag</th><th>Relation</th><th>Confidence</th><th>Publisher</th></tr></thead><tbody>' +
      (causalRows(d.causal_delay_radar) || '<tr><td colspan="5" class="empty">No publisher-supplied causal/lead-lag edges are currently available.</td></tr>') +
      '</tbody></table></div>' +

      '<h3 class="small" style="margin:16px 0 8px">Derivatives forward surface</h3>' +
      '<div class="scroll" style="max-height:280px"><table><thead><tr><th>Horizon</th><th>Expected return</th><th>Implied vol</th><th>Skew</th><th>Tail up</th><th>Tail down</th><th>Sources</th></tr></thead><tbody>' +
      (forwardRows(d.derivatives_forward_surface) || '<tr><td colspan="7" class="empty">No forward-surface evidence has been published.</td></tr>') +
      '</tbody></table></div>' +

      '<h3 class="small" style="margin:16px 0 8px">Observed calibration</h3>' +
      '<div class="scroll" style="max-height:260px"><table><thead><tr><th>Horizon</th><th>N</th><th>Mean Brier</th><th>Dominant hit rate</th><th>Mean stated confidence</th></tr></thead><tbody>' +
      (calibrationRows(cal.horizons) || '<tr><td colspan="5" class="empty">Unmeasured. SIBYL will not convert unscored confidence into a performance claim.</td></tr>') +
      '</tbody></table></div>' +

      '<h3 class="small" style="margin:16px 0 8px">Recent immutable forecasts</h3>' +
      '<div class="scroll" style="max-height:300px"><table><thead><tr><th>Observed</th><th>Basin</th><th>Collapse</th><th>State</th><th>Code revision</th></tr></thead><tbody>' +
      (forecastRows(d.recent_forecasts) || '<tr><td colspan="5" class="empty">No persisted SIBYL forecasts yet.</td></tr>') +
      '</tbody></table></div>' +

      '<div class="small muted" style="margin-top:12px">SIBYL Ω estimates distributions of reachable future states from available evidence. It is explicitly non-omniscient, can be wrong, and must be judged by observed calibration rather than confidence displays.</div>';
  }

  async function loadSibyl() {
    var el = document.querySelector('#sibylPanel');
    if (!el) return;
    try {
      var tok = localStorage.getItem('icarus-engine-token') || 'icarus';
      var input = document.querySelector('#sibylAsset');
      if (input && input.value.trim()) selectedAsset = input.value.trim().toUpperCase();
      var qs = selectedAsset ? '?asset=' + encodeURIComponent(selectedAsset) : '';
      var r = await fetch('/api/sibyl' + qs, {cache:'no-store', headers:{'Authorization':'Bearer ' + tok}});
      var d = await r.json();
      if (!r.ok) throw new Error(d.detail || ('SIBYL HTTP ' + r.status));
      render(d);
    } catch (err) {
      el.innerHTML = '<h2>SIBYL Ω</h2><div class="empty">future-lightcone state unavailable: ' + h(err.message || err) + '</div>';
    }
  }

  function wireSibyl() {
    var button = document.querySelector('#sibylLoad');
    var input = document.querySelector('#sibylAsset');
    if (button) button.addEventListener('click', loadSibyl);
    if (input) input.addEventListener('keydown', function (ev) {
      if (ev.key === 'Enter') loadSibyl();
    });
    loadSibyl();
    if (timer) clearInterval(timer);
    timer = setInterval(function () {
      if ((location.hash || '#overview').slice(1) === 'sibyl') loadSibyl();
    }, 5000);
  }

  window.sibylHtml = sibylHtml;
  window.wireSibyl = wireSibyl;
  window.loadSibyl = loadSibyl;
})();

(function () {
  'use strict';

  let timer = null;
  let lastState = null;
  let lastDatasets = null;

  function h(v) {
    return String(v == null ? '' : v).replace(/[&<>\"]/g, function (c) {
      return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];
    });
  }
  function val(v, digits) {
    if (v == null || (typeof v === 'number' && !Number.isFinite(v))) return 'UNAVAILABLE';
    if (typeof v === 'number') return v.toFixed(digits == null ? 3 : digits);
    return h(v);
  }
  function pct(v) {
    if (v == null || !Number.isFinite(Number(v))) return 'UNMEASURED';
    return (Number(v) * 100).toFixed(1) + '%';
  }
  function chip(v) {
    const s = String(v == null ? 'UNAVAILABLE' : v).toUpperCase();
    const cls = /DEGRADED|INVALID|FAIL|PARTIAL/.test(s) ? 'b' : /EARLY|WARM|PENDING/.test(s) ? 'w' : '';
    return '<span class="chip ' + cls + '">' + h(s) + '</span>';
  }
  function authHeaders(json) {
    const token = localStorage.getItem('icarus-engine-token') || 'icarus';
    const headers = {'Authorization':'Bearer ' + token};
    if (json) headers['Content-Type'] = 'application/json';
    return headers;
  }
  async function getJson(path) {
    const r = await fetch(path, {cache:'no-store', headers:authHeaders(false)});
    const j = await r.json();
    if (!r.ok) throw new Error(j.detail || ('HTTP ' + r.status));
    return j;
  }
  async function postJson(path, body) {
    const r = await fetch(path, {method:'POST', headers:authHeaders(true), body:JSON.stringify(body || {})});
    const j = await r.json();
    if (!r.ok) throw new Error(j.detail || ('HTTP ' + r.status));
    return j;
  }
  function table(headers, rows, empty) {
    return '<div class="scroll" style="max-height:340px"><table><thead><tr>' +
      headers.map(function (x) { return '<th>' + h(x) + '</th>'; }).join('') +
      '</tr></thead><tbody>' +
      (rows.length ? rows.join('') : '<tr><td colspan="' + headers.length + '" class="empty">' + h(empty) + '</td></tr>') +
      '</tbody></table></div>';
  }
  function scoreRows(cards) {
    return (cards || []).map(function (r) {
      return '<tr><td><b>' + h(r.producer) + '</b></td><td>' + h(r.asset) + '</td><td>' + h(r.regime) +
        '</td><td class="tnum">' + val(r.horizon_seconds, 0) + '</td><td>' + h(r.target) + '</td><td>' + chip(r.status) +
        '</td><td class="tnum">' + val(r.settled, 0) + '</td><td class="tnum">' + pct(r.hit_rate) +
        '</td><td class="tnum">' + val(r.mean_brier) + '</td><td class="tnum">' + pct(r.calibration_gap) + '</td></tr>';
    });
  }
  function experienceRows(rows) {
    return (rows || []).map(function (r) {
      return '<tr><td><b>' + h(r.source) + '</b></td><td>' + h(r.asset) + '</td><td>' + h(r.direction) +
        '</td><td>' + chip(r.status) + '</td><td class="tnum">' + val(r.count,0) +
        '</td><td class="tnum">' + pct(r.win_rate) + '</td><td class="tnum">' + val(r.net_pnl,2) +
        '</td><td class="tnum">' + val(r.average_pnl,2) + '</td><td class="tnum">' + val(r.profit_factor,3) + '</td></tr>';
    });
  }
  function datasetRows(rows, training) {
    const byDataset = {};
    (training || []).forEach(function (r) { (byDataset[r.dataset_id] ||= []).push(r); });
    return (rows || []).map(function (r) {
      const runs = byDataset[r.dataset_id] || [];
      const range = r.first_timestamp == null ? 'UNAVAILABLE' : new Date(r.first_timestamp * 1000).toISOString().slice(0,10) + ' → ' + new Date(r.last_timestamp * 1000).toISOString().slice(0,10);
      const intake = (r.manifest || {}).intake || {};
      return '<tr><td><b>' + h(r.asset) + '</b></td><td>' + h(r.chart_type) + '</td><td>' + h(r.artifact_class) +
        '</td><td class="tnum">' + val(r.rows,0) + '</td><td class="small">' + h(range) + '</td><td class="small">' +
        h(intake.chart_type || 'UNAVAILABLE') + '</td><td>' + h(runs.map(function(x){return x.slot+':'+x.status;}).join(', ') || 'UNMEASURED') +
        '</td><td><button type="button" data-learn-backfill="' + h(r.dataset_id) + '">Replay</button></td></tr>';
    });
  }
  function coverageRows(coverage) {
    return Object.keys(coverage || {}).sort().map(function (k) {
      return '<tr><td><b>' + h(k) + '</b></td><td>' + h(coverage[k]) + '</td></tr>';
    });
  }
  function learningHtml() {
    return '<section class="card c12">' +
      '<div class="row" style="justify-content:space-between;align-items:flex-start;gap:12px;flex-wrap:wrap">' +
        '<div><h2 style="margin-bottom:4px">LEARNING FABRIC Ω · Continuous Empirical Maturation</h2>' +
        '<div class="small muted">Historical replay → matured outcomes → calibration → credibility feedback. Research/shadow only.</div></div>' +
        '<div class="row" style="gap:8px"><button id="learningRefresh" type="button">Refresh</button><button id="learningTick" type="button">Run Cycle</button><button id="learningScan" type="button">Scan History</button><button id="learningToggle" type="button">Toggle Learning</button></div>' +
      '</div><div id="learningPanel" style="margin-top:12px"><div class="empty">loading Learning Fabric…</div></div></section>';
  }
  function render(state, data) {
    const panel = document.querySelector('#learningPanel');
    if (!panel) return;
    const cfg = state.config || {};
    const preds = state.predictions || {};
    const training = state.training || {};
    const experience = state.experiences || {};
    const datasets = (data || {}).datasets || [];
    const runs = (data || {}).training_runs || [];
    const latest = ((state.cycles || {}).latest) || {};
    panel.innerHTML =
      '<div class="tiles">' +
        '<div class="tile"><div class="k">LEARNING STATE</div><div class="v">' + chip(state.status) + '</div><div class="small muted">background ' + (state.background && state.background.running ? 'RUNNING' : 'STOPPED') + ' · cycle ' + val(cfg.cycle_seconds,0) + 's</div></div>' +
        '<div class="tile"><div class="k">DATASET COVERAGE</div><div class="v">' + val((state.datasets || {}).count,0) + '</div><div class="small muted">content-hash deduplicated local datasets</div></div>' +
        '<div class="tile"><div class="k">TRAINING REPLAY</div><div class="v">' + val(training.run_count,0) + '</div><div class="small muted">purged walk-forward / protected holdout trainers</div></div>' +
        '<div class="tile"><div class="k">LIVE MATURITY</div><div class="v">' + val(preds.settled,0) + ' / ' + val(preds.count,0) + '</div><div class="small muted">' + val(preds.pending,0) + ' pending forecasts</div></div>' +
        '<div class="tile"><div class="k">REALIZED EXPERIENCE</div><div class="v">' + val(experience.count,0) + '</div><div class="small muted">runtime_live_sim + historical_trade_list · outcome memory, not forecast accuracy</div></div>' +
        '<div class="tile"><div class="k">EMPIRICAL SCORECARDS</div><div class="v">' + val((state.scorecards || []).length,0) + '</div><div class="small muted">producer × asset × regime × horizon</div></div>' +
        '<div class="tile"><div class="k">HISTORY SCAN</div><div class="v">' + (state.background && state.background.last_history_scan_epoch ? new Date(state.background.last_history_scan_epoch*1000).toLocaleString() : 'UNAVAILABLE') + '</div><div class="small muted">history/, history/drop/, research/imports/</div></div>' +
        '<div class="tile"><div class="k">LAST CYCLE</div><div class="v">' + chip(latest.status || 'UNAVAILABLE') + '</div><div class="small muted">' + val((state.cycles || {}).count,0) + ' durable cycles</div></div>' +
        '<div class="tile"><div class="k">AUTHORITY</div><div class="v">RESEARCH ONLY</div><div class="small muted">AUTOMATIC PRODUCTION PROMOTION: OFF · execution_authorized=false</div></div>' +
      '</div>' +
      '<h3 class="small" style="margin:16px 0 8px">EMPIRICAL SCORECARDS</h3>' +
      table(['Producer','Asset','Regime','Horizon s','Target','State','Settled','Hit rate','Mean Brier','Calibration gap'], scoreRows(state.scorecards), 'UNMEASURED — no matured outcomes yet.') +
      '<h3 class="small" style="margin:16px 0 8px">REALIZED EXPERIENCE · P&L MEMORY</h3>' +
      table(['Source','Asset','Direction','State','Count','Win rate','Net P&L','Avg P&L','PROFIT FACTOR'], experienceRows(experience.summary), 'UNMEASURED — no fully closed realized trade experience yet.') +
      '<h3 class="small" style="margin:16px 0 8px">DATASET COVERAGE · TRAINING REPLAY</h3>' +
      table(['Asset','Cadence','Class','Rows','Coverage','Representation','Replay status','Action'], datasetRows(datasets,runs), 'UNAVAILABLE — no local historical datasets catalogued yet.') +
      '<h3 class="small" style="margin:16px 0 8px">SYSTEM LEARNING COVERAGE</h3>' +
      table(['Subsystem','Learning contract'], coverageRows(state.coverage), 'UNAVAILABLE') +
      '<div class="small muted" style="margin-top:12px">The learner does not treat repeated model agreement as new evidence. Credibility moves only from matured observed outcomes or protected historical replay. Missing metrics remain UNAVAILABLE/UNMEASURED.</div>';
  }
  async function loadLearning() {
    const panel = document.querySelector('#learningPanel');
    if (!panel) return;
    try {
      const pair = await Promise.all([getJson('/api/learning'), getJson('/api/learning/datasets')]);
      lastState = pair[0]; lastDatasets = pair[1]; render(lastState, lastDatasets);
    } catch (err) {
      panel.innerHTML = '<div class="empty">Learning Fabric UNAVAILABLE: ' + h(err && err.message ? err.message : err) + '</div>';
    }
  }
  async function action(fn) {
    const panel = document.querySelector('#learningPanel');
    try { await fn(); await loadLearning(); }
    catch (err) { if (panel) panel.insertAdjacentHTML('afterbegin','<div class="empty">' + h(err && err.message ? err.message : err) + '</div>'); }
  }
  function wireLearning() {
    const refresh = document.querySelector('#learningRefresh');
    const tick = document.querySelector('#learningTick');
    const scan = document.querySelector('#learningScan');
    const toggle = document.querySelector('#learningToggle');
    const panel = document.querySelector('#learningPanel');
    if (refresh) refresh.addEventListener('click', loadLearning);
    if (tick) tick.addEventListener('click', function () { action(function () { return postJson('/admin/learning/tick', {}); }); });
    if (scan) scan.addEventListener('click', function () { action(function () { return postJson('/admin/learning/scan', {}); }); });
    if (toggle) toggle.addEventListener('click', function () { action(function () { return postJson('/admin/learning/config', {enabled: !(lastState && lastState.config && lastState.config.enabled)}); }); });
    if (panel) panel.addEventListener('click', function (ev) {
      const button = ev.target.closest('[data-learn-backfill]');
      if (!button) return;
      const datasetId = button.getAttribute('data-learn-backfill');
      action(function () { return postJson('/admin/learning/backfill', {dataset_id:datasetId, slots:['logit']}); });
    });
    loadLearning();
    if (timer) clearInterval(timer);
    timer = setInterval(function () {
      if ((location.hash || '#overview').slice(1) === 'learning') loadLearning();
    }, 5000);
  }
  window.learningHtml = learningHtml;
  window.wireLearning = wireLearning;
  window.loadLearning = loadLearning;
})();
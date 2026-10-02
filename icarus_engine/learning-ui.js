(function () {
  'use strict';

  let timer = null;
  let mutationBusy = false;
  let loadSeq = 0;
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
      const revision = String(r.source_commit || 'UNAVAILABLE');
      const shortRevision = revision === 'UNAVAILABLE' ? revision : revision.slice(0, 12) + '…';
      return '<tr><td><b>' + h(r.producer) + '</b></td><td>' + h(r.asset) + '</td><td>' + h(r.regime) +
        '</td><td class="tnum">' + val(r.horizon_seconds, 0) + '</td><td>' + h(r.target) +
        '</td><td>' + h(r.prediction_label || 'UNAVAILABLE') +
        '</td><td class="small" title="' + h(revision) + '">' + h(shortRevision) +
        '</td><td class="tnum">' + val(r.settled, 0) +
        '</td><td class="tnum">' + val(r.raw_settled, r.settled || 0) +
        '</td><td class="tnum">' + val(r.overlap_purged, 0) +
        '</td><td>' + chip(r.status) +
        '</td><td class="tnum">' + pct(r.hit_rate) +
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
  function configurationExperienceRows(rows) {
    return (rows || []).map(function (r) {
      const fp = String(r.strategy_fingerprint || 'UNAVAILABLE');
      const shortFp = fp === 'UNAVAILABLE' ? fp : fp.slice(0, 12) + '…';
      const chart = [r.chart_type || 'UNAVAILABLE', r.timeframe || 'UNAVAILABLE'].join(' / ');
      const execution = [r.fill_on || 'UNAVAILABLE', r.security_source || 'UNAVAILABLE'].join(' / ');
      return '<tr><td title="' + h(fp) + '"><b>' + h(shortFp) + '</b></td><td>' + h(r.provenance_class || 'UNAVAILABLE') +
        '</td><td>' + h(r.asset) + '</td><td>' + h(r.direction) + '</td><td>' + h(r.session_mode || 'UNAVAILABLE') +
        '</td><td>' + h(chart) + '</td><td>' + h(execution) +
        '</td><td>' + h(r.preset || 'UNAVAILABLE') + '</td><td>' + chip(r.status) +
        '</td><td class="tnum">' + val(r.count,0) + '</td><td class="tnum">' + pct(r.win_rate) +
        '</td><td class="tnum">' + val(r.net_pnl,2) + '</td><td class="tnum">' + val(r.average_pnl,2) +
        '</td><td class="tnum">' + val(r.payoff_ratio,3) + '</td><td class="tnum">' + val(r.max_cumulative_drawdown,2) + '</td></tr>';
    });
  }
  function artifactExperienceRows(rows) {
    return (rows || []).map(function (r) {
      const fp = String(r.artifact_configuration_fingerprint || 'UNAVAILABLE');
      const shortFp = fp === 'UNAVAILABLE' ? fp : fp.slice(0, 12) + '…';
      const chart = [r.chart_type || 'UNAVAILABLE', r.timeframe || 'UNAVAILABLE'].join(' / ');
      return '<tr><td title="' + h(fp) + '"><b>' + h(shortFp) + '</b></td><td>' + h(r.provenance_class || 'UNAVAILABLE') +
        '</td><td>' + h(r.asset) + '</td><td>' + h(r.direction) + '</td><td>' + h(r.session_mode || 'UNAVAILABLE') +
        '</td><td>' + h(chart) +
        '</td><td class="small">' + h(r.strategy_report_filename || 'UNAVAILABLE') +
        '</td><td class="small" title="' + h(r.strategy_report_sha256 || '') + '">' +
        h((r.strategy_report_sha256 || 'UNAVAILABLE').slice(0, 12) + (r.strategy_report_sha256 ? '…' : '')) +
        '</td><td>' + chip(r.status) + '</td><td class="tnum">' + val(r.count,0) +
        '</td><td class="tnum">' + pct(r.win_rate) + '</td><td class="tnum">' + val(r.net_pnl,2) +
        '</td><td class="tnum">' + val(r.average_pnl,2) + '</td><td class="tnum">' + val(r.profit_factor,3) +
        '</td><td class="tnum">' + val(r.payoff_ratio,3) + '</td><td class="tnum">' + val(r.max_cumulative_drawdown,2) + '</td></tr>';
    });
  }
  function shadowCalibrationRows(rows) {
    return (rows || []).map(function (r) {
      const delta = (r.raw_validation_brier == null || r.calibrated_validation_brier == null)
        ? null : Number(r.raw_validation_brier) - Number(r.calibrated_validation_brier);
      const revision = String(r.source_commit || 'UNAVAILABLE');
      const shortRevision = revision === 'UNAVAILABLE' ? revision : revision.slice(0, 12) + '…';
      return '<tr><td><b>' + h(r.producer) + '</b></td><td>' + h(r.asset) +
        '</td><td>' + h(r.regime) + '</td><td class="tnum">' + val(r.horizon_seconds,0) +
        '</td><td>' + h(r.target) + '</td><td>' + h(r.prediction_label || 'UNAVAILABLE') +
        '</td><td class="small" title="' + h(revision) + '">' + h(shortRevision) + '</td><td>' + chip(r.status) +
        '</td><td class="tnum">' + val(r.train_count,0) + '</td><td class="tnum">' + val(r.validation_count,0) +
        '</td><td class="tnum">' + val(r.raw_validation_brier,6) +
        '</td><td class="tnum">' + val(r.calibrated_validation_brier,6) +
        '</td><td class="tnum">' + val(delta,6) + '</td><td class="small">' + h(r.training_cutoff || 'UNAVAILABLE') + '</td></tr>';
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
  function backlogRows(backlog) {
    return Object.keys(backlog || {}).sort().map(function (k) {
      return '<tr><td><b>' + h(k) + '</b></td><td class="tnum">' + val(backlog[k],0) + '</td></tr>';
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
    const shadow_calibration = state.shadow_calibration || {};
    const shadow_models = shadow_calibration.models || [];
    const shadow_assessments = shadow_calibration.assessments || {};
    const by_configuration = experience.by_configuration || [];
    const by_artifact_configuration = experience.by_artifact_configuration || [];
    const artifact_scoped_count = experience.artifact_scoped_count == null ? 0 : experience.artifact_scoped_count;
    const closure_scoped_count = experience.closure_scoped_count == null ? 0 : experience.closure_scoped_count;
    const unscoped_count = experience.unscoped_count == null ? 0 : experience.unscoped_count;
    const provenance_counts = experience.provenance_class_counts || {};
    const health = state.health || {};
    const datasets = (data || {}).datasets || [];
    const runs = (data || {}).training_runs || [];
    const latest = ((state.cycles || {}).latest) || {};
    const psi = ((((latest.summary || {}).native || {}).possibility) || {});
    panel.innerHTML =
      '<div class="tiles">' +
        '<div class="tile"><div class="k">LEARNING STATE</div><div class="v">' + chip(state.status) + '</div><div class="small muted">background ' + (state.background && state.background.running ? 'RUNNING' : 'STOPPED') + ' · cycle ' + val(cfg.cycle_seconds,0) + 's</div></div>' +
        '<div class="tile"><div class="k">LEARNER HEALTH</div><div class="v">' + chip(health.status) + '</div><div class="small muted">CONSECUTIVE FAILURES ' + val(health.consecutive_failures,0) + ' · partial ' + val(health.consecutive_partial,0) + ' · ' + (health.stale ? 'STALE' : 'fresh') + '</div></div>' +
        '<div class="tile"><div class="k">DATASET COVERAGE</div><div class="v">' + val((state.datasets || {}).count,0) + '</div><div class="small muted">content-hash deduplicated local datasets</div></div>' +
        '<div class="tile"><div class="k">TRAINING REPLAY</div><div class="v">' + val(training.run_count,0) + '</div><div class="small muted">purged walk-forward / protected holdout trainers</div></div>' +
        '<div class="tile"><div class="k">LIVE MATURITY</div><div class="v">' + val(preds.settled,0) + ' / ' + val(preds.count,0) + '</div><div class="small muted">' + val(preds.pending,0) + ' pending forecasts</div></div>' +
        '<div class="tile"><div class="k">REALIZED EXPERIENCE</div><div class="v">' + val(experience.count,0) + '</div><div class="small muted">runtime_live_sim + historical_trade_list · outcome memory, not forecast accuracy</div></div>' +
        '<div class="tile"><div class="k">MANIFEST-LINKED HISTORY</div><div class="v">' + val(artifact_scoped_count,0) + '</div><div class="small muted">HISTORICAL_ARTIFACT_CONFIG · unscoped ' + val(unscoped_count,0) + ' · never promoted to runtime configuration</div></div>' +
        '<div class="tile"><div class="k">PROVENANCE ISOLATION</div><div class="v">' + val(closure_scoped_count,0) + ' / ' + val(artifact_scoped_count,0) + '</div><div class="small muted">RUNTIME_CLOSURE_CONFIG / HISTORICAL_ARTIFACT_CONFIG · UNSCOPED ' + val(provenance_counts.UNSCOPED == null ? unscoped_count : provenance_counts.UNSCOPED,0) + '</div></div>' +
        '<div class="tile"><div class="k">EMPIRICAL SCORECARDS</div><div class="v">' + val((state.scorecards || []).length,0) + '</div><div class="small muted">producer × asset × regime × horizon × label × revision</div></div>' +
        '<div class="tile"><div class="k">SHADOW RECALIBRATION</div><div class="v">' + val(shadow_calibration.validated_model_count,0) + ' / ' + val(shadow_calibration.model_count,0) + '</div><div class="small muted">VALIDATED MODELS ' + val(shadow_calibration.validated_model_count,0) + ' · REJECTED MODELS ' + val(shadow_calibration.rejected_model_count,0) + ' · automatic probability rewrite: off</div></div>' +
        '<div class="tile"><div class="k">Ψ SCENARIO CALIBRATION</div><div class="v">' + chip(psi.status || 'UNAVAILABLE') + '</div><div class="small muted">captured ' + val(psi.forecasts_imported,0) + ' · matured ' + val(psi.outcomes_imported,0) + ' · overlap withheld ' + val(psi.overlap_withheld,0) + ' · RAW SHARES UNCALIBRATED · producer psi-scenario-v1</div></div>' +
        '<div class="tile"><div class="k">HISTORY SCAN</div><div class="v">' + (state.background && state.background.last_history_scan_epoch ? new Date(state.background.last_history_scan_epoch*1000).toLocaleString() : 'UNAVAILABLE') + '</div><div class="small muted">history/, history/drop/, research/imports/</div></div>' +
        '<div class="tile"><div class="k">LAST CYCLE</div><div class="v">' + chip(latest.status || 'UNAVAILABLE') + '</div><div class="small muted">' + val((state.cycles || {}).count,0) + ' durable cycles</div></div>' +
        '<div class="tile"><div class="k">AUTHORITY</div><div class="v">RESEARCH ONLY</div><div class="small muted">AUTOMATIC PRODUCTION PROMOTION: OFF · execution_authorized=false</div></div>' +
      '</div>' +
      '<h3 class="small" style="margin:16px 0 8px">EMPIRICAL SCORECARDS · LABEL-SCOPED · REVISION-SCOPED</h3>' +
      '<div class="small muted" style="margin-bottom:8px">Credibility metrics, Wilson intervals, and MEASURED/EARLY state use effective non-overlapping outcomes. Raw settled and overlap-purged counts remain visible for audit.</div>' +
      table(['Producer','Asset','Regime','Horizon s','Target','Prediction label','Source revision','Effective settled','Raw settled','Overlap purged','State','Hit rate','Mean Brier','Calibration gap'], scoreRows(state.scorecards), 'UNMEASURED — no matured outcomes yet.') +
      '<h3 class="small" style="margin:16px 0 8px">SHADOW RECALIBRATION · LABEL-SCOPED · REVISION-SCOPED · RAW VS CALIBRATED BRIER</h3>' +
      '<div class="small muted" style="margin-bottom:8px">Chronological 80/20 holdout only. Holdout raw Brier and Holdout calibrated Brier determine whether a map is SHADOW_VALIDATED. Settled shadow assessments: ' + val(shadow_assessments.settled,0) + ' · pending ' + val(shadow_assessments.pending,0) + ' · live raw Brier ' + val(shadow_assessments.mean_raw_brier,6) + ' · live calibrated Brier ' + val(shadow_assessments.mean_calibrated_brier,6) + '. Automatic probability rewrite: OFF.</div>' +
      table(['Producer','Asset','Regime','Horizon s','Target','Prediction label','Source revision','State','Train','Holdout','Holdout raw Brier','Holdout calibrated Brier','Brier improvement','Evidence cutoff'], shadowCalibrationRows(shadow_models), 'UNMEASURED — no holdout-validated shadow calibrators yet.') +
      '<h3 class="small" style="margin:16px 0 8px">REALIZED EXPERIENCE · P&L MEMORY</h3>' +
      table(['Source','Asset','Direction','State','Count','Win rate','Net P&L','Avg P&L','PROFIT FACTOR'], experienceRows(experience.summary), 'UNMEASURED — no fully closed realized trade experience yet.') +
      '<h3 class="small" style="margin:16px 0 8px">STRATEGY CONFIGURATION EXPERIENCE · CLOSURE-TIME PROVENANCE · RUNTIME_CLOSURE_CONFIG</h3>' +
      '<div class="small muted" style="margin-bottom:8px">Only runtime_live_sim trades carrying an exact closure-time configuration receipt and source-bound RUNTIME_CLOSURE_CONFIG appear here. Historical evidence cannot enter this class. Unscoped realized experience: ' + val(unscoped_count,0) + '.</div>' +
      table(['Strategy fingerprint','Provenance class','Asset','Side','Session','Chart / TF','Fill / Security','Preset','State','Count','Win rate','Net P&L','Avg P&L','PAYOFF RATIO','MAX DRAWDOWN'], configurationExperienceRows(by_configuration), 'UNMEASURED — no closure-scoped strategy experience yet.') +
      '<h3 class="small" style="margin:16px 0 8px">HISTORICAL ARTIFACT CONFIGURATION EXPERIENCE · HISTORICAL_ARTIFACT_CONFIG</h3>' +
      '<div class="small muted" style="margin-bottom:8px">Manifest/direct strategy-report evidence is source-bound to HISTORICAL_ARTIFACT_CONFIG. Explicit RTH/ETH manifest session evidence is preserved and can disambiguate otherwise identical reports; missing session evidence remains UNAVAILABLE and is never inferred. Artifact-scoped trades: ' + val(artifact_scoped_count,0) + '.</div>' +
      table(['Manifest-linked artifact fingerprint','Provenance class','Asset','Side','Session','Chart / TF','Strategy report','Report SHA','State','Count','Win rate','Net P&L','Avg P&L','PROFIT FACTOR','PAYOFF RATIO','MAX DRAWDOWN'], artifactExperienceRows(by_artifact_configuration), 'UNMEASURED — no uniquely manifest-linked historical artifact experience yet.') +
      '<h3 class="small" style="margin:16px 0 8px">DATASET COVERAGE · TRAINING REPLAY</h3>' +
      table(['Asset','Cadence','Class','Rows','Coverage','Representation','Replay status','Action'], datasetRows(datasets,runs), 'UNAVAILABLE — no local historical datasets catalogued yet.') +
      '<h3 class="small" style="margin:16px 0 8px">LEARNING BACKLOG</h3>' +
      table(['BACKLOG','Pending'], backlogRows(health.backlog), 'UNAVAILABLE') +
      '<div class="small muted">Last completed: ' + h(health.last_completed_at || 'UNAVAILABLE') + ' · last error: ' + h(health.last_error || 'none') + '</div>' +
      '<h3 class="small" style="margin:16px 0 8px">SYSTEM LEARNING COVERAGE</h3>' +
      table(['Subsystem','Learning contract'], coverageRows(state.coverage), 'UNAVAILABLE') +
      '<div class="small muted" style="margin-top:12px">The learner does not treat repeated model agreement as new evidence. Credibility moves only from matured observed outcomes or protected historical replay. Missing metrics remain UNAVAILABLE/UNMEASURED.</div>';
  }
  async function loadLearning() {
    const seq = ++loadSeq;
    const panel = document.querySelector('#learningPanel');
    if (!panel) return;
    try {
      const triple = await Promise.all([getJson('/api/learning'), getJson('/api/learning/datasets'), getJson('/api/learning/health')]);
      if (seq !== loadSeq) return;
      lastState = triple[0]; lastState.health = triple[2]; lastDatasets = triple[1]; render(lastState, lastDatasets);
    } catch (err) {
      if (seq !== loadSeq) return;
      panel.innerHTML = '<div class="empty">Learning Fabric UNAVAILABLE: ' + h(err && err.message ? err.message : err) + '</div>';
    }
  }
  async function action(fn, button) {
    const panel = document.querySelector('#learningPanel');
    if (mutationBusy) {
      if (typeof toast === 'function') toast('Learning action already running', true);
      return;
    }
    mutationBusy = true;
    if (button) button.disabled = true;
    try { await fn(); await loadLearning(); }
    catch (err) { if (panel) panel.insertAdjacentHTML('afterbegin','<div class="empty">' + h(err && err.message ? err.message : err) + '</div>'); }
    finally {
      mutationBusy = false;
      if (button && button.isConnected) button.disabled = false;
    }
  }
  function wireLearning() {
    const refresh = document.querySelector('#learningRefresh');
    const tick = document.querySelector('#learningTick');
    const scan = document.querySelector('#learningScan');
    const toggle = document.querySelector('#learningToggle');
    const panel = document.querySelector('#learningPanel');
    if (refresh) refresh.addEventListener('click', loadLearning);
    if (tick) tick.addEventListener('click', function () { action(function () { return postJson('/admin/learning/tick', {}); }, tick); });
    if (scan) scan.addEventListener('click', function () { action(function () { return postJson('/admin/learning/scan', {}); }, scan); });
    if (toggle) toggle.addEventListener('click', function () { action(function () { return postJson('/admin/learning/config', {enabled: !(lastState && lastState.config && lastState.config.enabled)}); }, toggle); });
    if (panel) panel.addEventListener('click', function (ev) {
      const button = ev.target.closest('[data-learn-backfill]');
      if (!button) return;
      const datasetId = button.getAttribute('data-learn-backfill');
      action(function () { return postJson('/admin/learning/backfill', {dataset_id:datasetId, slots:['logit']}); }, button);
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
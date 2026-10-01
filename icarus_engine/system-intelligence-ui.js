/* ICARUS read-only MCP / subsystem intelligence surface. */
(function () {
  const statusClass = status => status === 'merged' || status === 'verified' ? 'b'
    : status === 'blocked' ? 'r' : status === 'in_progress' ? 'w' : '';

  const checkClass = status => /pass|verified|merged|committed|recorded|added/i.test(status || '') ? 'b'
    : /fail|error|blocked|missing/i.test(status || '') ? 'r' : 'w';

  const clean = value => typeof value === 'string' ? value : '';

  window.systemIntelligenceHtml = function systemIntelligenceHtml(data) {
    const d = data || window.ICARUS_SYSTEM_INTELLIGENCE;
    if (!d) {
      return '<section class="card c12" id="systemIntelligenceRoot"><h2>System intelligence <span class="sub">MCP repairs · audits · subsystem evolution</span></h2><div class="empty">Loading system intelligence…</div></section>';
    }

    const s = d.summary || {};
    const items = Array.isArray(d.items) ? d.items : [];
    const warnings = Array.isArray(d.warnings) ? d.warnings : [];
    const mirror = d.mirror_ok === true;
    const runtime = d.runtime || {};
    const mirrorBanner = mirror
      ? '<div class="callout" style="border-color:var(--good);background:rgba(12,163,12,.07)"><div>✓</div><div><b>Interface mirror intact</b>Every important MCP item in this manifest has an ICARUS interface surface.</div></div>'
      : '<div class="callout" style="border-color:var(--crit);background:rgba(208,59,59,.08)"><div>!</div><div><b>Interface mirror incomplete</b>An important MCP change is missing an ICARUS surface. Treat the intelligence mirror as degraded until corrected.</div></div>';

    const rows = items.map(item => {
      const v = item.validation || {};
      const checks = Array.isArray(v.checks) ? v.checks : [];
      const checkHtml = checks.length
        ? checks.map(c => '<span class="chip ' + checkClass(c.status) + '" title="' + esc(clean(c.detail)) + '">' + esc(clean(c.name)) + ' · ' + esc(clean(c.status)) + '</span>').join(' ')
        : '<span class="muted">no checks recorded</span>';
      const commit = clean(item.source_commit);
      return '<tr>'
        + '<td><b>' + esc(clean(item.subsystem)) + '</b><div class="small muted">' + esc(clean(item.kind)) + '</div></td>'
        + '<td><span class="chip ' + statusClass(item.status) + '">' + esc(clean(item.status)) + '</span><div class="small muted">' + esc(clean(item.surface_status)) + '</div></td>'
        + '<td style="white-space:normal;min-width:280px"><b>' + esc(clean(item.summary)) + '</b><div class="small muted" style="margin-top:4px">' + esc(clean(item.detail)) + '</div></td>'
        + '<td style="white-space:normal;min-width:220px">' + checkHtml + '</td>'
        + '<td class="small"><div>' + esc(clean(item.source_repo)) + '</div><div class="muted">' + esc(clean(item.source_branch)) + '</div><code title="' + esc(commit) + '">' + esc(commit ? commit.slice(0,12) : '—') + '</code></td>'
        + '<td><span class="chip ' + (item.surface_status === 'mirrored' ? 'b' : 'r') + '">' + esc(clean(item.interface_surface) || 'MISSING') + '</span></td>'
        + '</tr>';
    }).join('');

    const warningHtml = warnings.length
      ? '<section class="card c12"><h2>Mirror warnings</h2><div class="log">' + warnings.map(w => '<div class="WARN">' + esc(String(w)) + '</div>').join('') + '</div></section>'
      : '';

    return ''
      + '<div id="systemIntelligenceRoot" style="display:contents">'
      + mirrorBanner
      + '<section class="card c12">'
      + '<h2>System intelligence <span class="sub">MCP repairs · audits · subsystem evolution · read only</span></h2>'
      + '<div class="tiles">'
      + '<div class="tile"><div class="k">Tracked</div><div class="v tnum">' + Number(s.total || 0) + '</div></div>'
      + '<div class="tile"><div class="k">Important</div><div class="v tnum">' + Number(s.important || 0) + '</div></div>'
      + '<div class="tile"><div class="k">Verified / merged</div><div class="v tnum">' + Number(s.verified_or_merged || 0) + '</div></div>'
      + '<div class="tile"><div class="k">Needs attention</div><div class="v tnum">' + Number(s.needs_attention || 0) + '</div></div>'
      + '<div class="tile"><div class="k">Mirror</div><div class="v ' + (mirror ? 'pos' : 'neg') + '">' + (mirror ? 'OK' : 'DEGRADED') + '</div></div>'
      + '<div class="tile"><div class="k">Engine</div><div class="v" style="font-size:15px">' + esc(clean(runtime.feed_mode) || '—') + '</div><small class="muted">' + (runtime.all_warm ? 'warm' : 'not fully warm') + '</small></div>'
      + '</div>'
      + '<div class="row"><button class="sm" id="systemIntelligenceRefresh" type="button">Refresh</button>'
      + '<span class="small muted">Generated ' + esc(clean(d.generated_at) || 'unknown') + ' · reported ' + esc(clean(runtime.reported_at) || 'unknown') + '</span></div>'
      + '</section>'
      + '<section class="card c12"><h2>Evolution ledger <span class="sub">Important changes must surface here</span></h2>'
      + '<div class="scroll" style="max-height:62vh"><table><thead><tr><th>Subsystem</th><th>Status</th><th>Change</th><th>Validation</th><th>Provenance</th><th>Interface</th></tr></thead>'
      + '<tbody>' + (rows || '<tr><td colspan="6" class="empty">No intelligence items recorded.</td></tr>') + '</tbody></table></div>'
      + '</section>'
      + '<section class="card c12"><h2>Authority boundary</h2><div class="small">'
      + '<b>Display and evidence only.</b> This panel cannot place orders, modify strategy inputs, change assets/timeframes, arm a broker, or convert research evidence into production authority.'
      + '</div><div class="small muted" style="margin-top:6px">execution_authorized=' + String(d.execution_authorized === true) + ' · production_authorized=' + String(d.production_authorized === true) + '</div></section>'
      + warningHtml
      + '</div>';
  };

  window.loadSystemIntelligence = async function loadSystemIntelligence() {
    try {
      const response = await fetch('/api/system-intelligence', {cache: 'no-store'});
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || data.error || ('HTTP ' + response.status));
      window.ICARUS_SYSTEM_INTELLIGENCE = data;
      const root = document.querySelector('#systemIntelligenceRoot');
      if (root && root.parentElement) {
        const host = root.parentElement;
        host.innerHTML = window.systemIntelligenceHtml(data);
        window.wireSystemIntelligence();
      }
      return data;
    } catch (error) {
      window.ICARUS_SYSTEM_INTELLIGENCE = {
        schema: 'icarus.system-intelligence.v1',
        mirror_ok: false,
        execution_authorized: false,
        production_authorized: false,
        summary: {total: 0, important: 0, verified_or_merged: 0, needs_attention: 1},
        runtime: {},
        items: [],
        warnings: ['System intelligence unavailable: ' + error.message],
      };
      return window.ICARUS_SYSTEM_INTELLIGENCE;
    }
  };

  window.wireSystemIntelligence = function wireSystemIntelligence() {
    const button = document.querySelector('#systemIntelligenceRefresh');
    if (button) button.onclick = () => window.loadSystemIntelligence();
  };
})();

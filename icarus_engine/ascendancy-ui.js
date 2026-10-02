(() => {
  'use strict';

  let timer = null;

  const h = v => String(v == null ? '' : v).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));

  function statusClass(value) {
    const s = String(value || 'UNVERIFIED').toUpperCase();
    if (s.startsWith('VERIFIED')) return 'pos';
    if (s.startsWith('BLOCKED')) return 'neg';
    return 'muted';
  }

  function ascendancyHtml() {
    return '<section class="card c12" id="ascendancyPanel">' +
      '<div><h2 style="margin-bottom:4px">ASCENDANCY · Capability Orchestrator</h2>' +
      '<div class="small muted">External/internal capability truth plane · evidence contracts · degradation visibility · research/shadow only</div></div>' +
      '<div id="ascendancyBody" style="margin-top:12px"><div class="empty">loading capability contracts…</div></div>' +
      '</section>';
  }

  function renderAscendancy(d) {
    const el = document.querySelector('#ascendancyBody');
    if (!el) return;
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

    el.innerHTML =
      '<div class="tiles">' +
        '<div class="tile"><div class="k">PROVIDERS</div><div class="v tnum">' + h(d.provider_count) + '</div></div>' +
        '<div class="tile"><div class="k">VERIFIED</div><div class="v pos tnum">' + h(d.verified_count) + '</div></div>' +
        '<div class="tile"><div class="k">BLOCKED</div><div class="v neg tnum">' + h(d.blocked_count) + '</div><div class="small muted">subscription / network policy remain visible</div></div>' +
        '<div class="tile"><div class="k">UNPROBED</div><div class="v tnum">' + h(d.unprobed_count) + '</div></div>' +
        '<div class="tile"><div class="k">AUTHORITY</div><div class="v">RESEARCH ONLY</div><div class="small muted">execution_authorized=false · production_decision_authorized=false</div></div>' +
      '</div>' +
      '<div class="small muted" style="margin:10px 0">Audit ' + h(d.audit_observed_at || 'UNAVAILABLE') + ' · ' + h(d.audit_rule || '') +
      ' · blocked states include BLOCKED_SUBSCRIPTION and BLOCKED_NETWORK_POLICY when observed.</div>' +
      '<div class="scroll" style="max-height:62vh"><table><thead><tr>' +
        '<th>Capability</th><th>Observed state</th><th>Claims allowed</th><th>Forbidden inferences</th><th>Authority domain</th>' +
      '</tr></thead><tbody>' + (body || '<tr><td colspan="5" class="empty">UNAVAILABLE — no capability contracts loaded.</td></tr>') +
      '</tbody></table></div>' +
      '<div class="small muted" style="margin-top:10px">Contract keys: claims_allowed / claims_forbidden. Tool presence never becomes market truth, and an unavailable source never becomes a zero-valued observation.</div>';
  }

  async function loadAscendancy() {
    const el = document.querySelector('#ascendancyBody');
    if (!el) return;
    try {
      const token = localStorage.getItem('icarus-engine-token') || 'icarus';
      const response = await fetch('/api/ascendancy/capabilities', {
        cache:'no-store',
        headers:{'Authorization':'Bearer ' + token}
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || ('ASCENDANCY HTTP ' + response.status));
      renderAscendancy(data);
    } catch (err) {
      el.innerHTML = '<div class="empty">ASCENDANCY capability state UNAVAILABLE: ' + h(err && err.message ? err.message : err) + '</div>';
    }
  }

  function wireAscendancy() {
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

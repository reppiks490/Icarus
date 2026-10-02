(() => {
  let timer = null;
  const h = value => String(value ?? '').replace(/[&<>"]/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[ch]));

  function cls(value) {
    const s = String(value || '').toUpperCase();
    if (s.includes('VERIFIED') || s.includes('SUCCESS') || s === 'GREEN' || s === 'QUALIFIED' || s === 'ACTIVE') return 'b';
    if (s.includes('ERROR') || s.includes('FAIL') || s.includes('BLOCK') || s.includes('REJECT')) return 'r';
    return 'w';
  }

  function evolutionHtml() {
    return '<section class="card c12" id="evolutionPanel">' +
      '<h2>MCP Evolution <span class="sub">repairs · audits · subsystem evolution · provenance · read only</span></h2>' +
      '<div class="empty">loading verified repository-native MCP events…</div></section>';
  }

  function renderEvolution(state) {
    const el = document.querySelector('#evolutionPanel');
    if (!el) return;

    const events = Array.isArray(state.events) ? state.events : [];
    const subsystems = state.subsystems && typeof state.subsystems === 'object' ? state.subsystems : {};
    const subRows = Object.entries(subsystems)
      .sort((a,b) => String((b[1]||{}).recorded_at||'').localeCompare(String((a[1]||{}).recorded_at||'')))
      .map(([name, row]) => '<div class="evo-sub '+cls(row.status)+'">' +
        '<div style="display:flex;justify-content:space-between;gap:8px;align-items:center"><b>'+h(name.toUpperCase())+'</b><span class="chip '+cls(row.status)+'">'+h(String(row.status||'unknown').toUpperCase())+'</span></div>' +
        '<div class="small" style="margin-top:6px"><b>'+h(row.title||'')+'</b></div>' +
        '<div class="small muted" style="margin-top:4px">'+h(row.summary||'')+'</div>' +
        '<div class="small muted tnum" style="margin-top:5px">'+h(row.recorded_at||'—')+' · '+h(row.source_repository||'')+' · '+h(String(row.source_commit||row.source_ref||'').slice(0,16))+'</div>' +
      '</div>').join('');

    const eventRows = events.slice(0,100).map(row => '<tr>' +
      '<td class="tnum">'+h(row.recorded_at||'—')+'</td>' +
      '<td><span class="chip '+cls(row.severity)+'">'+h(row.category||'EVENT')+'</span></td>' +
      '<td>'+((row.subsystems||[]).map(s=>'<span class="chip">'+h(String(s).toUpperCase())+'</span>').join(' '))+'</td>' +
      '<td><b>'+h(row.title||'')+'</b><div class="small muted">'+h(row.summary||'')+'</div></td>' +
      '<td class="tnum"><div>'+h(row.source_repository||'')+'</div><div class="muted small">'+h(String(row.source_commit||row.source_ref||'').slice(0,16))+'</div></td>' +
    '</tr>').join('');

    el.innerHTML = '<style>' +
      '.evo-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:10px}' +
      '.evo-sub{border:1px solid var(--ring);border-radius:12px;padding:10px;background:var(--surface-2)}' +
      '.evo-sub.b{border-color:var(--good)}.evo-sub.r{border-color:var(--crit)}.evo-sub.w{border-color:var(--warn)}' +
      '</style>' +
      '<h2>MCP Evolution <span class="sub">repository-native verified feed · execution_authorized=false</span></h2>' +
      '<div class="tiles" style="margin-top:0">' +
        '<div class="tile"><div class="k">Sync status</div><div class="v"><span class="chip '+cls(state.status)+'">'+h(String(state.status||'unknown').toUpperCase())+'</span></div></div>' +
        '<div class="tile"><div class="k">Events ingested</div><div class="v tnum">'+h(state.ingested_total ?? 0)+'</div></div>' +
        '<div class="tile"><div class="k">Subsystems surfaced</div><div class="v tnum">'+h(Object.keys(subsystems).length)+'</div></div>' +
        '<div class="tile"><div class="k">Current invalid receipts</div><div class="v tnum '+((state.current_rejected_count||0)>0?'neg':'pos')+'">'+h(state.current_rejected_count ?? 0)+'</div><div class="small muted">present rejected Git blob versions</div></div>' +
        '<div class="tile"><div class="k">Rejected versions total</div><div class="v tnum">'+h(state.rejected_total ?? 0)+'</div><div class="small muted">unique versions since dedupe accounting'+((state.legacy_rejection_attempt_total||0)>0?' · legacy attempts '+h(state.legacy_rejection_attempt_total)+' not treated as unique':'')+'</div></div>' +
        '<div class="tile"><div class="k">Other receipt families</div><div class="v tnum">'+h(state.ignored_total ?? 0)+'</div><div class="small muted">valid non-interface schemas ignored by this feed</div></div>' +
        '<div class="tile"><div class="k">Last successful ingest</div><div class="v small">'+h(state.last_success_at||'awaiting first ingest')+'</div></div>' +
        '<div class="tile"><div class="k">Authority</div><div class="v">READ ONLY</div><div class="small muted">no production decision or execution authority</div></div>' +
      '</div>' +
      '<div class="small muted" style="margin-top:10px">Feed: '+h(state.repository||'')+' / '+h(state.root||'')+' @ '+h(state.ref||'')+' · poll '+h(state.interval_seconds||'—')+'s'+(state.last_error ? ' · '+h(state.last_error) : '')+'</div>' +
      '<h3 class="small" style="margin:16px 0 8px">Subsystem evolution state</h3>' +
      '<div class="evo-grid">'+(subRows || '<div class="empty">No subsystem MCP receipts have been ingested yet.</div>')+'</div>' +
      '<h3 class="small" style="margin:16px 0 8px">Important MCP activity</h3>' +
      '<div class="scroll" style="max-height:560px"><table><thead><tr><th>Time</th><th>Kind</th><th>Subsystems</th><th>Event</th><th>Source</th></tr></thead><tbody>'+(eventRows || '<tr><td colspan="5" class="empty">No repository-native MCP events yet.</td></tr>')+'</tbody></table></div>' +
      '<div class="small muted" style="margin-top:12px">This panel is observability only. Foreign receipt schemas in the shared repository directory are counted as ignored, not rejected. Persistently invalid Git blob versions keep the feed degraded but are counted only once; replacing or removing that blob clears the current-invalid state without erasing historical rejection totals. A repair, audit, model evolution, provenance change, or subsystem finding appearing here does not grant a trade signal, production promotion, or broker permission.</div>';
  }

  async function loadEvolution() {
    const el = document.querySelector('#evolutionPanel');
    if (!el) return;
    try {
      const tok = localStorage.getItem('icarus-engine-token') || 'icarus';
      const r = await fetch('/api/evolution', {cache:'no-store', headers:{'Authorization':'Bearer '+tok}});
      const state = await r.json();
      if (!r.ok) throw new Error(state.detail || ('HTTP '+r.status));
      renderEvolution(state);
    } catch (err) {
      el.innerHTML = '<h2>MCP Evolution</h2><div class="empty">evolution feed unavailable: '+h(err.message||err)+'</div>';
    }
  }

  function wireEvolution() {
    loadEvolution();
    if (timer) clearInterval(timer);
    timer = setInterval(() => {
      if ((location.hash || '#overview').slice(1) === 'evolution') loadEvolution();
    }, 5000);
  }

  window.evolutionHtml = evolutionHtml;
  window.wireEvolution = wireEvolution;
  window.loadEvolution = loadEvolution;
})();

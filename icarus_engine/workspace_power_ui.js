/* Independent paper worker lifecycle. Page identity is captured once from server context. */
'use strict';
(() => {
  const source = window.IcarusClient?.context || window.IcarusWorkspace;
  const ids = Object.freeze(['cc1', 'cc2', 'cc3', 'cc4']);
  const nativeFetch = window.fetch.bind(window);
  const connections = ['/connections', '/dashboards/connections'].includes(location.pathname);
  if (connections) {
    const mountLink = () => {
      const host = document.querySelector('.shell > header');
      if (!host) return;
      const link = document.createElement('a');
      link.href = '/';
      link.textContent = 'Paper worker on/off controls in Main';
      link.style.cssText = 'display:block;margin:12px 0;color:var(--accent,#2878c8)';
      host.after(link);
    };
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mountLink, {once:true});
    else mountLink();
    return;
  }
  if (!source || !Object.isFrozen(source) || !['main', ...ids].includes(source.id)) return;
  const context = Object.freeze({id:source.id});
  const visible = context.id === 'main' ? ids : [context.id];
  const states = new Set(['ON', 'OFF', 'STARTING', 'STOPPING', 'ERROR']);
  const records = new Map(), pending = new Set(), errors = new Map(), rows = new Map();
  const activeRequests = new Set();
  let section, status, flight = null, timer = null, active = true, available = false, lifecycle = 0;
  let finishReady;
  const ready = new Promise(resolve => { finishReady = resolve; });

  function token() {
    return window.IcarusClient?.getToken?.() || window.IcarusWorkspaceAuth?.getToken?.() || '';
  }
  function validRecord(value) {
    if (!value || !ids.includes(value.id) || typeof value.desired_enabled !== 'boolean' ||
        !states.has(value.runtime_state) || !Number.isSafeInteger(value.revision) || value.revision < 0 ||
        !(value.error == null || typeof value.error === 'string')) throw Error('Invalid paper worker metadata');
    return Object.freeze({id:value.id, desired_enabled:value.desired_enabled,
      runtime_state:value.runtime_state, revision:value.revision,
      error:typeof value.error === 'string' ? value.error.slice(0, 600) : null});
  }
  function paperReceipt(data) {
    if (data?.paper_only !== true || data?.execution_authorized !== false) throw Error('Invalid paper worker safety receipt');
  }
  async function request(path, body, attempt=0, generation=lifecycle) {
    if (!active || generation !== lifecycle) throw Error('Paper worker request cancelled');
    if (!token()) {
      window.dispatchEvent(new Event('icarus:auth-required'));
      throw Error('Authentication required');
    }
    const controller = new AbortController();
    activeRequests.add(controller);
    const deadline = setTimeout(() => controller.abort(), 2000);
    try {
      const response = await nativeFetch(path, {method:body === undefined ? 'GET' : 'POST',
        cache:'no-store', signal:controller.signal,
        headers:{'Authorization':'Bearer ' + token(), 'X-Icarus-Workspace':context.id,
          ...(body === undefined ? {} : {'Content-Type':'application/json'})},
        ...(body === undefined ? {} : {body:JSON.stringify(body)})});
      const data = await response.json().catch(() => null);
      if (!response.ok) {
        const reason = typeof data?.detail === 'string' ? data.detail :
          typeof data?.error === 'string' ? data.error : 'Request refused';
        // This exact admission failure is emitted before any change is accepted.
        // Keep the original revision/body; never replay accepted changes or other refusals.
        if (body !== undefined && response.status === 409 &&
            reason === 'Workspace is busy; retry after its current operation.' && attempt < 3) {
          await new Promise(resolve => setTimeout(resolve, 100 * 2 ** attempt));
          if (!active || generation !== lifecycle || controller.signal.aborted)
            throw Error('Paper worker request cancelled');
          return request(path, body, attempt + 1, generation);
        }
        throw Error(`HTTP ${response.status} · ${reason}`);
      }
      if (!data) throw Error('Invalid paper worker response');
      return data;
    } catch (error) {
      if (error?.name === 'AbortError') throw Error('Paper worker request exceeded its 2 second deadline');
      throw error;
    } finally {
      clearTimeout(deadline);
      activeRequests.delete(controller);
    }
  }
  function isOff(id) {
    return ids.includes(id) && (!available || records.get(id)?.runtime_state !== 'ON');
  }
  function publish() {
    window.dispatchEvent(new CustomEvent('icarus:workspace-power', {detail:Object.freeze({
      context, available, workspaces:Object.freeze(ids.map(id => records.get(id)).filter(Boolean))
    })}));
  }
  function render() {
    if (!section) return;
    for (const [id, row] of rows) {
      const record = records.get(id), transitioning = ['STARTING', 'STOPPING'].includes(record?.runtime_state);
      const retryStop = record?.runtime_state === 'ERROR' && !record.desired_enabled;
      // The switch reflects confirmed workers. Desired startup is identified by STARTING below.
      row.input.checked = record?.runtime_state === 'ON';
      row.input.disabled = !available || !record || pending.has(id) || transitioning || retryStop;
      row.input.setAttribute('aria-busy', String(pending.has(id) || transitioning));
      row.cancel.hidden = !(record?.runtime_state === 'STARTING' && record.desired_enabled || retryStop);
      row.cancel.disabled = row.cancel.hidden || !available || pending.has(id);
      row.cancel.textContent = retryStop ? 'Retry stop' : 'Cancel start';
      row.cancel.setAttribute('aria-label', retryStop ? 'Retry ' + id.toUpperCase() + ' stop' : 'Cancel ' + id.toUpperCase() + ' start');
      row.state.textContent = record?.runtime_state || 'UNKNOWN';
      row.state.dataset.state = record?.runtime_state || 'UNKNOWN';
      row.error.textContent = errors.get(id) || record?.error || '';
      row.note.textContent = record?.runtime_state === 'STARTING' ? 'Starting paper workers; awaiting confirmation. Cancel start switches this workspace off.' :
        record?.runtime_state === 'STOPPING' ? 'Stopping paper workers; awaiting confirmation.' :
        retryStop ? 'Stopping failed. Retry stop to finish cleanup before enabling.' :
        record?.runtime_state === 'ERROR' ? 'Worker transition failed. Review the reason before retrying.' :
        record?.runtime_state === 'OFF' ? 'Paper workers stopped. Saved settings and journals are retained.' :
        record?.runtime_state === 'ON' ? 'Paper workers running.' : 'Awaiting worker state.';
    }
  }
  function accept(record) {
    const current = records.get(record.id);
    if (!current || record.revision >= current.revision) records.set(record.id, record);
  }
  function refresh() {
    if (!active) return Promise.resolve();
    if (flight) return flight;
    flight = (async () => {
      try {
        const data = await request('/api/workspace-runtime');
        paperReceipt(data);
        if (data.schema_version !== 'icarus.workspace-power.v1' || !Array.isArray(data.workspaces) || data.workspaces.length !== 4)
          throw Error('Invalid paper worker metadata contract');
        const next = data.workspaces.map(validRecord);
        if (new Set(next.map(record => record.id)).size !== 4) throw Error('Incomplete paper worker metadata');
        if (!active) return;
        next.forEach(accept);
        available = true;
        status.textContent = 'Independent paper workers · Main stays running. Switching off never flattens positions.';
      } catch (error) {
        if (!active) return;
        available = false;
        status.textContent = 'Paper worker controls unavailable: ' + (error.message || String(error));
      } finally {
        flight = null;
        if (active) { render(); publish(); }
        finishReady();
      }
    })();
    return flight;
  }
  async function change(id, stopAction=false) {
    const record = records.get(id);
    if (!active || !available || !record || pending.has(id) ||
        context.id !== 'main' && context.id !== id || record.runtime_state === 'STOPPING' ||
        record.runtime_state === 'STARTING' && !stopAction ||
        record.runtime_state === 'ERROR' && !record.desired_enabled && !stopAction ||
        stopAction && !(record.runtime_state === 'STARTING' && record.desired_enabled ||
          record.runtime_state === 'ERROR' && !record.desired_enabled)) {
      render(); return;
    }
    const generation = lifecycle;
    pending.add(id); errors.delete(id); render();
    try {
      const data = await request(`/admin/command-centers/${id}/runtime`,
        {enabled:stopAction ? false : record.runtime_state !== 'ON', expected_revision:record.revision});
      paperReceipt(data);
      if (data.ok !== true) throw Error('Worker transition was not accepted');
      const updated = validRecord(data.workspace);
      if (updated.id !== id) throw Error('Worker receipt belongs to another workspace');
      if (updated.revision < record.revision) throw Error('Stale worker transition receipt');
      if (!active || generation !== lifecycle) return;
      accept(updated); render(); publish();
    } catch (error) {
      if (active && generation === lifecycle) errors.set(id, error.message || String(error));
    } finally {
      // Wait for any earlier read, then obtain a read started after this action.
      if (flight) await flight;
      if (active) await refresh();
      pending.delete(id); render();
    }
  }
  function mount() {
    const host = document.querySelector('.top > #tabs')?.parentElement || document.querySelector('.shell > header');
    if (!host) { finishReady(); return; }
    const style = document.createElement('style');
    style.textContent = `
      #workspace-power{color:var(--ink,#e6edf5);background:var(--surface,var(--panel,#101d2b));border:1px solid var(--grid,var(--line,#34495f));border-radius:10px;margin:10px 22px;padding:12px;min-width:0;font:13px/1.45 system-ui,sans-serif;overflow-wrap:anywhere}
      #workspace-power h2{font:600 13px/1.4 system-ui,sans-serif;margin:0 0 4px;color:inherit}
      #workspace-power p{margin:4px 0;color:var(--ink-2,var(--muted,#a5b6c7))}
      #workspace-power .power-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,230px),1fr));gap:10px;margin-top:10px}
      #workspace-power [data-power-row]{min-width:0;padding:10px;border:1px solid var(--grid,var(--line,#34495f));border-radius:8px;background:var(--surface-2,#16283a)}
      #workspace-power label{display:flex;align-items:center;gap:10px;flex-wrap:wrap;cursor:pointer;color:inherit}
      #workspace-power input{appearance:auto;flex:0 0 auto;width:20px;height:20px;margin:0;accent-color:var(--s1,#72e4ca);cursor:pointer}
      #workspace-power input:focus-visible{outline:3px solid var(--s1,#72e4ca);outline-offset:4px}
      #workspace-power input:disabled{cursor:wait}
      #workspace-power button{margin-top:6px;max-width:100%;font:inherit;color:inherit;background:var(--surface,var(--panel,#101d2b));border:1px solid var(--axis,#496176);border-radius:7px;padding:6px 10px;cursor:pointer}
      #workspace-power button:focus-visible{outline:3px solid var(--s1,#72e4ca);outline-offset:3px}
      #workspace-power button:disabled{cursor:wait}
      #workspace-power .power-label{flex:1 1 100px;min-width:0}
      #workspace-power .power-label small{display:block;font-size:11px;color:var(--ink-2,var(--muted,#a5b6c7))}
      #workspace-power [data-power-state]{font:600 11px/1.5 ui-monospace,monospace;color:inherit}
      #workspace-power [data-state=ON]{color:var(--good-text,#72e4ca)}
      #workspace-power [data-state=ERROR],#workspace-power [data-power-error]{color:var(--crit,#ff9c9c)}
      #workspace-power [data-power-error]:empty{display:none}
      #workspace-power [data-power-error]{margin:5px 0 0}
      @media(max-width:600px){#workspace-power{margin:10px 12px}.shell #workspace-power{margin:12px 0}}
    `;
    document.head.append(style);
    section = document.createElement('section'); section.id = 'workspace-power';
    section.setAttribute('aria-label', 'Paper workspace worker power');
    const title = document.createElement('h2'); title.textContent = 'Paper workspace on/off';
    status = document.createElement('p'); status.id = 'workspace-power-status';
    status.setAttribute('role', 'status'); status.setAttribute('aria-live', 'polite');
    status.textContent = 'Reading paper worker state…';
    const grid = document.createElement('div'); grid.className = 'power-grid';
    for (const id of visible) {
      const row = document.createElement('div'); row.dataset.powerRow = id;
      const label = document.createElement('label');
      const input = document.createElement('input'); input.type = 'checkbox';
      input.id = 'workspace-power-' + id; input.setAttribute('role', 'switch');
      input.setAttribute('aria-label', id.toUpperCase() + ' paper workers'); input.disabled = true;
      input.setAttribute('aria-describedby', 'workspace-power-note-' + id + ' workspace-power-error-' + id);
      const name = document.createElement('span'); name.className = 'power-label';
      name.textContent = id.toUpperCase();
      const kind = document.createElement('small'); kind.textContent = id === 'cc3' ? 'Spare paper workspace' : 'Customized paper workspace';
      name.append(kind);
      const state = document.createElement('span'); state.dataset.powerState = id;
      const note = document.createElement('p'); note.id = 'workspace-power-note-' + id;
      const error = document.createElement('p'); error.id = 'workspace-power-error-' + id;
      error.dataset.powerError = id; error.setAttribute('role', 'status'); error.setAttribute('aria-live', 'polite');
      const cancel = document.createElement('button'); cancel.type = 'button'; cancel.hidden = true;
      cancel.textContent = 'Cancel start'; cancel.setAttribute('aria-label', 'Cancel ' + id.toUpperCase() + ' start');
      cancel.setAttribute('aria-describedby', note.id);
      label.append(input, name, state); row.append(label, note, cancel, error); grid.append(row);
      rows.set(id, {input, state, note, error, cancel});
      input.addEventListener('change', () => { void change(id); });
      cancel.addEventListener('click', () => { void change(id, true); });
    }
    section.append(title, status, grid); host.after(section);
    render(); void refresh(); timer = setInterval(() => { if (!document.hidden) void refresh(); }, 5000);
  }
  Object.defineProperty(window, 'IcarusWorkspacePower', {value:Object.freeze({context, ready, isOff, refresh}), writable:false, configurable:false});
  window.addEventListener('pagehide', () => {
    active = false; lifecycle++; clearInterval(timer); activeRequests.forEach(controller => controller.abort());
  });
  window.addEventListener('pageshow', event => {
    if (event.persisted) { active = true; void refresh(); timer = setInterval(() => { if (!document.hidden) void refresh(); }, 5000); }
  });
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mount, {once:true});
  else mount();
})();

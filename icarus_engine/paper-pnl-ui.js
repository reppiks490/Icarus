/* Shared display validation. Never convert missing or stale evidence to zero. */
'use strict';
globalThis.IcarusPaperPnl = (() => {
  const ids = ['cc1', 'cc2', 'cc3', 'cc4'];
  const amount = x => typeof x === 'number' && Number.isFinite(x) && Math.abs(x) <= Number.MAX_SAFE_INTEGER;
  const sum = values => {
    if (!values.every(amount)) return null;
    let total=0, correction=0;
    for (const value of values) {
      const next=total+value;
      correction += Math.abs(total)>=Math.abs(value) ? (total-next)+value : (value-next)+total;
      total=next;
    }
    const result=total+correction;
    return amount(result) ? result : null;
  };
  const same = (a, b) => a === b || (amount(a) && amount(b) && Math.abs(a - b) <= 1e-6);
  function read(data, now = Date.now() / 1000) {
    const p = data?.paper_pnl;
    if (!Number.isFinite(now) || now < 0 || data?.mode !== 'concurrent_paper' || p?.schema_version !== 'icarus.paper-pnl.v1' || p.paper_only !== true || p.execution_authorized !== false ||
        !Number.isSafeInteger(p.as_of_ts) || p.as_of_ts < 0 || p.as_of_ts > now || now - p.as_of_ts > 90 ||
        !Array.isArray(p.profiles) || p.profiles.length !== 4 ||
        new Set(p.profiles.map(row => row?.id)).size !== 4 ||
        !p.profiles.every(row => ids.includes(row?.id) && row.currency === 'USD')) return null;
    const a = p.aggregate;
    if (!a || a.currency !== 'USD' || a.workspace_count !== 4) return null;
    for (const row of p.profiles) {
      if (![row.realized_pnl, row.open_pnl, row.total_pnl].every(x => x === null || amount(x))) return null;
      if (row.runtime_available !== true && [row.realized_pnl, row.open_pnl, row.total_pnl].some(x => x !== null)) return null;
      const total = row.realized_pnl === null || row.open_pnl === null ? null : sum([row.realized_pnl, row.open_pnl]);
      if (!same(row.total_pnl, total) || row.accounting_complete !== (total !== null)) return null;
    }
    for (const field of ['realized_pnl', 'open_pnl', 'total_pnl']) {
      const expected = sum(p.profiles.map(row => row[field]));
      if (!(a[field] === null || amount(a[field])) || !same(a[field], expected)) return null;
    }
    if (a.accounting_complete !== (a.total_pnl !== null)) return null;
    return p;
  }
  async function fetchJson(path, options = {}) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 8000);
    try {
      const transport=globalThis.IcarusClient?globalThis.IcarusClient.request.bind(globalThis.IcarusClient):fetch;
      const response = await transport(path, {cache: 'no-store', ...options, signal: controller.signal});
      const data = await response.json();
      if (!response.ok) throw new Error('Engine request unavailable (' + response.status + ').');
      return data;
    } finally { clearTimeout(timer); }
  }
  return {read, amount, fetchJson};
})();

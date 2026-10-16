/* Read-only presentation of the default-off real-price shadow twin. */
(() => {
  const esc = value => String(value ?? '—').replace(/[&<>"']/g, char => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  })[char]);
  const hasNumber = value => value !== null && value !== undefined && value !== '' && Number.isFinite(Number(value));
  const number = value => hasNumber(value)
    ? Number(value).toLocaleString(undefined, {maximumFractionDigits: 4}) : '—';
  const money = value => hasNumber(value)
    ? `${Number(value) < 0 ? '−' : ''}$${Math.abs(Number(value)).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}` : '—';
  const moneyWithDenominator = (value, denominator) => hasNumber(value) && hasNumber(denominator) && Number(denominator) > 0
    ? `${money(value)} (n=${number(denominator)})` : '—';
  const percent = value => hasNumber(value) ? `${(Number(value) * 100).toFixed(1)}%` : '—';

  function start() {
    if (!document.body || document.getElementById('rt01-open')) return;
    const style = document.createElement('style');
    style.textContent = `
      #rt01-open{position:fixed;right:16px;bottom:16px;z-index:900;white-space:nowrap;box-shadow:0 5px 24px #0008}
      body:has(.world-intro) #rt01-open{display:none}
      #rt01-shade{position:fixed;inset:0;background:#070b10dd;z-index:1000;display:none;align-items:flex-start;justify-content:center;padding:7vh 16px 20px;overflow:auto}
      #rt01-shade.open{display:flex}
      #rt01-panel{width:min(1120px,96vw);max-height:86vh;overflow:auto;background:var(--surface,#111821);color:var(--text,#e8edf2);border:1px solid var(--ring,#46515e);border-radius:14px;padding:20px;box-shadow:0 20px 90px #000a}
      #rt01-panel h2{margin:0;font-size:20px} #rt01-panel h3{margin:18px 0 8px;font-size:15px}
      #rt01-panel .rt01-head{display:flex;align-items:center;justify-content:space-between;gap:14px}
      #rt01-panel .rt01-note{color:var(--muted,#9aa6b2);font-size:12px;line-height:1.55;margin:12px 0}
      #rt01-panel .rt01-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(145px,1fr));gap:8px}
      #rt01-panel .rt01-card{border:1px solid var(--ring,#46515e);border-radius:9px;padding:11px;background:#ffffff08}
      #rt01-panel .rt01-label{font-size:10px;letter-spacing:.07em;text-transform:uppercase;color:var(--muted,#9aa6b2)}
      #rt01-panel .rt01-value{font-size:18px;font-weight:700;margin-top:5px;overflow-wrap:anywhere}
      #rt01-panel .rt01-table-wrap{overflow:auto}
      #rt01-panel table{width:100%;border-collapse:collapse;font-size:12px;white-space:nowrap}
      #rt01-panel th,#rt01-panel td{text-align:left;padding:8px;border-bottom:1px solid var(--ring,#46515e)}
      #rt01-panel th{color:var(--muted,#9aa6b2);font-weight:600}
      #rt01-panel .rt01-status{font-weight:700} #rt01-panel .rt01-error{color:#ff9a9a}
      @media(max-width:600px){#rt01-shade{padding:2vh 8px}#rt01-panel{max-height:94vh;padding:14px}}
    `;
    document.head.append(style);
    const button = document.createElement('button');
    button.id = 'rt01-open'; button.className = 'icon-btn'; button.type = 'button';
    button.textContent = 'Shadow Twin'; button.title = 'Read-only real-price shadow evidence';
    document.body.append(button);
    const shade = document.createElement('div'); shade.id = 'rt01-shade';
    shade.innerHTML = `<section id="rt01-panel" role="dialog" aria-modal="true" aria-labelledby="rt01-title">
      <div class="rt01-head"><h2 id="rt01-title">Real-price shadow twin</h2><button id="rt01-close" class="icon-btn" type="button">Close</button></div>
      <p class="rt01-note">Research evidence only. The shadow twin is default-off and cannot authorize orders. Standard real-bar emulator results are compared with primary Icarus fills. Drawdown is marked at bar closes and can understate intrabar risk.</p>
      <div id="rt01-content" aria-live="polite">Loading shadow evidence…</div>
      <p class="rt01-note" id="rt01-updated"></p>
    </section>`;
    document.body.append(shade);

    const card = (label, value) => `<div class="rt01-card"><div class="rt01-label">${esc(label)}</div><div class="rt01-value">${esc(value)}</div></div>`;
    const outcomeText = matrix => {
      if (!matrix || typeof matrix !== 'object') return '—';
      return ['win', 'loss', 'break_even'].map(primary => `${primary}: ${['win', 'loss', 'break_even'].map(shadow => `${shadow} ${number(matrix?.[primary]?.[shadow])}`).join(' / ')}`).join('<br>');
    };
    const assetTable = (assets, runtimeAssets) => {
      const fullBySymbol = new Map((Array.isArray(runtimeAssets) ? runtimeAssets : [])
        .filter(row => row && row.real_price_shadow)
        .map(row => [String(row.symbol || row.real_price_shadow.asset), row.real_price_shadow]));
      const rows = (Array.isArray(assets) ? assets : []).map(row => {
        const metrics = row.status === 'READY' ? (fullBySymbol.get(String(row.asset)) || {}) : {};
        const p = row.provenance || metrics.provenance || {};
        const primaryExcursions = metrics.primary_closed_episode_excursions || {};
        const shadowExcursions = metrics.real_price_shadow_closed_episode_excursions || {};
        const favorableDelta = metrics.matched_closed_episode_favorable_excursion_delta_shadow_minus_primary || {};
        const adverseDelta = metrics.matched_closed_episode_adverse_excursion_delta_shadow_minus_primary || {};
        return `<tr><td>${esc(row.asset)}</td><td class="rt01-status">${esc(row.status)}</td><td>${esc(row.reason || '—')}</td><td>${esc(p.price_provider || '—')}</td><td>${esc(p.timeframe_minutes ? `${p.timeframe_minutes} min` : '—')}</td><td>${esc(p.calendar || '—')} / ${esc(p.session_mode || '—')}</td><td>${esc(p.primary_fill_basis || metrics.primary_fill_basis || '—')} / ${esc(p.shadow_fill_basis || metrics.fill_basis || '—')}</td><td>${esc(p.feed_health?.status || p.feed_health?.state || '—')}</td><td>${percent(metrics.entry_fill_parity)}</td><td>${number(metrics.pairable_closed_episodes)}</td><td>${metrics.outcome_agreement_rate == null ? '—' : `${percent(metrics.outcome_agreement_rate)} (${number(metrics.outcome_agreement_denominator)})`}</td><td>${money(metrics.primary?.net)} / ${money(metrics.real_price_shadow?.net)}</td><td>${percent(metrics.primary_win_preservation)}</td><td>${moneyWithDenominator(primaryExcursions.favorable_excursion, primaryExcursions.denominator)} / ${moneyWithDenominator(shadowExcursions.favorable_excursion, shadowExcursions.denominator)}</td><td>${moneyWithDenominator(primaryExcursions.adverse_excursion, primaryExcursions.denominator)} / ${moneyWithDenominator(shadowExcursions.adverse_excursion, shadowExcursions.denominator)}</td><td>${moneyWithDenominator(favorableDelta.mean, favorableDelta.count)} / ${moneyWithDenominator(adverseDelta.mean, adverseDelta.count)}</td><td>${money(metrics.primary_bar_close_max_drawdown)} / ${money(metrics.real_price_shadow_bar_close_max_drawdown)}</td><td>${row.status === 'READY' ? number(row.administrative_censored_shadow_positions) : '—'}</td></tr>`;
      }).join('');
      return `<div class="rt01-table-wrap"><table><thead><tr><th>Asset</th><th>Status</th><th>Reason</th><th>Price source</th><th>Timeframe</th><th>Calendar / session</th><th>Fill basis primary / shadow</th><th>Feed health</th><th>Entry parity</th><th>Closed pairs</th><th>Outcome agreement</th><th>Primary / shadow net</th><th>Winner preservation</th><th>Closed MFE primary / shadow</th><th>Closed MAE primary / shadow</th><th>Matched MFE / MAE delta</th><th>Bar-close DD primary / shadow</th><th>Censored positions</th></tr></thead><tbody>${rows || '<tr><td colspan="18">No per-asset shadow results are available.</td></tr>'}</tbody></table></div>`;
    };
    const render = data => {
      const content = document.getElementById('rt01-content');
      const portfolio = data?.real_price_shadow;
      if (!portfolio) {
        const assets = Array.isArray(data?.assets) ? data.assets : [];
        const anyShadow = assets.some(row => row.real_price_shadow);
        if (!anyShadow) {
          content.innerHTML = `<div class="rt01-card"><div class="rt01-status">No shadow twin evidence is currently published.</div><div class="rt01-note">The runner is either on code without RT01 support, the shadow twin is not enabled, or no runner has generated evidence yet. Status reads do not enable it.</div></div>`;
          return;
        }
      }
      if (!portfolio) { content.innerHTML = '<div class="rt01-error">Portfolio shadow summary is unavailable.</div>'; return; }
      const matrix = outcomeText(portfolio.outcome_matrix);
      content.innerHTML = `<div class="rt01-grid">
        ${card('Status', portfolio.status)}${card('Execution authorized', String(portfolio.execution_authorized))}
        ${card('Assets with evidence', number(portfolio.asset_count))}${card('Entry fill parity', percent(portfolio.entry_fill_parity))}
        ${card('Matched entry intents', number(portfolio.matched_entry_intents))}${card('Unmatched primary / shadow entries', `${number(portfolio.primary_only_entry_fills)} / ${number(portfolio.shadow_only_entry_fills)}`)}
        ${card('Pairable closed episodes', number(portfolio.pairable_closed_episodes))}${card('Outcome agreement', portfolio.outcome_agreement_rate == null ? '—' : `${percent(portfolio.outcome_agreement_rate)} (${number(portfolio.outcome_agreement_denominator)} directional pairs)`)}
        ${card('Primary net', money(portfolio.primary_net))}${card('Shadow net', money(portfolio.real_price_shadow_net))}
        ${card('Net realization ratio', percent(portfolio.net_realization_ratio))}${card('Primary winner capture', percent(portfolio.paired_profit_capture))}
        ${card('Primary winner preservation', percent(portfolio.primary_win_preservation))}${card('Admin-censored positions', number(portfolio.administrative_censored_shadow_positions))}
      </div>${portfolio.metrics_available === false ? `<div class="rt01-note">Portfolio comparison metrics are unavailable: ${esc(portfolio.metrics_unavailable_reason || 'one or more shadow assets are not READY')}.</div>` : ''}<h3>Matched closed outcome matrix</h3><div class="rt01-note">Rows are primary outcomes; columns are shadow outcomes. Each cell is a count: ${matrix}</div>
      <h3>Per-asset evidence and provenance</h3>${assetTable(portfolio.assets, data.assets)}
      <p class="rt01-note">Closed MFE and MAE sum emulator-observed high/low excursions through exit fills, quantity weighted and entry-commission adjusted. Only complete closed episodes are counted; matched deltas require the same mirrored entry intent. Portfolio drawdown: ${esc(portfolio.drawdown_aggregation || 'not reported')}. Values marked — have no valid denominator or no published measurement; they are not zeroes.</p>`;
    };
    let interval = null, loading = false;
    const refresh = async () => {
      if (loading || !shade.classList.contains('open')) return;
      loading = true;
      try {
        const response = await fetch('/status/public', {cache: 'no-store'});
        if (!response.ok) throw new Error(`Status request failed (${response.status})`);
        render(await response.json());
        document.getElementById('rt01-updated').textContent = `Updated ${new Date().toLocaleTimeString()}`;
      } catch (error) {
        document.getElementById('rt01-content').innerHTML = `<div class="rt01-error">${esc(error?.message || 'Unable to load status.')}</div>`;
      } finally { loading = false; }
    };
    const close = () => { shade.classList.remove('open'); if (interval) clearInterval(interval); interval = null; button.focus(); };
    button.addEventListener('click', () => {
      shade.classList.add('open'); refresh();
      if (!interval) interval = setInterval(refresh, 10000);
      document.getElementById('rt01-close').focus();
    });
    document.getElementById('rt01-close').addEventListener('click', close);
    shade.addEventListener('click', event => { if (event.target === shade) close(); });
    document.addEventListener('keydown', event => { if (event.key === 'Escape' && shade.classList.contains('open')) close(); });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, {once: true});
  else start();
})();

/* Account monitoring only. All untrusted values use textContent. */
(() => {
  'use strict';
  const root = document.querySelector('main#connections') || document.getElementById('connections');
  if (!root) return;
  const el = (tag, text, attrs = {}) => {
    const node = document.createElement(tag);
    if (text != null) node.textContent = String(text);
    for (const [name, value] of Object.entries(attrs)) node.setAttribute(name, value);
    return node;
  };
  root.replaceChildren();
  const heading = el('h1', 'Broker and prop firm connections');
  const notice = el('p', 'Read-only account monitoring. Configuration, successful readback and verified firm compliance are separate. Live execution is disabled.');
  const status = el('p', 'Loading account inventory…', {role: 'status', 'aria-live': 'polite'});
  const list = el('section', null, {'aria-label': 'Account connections'});
  const rules = el('section', null, {'aria-label': 'Firm rule coverage'});
  const form = el('form');
  form.append(el('h2', 'Configure an account'));
  const fields = {};
  const input = (name, title, type = 'text', value = '') => {
    const label = el('label', title);
    const field = el('input', null, {name, type, autocomplete: type === 'password' ? 'off' : 'off', maxlength: '200'});
    field.value = value;
    fields[name] = field;
    label.append(field);
    form.append(label);
    return field;
  };
  input('id', 'Unique account record ID', 'text', 'paper_account').pattern = '[A-Za-z0-9][A-Za-z0-9_-]{0,63}';
  input('alias', 'Display alias', 'text', 'Paper account');
  const platformLabel = el('label', 'Platform');
  const platform = el('select', null, {name: 'platform'});
  for (const [value, label] of [['alpaca_paper', 'Alpaca paper — account readback'], ['projectx_topstep', 'ProjectX / Topstep — unsupported'], ['rithmic', 'Rithmic — unsupported'], ['tradovate', 'Tradovate — unsupported'], ['ibkr', 'IBKR — unsupported'], ['other', 'Other — unsupported']]) {
    const option = el('option', label, {value});
    platform.append(option);
  }
  platformLabel.append(platform);
  form.append(platformLabel);
  input('environment', 'Environment (paper, demo, simulated, evaluation or funded)', 'text', 'paper');
  input('firm', 'Firm', 'text', 'independent');
  input('program', 'Exact program and account stage', 'text', 'paper');
  const secretNotice = el('p', 'Alpaca uses approved runtime references ALPACA_API_KEY and ALPACA_SECRET_KEY. Optional owner entry below requires an already provisioned encrypted local store; credentials are never stored in this browser.');
  form.append(secretNotice);
  input('api_key', 'Optional API key (encrypted local store only)', 'password');
  input('secret_key', 'Optional secret key (encrypted local store only)', 'password');
  input('owner_token', 'Owner or viewer token to load inventory (owner required for changes)', 'password');
  const submit = el('button', 'Save account configuration', {type: 'submit'});
  const refresh = el('button', 'Refresh account inventory', {type: 'button'});
  form.append(submit);
  root.append(heading, notice, status, refresh, list, form, rules);
  let busy = false;
  async function request(path, options = {}) {
    const response = await fetch(path, {credentials: 'same-origin', cache: 'no-store', ...options});
    if (!response.ok) throw new Error(`Account request unavailable (${response.status}).`);
    return response.json();
  }
  function auth() {
    if (!fields.owner_token.value) throw new Error('Enter an owner or viewer token, then refresh account inventory.');
    return {'Content-Type': 'application/json', 'Authorization': `Bearer ${fields.owner_token.value}`};
  }
  async function load() {
    try {
      const snapshot = await request('/api/account-connections', {headers: auth()});
      list.replaceChildren(el('h2', 'Account inventory'));
      if (!snapshot.connections?.length) list.append(el('p', 'No accounts configured. No external broker balance or brokerage P&L is available.'));
      for (const row of snapshot.connections || []) {
        const card = el('article');
        card.append(el('h3', row.alias || row.id), el('p', `${row.platform} · ${row.environment} · ${row.firm} / ${row.program}`));
        card.append(el('p', `${row.status} · Policy ${row.policy_status || 'UNVERIFIED'} · New intents blocked`));
        if (row.readback) card.append(el('p', `Last account read: equity ${row.readback.equity} ${row.readback.currency}; cash ${row.readback.cash} ${row.readback.currency}. This is an account balance, not reconciled Icarus P&L.`));
        const connect = el('button', 'Read account / check connection', {type: 'button'});
        connect.addEventListener('click', async () => {
          if (busy) return;
          busy = true;
          connect.disabled = true;
          try {
            const result = await request(`/admin/account-connections/${encodeURIComponent(row.id)}/connect`, {method: 'POST', headers: auth(), body: '{}'});
            await load();
            status.textContent = `${row.alias || row.id}: ${result.status}`;
          } catch (error) { status.textContent = error.message; }
          finally { busy = false; connect.disabled = false; fields.owner_token.value = ''; }
        });
        card.append(connect);
        list.append(card);
      }
      rules.replaceChildren(el('h2', 'Official rule coverage and blockers'));
      for (const policy of snapshot.rules || []) {
        const card = el('article');
        card.append(el('h3', `${policy.firm} / ${policy.program}: ${policy.status}`), el('p', policy.explanation));
        const blockers = el('ul');
        for (const clause of [...(policy.unknown_clauses || []), ...(policy.unsupported_clauses || [])]) blockers.append(el('li', clause));
        card.append(blockers);
        for (const source of policy.sources || []) {
          try {
            const url = new URL(source);
            if (url.protocol === 'https:') card.append(el('a', 'Official source', {href: url.href, target: '_blank', rel: 'noopener noreferrer'}));
          } catch (_) { /* Invalid metadata grants no link. */ }
        }
        rules.append(card);
      }
      const secure = snapshot.credential_entry?.encrypted_local_store_available === true;
      fields.api_key.disabled = fields.secret_key.disabled = !secure;
      secretNotice.textContent = secure ? 'Approved environment references or encrypted owner entry are available. Secret values are never returned by the account API.' : 'Encrypted owner entry is unavailable: the runtime has no provisioned secure master key. Approved environment references remain supported; missing credentials will remain explicit.';
      status.textContent = 'Account inventory loaded. Readback never authorizes execution.';
    } catch (error) { status.textContent = error.message; }
  }
  form.addEventListener('submit', async event => {
    event.preventDefault();
    if (busy) return;
    busy = true;
    submit.disabled = true;
    try {
      const body = {id: fields.id.value, alias: fields.alias.value, platform: platform.value, environment: fields.environment.value, firm: fields.firm.value, program: fields.program.value, credential_refs: {}};
      if (fields.api_key.value || fields.secret_key.value) body.credentials = {api_key: fields.api_key.value, secret_key: fields.secret_key.value};
      else if (platform.value === 'alpaca_paper') body.credential_refs = {api_key: 'ALPACA_API_KEY', secret_key: 'ALPACA_SECRET_KEY'};
      const result = await request('/admin/account-connections', {method: 'POST', headers: auth(), body: JSON.stringify(body)});
      await load();
      status.textContent = `Saved ${result.id}: ${result.status}. Select read account to verify connectivity.`;
    } catch (error) { status.textContent = error.message; }
    finally { fields.api_key.value = fields.secret_key.value = fields.owner_token.value = ''; busy = false; submit.disabled = false; }
  });
  refresh.addEventListener('click', load);
  load();
})();

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
  for (const [value, label] of [['manual_inventory', 'Prop firm — free local inventory (no remote API)'], ['alpaca_paper', 'Alpaca paper — account readback'], ['projectx_topstep', 'TopstepX — later configuration (paid API access required)'], ['rithmic', 'Rithmic — unsupported'], ['tradovate', 'Tradovate — unsupported'], ['ibkr', 'IBKR — unsupported'], ['other', 'Other — unsupported']]) {
    const option = el('option', label, {value});
    if (value === 'projectx_topstep') option.disabled = true;
    platform.append(option);
  }
  platformLabel.append(platform);
  form.append(platformLabel);
  input('environment', 'Environment (paper, demo, simulated, evaluation or funded)', 'text', 'paper');
  input('firm', 'Firm', 'text', 'independent');
  input('program', 'Exact program and account stage', 'text', 'paper');
  input('account_id', 'Topstep account ID (required for selection; hashed in browser, never persisted here)', 'password');
  const secretNotice = el('p', 'Alpaca uses approved runtime references ALPACA_API_KEY and ALPACA_SECRET_KEY. Optional owner entry below requires an already provisioned encrypted local store; credentials are never stored in this browser.');
  form.append(secretNotice);
  input('api_key', 'Optional API key (encrypted local store only)', 'password');
  input('secret_key', 'Optional secret key (encrypted local store only)', 'password');
  input('owner_token', 'Owner or viewer token to load inventory (owner required for changes)', 'password');
  const submit = el('button', 'Save account configuration', {type: 'submit'});
  const refresh = el('button', 'Refresh account inventory', {type: 'button'});
  form.append(submit);
  root.append(heading, notice, status, refresh, list, form, rules);
  let busy = false, firms = [];
  const catalogLabel=el('label','Researched firm (free local inventory)'),firmSelect=el('select',null,{id:'firm-catalog'});
  catalogLabel.append(firmSelect);form.insertBefore(catalogLabel,fields.firm.parentElement);
  const programLabel=el('label','Documented account type'),programSelect=el('select',null,{id:'firm-program'});
  programLabel.append(programSelect);form.insertBefore(programLabel,fields.program.parentElement);
  const stageLabel=el('label','Account stage'),stageSelect=el('select',null,{id:'firm-stage'});
  stageLabel.append(stageSelect);form.insertBefore(stageLabel,fields.program.parentElement);
  const sizeLabel=el('label','Documented size (USD simulation units)'),sizeSelect=el('select',null,{id:'firm-size'});
  sizeLabel.append(sizeSelect);form.insertBefore(sizeLabel,fields.program.parentElement);
  const variantLabel=el('label','Documented risk variant'),variantSelect=el('select',null,{id:'firm-variant'});
  variantLabel.append(variantSelect);form.insertBefore(variantLabel,fields.program.parentElement);
  function selectedProgram(){return firms.find(f=>f.id===firmSelect.value)?.account_types?.[Number(programSelect.value)];}
  function updateProgram(){
    const program=selectedProgram();if(!program)return;
    fields.program.value=[program.name,stageSelect.value,sizeSelect.value,variantSelect.value].filter(Boolean).join(' / ');
    const stage=stageSelect.value.toLowerCase();fields.environment.value=stage.includes('eval')||stage==='qualification'?'evaluation':stage.includes('live')&&!stage.includes('sim')?'funded':'simulated';
  }
  function updateStages(){const program=selectedProgram();stageSelect.replaceChildren();sizeSelect.replaceChildren();variantSelect.replaceChildren();if(!program)return;
    variantSelect.append(el('option','Variant / exact agreement not assigned',{value:''}));
    for(const [index,variant] of (program.variants||[]).entries())variantSelect.append(el('option',variant,{value:'variant #'+(index+1)}));
    const choices=program.funded_choices||program.funding_choices||[];
    for(const stage of program.stages||[]){
      const options=choices.length&&['Funded','Sim Funded'].includes(stage)?choices:[stage];
      for(const option of options)stageSelect.append(el('option',option,{value:option}));
    }
    sizeSelect.append(el('option','Size / agreement not assigned',{value:''}));
    for(const size of [...new Set([...(program.documented_sizes_usd||[]),...(program.funded_progression_sizes_usd||[])])])sizeSelect.append(el('option',Number(size).toLocaleString('en-US'),{value:String(size)}));
    updateProgram();
  }
  function updateFirm(){const firm=firms.find(f=>f.id===firmSelect.value);programSelect.replaceChildren();if(!firm)return;
    platform.value='manual_inventory';fields.firm.value=firm.name;
    fields.api_key.value=fields.secret_key.value=fields.account_id.value='';
    for(const [index,program] of firm.account_types.entries())programSelect.append(el('option',program.name,{value:String(index)}));
    updateStages();
  }
  firmSelect.addEventListener('change',updateFirm);programSelect.addEventListener('change',updateStages);
  stageSelect.addEventListener('change',updateProgram);sizeSelect.addEventListener('change',updateProgram);variantSelect.addEventListener('change',updateProgram);
  async function loadCatalog(){try{
    const catalog=await IcarusPaperPnl.fetchJson('/api/prop-firm-catalog');firms=Array.isArray(catalog.firms)?catalog.firms:[];
    firmSelect.replaceChildren(el('option','Choose a researched firm',{value:''}));
    for(const firm of firms)firmSelect.append(el('option',firm.name,{value:firm.id}));
    const overview=el('section',null,{'aria-label':'Eight researched prop firms'});overview.append(el('h2','Eight prop firm integrations · no local software charge'),el('p','Local account records are free. Evaluations, funded access, exchange data and APIs can cost money. No external account is connected and no purchases are made. TopstepX is deferred.'));
    for(const firm of firms){const card=el('details');card.append(el('summary',firm.name+' · '+firm.account_types.length+' documented account types'),el('p',(firm.confirmed_restrictions||[]).join(' ')));
      const types=el('ul');for(const type of firm.account_types)types.append(el('li',type.name+' — '+type.stages.join(' → ')+((type.funded_choices||type.funding_choices)?.length?' · alternative funding choices: '+(type.funded_choices||type.funding_choices).join(' OR '):'')+(type.documented_sizes_usd?.length?' · '+(type.size_scope==='EVALUATION_ENTRY'?'Evaluation entry ':'')+'USD '+type.documented_sizes_usd.join(', '):' · sizes require exact agreement')+(type.funded_progression_sizes_usd?.length?' · Funded progression sizes USD '+type.funded_progression_sizes_usd.join(', '):'')+(type.variants?.length?' · Risk variants: '+type.variants.join(' OR '):'')));card.append(types);
      card.append(el('p','Complete FAQ coverage and account-specific compliance remain unverified. All new intents are blocked.'));
      for(const source of firm.source_review||[]){try{const url=new URL(source.url);if(url.protocol==='https:')card.append(el('a','Official source ↗ ',{href:url.href,target:'_blank',rel:'noopener noreferrer'}));}catch{}}
      overview.append(card);
    }root.insertBefore(overview,list);
  }catch{status.textContent='Official firm catalog unavailable.';}}
  loadCatalog();
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
        if (row.readback) {
          const text = row.platform === 'projectx_topstep' ? `Reported balance ${row.readback.balance}; currency is not supplied by this API contract.` : `Equity ${row.readback.equity} ${row.readback.currency}; cash ${row.readback.cash} ${row.readback.currency}.`;
          card.append(el('p', `Last account read: ${text} This is an account balance, not reconciled Icarus P&L.`));
        }
        const connect = el('button', row.platform==='manual_inventory'?'Verify local record (no remote connection)':'Read account / check connection', {type: 'button'});
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
        const card = el('details');
        card.append(el('summary', `${policy.firm} / ${policy.program}: ${policy.status}`), el('p', policy.explanation));
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
      secretNotice.textContent = (secure ? 'Approved environment references or encrypted owner entry are available.' : 'Encrypted owner entry is unavailable: the runtime has no provisioned secure master key. Approved environment references remain supported.') + ' TopstepX is deferred to a later configuration and requires existing paid API subscription access; this interface never enrolls or purchases access, and sends no orders. For Topstep, the second credential field is your platform username.';
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
      if (platform.value === 'projectx_topstep') {
        if (!/^[1-9][0-9]*$/.test(fields.account_id.value) || !globalThis.crypto?.subtle) throw new Error('An explicit Topstep account ID and a secure browser context are required.');
        const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(`projectx_topstep:${fields.account_id.value}`));
        body.account_selector = Array.from(new Uint8Array(digest), byte => byte.toString(16).padStart(2, '0')).join('');
      }
      if (fields.api_key.value || fields.secret_key.value) body.credentials = platform.value === 'projectx_topstep' ? {api_key: fields.api_key.value, username: fields.secret_key.value} : {api_key: fields.api_key.value, secret_key: fields.secret_key.value};
      else if (platform.value === 'alpaca_paper') body.credential_refs = {api_key: 'ALPACA_API_KEY', secret_key: 'ALPACA_SECRET_KEY'};
      else if (platform.value === 'projectx_topstep') body.credential_refs = {api_key: 'PROJECTX_API_KEY', username: 'PROJECTX_USERNAME'};
      const result = await request('/admin/account-connections', {method: 'POST', headers: auth(), body: JSON.stringify(body)});
      await load();
      status.textContent = `Saved ${result.id}: ${result.status}. Select read account to verify connectivity.`;
    } catch (error) { status.textContent = error.message; }
    finally { fields.api_key.value = fields.secret_key.value = fields.owner_token.value = fields.account_id.value = ''; busy = false; submit.disabled = false; }
  });
  platform.addEventListener('change', () => {
    const topstep = platform.value === 'projectx_topstep';
    if(platform.value==='manual_inventory'){updateFirm();return;}
    fields.environment.value = topstep ? 'evaluation' : 'paper';
    fields.firm.value = topstep ? 'Topstep' : 'independent';
    fields.program.value = topstep ? 'UNASSIGNED' : 'paper';
    fields.api_key.value = fields.secret_key.value = fields.account_id.value = '';
  });
  refresh.addEventListener('click', load);
  load();
})();

/* Core action translation for one immutable dashboard workspace. */
'use strict';
(() => {
  const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
  const copy = value => JSON.parse(JSON.stringify(value));
  const freeze = value => {
    if (object(value) || Array.isArray(value)) {
      Object.values(value).forEach(freeze);
      Object.freeze(value);
    }
    return value;
  };
  const fail = (code, message, status=0, receipt=undefined) => {
    throw new globalThis.IcarusWorkspaceClient.WorkspaceClientError(code, message, status, receipt);
  };
  const symbol = value => typeof value === 'string' && /^[A-Z0-9]{1,16}$/.test(value)
    ? value : fail('INVALID_REQUEST', 'An explicit canonical asset symbol is required');
  const revision = value => Number.isSafeInteger(value) && value >= 0
    ? value : fail('INVALID_IDENTITY', 'The captured configuration revision is unavailable');
  const fields = (value, allowed) => {
    if (!object(value) || Object.keys(value).some(key => !allowed.includes(key)))
      fail('INVALID_REQUEST', 'Unknown fields or conflicting scope selectors');
  };

  function create(client) {
    const id = client?.context?.id;
    if (!['main','cc1','cc2','cc3','cc4'].includes(id))
      fail('INVALID_CONTEXT', 'An explicit page-owned workspace client is required');
    const scoped = id !== 'main';

    function validateProfile(profile) {
      if (!object(profile) || profile.id !== id)
        fail('INVALID_IDENTITY', 'Configuration does not belong to this workspace');
      revision(profile.config_revision);
      if (!Array.isArray(profile.assets) || !profile.assets.length || new Set(profile.assets).size !== profile.assets.length ||
          profile.assets.some(asset => typeof asset !== 'string' || !/^[A-Z0-9]{1,16}$/.test(asset)) ||
          !object(profile.inputs) || !object(profile.chart) || !object(profile.asset_overrides))
        fail('INVALID_RESPONSE', 'Selected workspace configuration is incomplete');
      return profile;
    }
    async function currentProfile() {
      return copy(validateProfile(await client.read('configuration')));
    }
    async function stateFor(asset, draft) {
      if (asset !== '*') symbol(asset);
      if (draft !== null && (!object(draft) || draft.asset !== asset))
        fail('INVALID_REQUEST', 'This draft belongs to a different asset selection');
      if (!scoped) return {profile:null, revision:null};
      const profile = draft === null ? await currentProfile() : copy(validateProfile(draft.profile));
      const sourceRevision = draft === null ? profile.config_revision : revision(draft.revision);
      if (sourceRevision !== profile.config_revision)
        fail('INVALID_IDENTITY', 'Draft and configuration revisions differ');
      if (asset !== '*' && !profile.assets.includes(asset))
        fail('INVALID_REQUEST', 'Asset is not admitted to this workspace');
      return {profile, revision:sourceRevision};
    }
    async function loadInputs(asset, sampleAsset) {
      if (asset !== '*') symbol(asset);
      const sample = symbol(asset === '*' ? sampleAsset : asset);
      const profile = scoped ? await currentProfile() : null;
      if (profile && !profile.assets.includes(sample))
        fail('INVALID_REQUEST', 'Sample asset is not admitted to this workspace');
      const input = await client.read('inputs', {asset:sample});
      if (!object(input) || input.asset !== sample)
        fail('INVALID_IDENTITY', 'Inputs belong to a different asset');
      if (scoped && (input.workspace_id !== id || input.config_revision !== profile.config_revision))
        fail('REVISION_CONFLICT', 'Configuration changed while inputs loaded; reload before editing', 409);
      return freeze(copy({asset, input, profile, revision:profile?.config_revision ?? null}));
    }
    function wholeChanges(profile, operation, body) {
      if (operation === 'reset') return {asset_overrides:{}};
      const overrides = copy(profile.asset_overrides);
      if (operation === 'preset') {
        for (const asset of profile.assets) overrides[asset] = {...overrides[asset], preset:body.preset};
        return {asset_overrides:overrides};
      }
      const inputs = body.values ?? {}, chart = body.chart ?? {};
      for (const override of Object.values(overrides)) {
        for (const key of Object.keys(inputs)) if (override.inputs) delete override.inputs[key];
        for (const key of Object.keys(chart)) if (override.chart) delete override.chart[key];
      }
      return {inputs:{...profile.inputs, ...inputs}, chart:{...profile.chart, ...chart}, asset_overrides:overrides};
    }
    async function configure(operation, body, draft) {
      const asset = body.asset;
      if (asset !== '*') symbol(asset);
      if (operation === 'inputs') {
        fields(body, ['asset','values','chart','persist']);
        if (!object(body.values ?? {}) || !object(body.chart ?? {}))
          fail('INVALID_REQUEST', 'Input and chart edits must be objects');
        if (!Object.keys(body.values ?? {}).length && !Object.keys(body.chart ?? {}).length)
          fail('INVALID_REQUEST', 'Configuration changes are required');
      } else if (operation === 'reset') {
        fields(body, ['asset']);
      } else {
        fields(body, ['asset','preset']);
        if (!('preset' in body) || body.preset !== null && (typeof body.preset !== 'string' || !body.preset))
          fail('INVALID_REQUEST', 'A preset name or explicit null is required');
      }
      const state = await stateFor(asset, draft);
      const changes = scoped && asset === '*' ? wholeChanges(state.profile, operation, body)
        : operation === 'reset' ? {reset:true}
        : operation === 'preset' ? {preset:body.preset}
        : {...(body.values ? {inputs:copy(body.values)} : {}), ...(body.chart ? {chart:copy(body.chart)} : {})};
      return client.configure(asset, changes, state.revision);
    }
    async function assetChange(adding, body) {
      fields(body, adding ? ['symbol','tf','preset'] : ['symbol']);
      const asset = symbol(body.symbol);
      const profile = await currentProfile();
      const overrides = copy(profile.asset_overrides);
      let assets;
      if (adding) {
        if (profile.assets.includes(asset)) fail('INVALID_REQUEST', 'Asset is already admitted to this workspace');
        const catalog = await client.read('assets');
        if (catalog.workspace_id !== id || catalog.config_revision !== profile.config_revision)
          fail('REVISION_CONFLICT', 'Configuration changed while asset admission loaded', 409);
        const row = catalog.registry?.find(row => row.symbol === asset);
        if (!row || row.selectable !== true || row.runtime_qualified !== true)
          fail('INVALID_REQUEST', 'Asset is not selectable and runtime-qualified');
        assets = [...profile.assets, asset];
        const override = {};
        if (body.tf !== undefined) {
          if (typeof body.tf !== 'string' || !body.tf) fail('INVALID_REQUEST', 'An explicit chart timeframe is required');
          override.chart = {timeframe:body.tf};
        }
        if ('preset' in body) {
          if (body.preset !== null && (typeof body.preset !== 'string' || !body.preset))
            fail('INVALID_REQUEST', 'A preset name or explicit null is required');
          override.preset = body.preset;
        }
        if (Object.keys(override).length) overrides[asset] = override;
      } else {
        if (!profile.assets.includes(asset)) fail('INVALID_REQUEST', 'Asset is not admitted to this workspace');
        assets = profile.assets.filter(value => value !== asset);
        if (!assets.length) fail('INVALID_REQUEST', 'A workspace must retain at least one asset');
        delete overrides[asset];
      }
      return client.configure('*', {assets, asset_overrides:overrides}, profile.config_revision);
    }
    async function requestAdmin(path, body) {
      const response = await client.request(path, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
      const receipt = await response.json().catch(() => null);
      if (!response.ok) fail('HTTP_ERROR', receipt?.detail || receipt?.error || `HTTP ${response.status}`, response.status, object(receipt) ? receipt : undefined);
      if (!object(receipt)) fail('INVALID_RESPONSE', 'Operation receipt is not valid JSON');
      return receipt;
    }
    async function admin(path, body={}, draft=null) {
      if (typeof path !== 'string' || !path.startsWith('/admin/') || path.startsWith('//'))
        fail('INVALID_REQUEST', 'An explicit admin operation is required');
      if (!object(body)) fail('INVALID_REQUEST', 'An operation body must be an object');
      if (['/admin/pause','/admin/resume','/admin/flatten'].includes(path)) {
        fields(body, ['asset','reason', ...(path === '/admin/flatten' ? ['confirm'] : [])]);
        const asset = body.asset === '*' || body.asset === null || body.asset === undefined ? null : symbol(body.asset);
        if (path === '/admin/flatten' && body.confirm !== true)
          fail('INVALID_REQUEST', 'Paper flatten requires explicit confirmation');
        return client.control(path.slice('/admin/'.length), asset);
      }
      if (['/admin/inputs','/admin/inputs/async'].includes(path)) return configure('inputs', body, draft);
      if (['/admin/inputs/reset','/admin/inputs/reset/async'].includes(path)) return configure('reset', body, draft);
      if (['/admin/preset','/admin/preset/async'].includes(path)) return configure('preset', body, draft);
      if (['/admin/rewarm','/admin/rewarm/async'].includes(path)) {
        fields(body, ['asset']);
        const asset = body.asset === null || body.asset === undefined ? '*' : body.asset;
        const state = await stateFor(asset, draft);
        return client.rewarm(asset === '*' ? null : asset, state.revision);
      }
      if (scoped && ['/admin/assets/add','/admin/assets/remove'].includes(path))
        return assetChange(path.endsWith('/add'), body);
      return requestAdmin(path, body);
    }
    async function backtest(asset, params={}) {
      symbol(asset);
      if (!object(params)) fail('INVALID_REQUEST', 'Backtest parameters must be an object');
      const cleaned = Object.fromEntries(Object.entries(params).filter(([key, value]) =>
        value !== undefined && value !== '' && (value !== null || key === 'preset')));
      const profile = scoped ? await currentProfile() : null;
      if (profile && !profile.assets.includes(asset))
        fail('INVALID_REQUEST', 'Backtest asset is not admitted to this workspace');
      return client.backtest(asset, cleaned, profile?.config_revision ?? null);
    }
    return Object.freeze({loadInputs, admin, backtest});
  }
  globalThis.IcarusWorkspaceUI = Object.freeze({create});
})();

/* Explicit page-owned transport. No mutable scope selection or parent fallback. */
'use strict';
(() => {
  class WorkspaceClientError extends Error {
    constructor(code, detail, status=0, receipt=undefined) {
      super(detail); this.name='WorkspaceClientError'; this.code=code; this.status=status;
      if (receipt!==undefined) Object.defineProperty(this,'receipt',{
        value:freeze(JSON.parse(JSON.stringify(receipt))),enumerable:true
      });
    }
  }
  const fail = (code, message, status=0, receipt=undefined) => { throw new WorkspaceClientError(code,message,status,receipt); };
  const object = value => value !== null && typeof value==='object' && !Array.isArray(value);
  const freeze = value => { if (object(value)||Array.isArray(value)) { Object.values(value).forEach(freeze); Object.freeze(value); } return value; };
  const symbol = value => typeof value==='string' && /^[A-Z0-9]{1,16}$/.test(value)
    ? value : fail('INVALID_REQUEST','An explicit canonical asset symbol is required');
  const jobId = value => typeof value==='string' && /^[A-Za-z0-9_-]{1,100}$/.test(value)
    ? value : fail('INVALID_REQUEST','An explicit job identifier is required');
  const revision = value => Number.isSafeInteger(value) && value>=0
    ? value : fail('INVALID_IDENTITY','Invalid workspace configuration revision');
  const sharedPaths = new Set(['/api/input-meta','/api/presets','/api/command-centers',
    '/api/market-universe','/api/system/audit','/api/agent','/api/integrity',
    '/api/research/sources','/api/research/records','/api/research/source-watch','/api/research/market-context',
    '/api/commands','/api/overview/command-center','/api/discovery-registry','/api/provider-corpus',
    '/api/corpus-consumption','/api/corpus-expansion','/api/account-connections',
    '/api/prop-firm-catalog','/api/evolution','/api/evidence-lab','/api/access','/healthz']);
  const sharedPath = path => sharedPaths.has(path)||path.startsWith('/api/market-history/');
  const sharedActions = new Set(['/admin/access/add','/admin/access/kick']);
  const accessPath = path => /^\/(api|admin)\/access(?:[;/]|$)/.test(path);

  function create(bootstrap, options={}) {
    if (!object(bootstrap)||!['main','cc1','cc2','cc3','cc4'].includes(bootstrap.id))
      fail('INVALID_CONTEXT','A valid server-provided workspace identity is required');
    if (typeof options.fetch!=='function') fail('INVALID_CONTEXT','An explicit fetch transport is required');
    let origin;
    try { origin=new URL(options.origin); } catch (_) { fail('INVALID_CONTEXT','A same-origin HTTP location is required'); }
    if (!['http:','https:'].includes(origin.protocol)) fail('INVALID_CONTEXT','An HTTP origin is required');
    const timeout=options.timeoutMs??10000;
    if (!Number.isFinite(timeout)||timeout<=0||timeout>120000) fail('INVALID_CONTEXT','Invalid request deadline');
    const context=freeze(JSON.parse(JSON.stringify({id:bootstrap.id,capabilities:bootstrap.capabilities||{}})));
    const scoped=context.id!=='main', api=`/api/command-centers/${context.id}`, admin=`/admin/command-centers/${context.id}`;
    const latest=new Map(), jobs=new Map(), active=new Set(), pendingReads=new Map();
    let observedRevision=-1, closed=false, lifecycle=0;
    const token=typeof options.token==='function'?options.token:()=>'';
    function current(generation, signal) {
      if (closed||generation!==lifecycle||signal?.aborted) fail('CANCELLED','Request cancelled');
    }

    function pathURL(path) {
      if (typeof path!=='string'||!path.startsWith('/')||path.startsWith('//')) fail('INVALID_REQUEST','An explicit same-origin path is required');
      const url=new URL(path,origin.origin);
      if (url.origin!==origin.origin) fail('INVALID_REQUEST','Cross-origin requests are unavailable');
      return url;
    }
    function identity(data, historical=false, expected=null, advance=true) {
      if (!object(data)||data.workspace_id!==context.id||data.execution_authorized===true||data.paper_only===false)
        fail('INVALID_IDENTITY','Response does not belong to the selected paper workspace');
      const rev=revision(data.config_revision);
      if (expected!==null&&rev!==expected) fail('INVALID_IDENTITY','Job source revision changed');
      if (!historical&&rev<observedRevision) fail('STALE_RESPONSE','Workspace configuration changed before this response arrived');
      if (advance&&!historical) observedRevision=Math.max(observedRevision,rev);
      return data;
    }
    async function network(path, init, consume, channel=null, acceptHttpErrors=false) {
      if (closed) fail('CANCELLED','The page client is closed');
      const requestTimeout=init.timeoutMs??timeout;
      if (!Number.isFinite(requestTimeout)||requestTimeout<=0||requestTimeout>120000)
        fail('INVALID_REQUEST','Invalid request deadline');
      const fetchInit={...init};
      delete fetchInit.timeoutMs;
      const generation=lifecycle;
      const url=pathURL(path), controller=new AbortController(), external=init.signal;
      if (external?.aborted) fail('CANCELLED','Request cancelled');
      const sequence=channel?(latest.get(channel)||0)+1:0;
      if (channel) latest.set(channel,sequence);
      const headers=new Headers(init.headers||{}), bearer=token();
      if (bearer&&!headers.has('Authorization')) headers.set('Authorization','Bearer '+bearer);
      headers.set('X-Icarus-Workspace',context.id);
      let timer, cancel;
      const cancelled=new Promise((_,reject)=>{
        cancel=(code='CANCELLED')=>{controller.abort();reject(new WorkspaceClientError(code,code==='TIMEOUT'?'Request deadline exceeded':'Request cancelled'));};
        timer=setTimeout(()=>cancel('TIMEOUT'),requestTimeout);
      });
      const abort=()=>cancel(); active.add(cancel); external?.addEventListener('abort',abort,{once:true});
      try {
        const work=Promise.resolve().then(()=>options.fetch(url.href,{cache:'no-store',...fetchInit,headers,signal:controller.signal})).then(async response=>{
          if (response.status===401&&typeof options.onUnauthorized==='function') {
            try { options.onUnauthorized(); } catch (_) { /* auth UI must not break request handling */ }
          }
          if (!response.ok&&!acceptHttpErrors) {
            const data=await response.json().catch(()=>null);
            if (object(data)&&'workspace_id' in data) {
              if (data.workspace_id!==context.id||scoped&&(data.execution_authorized===true||data.paper_only===false))
                fail('INVALID_IDENTITY','Error receipt does not belong to the selected paper workspace');
              if ('config_revision' in data) revision(data.config_revision);
            }
            const detail=typeof data?.detail==='string'?data.detail:
              typeof data?.error==='string'?data.error:`HTTP ${response.status}`;
            fail('HTTP_ERROR',detail,response.status,object(data)?data:undefined);
          }
          return consume(response);
        });
        const data=await Promise.race([work,cancelled]);
        current(generation,external);
        if (channel&&latest.get(channel)!==sequence) fail('STALE_RESPONSE','A newer request replaced this observation');
        return data;
      } catch (error) {
        if (error instanceof WorkspaceClientError) throw error;
        fail('TRANSPORT_ERROR','Request failed: '+(error?.message||String(error)));
      } finally {
        clearTimeout(timer); active.delete(cancel); external?.removeEventListener('abort',abort);
      }
    }
    async function json(path, {body,signal,channel=null,historical=false,expected=null,validate=true}={}) {
      const init={method:body===undefined?'GET':'POST',signal};
      if (body!==undefined) { init.headers={'Content-Type':'application/json'}; init.body=JSON.stringify(body); }
      const data=await network(path,init,async response=>{
        try { return await response.json(); } catch (_) { fail('INVALID_RESPONSE','Response is not valid JSON'); }
      },channel);
      return scoped&&validate?identity(data,historical,expected):data;
    }
    function fields(value, allowed) {
      if (!object(value)||Object.keys(value).some(key=>!allowed.includes(key))) fail('INVALID_REQUEST','Unknown fields or conflicting scope selectors');
    }
    function accessRequest(url, method, body, path) {
      if (!accessPath(url.pathname)) return false;
      if (path.split(/[?#]/,1)[0]!==url.pathname)
        fail('INVALID_REQUEST','An exact native Access path is required',400);
      if (!(method==='GET'&&url.pathname==='/api/access'||method==='POST'&&sharedActions.has(url.pathname)))
        fail('UNAVAILABLE','This shared Access operation is unavailable',503);
      if (url.search||url.hash) fail('INVALID_REQUEST','Shared Access does not accept query selectors',400);
      if (method==='GET'&&body!==undefined) fail('INVALID_REQUEST','The shared Access reader does not accept a body',400);
      if (method==='POST') {
        let data;
        try { data=JSON.parse(body); } catch (_) { fail('INVALID_REQUEST','An explicit JSON Access action is required',400); }
        const field=url.pathname==='/admin/access/add'?'label':'id';
        fields(data,[field]);
        if (!Object.hasOwn(data,field)) fail('INVALID_REQUEST','The Access action requires '+field,400);
      }
      return true;
    }
    function bound(value, fallback, low, high) {
      value=value??fallback;
      if (!Number.isSafeInteger(value)||value<low||value>high) fail('INVALID_REQUEST',`Expected an integer from ${low} to ${high}`);
      return value;
    }
    async function read(resource, args={}) {
      const withAsset=['inputs','chart','trades'].includes(resource);
      const allowed={status:[],assets:[],inputs:['asset'],chart:['asset','n','offset'],trades:['asset','limit'],performance:[],configuration:[]}[resource];
      if (!allowed) fail('UNAVAILABLE','This runtime reader is unavailable',503);
      fields(args,[...allowed,'channel','signal']);
      const asset=withAsset?symbol(args.asset):null;
      let path;
      if (scoped) {
        path=resource==='configuration'?api:`${api}/${resource}${asset?'/'+asset:''}`;
      } else {
        if (resource==='configuration') fail('UNAVAILABLE','This reader is workspace-specific',503);
        path=resource==='status'?'/status/public':`/api/${resource}${asset?'/'+asset:''}`;
      }
      if (resource==='chart') path+=`?n=${bound(args.n,240,20,5000)}&offset=${bound(args.offset,0,0,50000)}`;
      if (resource==='trades') path+=`?limit=${bound(args.limit,100,1,2000)}`;
      const data=await json(path,{signal:args.signal,channel:args.channel||`read:${path}`,validate:resource!=='configuration'});
      if (resource==='configuration') {
        const profile=data?.profile;
        if (!object(profile)) fail('INVALID_RESPONSE','Selected workspace configuration is unavailable');
        identity({workspace_id:profile.id,config_revision:profile.config_revision});
        return profile;
      }
      if (resource==='trades') {
        const rows=scoped?data.trades:data;
        if (!Array.isArray(rows)) fail('INVALID_RESPONSE','Selected trades are unavailable');
        return rows;
      }
      return data;
    }
    function accepted(receipt, kind) {
      const id=jobId(receipt?.job);
      jobs.set(id,{revision:scoped?revision(receipt.config_revision):null,kind});
      return receipt;
    }
    async function configure(asset, changes, expectedRevision) {
      const whole=asset==='*'; if (!whole) symbol(asset);
      fields(changes,scoped&&whole?['assets','inputs','chart','asset_overrides']:['inputs','chart','preset','reset']);
      if (!Object.keys(changes).length) fail('INVALID_REQUEST','Configuration changes are required');
      let path, body;
      if (scoped) {
        revision(expectedRevision);
        path=whole?`${admin}/config/async`:`${admin}/assets/${asset}/config/async`;
        body={...changes,expected_revision:expectedRevision};
      } else if ('preset' in changes&&Object.keys(changes).length===1) {
        path='/admin/preset/async';body={asset,preset:changes.preset};
      } else if (changes.reset===true&&Object.keys(changes).length===1) {
        path='/admin/inputs/reset/async';body={asset};
      } else {
        fields(changes,['inputs','chart']);path='/admin/inputs/async';
        body={asset,values:changes.inputs||{},chart:changes.chart||{},persist:true};
      }
      return accepted(await json(path,{body,historical:true,expected:scoped?expectedRevision:null}),'config');
    }
    async function backtest(asset, params={}, expectedRevision) {
      symbol(asset);
      fields(params,['preset','inputs','fill_on','chart_type','timeframe','security_source','slippage_ticks',
        'commission','capital','session','window_start','window_end','leverage']);
      const body={...params};
      if (scoped) { revision(expectedRevision);body.expected_revision=expectedRevision; } else body.asset=asset;
      return accepted(await json(scoped?`${admin}/assets/${asset}/backtest`:'/admin/backtest',
        {body,historical:true,expected:scoped?expectedRevision:null}),'backtest');
    }
    async function rewarm(asset=null, expectedRevision) {
      if (asset!==null) symbol(asset);
      let path, body;
      if (scoped) {
        revision(expectedRevision);
        path=asset===null?`${admin}/rewarm/async`:`${admin}/assets/${asset}/rewarm/async`;
        body={expected_revision:expectedRevision};
      } else { path='/admin/rewarm/async';body={asset:asset??'*'}; }
      return accepted(await json(path,{body,historical:true,expected:scoped?expectedRevision:null}),'config');
    }
    async function control(action, asset=null) {
      if (!['pause','resume','flatten'].includes(action)) fail('UNAVAILABLE','This control is unavailable',503);
      if (asset!==null) symbol(asset);
      if (!scoped) return json('/admin/'+action,{body:action==='flatten'?{asset,confirm:true}:{asset}});
      const path=asset===null?admin:`${admin}/assets/${asset}`;
      const operation=path+(action==='flatten'?'/flatten':'/pause');
      const body=action==='flatten'?{confirm:true}:{paused:action==='pause'};
      let receipt;
      for (let attempt=0;;attempt++) {
        try {
          receipt=await json(operation,{body,historical:true});
          break;
        } catch (error) {
          // Workspace controls can briefly race a chart or ledger reader. The
          // server's exact 409 is emitted by its admission lock before the
          // operation runs, so retrying this response cannot repeat a change.
          const retryable=error instanceof WorkspaceClientError&&error.status===409&&
            error.receipt?.detail==='selected workspace is busy; retry after its current operation';
          if (!retryable||attempt>=3) throw error;
          await new Promise(resolve=>setTimeout(resolve,75*(2**attempt)));
        }
      }
      // Completed actions retain their receipt while the live observation floor only advances.
      observedRevision=Math.max(observedRevision,receipt.config_revision);
      return receipt;
    }
    async function job(id, args={}) {
      jobId(id);fields(args,['full','channel','signal']);
      const known=jobs.get(id), path=scoped?`${api}/jobs/${id}`:known?.kind==='config'?`/api/config-jobs/${id}`:`/api/backtest/${id}`;
      const data=await json(path+(args.full===false?'?full=0':''),{signal:args.signal,channel:args.channel||`job:${id}`,historical:true,expected:known?.revision??null});
      if (data.id!==id) fail('INVALID_IDENTITY','Response belongs to another job');
      if (scoped&&data.kind==='backtest'&&data.result) identity(data.result,true,data.config_revision);
      if (!known) jobs.set(id,{revision:scoped?data.config_revision:null,kind:data.kind||'backtest'});
      return data;
    }
    async function compare(id, csvText, tolerance=1) {
      jobId(id);
      const data=await json(scoped?`${admin}/jobs/${id}/compare`:'/admin/backtest/compare',{
        body:scoped?{csv:csvText,tol:tolerance}:{job:id,csv:csvText,tol:tolerance},historical:true,expected:jobs.get(id)?.revision??null});
      if (scoped&&data.job!==id) fail('INVALID_IDENTITY','Comparison belongs to another job');
      return data;
    }
    async function csv(selection) {
      fields(selection,['asset','job']);
      if (('asset' in selection)===('job' in selection)) fail('INVALID_REQUEST','Select exactly one asset or historical job');
      const historical='job' in selection, id=historical?jobId(selection.job):symbol(selection.asset);
      if (historical&&!jobs.has(id)) await job(id);
      const expected=historical?jobs.get(id).revision:null;
      const path=historical?(scoped?`${api}/jobs/${id}/trades.csv`:`/api/backtest/${id}/trades.csv`):
        (scoped?`${api}/export/${id}.csv`:`/api/export/${id}.csv`);
      const data=await network(path,{method:'GET'},async response=>{
        let rev=null;
        if (scoped) {
          const raw=response.headers.get('X-Icarus-Config-Revision');
          if (typeof raw!=='string'||!/^(0|[1-9][0-9]*)$/.test(raw)) fail('INVALID_IDENTITY','CSV lacks a valid workspace revision');
          rev=Number(raw);
          identity({workspace_id:response.headers.get('X-Icarus-Workspace'),config_revision:rev},historical,expected,false);
        }
        return {blob:await response.blob(),revision:rev};
      });
      if (scoped) identity({workspace_id:context.id,config_revision:data.revision},historical,expected);
      return {blob:data.blob,filename:`${context.id}_${id}_trades.csv`};
    }
    async function shared(path) {
      const url=pathURL(path);
      accessRequest(url,'GET',undefined,path);
      if (!sharedPath(url.pathname)) fail('UNAVAILABLE','This service has no shared read-only adapter',503);
      return json(url.pathname+url.search,{validate:false,channel:'shared:'+url.pathname+url.search});
    }
    async function requestOnce(path, init={}) {
      const generation=lifecycle;
      current(generation,init.signal);
      const url=pathURL(path), method=String(init.method||'GET').toUpperCase();
      const sharedAccess=accessRequest(url,method,init.body,path);
      let selected=false, isShared=sharedAccess, target=url.pathname+url.search, options={...init,method};
      if (scoped) {
        const foreign=/^\/(api|admin)\/command-centers\/([^/]+)/.exec(url.pathname);
        if (foreign&&foreign[2]!==context.id) fail('INVALID_REQUEST','Another workspace requires full-page navigation',409);
        selected=url.pathname===api||url.pathname.startsWith(api+'/')||url.pathname===admin||url.pathname.startsWith(admin+'/');
        isShared=sharedAccess||method==='GET'&&sharedPath(url.pathname);
        if (!selected&&!isShared) {
          if (method==='GET') {
            const panel=url.pathname.startsWith('/api/')?url.pathname.slice(5):'unavailable';
            target=`${api}/panels/${panel}${url.search}`;
            selected=true;
          } else if (method==='POST'&&url.pathname.startsWith('/admin/')&&
                     ['engine-control','possibility/evidence','intuition-omega/import-learning'].includes(url.pathname.slice(7))) {
            if (observedRevision<0) fail('INVALID_IDENTITY','Observe the selected workspace before running a panel action');
            target=`${admin}/panels/${url.pathname.slice(7)}${url.search}`;
            const headers=new Headers(options.headers||{});
            headers.set('X-Icarus-Config-Revision',String(observedRevision));
            options={...options,headers};selected=true;
          } else {
            target=`${admin}/unavailable`;
            options={method:'POST',signal:init.signal,headers:{'Content-Type':'application/json'},
              body:JSON.stringify({operation:method+' '+url.pathname})};
          }
        }
      }
      const response=await network(target,options,async raw=>{
        const headers=new Headers(raw.headers);
        if (isShared) headers.set('X-Icarus-Scope','shared');
        const body=[204,205,304].includes(raw.status)?null:await raw.arrayBuffer();
        return new Response(body,{status:raw.status,statusText:raw.statusText,headers});
      },null,true);
      current(generation,init.signal);
      if (scoped&&selected&&response.ok) {
        let data;
        try { data=await response.clone().json(); } catch (_) {
          current(generation,init.signal);
          fail('INVALID_RESPONSE','Selected module response is not JSON');
        }
        current(generation,init.signal);
        if (url.pathname===api) {
          identity({workspace_id:data?.profile?.id,config_revision:data?.profile?.config_revision});
        } else {
          const jobPath=url.pathname.startsWith(api+'/jobs/')?api+'/jobs/':
            url.pathname.startsWith(admin+'/jobs/')?admin+'/jobs/':null;
          const requested=jobPath?url.pathname.slice(jobPath.length).split('/')[0]:null;
          if (requested&&(jobPath.startsWith(api)?data?.id:data?.job)!==requested)
            fail('INVALID_IDENTITY','Response belongs to another job');
          const historical=!target.startsWith(api+'/panels/')&&(Boolean(requested)||typeof data?.job==='string');
          const known=jobs.get(requested||data?.job);
          identity(data,historical,known?.revision??null);
          if (data.kind==='backtest'&&data.result) identity(data.result,true,data.config_revision);
        }
      }
      return response;
    }
    async function request(path, init={}) {
      // Share only simultaneous read work. Every consumer receives its own body;
      // completed observations, mutations and independently cancelled reads are never cached.
      if (String(init.method||'GET').toUpperCase()!=='GET'||init.body!==undefined||init.signal)
        return requestOnce(path,init);
      const headers=new Headers(init.headers||{}), bearer=token();
      if (bearer&&!headers.has('Authorization')) headers.set('Authorization','Bearer '+bearer);
      const options={...init,headers};
      const key=JSON.stringify([lifecycle,pathURL(path).href,{...init,headers:[...headers]}]);
      let pending=pendingReads.get(key);
      if (!pending) {
        pending=requestOnce(path,options);
        pendingReads.set(key,pending);
        const clear=()=>{if(pendingReads.get(key)===pending)pendingReads.delete(key);};
        pending.then(clear,clear);
      }
      return (await pending).clone();
    }
    function href(asset=null) {
      const path=scoped?`/dashboards/${context.id}`:'/';
      return path+(asset===null?'':'?asset='+symbol(asset));
    }
    function cancelPending() { lifecycle++; latest.clear(); pendingReads.clear(); for (const cancel of active) cancel(); }
    function close() { closed=true; cancelPending(); }
    return Object.freeze({context,read,configure,backtest,rewarm,control,job,compare,csv,shared,request,href,
      getToken:()=>{const value=token();return typeof value==='string'?value.trim():'';},cancelPending,close});
  }
  globalThis.IcarusWorkspaceClient=Object.freeze({create,WorkspaceClientError});
})();

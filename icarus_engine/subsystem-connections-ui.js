/* Native runtime diagnostics; receipt continuity grants no trading authority. */
'use strict';
(() => {
  const mounted=new WeakMap(), states=new Set(['STARTING','OBSERVING','DEGRADED','UNAVAILABLE','STOPPED']);
  const finite=value=>typeof value==='number'&&Number.isFinite(value);
  const record=value=>value!==null&&typeof value==='object'&&!Array.isArray(value);
  const nullableCount=value=>value===null||Number.isSafeInteger(value)&&value>=0;
  const nullableTime=value=>value===null||finite(value)&&value>=0;
  const count=value=>Number.isSafeInteger(value)&&value>=0?String(value):'Unknown';
  const label=value=>typeof value==='string'&&value?value.slice(0,1024):'Unknown';
  const age=value=>finite(value)&&value>=0?value.toFixed(1)+'s':'Unknown';
  const utc=value=>finite(value)&&value>0&&value/1e6<8640000000000000?new Date(value/1e6).toISOString():'Unknown';

  function mount(container,client) {
    if(!container||!['main','cc1','cc2','cc3','cc4'].includes(client?.context?.id)||typeof client.request!=='function')
      throw new Error('An explicit page-owned subsystem client is required');
    if(mounted.has(container))return mounted.get(container);
    const id=client.context.id,section=document.createElement('section');
    section.id='subsystem-connections';section.className='card c12';section.setAttribute('aria-labelledby','subsystem-title');
    section.innerHTML=`<style>
      #subsystem-connections{box-sizing:border-box;min-width:0;max-width:100%;overflow-wrap:anywhere;color:var(--ink,var(--text,#e6edf5));background:var(--surface,var(--panel,#101d2b));border:1px solid var(--ring,var(--line,#34495f));border-radius:10px;padding:16px;font:13px/1.5 system-ui,sans-serif}
      #subsystem-connections .subsystem-top{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}
      #subsystem-connections h2{margin:0;font-size:16px}#subsystem-connections h3{font-size:14px;margin:0 0 8px}
      #subsystem-connections p{margin:8px 0;color:var(--ink-2,var(--muted,#a5b6c7))}
      #subsystem-connections .subsystem-pair{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,260px),1fr));gap:16px;margin:16px 0}
      #subsystem-connections article{min-width:0;border:1px solid var(--grid,var(--line,#34495f));border-radius:8px;padding:12px}
      #subsystem-connections button{font:inherit;color:inherit;background:var(--surface-2,#16283a);border:1px solid var(--axis,#496176);border-radius:7px;padding:8px 12px;cursor:pointer;max-width:100%}
      #subsystem-connections button:focus-visible{outline:3px solid var(--s1,#72e4ca);outline-offset:3px}
      #subsystem-connections[data-state=UNAVAILABLE] #subsystem-state,#subsystem-connections[data-state=STALE] #subsystem-state{color:var(--crit,#ff9c9c)}
      #subsystem-connections[data-state=DEGRADED] #subsystem-state{color:var(--warn,#f5cf81)}
      #subsystem-connections ul{padding-left:20px;margin:8px 0}#subsystem-connections li{margin:8px 0}
      #subsystem-connections .subsystem-meta{font-size:12px;font-variant-numeric:tabular-nums}
    </style><div class="subsystem-top"><h2 id="subsystem-title"></h2><button type="button" id="subsystem-refresh">Refresh subsystem status</button></div>
    <p id="subsystem-state" role="status" aria-live="polite">STARTING · Waiting for a native observation.</p>
    <p id="subsystem-observed" class="subsystem-meta">Observation time and capture age unknown.</p>
    <div class="subsystem-pair"><article><h3>NEXUS · source-health observations</h3><p id="subsystem-nexus">Unavailable</p><p id="subsystem-slo"></p></article>
    <article><h3>AION · persisted monitoring memory</h3><p id="subsystem-aion">Unavailable</p><p id="subsystem-chain">Chain verification unknown.</p><p id="subsystem-persisted" class="subsystem-meta"></p></article></div>
    <h3>Published runner caches · values at observation</h3><ul id="subsystem-assets"><li>Current source observations unknown.</li></ul>
    <p id="subsystem-warnings"></p><p id="subsystem-source" class="subsystem-meta"></p>
    <p>Monitoring and research context only. Provider SLOs and upstream sequences remain unknown unless independently supplied. Persisted memory contains monitoring receipts; open positions and market history are not reconstructed. Execution and production decisions are not authorized.</p>`;
    container.append(section);
    const $=name=>section.querySelector('#subsystem-'+name);
    const text=(name,value)=>{if($(name).textContent!==value)$(name).textContent=value;};
    text('title',id.toUpperCase()+' · Native subsystem connections');
    let active=true,pending=null,poll=null,expiry=null,sequence=0,snapshot=null,received=0,assetSignature='';
    const off=()=>id!=='main'&&!!globalThis.IcarusWorkspacePower?.isOff(id);
    const visible=()=>active&&section.isConnected&&!document.hidden&&section.getClientRects().length>0&&getComputedStyle(section).visibility!=='hidden';
    function invalidate(state,reason) {
      snapshot=null;section.dataset.state=state;text('state',state+' · '+reason);
      text('observed','Current observation time and capture age unknown.');
      text('nexus','Unavailable · current native source health unknown.');
      text('aion','Unavailable · persisted receipt count and recovery unknown.');
      text('chain','Chain verification unknown.');text('persisted','');text('source','');text('warnings','');
      assetSignature='';text('assets','Current source observations unknown.');
    }
    function render() {
      if(!snapshot)return;
      const data=snapshot,n=data.nexus,a=data.aion;
      const observationAge=finite(data.observed_at_ns)?Math.max(0,Date.now()/1000-data.observed_at_ns/1e9):null;
      const captureAge=finite(data.capture_age_seconds)?data.capture_age_seconds+(Date.now()-received)/1000:null;
      const stale=observationAge!==null&&observationAge>15||captureAge!==null&&captureAge>15;
      let state=stale&&['OBSERVING','DEGRADED'].includes(data.state)?'STALE':data.state;
      if(state==='OBSERVING'&&(observationAge===null||captureAge===null||a.chain_verified!==true||['UNAVAILABLE','STOPPED','STARTING'].includes(n.state)||!['VERIFIED','OBSERVING'].includes(a.state)))state='DEGRADED';
      section.dataset.state=state;
      text('state',state+' · '+(stale?'Last observation expired; current native health unknown.':state==='OBSERVING'?'Local monitor observation available; provider health is not established.':state==='STOPPED'?'Native monitor stopped; current source health unknown.':'Current source health is incomplete or unavailable.'));
      text('observed',`Observed ${utc(data.observed_at_ns)} · observation age ${age(observationAge)} · runner capture age ${age(captureAge)}.`);
      const prefix=stale?'Last observation: ':'';
      text('nexus',`${prefix}Native state ${label(n.state)} · ${count(n.stream_count)} streams · plane hash ${label(n.plane_hash)}.`);
      text('slo',`${count(n.unknown_slo_streams)} streams with unknown provider SLOs. Sequences describe adapter-local observations; upstream provider sequences remain unknown.`);
      text('aion',`${prefix}Native state ${label(a.state)} · ${count(a.event_count)} persisted context receipts · ${count(a.recovered_event_count)} recovered receipts.`);
      text('chain',a.chain_verified===true?'Native chain verified at observation.':a.chain_verified===false?'Native chain unverified; persisted memory cannot be trusted.':'Native chain verification unknown.');
      text('persisted','Last persisted receipt '+utc(a.last_persisted_ns)+'.');
      text('source',`Workspace ${id.toUpperCase()} · native source revision ${label(data.source_revision)}.`);
      text('warnings',data.warnings.length?'Warnings: '+data.warnings.map(label).join(' · '):'No monitor warnings reported; provider qualification remains unknown.');
      const signature=JSON.stringify(data.assets);
      if(signature!==assetSignature){
        assetSignature=signature;const rows=data.assets.slice(0,64).map(asset=>{
          const row=document.createElement('li');
          row.textContent=`${label(asset.symbol)} · ${label(asset.provider)} / ${label(asset.provider_symbol)} · cache ${label(asset.cache_state)} · ${label(asset.state)} · capture ${age(asset.capture_age_seconds)} · poll ${age(asset.poll_age_seconds)} · bar ${age(asset.bar_age_seconds)} · price ${age(asset.price_age_seconds)}${asset.active_error===true?' · active source error':''}`;
          return row;
        });
        if(!rows.length){const row=document.createElement('li');row.textContent='No published runner observations; current source health unknown.';rows.push(row);}
        if(data.assets.length>64){const row=document.createElement('li');row.textContent='Additional published observations omitted from this bounded view.';rows.push(row);}
        $('assets').replaceChildren(...rows);
      }
    }
    function stopTimers(){clearTimeout(poll);clearTimeout(expiry);poll=null;expiry=null;}
    function schedule(){if(visible()&&!off()&&poll===null)poll=setTimeout(()=>{poll=null;void refresh();},5000);}
    function ageTick(){if(!visible()||off())return;render();expiry=setTimeout(ageTick,1000);}
    async function refresh() {
      if(!visible()||off()||pending)return;
      clearTimeout(poll);poll=null;
      const current=++sequence,controller=new AbortController();pending=controller;
      section.setAttribute('aria-busy','true');$('refresh').setAttribute('aria-disabled','true');
      const deadline=setTimeout(()=>controller.abort(),8000);
      try {
        const response=await client.request('/api/subsystem-connections',{signal:controller.signal});
        if(!response.ok)throw new Error('HTTP '+response.status);
        const data=await response.json();
        if(!active||current!==sequence||!visible()||off())return;
        if(data?.schema_version!=='icarus-nexus-aion-v1'||data.workspace_id!==id||data.execution_authorized!==false||data.production_decision_authorized!==false||!states.has(data.state))throw new Error('Diagnostic identity or authority mismatch');
        if(!record(data.nexus)||!record(data.aion)||!Array.isArray(data.assets)||data.assets.length>256||data.assets.some(row=>!record(row))||!Array.isArray(data.warnings)||data.warnings.length>256)throw new Error('Invalid native diagnostic');
        const n=data.nexus,a=data.aion;
        if(![n.state,a.state].every(value=>typeof value==='string'&&value.length>0&&value.length<=80)||!(n.plane_hash===null||typeof n.plane_hash==='string')||![n.stream_count,n.unknown_slo_streams,a.event_count,a.recovered_event_count].every(nullableCount)||![true,false,null].includes(a.chain_verified)||!nullableTime(a.last_persisted_ns))throw new Error('Incomplete native diagnostic');
        if(data.observed_at_ns!==null&&(!finite(data.observed_at_ns)||data.observed_at_ns<0||data.observed_at_ns/1e9>Date.now()/1000+5)||data.capture_age_seconds!==null&&(!finite(data.capture_age_seconds)||data.capture_age_seconds<0))throw new Error('Invalid observation time');
        snapshot=data;received=Date.now();render();
      } catch(error) {
        if(active&&current===sequence&&visible()&&!off())invalidate('UNAVAILABLE','Latest diagnostic read failed; current native health and memory verification unknown.');
      } finally {
        clearTimeout(deadline);
        if(pending===controller){pending=null;section.removeAttribute('aria-busy');$('refresh').removeAttribute('aria-disabled');schedule();}
      }
    }
    function reconcile() {
      if(!active)return;
      if(!section.isConnected){dispose();return;}
      if(!visible()||off()){
        stopTimers();sequence++;pending?.abort();pending=null;section.removeAttribute('aria-busy');$('refresh').removeAttribute('aria-disabled');
        if(off())invalidate('STOPPED',id.toUpperCase()+' runtime is off or changing state; current health unknown.');
        return;
      }
      if(expiry===null)ageTick();
      if(!pending&&poll===null)void refresh();
    }
    const observer=new MutationObserver(reconcile);
    for(let ancestor=section;ancestor;ancestor=ancestor.parentElement)observer.observe(ancestor,{attributes:true,attributeFilter:['hidden','style','class'],childList:ancestor!==section});
    $('refresh').addEventListener('click',refresh);
    document.addEventListener('visibilitychange',reconcile);
    globalThis.addEventListener('icarus:workspace-power',reconcile);
    globalThis.addEventListener('pagehide',dispose);
    function dispose(){
      if(!active)return;active=false;sequence++;stopTimers();pending?.abort();pending=null;observer.disconnect();
      document.removeEventListener('visibilitychange',reconcile);globalThis.removeEventListener('icarus:workspace-power',reconcile);globalThis.removeEventListener('pagehide',dispose);
      $('refresh').removeEventListener('click',refresh);mounted.delete(container);
    }
    const component=Object.freeze({dispose});mounted.set(container,component);reconcile();return component;
  }
  globalThis.IcarusSubsystemConnections=Object.freeze({mount});
})();

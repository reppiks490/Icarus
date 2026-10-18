/* Addressable views of existing paper workspaces; no generated prices or performance. */
'use strict';
(() => {
  const id = location.pathname.split('/').pop();
  if (id === 'connections') {
    document.querySelector('#workspace-panel').hidden = true;
    document.querySelector('#connections').hidden = false;
    const script = document.createElement('script'); script.src = '/connections-ui.js'; document.head.append(script);
    async function sharedAccounting() {
      const selectors=['#all-realized','#all-open','#all-total'];
      try {
        const reply=await fetch('/api/command-centers/cc1',{cache:'no-store'});
        if(!reply.ok)throw new Error('Accounting unavailable');
        const data=await reply.json(),a=data.aggregate||{};
        const complete=data.accounting?.complete===true&&typeof a.realized_pnl==='number'&&Number.isFinite(a.realized_pnl)&&typeof a.open_pnl==='number'&&Number.isFinite(a.open_pnl);
        const amounts=complete?[a.realized_pnl,a.open_pnl,a.realized_pnl+a.open_pnl]:[null,null,null];
        selectors.forEach((selector,i)=>document.querySelector(selector).textContent=amounts[i]==null?'Unavailable':amounts[i].toLocaleString(undefined,{style:'currency',currency:'USD'}));
        document.querySelector('#accounting-basis').textContent=(complete?'All four paper ledgers observed. ':'Aggregate unavailable. ')+'Open marks may include warmup-origin positions. Fees and brokerage reconciliation are unverified; no true broker P&L is available.';
      } catch {
        selectors.forEach(selector=>document.querySelector(selector).textContent='Unavailable');
      }
    }
    sharedAccounting();setInterval(()=>{if(!document.hidden)sharedAccounting();},15000);
    return;
  }
  if (!['cc1','cc2','cc3','cc4'].includes(id)) return;
  const $ = selector => document.querySelector(selector);
  const text = (selector, value) => { $(selector).textContent = String(value ?? 'Unavailable'); };
  const number = value => typeof value === 'number' && Number.isFinite(value) ? value : null;
  const money = value => number(value) == null ? 'Unavailable' : value.toLocaleString(undefined,{style:'currency',currency:'USD'});
  const node = (tag, value, cls) => { const el=document.createElement(tag); if(value!=null)el.textContent=String(value); if(cls)el.className=cls; return el; };
  const fail = error => { text('#snapshot-notice', error.message || String(error)); $('#snapshot-notice').classList.add('error'); };
  let state=null, baseline='', dirty=false, pending=false, sequence=0, chartSequence=0;
  document.querySelector(`nav a[href="/dashboards/${id}"]`).setAttribute('aria-current','page');
  async function get(path) { const reply=await fetch(path,{cache:'no-store'}); const data=await reply.json(); if(!reply.ok)throw new Error(data.detail||data.reason||`HTTP ${reply.status}`); return data; }
  async function admin(suffix, body) {
    const token=$('#owner-token').value;
    if(!token)throw new Error('Owner access token is required to change this paper workspace.');
    const reply=await fetch(`/admin/command-centers/${id}${suffix}`,{method:'POST',headers:{'Content-Type':'application/json','Authorization':'Bearer '+token},body:JSON.stringify(body)});
    const data=await reply.json(); if(!reply.ok)throw new Error(data.detail||data.error||`HTTP ${reply.status}`); return data;
  }
  const signature = profile => JSON.stringify([profile.chart,profile.effective_inputs,profile.inputs,profile.assets]);
  function renderConfig(data, force=false) {
    const profile=data.profile;
    if(dirty&&!force) {if(baseline!==signature(profile))text('#config-notice','Settings changed elsewhere. Discard edits to load the current settings.');return;}
    baseline=signature(profile); dirty=false;
    const chart=profile.chart||{};
    $('#config-timeframe').replaceChildren(...['1','2','3','5','10','15','20','30','45','60','120','180','240','D','W'].map(tf=>{const el=node('option',tf);el.value=tf;return el;}));
    $('#config-timeframe').value=String(chart.timeframe||'20');
    $('#config-chart-type').value=chart.chart_type||'heikin_ashi'; $('#config-fill').value=chart.fill_on||'real';
    $('#config-fields').replaceChildren();
    const selection=$('#workspace-assets');selection.replaceChildren();
    for(const asset of data.available_assets||[]){const label=node('label'),check=document.createElement('input');check.type='checkbox';check.dataset.asset=asset.symbol;check.checked=(profile.assets||[]).includes(asset.symbol);check.disabled=asset.selectable!==true;label.append(check,node('span',`${asset.symbol} · ${asset.name||''} · ${asset.selectable?'Selectable paper runtime':'Not admitted'} · ${asset.data_access_note||'Data access unverified'}`));selection.append(label);}
    const values={...(profile.effective_inputs||{}),...(profile.inputs||{})};
    for(const meta of data.input_meta||[]) {
      const label=node('label',meta.label||meta.name,'field'); const field=document.createElement(Array.isArray(meta.options)?'select':'input'); field.dataset.input=meta.name;field.dataset.kind=meta.kind;
      if(Array.isArray(meta.options)) {for(const value of meta.options){const option=node('option',value);option.value=String(value);field.append(option);}field.value=String(values[meta.name]??meta.default);}
      else if(meta.kind==='bool'){field.type='checkbox';field.checked=Boolean(values[meta.name]??meta.default);}
      else {field.type=['int','float'].includes(meta.kind)?'number':'text';field.value=values[meta.name]??meta.default??'';if(field.type==='number'){field.step=meta.step??(meta.kind==='int'?'1':'any');if(meta.minval!=null)field.min=meta.minval;if(meta.maxval!=null)field.max=meta.maxval;}}
      label.append(field);$('#config-fields').append(label);
    }
    text('#config-notice','No pending edits.');
  }
  function render(data) {
    state=data; const p=data.profile, aggregate=data.aggregate||{}, complete=data.accounting?.complete===true;
    document.title=`Icarus · ${id.toUpperCase()} · ${p.name}`;
    text('#workspace-id',`${id.toUpperCase()} / isolated paper ledger`);text('#workspace-name',p.name);text('#workspace-description',p.description||'');
    text('#all-realized',money(complete?aggregate.realized_pnl:null));text('#all-open',money(complete?aggregate.open_pnl:null));
    const closed=number(aggregate.realized_pnl),open=number(aggregate.open_pnl);text('#all-total',money(complete&&closed!=null&&open!=null?closed+open:null));
    text('#accounting-basis',`${complete?'All four paper ledgers observed.':'Aggregate unavailable: at least one ledger or mark is missing.'} Persisted closures after paper cutover; open marks may include warmup-origin positions. Fees and brokerage reconciliation are unverified. No true broker P&L is available.`);
    text('#own-realized',money(p.runtime_available?p.pnl?.realized_pnl:null));text('#own-open',money(p.runtime_available?p.pnl?.open_pnl:null));text('#own-feed',p.feed?.status||'Unobserved');
    text('#snapshot-notice',p.runtime_available?'Current engine snapshot · isolated simulated ledger':'Runtime unavailable · saved configuration only');$('#snapshot-notice').classList.remove('error');
    const assets=Array.isArray(p.status?.assets)?p.status.assets:[],table=$('#asset-rows');table.replaceChildren();
    for(const asset of assets){const row=node('tr');for(const value of [asset.symbol,asset.feed_provider||asset.feed||'Unobserved',asset.paused?'Paused':asset.warm?'Warm':'Warming',asset.position??'Unknown',money(asset.open_profit),money(asset.live_profit),asset.last_error||'No error reported'])row.append(node('td',value));table.append(row);}
    if(!assets.length){const row=node('tr'),cell=node('td','No runtime asset observations are available.');cell.colSpan=7;row.append(cell);table.append(row);}
    const previous=$('#chart-asset').value;$('#chart-asset').replaceChildren(...assets.map(asset=>{const option=node('option',asset.symbol);option.value=asset.symbol;return option;}));if(assets.some(asset=>asset.symbol===previous))$('#chart-asset').value=previous;
    text('#chart-config',`Chart: ${p.chart?.timeframe||'Unknown'} · ${p.chart?.chart_type||'Unknown'} · Fill prices: ${p.chart?.fill_on||'Unknown'}`);
    $('#pause').textContent=p.status?.paused?'Resume entries':'Pause entries';$('#pause').disabled=pending||!p.runtime_available;$('#flatten').disabled=pending||!p.runtime_available;
    renderConfig(data);loadChart();
  }
  async function loadChart() {
    const current=++chartSequence,symbol=$('#chart-asset').value,canvas=$('#price-chart'),ctx=canvas.getContext('2d');ctx.clearRect(0,0,canvas.width,canvas.height);
    if(!symbol){text('#chart-note','No selected workspace runner or observed bars.');return;}
    try{const chart=await get(`/api/command-centers/${id}/chart/${encodeURIComponent(symbol)}?n=240`);if(current!==chartSequence)return;
      const bars=(chart.bars||[]).filter(row=>Array.isArray(row)&&row.length>=5&&row.slice(0,5).every(v=>number(v)!=null));
      if(bars.length<2){text('#chart-note','Fewer than two observed bars; chart unavailable.');return;}
      const values=bars.map(row=>row[4]),lo=Math.min(...values),hi=Math.max(...values),range=hi-lo||1,pad=36;
      ctx.strokeStyle='#293d50';ctx.lineWidth=1;for(let i=0;i<5;i++){const y=pad+i*(canvas.height-pad*2)/4;ctx.beginPath();ctx.moveTo(pad,y);ctx.lineTo(canvas.width-pad,y);ctx.stroke();}
      ctx.strokeStyle='#72e4ca';ctx.lineWidth=2;ctx.beginPath();values.forEach((value,i)=>{const x=pad+i*(canvas.width-pad*2)/(values.length-1),y=canvas.height-pad-(value-lo)*(canvas.height-pad*2)/range;i?ctx.lineTo(x,y):ctx.moveTo(x,y);});ctx.stroke();
      text('#chart-note',`${symbol} · ${bars.length} observed bars · ${new Date(bars[0][0]*1000).toISOString()} — ${new Date(bars.at(-1)[0]*1000).toISOString()} · selected workspace chart closes`);
    }catch(error){if(current===chartSequence)text('#chart-note',`Chart unavailable: ${error.message}`);}
  }
  async function loadCorpus(){const target=$('#corpus-sources');try{const evidence=await get('/api/corpus-consumption');target.replaceChildren(node('p',evidence.status,'note'));for(const corpus of evidence.corpora||[]){const item=node('article',null,'source');item.append(node('h3',corpus.cache_name));item.append(node('p',`${corpus.dataset_count} datasets · ${corpus.retained_rows} retained rows · Historical: ${corpus.historical===true?'yes':'unknown'}`));item.append(node('p',`Latest closed source bar: ${Number.isFinite(corpus.latest_bar_closed_ts)?new Date(corpus.latest_bar_closed_ts*1000).toISOString():'unknown'} · source age ${Number.isFinite(corpus.age_seconds)?Math.floor(corpus.age_seconds/86400)+' days':'unknown'}`));item.append(node('p',`Native run ${corpus.run_id} · artifact ${corpus.artifact_id}`));const details=node('details');details.append(node('summary','Receipt and workspace consumption'));details.append(node('pre',JSON.stringify({receipt_sha256:corpus.receipt_sha256,paper_warmup_used:corpus.paper_warmup_used,workspace:corpus.workspaces?.find?.(row=>row.id===id)||corpus.workspaces?.[id]},null,2)));item.append(details);target.append(item);}}catch(error){target.replaceChildren(node('p',`Corpus evidence unavailable: ${error.message}`,'error'));}}
  async function refresh(){const request=++sequence;try{const data=await get(`/api/command-centers/${id}`);if(request===sequence)render(data);}catch(error){if(request!==sequence)return;state=null;chartSequence++;$('#price-chart').getContext('2d').clearRect(0,0,960,360);text('#chart-note','Workspace snapshot unavailable; chart cleared.');for(const selector of ['#all-realized','#all-open','#all-total','#own-realized','#own-open'])text(selector,'Unavailable');$('#pause').disabled=true;$('#flatten').disabled=true;fail(error);}loadCorpus();}
  $('#refresh').addEventListener('click',refresh);$('#chart-asset').addEventListener('change',loadChart);
  async function action(suffix,body){if(pending)return;pending=true;try{await admin(suffix,body);await refresh();}catch(error){fail(error);}finally{pending=false;if(state)render(state);}}
  $('#pause').addEventListener('click',()=>action('/pause',{paused:!state?.profile?.status?.paused}));
  $('#flatten').addEventListener('click',()=>{if(confirm(`Flatten all simulated paper positions only in ${id.toUpperCase()}?`))action('/flatten',{confirm:true});});
  $('#workspace-config').addEventListener('input',()=>{dirty=true;text('#config-notice','Unsaved edits.');});$('#workspace-config').addEventListener('change',()=>{dirty=true;});
  $('#discard-config').addEventListener('click',()=>{if(state)renderConfig(state,true);});
  $('#workspace-config').addEventListener('submit',async event=>{event.preventDefault();if(pending||!state)return;pending=true;try{const latest=await get(`/api/command-centers/${id}`);if(signature(latest.profile)!==baseline)throw new Error('Settings changed elsewhere. Discard edits before applying.');const inputs={};for(const field of document.querySelectorAll('[data-input]')){let value=field.type==='checkbox'?field.checked:field.value;if(['int','float'].includes(field.dataset.kind)){value=Number(value);if(!field.value||!Number.isFinite(value))throw new Error(`Invalid numeric input: ${field.dataset.input}`);}inputs[field.dataset.input]=value;}const assets=Array.from(document.querySelectorAll('[data-asset]:checked')).map(field=>field.dataset.asset);const assetUpdate=(state.available_assets||[]).length?{assets}:{};await admin('',{...assetUpdate,chart:{...state.profile.chart,timeframe:$('#config-timeframe').value,chart_type:$('#config-chart-type').value,fill_on:$('#config-fill').value},inputs});dirty=false;await refresh();text('#config-notice','Applied to this workspace.');}catch(error){text('#config-notice',error.message);}finally{pending=false;}});
  refresh();setInterval(()=>{if(!document.hidden&&!pending)refresh();},15000);
})();

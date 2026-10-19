/* Addressable views of existing paper workspaces; no generated prices or performance. */
'use strict';
(() => {
  const id = location.pathname.split('/').pop();
  if (id === 'connections') {
    document.querySelector('#workspace-panel').hidden = true;
    document.querySelector('#connections').hidden = false;
    const script = document.createElement('script'); script.src = '/connections-ui.js'; document.head.append(script);
    let sharedState=null, sharedSequence=0;
    async function sharedAccounting() {
      const sequence=++sharedSequence;
      const selectors=['#all-realized','#all-open','#all-total'];
      try {
        const data=await IcarusPaperPnl.fetchJson('/api/command-centers/cc1'),pnl=IcarusPaperPnl.read(data),a=pnl?.aggregate||{};
        if(sequence!==sharedSequence)return;
        sharedState=data;
        const complete=a.accounting_complete===true;
        const amounts=[a.realized_pnl??null,a.open_pnl??null,a.total_pnl??null];
        selectors.forEach((selector,i)=>document.querySelector(selector).textContent=amounts[i]==null?'Unavailable':amounts[i].toLocaleString(undefined,{style:'currency',currency:'USD'}));
        document.querySelector('#accounting-basis').textContent=(complete?'All four paper ledgers observed. ':'Aggregate unavailable. ')+'Open marks may include warmup-origin positions. Fees and brokerage reconciliation are unverified; no true broker P&L is available.';
      } catch {
        if(sequence!==sharedSequence)return;
        sharedState=null;
        selectors.forEach(selector=>document.querySelector(selector).textContent='Unavailable');
      }
    }
    setInterval(()=>{if(sharedState&&!IcarusPaperPnl.read(sharedState)){sharedState=null;['#all-realized','#all-open','#all-total'].forEach(selector=>document.querySelector(selector).textContent='Unavailable');document.querySelector('#accounting-basis').textContent='Accounting snapshot expired. No current total is available.';}},1000);
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
  async function get(path) { return IcarusPaperPnl.fetchJson(path); }
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
    for(const asset of data.available_assets||[]){const label=node('label'),check=document.createElement('input');check.type='checkbox';check.dataset.asset=asset.symbol;check.checked=(profile.assets||[]).includes(asset.symbol);check.disabled=asset.selectable!==true;label.append(check,node('span',`${asset.symbol} · ${asset.name||''} · ${asset.requested_expansion?'Added futures family / micro · ':''}${asset.selectable?'Selectable paper runtime':'Not admitted'} · ${asset.data_access_note||'Data access unverified'}`));selection.append(label);}
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
    state=data; const p=data.profile,pnl=IcarusPaperPnl.read(data),aggregate=pnl?.aggregate||{},own=pnl?.profiles.find(row=>row.id===id)||{},complete=aggregate.accounting_complete===true;
    document.title=`Icarus · ${id.toUpperCase()} · ${p.name}`;
    text('#workspace-id',`${id.toUpperCase()} / isolated paper ledger`);text('#workspace-name',p.name);text('#workspace-description',p.description||'');
    text('#all-realized',money(aggregate.realized_pnl));text('#all-open',money(aggregate.open_pnl));
    const closed=number(aggregate.realized_pnl),open=number(aggregate.open_pnl);text('#all-total',money(aggregate.total_pnl));
    text('#accounting-basis',`${complete?'All four paper ledgers observed.':'Aggregate unavailable: at least one ledger or mark is missing.'} Persisted closures after paper cutover; open marks may include warmup-origin positions. Fees and brokerage reconciliation are unverified. No true broker P&L is available.`);
    text('#own-realized',money(own.realized_pnl));text('#own-open',money(own.open_pnl));text('#own-feed',p.feed?.status||'Unobserved');
    text('#snapshot-notice',p.runtime_available?'Current engine snapshot · isolated simulated ledger':'Runtime unavailable · saved configuration only');$('#snapshot-notice').classList.remove('error');
    const assets=Array.isArray(p.status?.assets)?p.status.assets:[],table=$('#asset-rows');table.replaceChildren();
    for(const asset of assets){const row=node('tr');for(const value of [asset.symbol,asset.feed_provider||asset.feed||'Unobserved',asset.paused?'Paused':asset.warm?'Warm':'Warming',asset.position??'Unknown',money(pnl&&own.open_pnl!=null&&number(asset.price_age)!=null&&asset.price_age>=0&&asset.price_age<=90?asset.open_profit:null),money(pnl&&own.realized_pnl!=null?asset.live_profit:null),asset.last_error||'No error reported'])row.append(node('td',value));table.append(row);}
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
  async function loadCorpus(){const target=$('#corpus-sources');try{const evidence=await get('/api/corpus-consumption');target.replaceChildren(node('p',evidence.status,'note'));for(const corpus of evidence.corpora||[]){const item=node('article',null,'source');item.append(node('h3',corpus.cache_name));item.append(node('p',`${corpus.dataset_count} datasets · ${corpus.retained_rows} retained rows · Historical: ${corpus.historical===true?'yes':'unknown'}`));item.append(node('p',`Latest closed source bar: ${Number.isFinite(corpus.latest_bar_closed_ts)?new Date(corpus.latest_bar_closed_ts*1000).toISOString():'unknown'} · source age ${Number.isFinite(corpus.age_seconds)?Math.floor(corpus.age_seconds/86400)+' days':'unknown'}`));item.append(node('p',`Native run ${corpus.run_id} · artifact ${corpus.artifact_id}`));const details=node('details');details.append(node('summary','Receipt and workspace consumption'));details.append(node('pre',JSON.stringify({receipt_sha256:corpus.receipt_sha256,paper_warmup_used:corpus.paper_warmup_used,workspace:corpus.workspaces?.find?.(row=>row.id===id)||corpus.workspaces?.[id]},null,2)));item.append(details);target.append(item);}}catch(error){target.replaceChildren(node('p',`Corpus evidence unavailable: ${error.message}`,'error'));} await loadExpansion(target);}
  async function loadExpansion(target){
    try{
      const proof=await get('/api/corpus-expansion'),item=node('article',null,'source');
      item.append(node('h3','Ten added futures families · archived consumption'));
      if(proof.status!=='HISTORICAL_EXPANSION_CONSUMPTION_VERIFIED'){item.append(node('p','Verified expansion evidence unavailable.'));target.append(item);return;}
      const expansion=proof.requested_futures_expansion;
      item.append(node('p',`${expansion.full_roots.join(', ')} · ${expansion.all_full_families_warmed?'all ten warmed in all four workspaces':'coverage incomplete'}`));
      item.append(node('p',`Exact available micros: ${expansion.available_symbols.filter(root=>expansion.micro_roots.includes(root)).join(', ')||'None'}. Missing archived micros: ${expansion.unavailable_symbols.join(', ')||'None'}. No full-size series was substituted.`));
      item.append(node('p',`${id.toUpperCase()}: ${(expansion.warmed_symbols_by_workspace[id]||[]).join(', ')}. Historical warmup only; fresh feed rights and profitability are unverified.`));
      item.append(node('p',`Native run ${proof.run_id} · artifact ${proof.artifact_id} · receipt SHA256 ${proof.receipt_sha256}`));
      target.append(item);
    }catch{target.append(node('p','Expansion consumption proof unavailable.','error'));}
  }
  function clearAccounting(){
    for(const selector of ['#all-realized','#all-open','#all-total','#own-realized','#own-open'])text(selector,'Unavailable');
    $('#asset-rows').replaceChildren();
    text('#accounting-basis','Current accounting unavailable. Fees and broker reconciliation remain unverified.');
    $('#pause').disabled=true;$('#flatten').disabled=true;
  }
  setInterval(()=>{if(state&&!IcarusPaperPnl.read(state)){clearAccounting();}},1000);
  async function refresh(){const request=++sequence;try{const data=await get(`/api/command-centers/${id}`);if(request===sequence)render(data);}catch(error){if(request!==sequence)return;state=null;chartSequence++;$('#price-chart').getContext('2d').clearRect(0,0,960,360);text('#chart-note','Workspace snapshot unavailable; chart cleared.');clearAccounting();$('#pause').disabled=true;$('#flatten').disabled=true;fail(error);}loadCorpus();}
  $('#refresh').addEventListener('click',refresh);$('#chart-asset').addEventListener('change',loadChart);
  async function action(suffix,body){if(pending)return;pending=true;try{await admin(suffix,body);await refresh();}catch(error){fail(error);}finally{pending=false;if(state)render(state);}}
  $('#pause').addEventListener('click',()=>action('/pause',{paused:!state?.profile?.status?.paused}));
  $('#flatten').addEventListener('click',()=>{if(confirm(`Flatten all simulated paper positions only in ${id.toUpperCase()}?`))action('/flatten',{confirm:true});});
  $('#workspace-config').addEventListener('input',()=>{dirty=true;text('#config-notice','Unsaved edits.');});$('#workspace-config').addEventListener('change',()=>{dirty=true;});
  $('#discard-config').addEventListener('click',()=>{if(state)renderConfig(state,true);});
  $('#expand-assets').addEventListener('click',()=>{for(const field of document.querySelectorAll('[data-asset]'))if(!field.disabled)field.checked=true;dirty=true;text('#config-notice','Full universe selected in this draft. Apply to this workspace when flat; saved settings are unchanged until then.');});
  $('#workspace-config').addEventListener('submit',async event=>{event.preventDefault();if(pending||!state)return;pending=true;try{const latest=await get(`/api/command-centers/${id}`);if(signature(latest.profile)!==baseline)throw new Error('Settings changed elsewhere. Discard edits before applying.');const inputs={};for(const field of document.querySelectorAll('[data-input]')){let value=field.type==='checkbox'?field.checked:field.value;if(['int','float'].includes(field.dataset.kind)){value=Number(value);if(!field.value||!Number.isFinite(value))throw new Error(`Invalid numeric input: ${field.dataset.input}`);}inputs[field.dataset.input]=value;}const assets=Array.from(document.querySelectorAll('[data-asset]:checked')).map(field=>field.dataset.asset);const assetUpdate=(state.available_assets||[]).length?{assets}:{};await admin('',{...assetUpdate,chart:{...state.profile.chart,timeframe:$('#config-timeframe').value,chart_type:$('#config-chart-type').value,fill_on:$('#config-fill').value},inputs});dirty=false;await refresh();text('#config-notice','Applied to this workspace.');}catch(error){text('#config-notice',error.message);}finally{pending=false;}});
  // A200 remains a separate, read-only research surface. Selection never mutates
  // workspace assets, accounting, qualification records or the Pulse runner.
  let equityCatalog=null, equityLoad=0, equityRead=0, equityBusy=false;
  const equityContext=$('#a200-chart').getContext('2d');
  function clearEquityHistory() {
    equityRead++;
    equityContext.clearRect(0,0,960,300);
    text('#a200-history-note','No history requested for this selection. No sample prices are drawn.');
    text('#a200-receipt','Entitlement and corporate-action policy are unknown until independently verified. No research chart admits an asset to Pulse.');
  }
  function equityRows() {
    const target=$('#a200-rows'), search=$('#a200-search').value.trim().toLowerCase();
    target.replaceChildren();
    if(!equityCatalog)return;
    const probe=equityCatalog.source_probe||{};
    const saved=new Map((probe.results||[]).map(row=>[row.instrument_id,row]));
    for(const row of equityCatalog.instruments) {
      if(![row.display_symbol,row.name,row.venue,row.instrument_id].join(' ').toLowerCase().includes(search))continue;
      const evidence=saved.get(row.instrument_id), tr=node('tr'),symbol=node('td');
      const choose=node('button',row.display_symbol);choose.type='button';
      choose.setAttribute('aria-label',`Research ${row.display_symbol}`);
      choose.addEventListener('click',()=>{$('#a200-instrument').value=row.instrument_id;clearEquityHistory();});
      symbol.append(choose,node('small',row.name));
      tr.append(symbol,node('td',row.venue),node('td',row.instrument_id));
      const last=number(evidence?.received_end_ts);
      const source=evidence?`${evidence.probe_status} · ${probe.status||'freshness unknown'} · ${evidence.row_count??'unknown'} saved rows · last source bar ${last==null?'unknown':new Date(last*1000).toISOString()}`:'No saved source probe for this identity';
      const blockers=`Identity ${row.identity_status||'UNKNOWN'}; entitlement ${row.entitlement||'UNKNOWN'}; corporate actions ${row.corporate_action_policy||'UNKNOWN'}; historical bars ${row.historical_bars||'UNVERIFIED'}; Pulse ${row.pulse_enabled===true?'enabled':'not admitted'}`;
      tr.append(node('td',source),node('td',blockers));target.append(tr);
    }
    if(!target.children.length){const tr=node('tr'),td=node('td','No matching catalog identity.');td.colSpan=5;tr.append(td);target.append(tr);}
  }
  async function loadEquityCatalog() {
    const current=++equityLoad;
    try {
      const catalog=await get('/api/market-universe');
      if(current!==equityLoad)return;
      if(!Array.isArray(catalog.instruments)||catalog.instruments.length!==200||new Set(catalog.instruments.map(row=>row.instrument_id)).size!==200)throw new Error('The expected 200 distinct catalog identities are unavailable.');
      equityCatalog=catalog;const counts=catalog.counts||{},probe=catalog.source_probe||{};
      text('#a200-summary',`${counts.catalogued_count} catalogued · ${counts.source_connected_count} source-qualified · ${counts.historical_bars_qualified_count} historical-bar qualified · ${counts.live_bars_qualified_count} live-bar qualified · ${counts.pulse_enabled_count} Pulse enabled · ${counts.strategy_qualified_count} strategy-qualified`);
      text('#a200-probe',`Saved Yahoo probe: ${probe.status||'UNAVAILABLE'} · recorded ${probe.probe_updated_at||'unknown'} · age ${number(probe.age_seconds)==null?'unknown':Math.floor(probe.age_seconds/3600)+' hours'} · ${probe.counts?.response_received_count??'unknown'}/${probe.requested_count??200} responses. These saved observations are not a current live feed. Listing crosswalk: ${catalog.listing_crosswalk?.status||'UNAVAILABLE'}.`);
      const previous=$('#a200-instrument').value;
      $('#a200-instrument').replaceChildren(...catalog.instruments.map(row=>{const option=node('option',`${row.display_symbol} · ${row.name} · ${row.venue}`);option.value=row.instrument_id;return option;}));
      if(catalog.instruments.some(row=>row.instrument_id===previous))$('#a200-instrument').value=previous;
      $('#a200-history').disabled=equityBusy;clearEquityHistory();equityRows();
    } catch(error) {
      if(current!==equityLoad)return;
      equityCatalog=null;$('#a200-instrument').replaceChildren();$('#a200-rows').replaceChildren();$('#a200-history').disabled=true;clearEquityHistory();
      text('#a200-summary',`Equity catalog unavailable: ${error.message}`);
      text('#a200-probe','Source access, freshness and qualification are unavailable.');
    }
  }
  async function readEquityHistory() {
    if(equityBusy||!equityCatalog)return;
    const instrument=equityCatalog.instruments.find(row=>row.instrument_id===$('#a200-instrument').value);
    const token=$('#owner-token').value;
    if(!token){text('#a200-history-note','Enter the access token above before requesting selected research history.');return;}
    if(!instrument)return;
    clearEquityHistory();const current=equityRead;
    equityBusy=true;$('#a200-history').disabled=true;
    try {
      const end=Math.floor(Date.now()/3600000)*3600,start=end-5*86400;
      const query=new URLSearchParams({start_ts:String(start),end_ts:String(end),interval_seconds:'3600',limit:'240',provider:'yahoo'});
      const reply=await fetch(`/api/market-history/${encodeURIComponent(instrument.instrument_id)}?${query}`,{cache:'no-store',headers:{Authorization:'Bearer '+token}});
      const data=await reply.json();
      if(current!==equityRead)return;
      if(!reply.ok)throw new Error(data.error||data.detail||`HTTP ${reply.status}`);
      if(data.instrument?.instrument_id!==instrument.instrument_id||data.provider!=='yahoo'||data.receipt?.instrument_id!==instrument.instrument_id||data.receipt?.provider!=='yahoo'||data.execution_authorized!==false||data.pulse_enabled!==false)throw new Error('Research response identity or authority does not match this request.');
      if(!Array.isArray(data.bars)||data.bars.length>240)throw new Error('Research response exceeds the requested bar bound.');
      const bars=data.bars;
      if(bars.some((row,index)=>!['ts','o','h','l','c','v'].every(key=>number(row[key])!=null)||!Number.isInteger(row.ts)||row.ts<start||row.ts>=end||(index>0&&row.ts<=bars[index-1].ts)))throw new Error('Research response has invalid bar timestamps or values.');
      const receipt=data.receipt;
      text('#a200-receipt',JSON.stringify({instrument_id:instrument.instrument_id,provider:'yahoo',qualification:data.qualification,pulse_enabled:false,scope:'RESEARCH_CONTEXT_ONLY',execution_authorized:false,receipt_id:receipt.receipt_id,checksum_sha256:receipt.checksum_sha256,entitlement_status:receipt.entitlement_status||'UNKNOWN',corporate_action_policy:receipt.corporate_action_policy||'UNKNOWN',identity_status:receipt.identity_status||'UNKNOWN',provider_mapping_status:receipt.provider_mapping_status||'UNKNOWN',session_validation_status:receipt.session_validation_status||'UNKNOWN',historical_bars_qualified:receipt.historical_bars_qualified===true},null,2));
      if(bars.length>=2) {
        const values=bars.map(row=>row.c),lo=Math.min(...values),hi=Math.max(...values),range=hi-lo||1,pad=30;
        equityContext.strokeStyle='#f5cf81';equityContext.lineWidth=2;equityContext.beginPath();
        values.forEach((value,index)=>{const x=pad+index*(960-2*pad)/(values.length-1),y=300-pad-(value-lo)*(300-2*pad)/range;index?equityContext.lineTo(x,y):equityContext.moveTo(x,y);});equityContext.stroke();
      }
      text('#a200-history-note',`${instrument.display_symbol} · ${bars.length} observed bars · Yahoo research context only · ${data.qualification||'UNQUALIFIED'} · entitlement ${receipt.entitlement_status||'UNKNOWN'} · corporate actions ${receipt.corporate_action_policy||'UNKNOWN'}. This chart does not feed Pulse or P&L.${bars.length<2?' Fewer than two bars; no line drawn.':''}`);
    } catch(error) {
      if(current===equityRead){equityContext.clearRect(0,0,960,300);text('#a200-history-note',`Research history unavailable: ${error.message}`);}
    } finally {
      equityBusy=false;$('#a200-history').disabled=!equityCatalog;
    }
  }
  $('#a200-search').addEventListener('input',equityRows);
  $('#a200-instrument').addEventListener('change',clearEquityHistory);
  $('#a200-history').addEventListener('click',readEquityHistory);
  $('#a200-refresh').addEventListener('click',loadEquityCatalog);
  loadEquityCatalog();
  refresh();setInterval(()=>{if(!document.hidden&&!pending)refresh();},15000);
})();

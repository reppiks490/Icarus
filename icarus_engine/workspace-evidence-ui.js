/* Shared corpus/catalog receipts with explicit selected-consumer provenance. */
'use strict';
(() => {
  function mount(parent,client,{canReadHistory=()=>false}={}) {
    if(!parent||!['main','cc1','cc2','cc3','cc4'].includes(client?.context?.id))throw new Error('An explicit evidence workspace is required');
    const id=client.context.id,section=document.createElement('section');
    section.id='workspace-evidence';section.className='card c12';
    section.innerHTML=`<style>
      #workspace-evidence{min-width:0;max-width:100%;box-sizing:border-box}
      #workspace-evidence .sources{display:grid;gap:12px}
      #workspace-evidence .source{padding:12px;border:1px solid var(--ring);border-radius:8px;min-width:0;overflow-wrap:anywhere}
      #workspace-evidence pre{white-space:pre-wrap;overflow-wrap:anywhere;max-width:100%;font-size:12px}
      #workspace-evidence .toolbar{flex-wrap:wrap}
      #workspace-evidence select{max-width:min(75vw,460px)}
      #workspace-evidence table{min-width:750px}
      #workspace-evidence td{white-space:normal;overflow-wrap:anywhere}
      #workspace-evidence td small{display:block;max-width:230px}
      #workspace-evidence canvas{width:100%;max-width:100%;height:300px}
    </style><h2>Shared evidence and research <span class="sub">historical receipts, separate from current runtime operation</span></h2>
    <p><a href="/dashboards/connections">Shared connections and account inventory ↗</a></p>
    <h3>Corpus provenance and selected-workspace consumption</h3><div id="corpus-sources" class="sources"><p class="empty">Loading shared receipts…</p></div>
    <h3 style="margin-top:20px">200 equity candidates · research context only</h3>
    <p id="a200-summary">Loading shared catalog…</p><p id="a200-probe" class="small muted"></p>
    <div class="toolbar"><label>Filter <input id="a200-search" placeholder="symbol, venue or identity"></label>
      <label>Research instrument <select id="a200-instrument"></select></label>
      <button id="evidenceRefresh" type="button">Refresh shared evidence</button>
      <button id="evidenceReadHistory" type="button" disabled>Request selected research history</button></div>
    <p class="small muted">History is requested only by an owner action. Selection and returned research bars do not admit an asset to Pulse or alter paper P&amp;L.</p>
    <p id="a200-history-note" role="status"></p><canvas id="a200-chart" width="960" height="300" aria-label="Selected research history"></canvas>
    <pre id="a200-receipt"></pre><div class="scroll" style="max-height:440px"><table><thead><tr><th>Symbol</th><th>Venue</th><th>Identity</th><th>Saved source probe</th><th>Qualification</th></tr></thead><tbody id="a200-rows"></tbody></table></div>`;
    parent.append(section);
    const $=selector=>section.querySelector(selector);
    const text=(selector,value)=>{$(selector).textContent=String(value??'Unavailable');};
    const node=(tag,value,cls)=>{const el=document.createElement(tag);if(value!=null)el.textContent=String(value);if(cls)el.className=cls;return el;};
    const number=value=>typeof value==='number'&&Number.isFinite(value)?value:null;
    let active=true,controller=new AbortController(),historyAbort=null,corpusSequence=0;
    async function get(path) {
      const response=await client.request(path,{signal:controller.signal});
      const data=await response.json();if(!response.ok)throw new Error(data.detail||data.error||'Shared evidence unavailable');return data;
    }
    async function loadCorpus() {
      const ticket=++corpusSequence,target=$('#corpus-sources');
      try {
        const evidence=await get('/api/corpus-consumption');if(!active||ticket!==corpusSequence)return;
        if(!Array.isArray(evidence.corpora))throw new Error('Corpus receipt list unavailable');
        target.replaceChildren(node('p','Shared receipt status: '+(evidence.status||'UNAVAILABLE')));
        for(const corpus of evidence.corpora){
          const item=node('article',null,'source');item.append(node('h3',corpus.cache_name||'Unnamed cache'));
          item.append(node('p',`${corpus.dataset_count??'unknown'} datasets · ${corpus.retained_rows??'unknown'} retained rows · historical ${corpus.historical===true?'yes':'unverified'}`));
          item.append(node('p',`Latest closed source bar: ${Number.isFinite(corpus.latest_bar_closed_ts)?new Date(corpus.latest_bar_closed_ts*1000).toISOString():'unknown'} · source age ${Number.isFinite(corpus.age_seconds)?Math.floor(corpus.age_seconds/86400)+' days':'unknown'}`));
          item.append(node('p',`Native run ${corpus.run_id??'unknown'} · artifact ${corpus.artifact_id??'unknown'}`));
          if(id==='main')item.append(node('p','Shared four-workspace evidence does not establish main-runtime consumption.'));
          const details=node('details');details.append(node('summary',id.toUpperCase()+' consumption receipt'));
          details.append(node('pre',JSON.stringify({receipt_sha256:corpus.receipt_sha256,paper_warmup_used:corpus.paper_warmup_used,workspace:corpus.workspaces?.find?.(row=>row.id===id)||corpus.workspaces?.[id]},null,2)));
          item.append(details);target.append(item);
        }
      }catch(error){if(!active||ticket!==corpusSequence)return;target.replaceChildren(node('p','Corpus evidence unavailable: '+error.message,'neg'));}
      if(active&&ticket===corpusSequence)await loadExpansion(target,ticket);
    }
    async function loadExpansion(target,ticket) {
      try {
        const proof=await get('/api/corpus-expansion');if(!active||ticket!==corpusSequence)return;
        const item=node('article',null,'source');item.append(node('h3','Added futures families · archived consumption'));
        if(proof.status!=='HISTORICAL_EXPANSION_CONSUMPTION_VERIFIED'){item.append(node('p','Verified expansion evidence unavailable.'));target.append(item);return;}
        const expansion=proof.requested_futures_expansion;
        item.append(node('p',`${expansion.full_roots.join(', ')} · ${expansion.all_full_families_warmed?'historical four-workspace warmup recorded':'coverage incomplete'}`));
        item.append(node('p',`Exact available micros: ${expansion.available_symbols.filter(root=>expansion.micro_roots.includes(root)).join(', ')||'None'}. Missing archived micros: ${expansion.unavailable_symbols.join(', ')||'None'}. No full-size series was substituted.`));
        item.append(node('p',`${id.toUpperCase()}: ${(expansion.warmed_symbols_by_workspace[id]||[]).join(', ')||'no selected receipt'}. Historical warmup only; fresh feed rights and profitability are unverified.`));
        item.append(node('p',`Native run ${proof.run_id} · artifact ${proof.artifact_id} · receipt SHA256 ${proof.receipt_sha256}`));target.append(item);
      }catch(error){if(active&&ticket===corpusSequence)target.append(node('p','Expansion consumption proof unavailable.','neg'));}
    }
    // The A200 reader below preserves the dedicated renderer's source identity,
    // bar bounds, qualification and authority checks. Only transport/lifetime
    // and owner-role handling change for the common component.
      let equityCatalog=null, equityLoad=0, equityRead=0, equityBusy=false;
  const equityContext=$('#a200-chart').getContext('2d');
  function clearEquityHistory() {
    equityRead++;historyAbort?.abort();historyAbort=null;equityBusy=false;
    equityContext?.clearRect(0,0,960,300);
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
      const choose=node('button',row.display_symbol);choose.type='button';choose.dataset.workspaceReadOnly='true';
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
      if(!active||current!==equityLoad)return;
      if(!Array.isArray(catalog.instruments)||catalog.instruments.length!==200||new Set(catalog.instruments.map(row=>row.instrument_id)).size!==200)throw new Error('The expected 200 distinct catalog identities are unavailable.');
      equityCatalog=catalog;const counts=catalog.counts||{},probe=catalog.source_probe||{};
      text('#a200-summary',`${counts.catalogued_count} catalogued · ${counts.source_connected_count} source-qualified · ${counts.historical_bars_qualified_count} historical-bar qualified · ${counts.live_bars_qualified_count} live-bar qualified · ${counts.pulse_enabled_count} Pulse enabled · ${counts.strategy_qualified_count} strategy-qualified`);
      text('#a200-probe',`Saved Yahoo probe: ${probe.status||'UNAVAILABLE'} · recorded ${probe.probe_updated_at||'unknown'} · age ${number(probe.age_seconds)==null?'unknown':Math.floor(probe.age_seconds/3600)+' hours'} · ${probe.counts?.response_received_count??'unknown'}/${probe.requested_count??200} responses. These saved observations are not a current live feed. Listing crosswalk: ${catalog.listing_crosswalk?.status||'UNAVAILABLE'}.`);
      const previous=$('#a200-instrument').value;
      $('#a200-instrument').replaceChildren(...catalog.instruments.map(row=>{const option=node('option',`${row.display_symbol} · ${row.name} · ${row.venue}`);option.value=row.instrument_id;return option;}));
      if(catalog.instruments.some(row=>row.instrument_id===previous))$('#a200-instrument').value=previous;
      $('#evidenceReadHistory').disabled=!canReadHistory()||equityBusy;clearEquityHistory();equityRows();
    } catch(error) {
      if(!active||current!==equityLoad)return;
      equityCatalog=null;$('#a200-instrument').replaceChildren();$('#a200-rows').replaceChildren();$('#evidenceReadHistory').disabled=true;clearEquityHistory();
      text('#a200-summary',`Equity catalog unavailable: ${error.message}`);
      text('#a200-probe','Source access, freshness and qualification are unavailable.');
    }
  }
  async function readEquityHistory() {
    if(!active||equityBusy||!equityCatalog)return;
    if(!canReadHistory()){text('#a200-history-note','Owner access is required to request research history.');return;}
    const instrument=equityCatalog.instruments.find(row=>row.instrument_id===$('#a200-instrument').value);
    const token=localStorage.getItem('icarus-engine-token')||'';
    if(!token){text('#a200-history-note','Set an owner token before requesting selected research history.');return;}
    if(!instrument)return;
    clearEquityHistory();const current=equityRead,historyRequest=new AbortController();historyAbort=historyRequest;
    equityBusy=true;$('#evidenceReadHistory').disabled=true;
    try {
      const end=Math.floor(Date.now()/3600000)*3600,start=end-5*86400;
      const query=new URLSearchParams({start_ts:String(start),end_ts:String(end),interval_seconds:'3600',limit:'240',provider:'yahoo'});
      const reply=await client.request(`/api/market-history/${encodeURIComponent(instrument.instrument_id)}?${query}`,{cache:'no-store',signal:historyRequest.signal});
      const data=await reply.json();
      if(!active||current!==equityRead)return;
      if(!reply.ok)throw new Error(data.error||data.detail||`HTTP ${reply.status}`);
      if(data.instrument?.instrument_id!==instrument.instrument_id||data.provider!=='yahoo'||data.receipt?.instrument_id!==instrument.instrument_id||data.receipt?.provider!=='yahoo'||data.execution_authorized!==false||data.pulse_enabled!==false)throw new Error('Research response identity or authority does not match this request.');
      if(!Array.isArray(data.bars)||data.bars.length>240)throw new Error('Research response exceeds the requested bar bound.');
      const bars=data.bars;
      if(bars.some((row,index)=>!['ts','o','h','l','c','v'].every(key=>number(row[key])!=null)||!Number.isInteger(row.ts)||row.ts<start||row.ts>=end||(index>0&&row.ts<=bars[index-1].ts)))throw new Error('Research response has invalid bar timestamps or values.');
      const receipt=data.receipt;
      text('#a200-receipt',JSON.stringify({instrument_id:instrument.instrument_id,provider:'yahoo',qualification:data.qualification,pulse_enabled:false,scope:'RESEARCH_CONTEXT_ONLY',execution_authorized:false,receipt_id:receipt.receipt_id,checksum_sha256:receipt.checksum_sha256,entitlement_status:receipt.entitlement_status||'UNKNOWN',corporate_action_policy:receipt.corporate_action_policy||'UNKNOWN',identity_status:receipt.identity_status||'UNKNOWN',provider_mapping_status:receipt.provider_mapping_status||'UNKNOWN',session_validation_status:receipt.session_validation_status||'UNKNOWN',historical_bars_qualified:receipt.historical_bars_qualified===true},null,2));
      if(bars.length>=2&&equityContext) {
        const values=bars.map(row=>row.c),lo=Math.min(...values),hi=Math.max(...values),range=hi-lo||1,pad=30;
        equityContext.strokeStyle='#f5cf81';equityContext.lineWidth=2;equityContext.beginPath();
        values.forEach((value,index)=>{const x=pad+index*(960-2*pad)/(values.length-1),y=300-pad-(value-lo)*(300-2*pad)/range;index?equityContext.lineTo(x,y):equityContext.moveTo(x,y);});equityContext.stroke();
      }
      text('#a200-history-note',`${instrument.display_symbol} · ${bars.length} observed bars · Yahoo research context only · ${data.qualification||'UNQUALIFIED'} · entitlement ${receipt.entitlement_status||'UNKNOWN'} · corporate actions ${receipt.corporate_action_policy||'UNKNOWN'}. This chart does not feed Pulse or P&L.${bars.length<2?' Fewer than two bars; no line drawn.':''}`);
    } catch(error) {
      if(active&&current===equityRead){equityContext?.clearRect(0,0,960,300);text('#a200-history-note',`Research history unavailable: ${error.message}`);}
    } finally {
      if(active&&current===equityRead){equityBusy=false;historyAbort=null;$('#evidenceReadHistory').disabled=!canReadHistory()||!equityCatalog;}
    }
  }
  $('#a200-search').addEventListener('input',equityRows);
  $('#a200-instrument').addEventListener('change',clearEquityHistory);
  $('#evidenceReadHistory').addEventListener('click',readEquityHistory);
  $('#evidenceRefresh').addEventListener('click',refresh);
  function refresh(){if(!active)return;controller.abort();controller=new AbortController();clearEquityHistory();void loadCorpus();void loadEquityCatalog();}
  function dispose(){if(!active)return;active=false;corpusSequence++;equityLoad++;equityRead++;controller.abort();historyAbort?.abort();globalThis.removeEventListener('pagehide',dispose);}
  globalThis.addEventListener('pagehide',dispose);
  refresh();return Object.freeze({refresh,dispose});

  }
  globalThis.IcarusWorkspaceEvidence=Object.freeze({mount});
})();

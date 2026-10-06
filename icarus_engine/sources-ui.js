/* Public-source observations. Collection only runs after a button click. */
let sourcesLoading = false, sourcesPendingLoad = false, sourceRecordsSeq = 0, sourceWatchLoaded = false, sourcesLatest = {};
const sourceNames = {cftc:'CFTC commitments of traders',bls:'BLS CPI',
  'federal-reserve':'Federal Reserve releases',bea:'BEA releases',sec:'SEC company filings',coinbase:'Coinbase BTC-USD trades',
  'yahoo-dxy':'DXY / asset return correlations'};
function sourcesHtml(assets) {
  sourceWatchLoaded=false;
  const options=assets.map(a=>`<option value="${esc(a.symbol)}">${esc(a.symbol)}</option>`).join('');
  return `<section class="card c12"><h2>Financial &amp; data <span class="sub">Source-backed public observations</span></h2>
    <p class="small muted">Collect on demand or enable bounded background refresh below. CFTC positions, macro releases, company filings and spot BTC trades are research evidence; they do not place orders or supply a licensed futures tick feed.</p>
    <div id="sourcesStatus" role="status" class="small muted">Loading saved source status…</div></section>
    <section class="card c12"><h2>Economic event clock <span class="sub">BLS · BEA · Census · FOMC · point-in-time schedule</span></h2>
      <div id="eventClockStatus" role="status" class="small muted">Loading verified release schedule…</div>
      <div class="tiles" style="grid-template-columns:repeat(auto-fit,minmax(min(100%,220px),1fr));margin-top:10px">
        <div class="tile" id="eventClockNext">Next high-impact event —</div>
        <div class="tile" id="eventClockCoverage">Source coverage —</div>
      </div>
      <div id="eventClockList" class="scroll" style="max-height:360px;margin-top:10px">Loading upcoming events…</div>
    </section>
    <section class="card c7"><h2>Public collection</h2><div id="sourcesCards" class="tiles" style="grid-template-columns:repeat(auto-fit,minmax(min(100%,180px),1fr));overflow-wrap:anywhere"></div>
    <div class="toolbar"><label>Map SEC facts to asset <select id="sourceAsset"><option value="">No mapping</option>${options}</select></label>
    <label>SEC CIK <input id="sourceCik" inputmode="numeric" maxlength="10" placeholder="Numeric CIK"></label>
    <label>BTC seconds <input id="sourceSeconds" type="number" min="1" max="3600" value="1"></label></div>
    <p class="small muted">SEC needs the server's real contact identity. Map a company only when it is relevant to that asset; a filing is not the asset's own market data. Coinbase seconds must stay fixed for an existing stream.</p>
    <pre id="sourceCollectResult" class="log" style="max-height:170px">No collection requested.</pre></section>
    <section class="card c5"><h2>Saved observations</h2><div class="toolbar"><label>Kind <select id="sourceKind"><option value="asset">COT &amp; macro</option><option value="companies">Companies</option><option value="trades">BTC trades</option></select></label>
    <label>Asset <select id="sourceFilterAsset"><option value="">All</option>${options}</select></label><button id="sourceRefresh">Refresh records</button></div>
    <div id="sourceRecords" class="scroll" style="max-height:610px;overflow-wrap:anywhere">Loading saved records…</div></section>
    <section class="card c12"><h2>BTC-USD seconds &amp; footprint</h2><div id="sourceStream" class="scroll" style="max-height:380px;overflow-wrap:anywhere">No trade stream loaded.</div></section>
    <section class="card c12"><h2>Background source refresh</h2><p class="small muted">Public requests only. Configure each source's cadence and options, including an exact CIK for SEC. Missing credentials or sequence gaps remain visible. Model analysis has separate Research controls.</p>
    <pre id="sourceWatchStatus" class="log" style="max-height:180px">Loading…</pre><details><summary>Collection schedule</summary><textarea id="sourceWatchConfig" rows="14" style="width:100%;background:var(--surface-2);color:var(--ink)"></textarea>
    <p><button id="sourceWatchSave" disabled>Save schedule</button> <button id="sourceWatchEnable" disabled>Enable refresh</button> <button id="sourceWatchDisable" disabled>Disable refresh</button></p></details></section>`;
}
function eventClockTime(row) {
  if(row.scheduled_at_utc) {
    const d=new Date(row.scheduled_at_utc);
    if(!Number.isNaN(d.getTime())) return d.toLocaleString([], {month:'short',day:'numeric',hour:'2-digit',minute:'2-digit',timeZoneName:'short'});
  }
  return row.event_date ? new Date(row.event_date+'T12:00:00').toLocaleDateString([], {month:'short',day:'numeric',year:'numeric'})+' · date only' : 'time unavailable';
}
function eventClockFuture(row, now=Date.now()) {
  if(row.scheduled_at_utc) {
    const ts=Date.parse(row.scheduled_at_utc);
    return Number.isFinite(ts) && ts>=now;
  }
  if(!row.event_date) return false;
  const end=Date.parse(row.event_date+'T23:59:59');
  return Number.isFinite(end) && end>=now;
}
function eventClockCountdown(row, now=Date.now()) {
  if(!row.scheduled_at_utc) return 'date-only schedule';
  const ms=Date.parse(row.scheduled_at_utc)-now;
  if(!Number.isFinite(ms) || ms<0) return 'passed';
  const mins=Math.round(ms/60000);
  if(mins<60) return mins+'m';
  if(mins<1440) return Math.floor(mins/60)+'h '+(mins%60)+'m';
  return Math.floor(mins/1440)+'d '+Math.floor((mins%1440)/60)+'h';
}
function renderEventClock(data) {
  const status=$('#eventClockStatus'), next=$('#eventClockNext'), coverage=$('#eventClockCoverage'), list=$('#eventClockList');
  if(!status||!next||!coverage||!list) return;
  const sources=data?.sources||{}, rows=Object.entries(sources);
  const degraded=rows.filter(([,s])=>s.status!=='ok');
  const usable=Array.isArray(data?.events) ? data.events.filter(r=>eventClockFuture(r)) : [];
  const high=usable.filter(r=>r.impact==='high');
  const health=data?.source_health||data?.status||'unavailable';
  status.innerHTML=`Sync <b>${esc(data?.status||'unavailable')}</b> · source health <b>${esc(health)}</b> · remote generated ${esc(data?.remote_generated_at||'unknown')} · ${esc(data?.upcoming_count??0)} upcoming`+
    (data?.last_error?`<div class="neg">${esc(data.last_error)}</div>`:'')+
    (degraded.length?`<div class="small">${degraded.map(([name,s])=>`${esc(name)}: ${esc(s.status||'unknown')}${s.transport?` via ${esc(s.transport)}`:''}${s.snapshot_as_of?` · snapshot ${esc(s.snapshot_as_of)}`:''}`).join(' · ')}</div>`:'');
  const first=high[0];
  next.innerHTML=first?`<div class="k">Next high-impact</div><div class="v">${esc(first.title)}</div><div class="small">${esc(eventClockTime(first))} · ${esc(eventClockCountdown(first))}</div>`:
    '<div class="k">Next high-impact</div><div class="v">None in verified horizon</div>';
  coverage.innerHTML=`<div class="k">Coverage</div><div class="v">${rows.filter(([,s])=>s.status==='ok').length}/${rows.length} live-clean</div><div class="small">${rows.map(([name,s])=>`${esc(name)} ${esc(s.status||'?')} (${esc(s.rows??0)})`).join(' · ')}</div>`;
  list.innerHTML=usable.slice(0,16).map(row=>`<div class="tile" style="margin-bottom:6px">
    <div><b>${esc(row.title)}</b> <span class="st ${row.impact==='high'?'warn':''}">${esc(row.impact)}</span></div>
    <div class="small">${esc(eventClockTime(row))} · ${esc(row.source)} · ${esc(row.category)}${row.reference_period?` · ref ${esc(row.reference_period)}`:''}</div>
    <div class="small muted">${row.time_known?`countdown ${esc(eventClockCountdown(row))}`:'exact release time not asserted'} · ${esc(row.timing_basis||'timing basis unavailable')}</div>
  </div>`).join('')||'<p class="empty">No future events in the verified schedule horizon.</p>';
}

function sourceLink(url,label) {
  try {const parsed=new URL(url);if(parsed.protocol==='https:')
    return `<a href="${esc(parsed.href)}" target="_blank" rel="noopener noreferrer">${esc(label||parsed.hostname)}</a>`;}
  catch (_) {} return esc(label||'Source URL unavailable');
}
function sourceTime(value) {return value?esc(value):'unknown';}
function sourceQuantity(value) {return Number.isFinite(value)?value.toLocaleString('en-US',{maximumFractionDigits:8}):'unknown';}
function sourceRecord(r) {
  const title=r.kind==='company'?(r.data?.name||r.instrument_id):r.kind==='cot'?`${r.asset_ids?.join(', ')||'CFTC'} · ${r.report_family||'COT'}`:
    r.kind==='news'?(r.data?.title||r.source):`${r.source} · ${r.report_family||r.instrument_id}`;
  const details=r.kind==='correlation'?`<p class="small">${esc(r.data?.asset_vendor_ticker)} / DX-Y.NYB · ${esc(r.data?.pairs)} aligned return pairs · ${esc(r.data?.direction)} association. ${esc(r.data?.reason||'')}</p><p class="small muted">Hourly vendor history; gaps are not filled. Correlation does not establish predictive lead. ${esc((r.data?.caveats||[]).join(' '))}</p>`:
    r.kind==='company'&&r.data?.filings?`<p class="small">Recent filings: ${r.data.filings.slice(0,5).map(f=>`${esc(f.form||'filing')} ${esc(f.filingDate||'')}`).join(' · ')}</p>`:'';
  return `<div class="tile" style="margin-bottom:8px"><b>${esc(title)}</b> <span class="chip">${esc(r.source)}</span>
    <div class="small muted">${sourceLink(r.source_url,'Official record')} · ${esc(r.instrument_id)} · ${esc((r.asset_ids||[]).join(', ')||'no asset mapping')}</div>
    <div class="small">Observed ${sourceTime(r.observed_at)} · Published ${r.published_at?sourceTime(r.published_at):'unknown'} · First receipt ${sourceTime(r.available_at)}</div>
    <div class="small muted">Timing ${esc(r.timing_basis||'unknown')} · ${esc((r.quality_flags||[]).join(', ')||'no quality flags')} · revision ${esc((r.revision_id||'').slice(0,12))}</div>
    ${r.values&&Object.keys(r.values).length?`<p class="small">${Object.entries(r.values).map(([k,v])=>`${esc(k)} ${esc(v)} ${esc(r.units?.[k]||'')}`).join(' · ')}</p>`:''}${details}</div>`;
}
function sourceFootprint(bar) {
  const levels=Object.entries(bar.footprint||{}).sort((a,b)=>Number(b[0])-Number(a[0])).slice(0,40);
  return `<div class="tile" style="margin-bottom:8px"><b>${bar.active?'Active partial bucket':'Completed second bar'}</b>
    <div class="small">${esc(new Date(bar.start_ns/1e6).toISOString())} · O/H/L/C ${[bar.open_ticks,bar.high_ticks,bar.low_ticks,bar.close_ticks].map(v=>esc(v==null?'—':(v/100).toFixed(2))).join(' / ')} · ${esc(bar.trades||0)} trades · volume ${esc(sourceQuantity(bar.volume||0))}</div>
    <div class="small muted">Available ${bar.available_at_ns?esc(new Date(bar.available_at_ns/1e6).toISOString()):'only after completion'} · Aggressor ${bar.aggressor_complete===false?'partly unknown':'recorded'}</div>
    ${levels.length?`<div class="scroll"><table><thead><tr><th>Price</th><th>Buy</th><th>Sell</th><th>Unknown</th></tr></thead><tbody>${levels.map(([price,v])=>`<tr><td>${esc((Number(price)/100).toFixed(2))}</td><td>${esc(sourceQuantity(v.buy||0))}</td><td>${esc(sourceQuantity(v.sell||0))}</td><td>${esc(sourceQuantity(v.unknown||0))}</td></tr>`).join('')}</tbody></table></div>`:''}</div>`;
}
async function loadSources() {
  if(view!=='sources') return;
  if(sourcesLoading){sourcesPendingLoad=true;return;}
  sourcesLoading=true;
  sourcesPendingLoad=false;
  try {
    const eventClockPromise=researchGet('/api/economic-events').catch(e=>({
      status:'unavailable',source_health:'unavailable',last_error:e?.message||String(e),sources:{},events:[]
    }));
    const status=await researchGet('/api/research/sources');
    const eventClock=await eventClockPromise;
    if(view!=='sources') return;
    renderEventClock(eventClock);
    sourcesLatest=status.sources||{};
    $('#sourcesStatus').textContent=`SEC contact identity ${status.sec_identity_configured?'configured':'not configured'} · ${status.note||''}`;
    $('#sourcesCards').innerHTML=Object.entries(sourceNames).map(([source,name])=>{
      const s=status.sources?.[source]||{};
      return `<div class="tile"><b>${esc(name)}</b><div class="small muted">${esc(s.status||'not_collected')} · ${s.last_success_at?`last success ${esc(s.last_success_at)}`:'no successful collection'}</div>
        ${s.error?`<div class="small neg">${esc(s.error)}</div>`:''}<button class="sm" data-collect="${esc(source)}">Collect ${esc(source)}</button></div>`;
    }).join('');
    $('#sourcesCards').querySelectorAll('[data-collect]').forEach(button=>button.onclick=()=>collectSource(button));
    await loadSourceRecords();
    await loadSourceWatch();
  } catch(e) {if($('#sourcesStatus')) $('#sourcesStatus').textContent='Financial data unavailable: '+e.message;}
  finally {
    sourcesLoading=false;
    if(sourcesPendingLoad&&view==='sources'){sourcesPendingLoad=false;setTimeout(loadSources,0);}
  }
}
async function loadSourceRecords() {
  if(view!=='sources') return;
  const seq=++sourceRecordsSeq;
  const kind=$('#sourceKind').value,asset=$('#sourceFilterAsset').value,cik=$('#sourceCik').value.trim();
  const query=new URLSearchParams({kind,limit:'100'});
  if(asset&&kind!=='trades') query.set('asset',asset);
  if(kind==='companies'&&cik) query.set('cik',cik);
  try {
    const data=await researchGet('/api/research/records?'+query);
    if(seq!==sourceRecordsSeq||view!=='sources'||$('#sourceKind').value!==kind||$('#sourceFilterAsset').value!==asset) return;
    const rows=kind==='asset'?(data.records||[]).filter(r=>r.kind!=='company'):(data.records||[]);
    $('#sourceRecords').innerHTML=rows.map(r=>kind==='trades'?`<div class="tile" style="margin-bottom:6px">Trade ${esc(r.event?.sequence)} · ${esc(r.trade?.time)} · ${esc(r.trade?.price)} · ${esc(r.trade?.size)} · aggressor ${esc(r.event?.aggressor||'unknown')} · ${sourceLink(r.source_url,'Coinbase receipt')}</div>`:sourceRecord(r)).join('')||'<p class="empty">No saved records match this filter.</p>';
    if(kind==='trades') {
      const stream=data.stream;
      $('#sourceStream').innerHTML=stream?`<p class="small">${esc(stream.instrument)} · ${esc(stream.seconds)}s buckets · ${stream.sequence_continuity_checked===true?'saved batches checked for continuity':'continuity unknown'} · latest collection ${esc(sourcesLatest.coinbase?.status||'unknown')} · ${esc(sourcesLatest.coinbase?.error||'')} · active bucket ${stream.active_bucket_is_partial?'partial':'none'} · last receipt ${stream.last_success_received_ns?esc(new Date(stream.last_success_received_ns/1e6).toISOString()):'unknown'}</p>
        ${(stream.completed_bars||[]).slice(-10).reverse().map(sourceFootprint).join('')}${stream.active_bucket?sourceFootprint({...stream.active_bucket,active:true}):''}`:'<p class="empty">No Coinbase trade stream collected.</p>';
    } else $('#sourceStream').textContent='Select BTC trades to inspect completed seconds and the partial active bucket.';
  } catch(e) {if(seq===sourceRecordsSeq&&$('#sourceRecords')) $('#sourceRecords').textContent='Records unavailable: '+e.message;}
}
async function collectSource(button) {
  const source=button.dataset.collect,options={};
  try {
    if(source==='sec') {
      const cik=$('#sourceCik').value.trim();if(!/^[0-9]{1,10}$/.test(cik)||Number(cik)===0) throw new Error('Enter a numeric SEC CIK.');
      options.cik=cik;if($('#sourceAsset').value) options.assets=[$('#sourceAsset').value];
    } else if(source==='coinbase') {
      const seconds=Number($('#sourceSeconds').value);if(!Number.isInteger(seconds)||seconds<1||seconds>3600) throw new Error('BTC seconds must be 1 to 3600.');
      options.seconds=seconds;
    } else if(source==='cftc'&&$('#sourceAsset').value) {
      if($('#sourceAsset').value==='BTC') throw new Error('CFTC has a mapped BTCF futures contract, not spot BTC.');
      options.assets=[$('#sourceAsset').value];
    }
    else if(['bls','federal-reserve','bea','yahoo-dxy'].includes(source)&&$('#sourceAsset').value) options.assets=[$('#sourceAsset').value];
    button.disabled=true;
    const result=await admin('/admin/research/collect',{source,options});
    if(result&&view==='sources'&&$('#sourceCollectResult')) {$('#sourceCollectResult').textContent=JSON.stringify(result,null,2);await loadSources();}
  } catch(e) {toast(e.message,true);} finally {if(button.isConnected) button.disabled=false;}
}
function wireSources() {
  $('#sourceKind').onchange=loadSourceRecords;
  $('#sourceFilterAsset').onchange=loadSourceRecords;
  $('#sourceRefresh').onclick=loadSources;
  const configure=async(partial,button)=>{
    if(button&&button.disabled)return;
    if(button)button.disabled=true;
    try {const result=await admin('/admin/research/source-watch',partial);if(result&&view==='sources'){sourceWatchLoaded=false;await loadSourceWatch();}}
    catch(e){toast(e.message,true);}
    finally{if(button&&button.isConnected)button.disabled=false;}
  };
  $('#sourceWatchSave').onclick=()=>{try{configure(JSON.parse($('#sourceWatchConfig').value),$('#sourceWatchSave'));}catch(e){toast(e.message,true);}};
  $('#sourceWatchEnable').onclick=()=>configure({enabled:true},$('#sourceWatchEnable'));
  $('#sourceWatchDisable').onclick=()=>configure({enabled:false},$('#sourceWatchDisable'));
  loadSources();
}

async function loadSourceWatch() {
  try {
    const status=await researchGet('/api/research/source-watch');
    if(view!=='sources') return;
    $('#sourceWatchStatus').textContent=JSON.stringify({running:status.running,enabled:status.config.enabled,collections:status.collections},null,2);
    if(!sourceWatchLoaded){
      $('#sourceWatchConfig').value=JSON.stringify(status.config,null,2);sourceWatchLoaded=true;
      ['sourceWatchSave','sourceWatchEnable','sourceWatchDisable'].forEach(id=>$('#'+id).disabled=false);
    }
  } catch(e){if($('#sourceWatchStatus')) $('#sourceWatchStatus').textContent='Source refresh unavailable: '+e.message;}
}

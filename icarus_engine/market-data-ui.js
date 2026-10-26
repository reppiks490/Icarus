/* ICARUS authentic market-data console.
   Read-only except the explicit MBO snapshot button. It consumes the same engine
   endpoints exposed through MCP; it never fabricates ticks, depth, or execution state. */
let marketDataLoading=false, marketDataPendingLoad=false, marketDataForcePending=false;
const marketDataState={asset:'',schema:'mbp-10',snapshot:null,snapshotError:'',unavailable:{},results:{}};

function marketDataHtml(assets){
  const rows=Array.isArray(assets)?assets:[];
  if(!marketDataState.asset&&rows.length) marketDataState.asset=String(rows[0].symbol||'').toUpperCase();
  const options=rows.map(function(a){
    const s=String(a.symbol||'').toUpperCase();
    const label=String(a.continuous_symbol||a.provider_symbol||s);
    return '<option value="'+esc(s)+'" '+(s===marketDataState.asset?'selected':'')+'>'+esc(label)+'</option>';
  }).join('');
  return '<section class="card c12"><h2>Authentic Market Data <span class="sub">Databento raw events · continuous futures · microstructure · depth/MBO</span></h2>'+
    '<div class="toolbar"><label class="small muted">Asset <select id="mdAsset">'+options+'</select></label>'+
    '<label class="small muted">Depth <select id="mdSchema"><option value="mbp-10" '+(marketDataState.schema==='mbp-10'?'selected':'')+'>MBP-10</option><option value="mbo" '+(marketDataState.schema==='mbo'?'selected':'')+'>MBO</option></select></label>'+
    '<button id="mdRefresh">Refresh now</button><button id="mdSnapshot">Request MBO snapshot</button>'+
    '<span id="mdBusy" class="small muted"></span></div>'+
    '<div class="small muted">Same backend used by MCP tools <code>engine_market_data_capabilities</code>, <code>engine_recent_ticks</code>, <code>engine_order_book_events</code>, and <code>engine_mbo_snapshot</code>. Raw Databento side codes are shown as A/B; ICARUS does not invent a buy/sell interpretation.</div></section>'+
    '<section class="card c12"><h2>200 equity candidates <span class="sub">catalog and readiness · no automatic activation</span></h2><div id="mdUniverseSummary" class="tiles"><p class="empty">Loading catalog…</p></div><div id="mdUniverseTable" class="scroll" style="max-height:420px;margin-top:10px"></div></section>'+
    '<section class="card c12"><h2>Feed health &amp; continuous mapping</h2><div id="mdHealth" class="tiles"></div><div id="mdErrors" class="small" style="margin-top:8px"></div></section>'+
    '<section class="card c12"><h2>Microstructure window <span class="sub">derived only from returned authentic trade events</span></h2><div id="mdMicro" class="tiles"></div></section>'+
    '<section class="card c12"><h2>Recent trade events</h2><div id="mdTicks" class="scroll" style="max-height:520px"></div></section>'+
    '<section class="card c12"><h2>Order-book events <span class="sub" id="mdDepthSub"></span></h2><div id="mdDepth" class="scroll" style="max-height:520px"></div></section>'+
    '<section class="card c12"><h2>MBO snapshot <span class="sub">on demand · authenticated admin read</span></h2><div id="mdSnapshotOut" class="scroll" style="max-height:520px"><p class="empty">No snapshot requested in this browser session.</p></div></section>'+
    '<section class="card c12"><h2>Provider capabilities</h2><div id="mdCaps"></div></section>';
}

function marketDataFmt(value,digits){
  const n=Number(value);
  if(!Number.isFinite(n)) return '—';
  return n.toLocaleString(undefined,{maximumFractionDigits:digits==null?3:digits});
}

function marketDataTimeSec(sec){
  const n=Number(sec);
  if(!Number.isFinite(n)||n<=0) return '—';
  return new Date(n*1000).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit',second:'2-digit',fractionalSecondDigits:3});
}

function marketDataTimeNs(ns,sec){
  const n=Number(ns);
  if(Number.isFinite(n)&&n>0){
    const ms=Math.floor(n/1e6);
    const rem=Math.floor(n%1e6);
    return new Date(ms).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit',second:'2-digit',fractionalSecondDigits:3})+' +'+String(rem).padStart(6,'0')+'ns';
  }
  return marketDataTimeSec(sec);
}

function marketDataChip(label,cls){
  return '<span class="chip '+(cls||'')+'">'+esc(label)+'</span>';
}

async function marketDataFetch(path){
  try{
    const token=IcarusClient.getToken();
    const client=globalThis.IcarusClient;
    let target=path;
    if(client&&client.context.id!=='main'&&path.startsWith('/api/market-data/')){
      const url=new URL(path,location.origin),parts=url.pathname.slice('/api/market-data/'.length).split('/');
      if(parts.length!==2)throw new Error('Explicit selected asset and cached resource required');
      const query=new URLSearchParams(url.search);
      query.set('asset',parts[0]);query.set('resource',parts[1]);
      target='/api/command-centers/'+client.context.id+'/panels/market-data?'+query.toString();
    }
    const r=await (client?client.request(target,{cache:'no-store'}):fetch(target,{cache:'no-store',headers:{'Authorization':'Bearer '+token}}));
    const data=await r.json().catch(function(){return {};});
    if(!r.ok) return {ok:false,error:String(data.detail||data.error||('HTTP '+r.status)),status:r.status};
    return {ok:true,data:data};
  }catch(e){
    return {ok:false,error:String(e&&e.message||e),status:Number(e&&e.status)||0};
  }
}

async function marketDataAdminPost(path,body){
  const token=IcarusClient.getToken();
  const init={method:'POST',cache:'no-store',headers:{'Content-Type':'application/json','Authorization':'Bearer '+token},body:JSON.stringify(body||{})};
  const r=await (globalThis.IcarusClient?IcarusClient.request(path,init):fetch(path,init));
  const data=await r.json().catch(function(){return {};});
  if(!r.ok) throw new Error(String(data.detail||data.error||('HTTP '+r.status)));
  return data;
}

function marketDataLatencyMs(tick){
  const recv=Number(tick&&tick.ts_recv_ns), event=Number(tick&&tick.ts_event_ns);
  if(!Number.isFinite(recv)||!Number.isFinite(event)||recv<event) return null;
  return (recv-event)/1e6;
}

function marketDataMedian(values){
  const a=values.filter(Number.isFinite).slice().sort(function(x,y){return x-y;});
  if(!a.length) return null;
  const m=Math.floor(a.length/2);
  return a.length%2?a[m]:(a[m-1]+a[m])/2;
}

function marketDataRowsTable(rows,kind){
  if(!rows.length) return '<p class="empty">No '+esc(kind)+' records returned yet.</p>';
  if(kind==='trade'){
    return '<table><thead><tr><th>Event time</th><th>Price</th><th>Size</th><th>Side</th><th>Seq</th><th>Recv-event</th></tr></thead><tbody>'+
      rows.slice().reverse().slice(0,80).map(function(r){
        const lat=marketDataLatencyMs(r);
        return '<tr><td class="tnum">'+esc(marketDataTimeNs(r.ts_event_ns,r.ts_event))+'</td><td class="tnum">'+esc(marketDataFmt(r.price,6))+'</td><td class="tnum">'+esc(r.size==null?'—':r.size)+'</td><td>'+marketDataChip(r.side||'—',String(r.side||'').toUpperCase()==='A'?'r':String(r.side||'').toUpperCase()==='B'?'b':'')+'</td><td class="tnum">'+esc(r.sequence==null?'—':r.sequence)+'</td><td class="tnum">'+esc(lat==null?'—':marketDataFmt(lat,3)+' ms')+'</td></tr>';
      }).join('')+'</tbody></table>';
  }
  return '<table><thead><tr><th>Event time</th><th>Schema</th><th>Action</th><th>Side</th><th>Price</th><th>Size</th><th>Depth/order</th><th>Seq</th><th>Payload</th></tr></thead><tbody>'+
    rows.slice().reverse().slice(0,80).map(function(r){
      let extra='';
      try{ extra=JSON.stringify(r.levels||r).slice(0,700); }catch(e){ extra='unserializable'; }
      const depth=r.order_id!=null?('order '+r.order_id):(r.depth!=null?('depth '+r.depth):'—');
      return '<tr><td class="tnum">'+esc(marketDataTimeNs(r.ts_event_ns,r.ts_event))+'</td><td>'+esc(r.schema||'—')+'</td><td>'+esc(r.action||'—')+'</td><td>'+esc(r.side||'—')+'</td><td class="tnum">'+esc(marketDataFmt(r.price,6))+'</td><td class="tnum">'+esc(r.size==null?'—':r.size)+'</td><td class="tnum">'+esc(depth)+'</td><td class="tnum">'+esc(r.sequence==null?'—':r.sequence)+'</td><td><code style="white-space:normal">'+esc(extra)+'</code></td></tr>';
    }).join('')+'</tbody></table>';
}

function marketDataRender(capResult,tickResult,depthResult,healthResult){
  const asset=marketDataState.asset;
  const caps=capResult.ok?(capResult.data||{}):{};
  const c=caps.capabilities||{};
  const m=caps.metadata||{};
  const ticks=tickResult.ok&&Array.isArray(tickResult.data&&tickResult.data.ticks)?tickResult.data.ticks:[];
  const depth=depthResult.ok&&Array.isArray(depthResult.data&&depthResult.data.events)?depthResult.data.events:
              depthResult.ok&&Array.isArray(depthResult.data&&depthResult.data.depth)?depthResult.data.depth:[];
  const health=healthResult.ok?(healthResult.data||{}):{};
  const latest=ticks.length?ticks[ticks.length-1]:null;
  const latestSec=latest?Number(latest.ts_event||0):Number(m.regularMarketTime||0);
  const ageSec=latestSec>0?Math.max(0,Date.now()/1000-latestSec):null;
  const assetState=(typeof last!=='undefined'&&last&&Array.isArray(last.assets))?last.assets.find(function(a){return String(a.symbol||'').toUpperCase()===asset;}):null;
  const marketOpen=!(assetState&&assetState.market&&assetState.market.open===false);
  const liveError=String(m.live_error||m.depth_error||'');
  const coreKnown=typeof m.core_session_ok==='boolean'||Boolean(m.live_error),coreOk=m.core_session_ok===true&&!m.live_error;
  const depthHealth=m.depth_schema_health||{};
  const selectedDepthError=m.depth_errors?.[marketDataState.schema]||(!m.depth_errors?m.depth_error:'');
  const depthKnown=typeof depthHealth[marketDataState.schema]==='boolean'||Boolean(selectedDepthError);
  const selectedDepthOk=depthHealth[marketDataState.schema]===true&&!selectedDepthError;
  let freshness='NO EVENTS',freshClass='w';
  if(!marketOpen){ freshness='MARKET CLOSED'; freshClass=''; }
  else if(ageSec!=null&&ageSec<=20){ freshness='LIVE '+Math.round(ageSec)+'s'; freshClass='b'; }
  else if(ageSec!=null){ freshness='STALE '+Math.round(ageSec)+'s'; freshClass='r'; }

  const tiles=[
    ['Server (shared)',health.ok===true?'HEALTHY':'UNKNOWN',health.ok===true?'b':'w'],
    ['Provider',caps.provider||c.provider||'—',String(caps.provider||c.provider||'').toLowerCase().includes('databento')?'b':''],
    ['Dataset',c.dataset||m.dataset||'—',''],
    ['Core session',coreKnown?(coreOk?'OK':'DEGRADED'):'UNOBSERVED',coreKnown?(coreOk?'b':'r'):'w'],
    ['Depth '+marketDataState.schema,depthKnown?(selectedDepthOk?'OK':'DEGRADED'):'UNOBSERVED',depthKnown?(selectedDepthOk?'b':'r'):'w'],
    ['Freshness',freshness,freshClass],
    ['Continuous',m.continuous_symbol||'—',m.continuous_symbol?'b':''],
    ['Resolved contract',m.resolved_raw_symbol||'—',m.resolved_raw_symbol?'b':'w'],
    ['Instrument ID',m.resolved_instrument_id==null?'—':m.resolved_instrument_id,''],
    ['Mapping',m.mapping_current===true?'CURRENT':m.mapping_current===false?'NOT CURRENT':'UNKNOWN',m.mapping_current===true?'b':m.mapping_current===false?'r':'w'],
    ['Roll rule',c.continuous_rule||c.continuous_rule_code||'—',''],
    ['Last event',latestSec?marketDataTimeSec(latestSec):'—','']
  ];
  const healthEl=document.querySelector('#mdHealth');
  if(healthEl) healthEl.innerHTML=tiles.map(function(x){return '<div class="tile"><div class="k">'+esc(x[0])+'</div><div class="v">'+marketDataChip(x[1],x[2])+'</div></div>';}).join('');
  const errEl=document.querySelector('#mdErrors');
  if(errEl){
    const errs=[],info=[];
    if(!capResult.ok) errs.push('capabilities: '+capResult.error);
    if(!tickResult.ok) (tickResult.unavailable||tickResult.status===409?info:errs).push('ticks: '+tickResult.error);
    if(!depthResult.ok) (depthResult.unavailable||depthResult.status===409?info:errs).push('depth: '+depthResult.error);
    if(caps.cached_only) info.push('Selected runner cache only; no acquisition or subscription requested. '+(caps.available===false?caps.reason||'Cache unavailable.':''));
    if(!coreKnown||!depthKnown) info.push('Session health unobserved; missing metadata is not a healthy session.');
    if((tickResult.unavailable||tickResult.status===409)||(depthResult.unavailable||depthResult.status===409))
      info.push('The configured provider does not supply these authentic event streams. Use Refresh now after changing provider or entitlement.');
    if(liveError) errs.push(liveError);
    if(m.depth_error_codes) errs.push('depth codes '+JSON.stringify(m.depth_error_codes));
    if(m.core_error_code!=null) errs.push('core error code '+m.core_error_code);
    errEl.innerHTML=errs.length?'<span class="neg"><b>Feed errors:</b> '+esc(errs.join(' · '))+'</span>':
      info.length?'<span class="muted"><b>Feed status:</b> '+esc(info.join(' · '))+'</span>':
      '<span class="pos">No feed error reported by the current capability/metadata snapshot.</span>';
  }

  const totalSize=ticks.reduce(function(s,r){return s+Math.max(0,Number(r.size)||0);},0);
  const sideA=ticks.reduce(function(s,r){return s+(String(r.side||'').toUpperCase()==='A'?(Number(r.size)||0):0);},0);
  const sideB=ticks.reduce(function(s,r){return s+(String(r.side||'').toUpperCase()==='B'?(Number(r.size)||0):0);},0);
  const lat=marketDataMedian(ticks.map(marketDataLatencyMs));
  let seqJumps=0;
  for(let i=1;i<ticks.length;i++){
    const a=Number(ticks[i-1].sequence),b=Number(ticks[i].sequence);
    if(Number.isInteger(a)&&Number.isInteger(b)&&a>0&&b>a+1) seqJumps++;
  }
  const micro=[
    ['Events in window',ticks.length],
    ['Total size',totalSize],
    ['Aggressor A size',sideA],
    ['Aggressor B size',sideB],
    ['A − B size',sideA-sideB],
    ['Last price',latest?marketDataFmt(latest.price,6):'—'],
    ['Median recv-event',lat==null?'—':marketDataFmt(lat,3)+' ms'],
    ['Sequence jumps in window',seqJumps]
  ];
  const microEl=document.querySelector('#mdMicro');
  if(microEl) microEl.innerHTML=micro.map(function(x){return '<div class="tile"><div class="k">'+esc(x[0])+'</div><div class="v tnum">'+esc(x[1])+'</div></div>';}).join('')+
    '<div class="small muted" style="grid-column:1/-1">Sequence jumps are descriptive for the visible sample only; Databento sequence numbers can advance for records not represented in this trade-only view. Feed integrity failures are taken from the adapter metadata above, not inferred from this counter.</div>';

  const tickEl=document.querySelector('#mdTicks');
  if(tickEl) tickEl.innerHTML=tickResult.ok?marketDataRowsTable(ticks,'trade'):'<p class="empty">'+esc(tickResult.error||'ticks unavailable')+'</p>';
  const depthEl=document.querySelector('#mdDepth');
  if(depthEl) depthEl.innerHTML=depthResult.ok?marketDataRowsTable(depth,'depth'):'<p class="empty">'+esc(depthResult.error||'depth unavailable')+'</p>';
  const depthSub=document.querySelector('#mdDepthSub');
  if(depthSub) depthSub.textContent=marketDataState.schema+' · '+depth.length+' records in current response';

  const capEl=document.querySelector('#mdCaps');
  if(capEl){
    const schemas=Array.isArray(c.schemas)?c.schemas:[];
    capEl.innerHTML='<div class="toolbar">'+schemas.map(function(s){return marketDataChip(s,'b');}).join(' ')+'</div>'+
      '<div class="small muted" style="margin-top:8px">1-second OHLCV '+marketDataChip(c.ohlcv_seconds?'YES':'NO',c.ohlcv_seconds?'b':'r')+
      ' · ticks '+marketDataChip(c.ticks?'YES':'NO',c.ticks?'b':'r')+
      ' · MBP-10 '+marketDataChip(c.mbp_10?'YES':'NO',c.mbp_10?'b':'r')+
      ' · MBO '+marketDataChip(c.mbo?'YES':'NO',c.mbo?'b':'r')+
      ' · snapshot '+marketDataChip(c.mbo_snapshot?'YES':'NO',c.mbo_snapshot?'b':'r')+'</div>'+
      '<details style="margin-top:8px"><summary class="muted">Raw capability / metadata payload</summary><pre class="small" style="white-space:pre-wrap;max-height:420px;overflow:auto">'+esc(JSON.stringify({capabilities:c,metadata:m},null,2))+'</pre></details>';
  }
  marketDataRenderSnapshot();
}

function marketDataRenderSnapshot(){
  const el=document.querySelector('#mdSnapshotOut');
  if(!el) return;
  if(marketDataState.snapshotError){
    el.innerHTML='<p class="neg">'+esc(marketDataState.snapshotError)+'</p>';
    return;
  }
  const payload=marketDataState.snapshot;
  if(!payload){ el.innerHTML='<p class="empty">No snapshot requested in this browser session.</p>'; return; }
  const rows=Array.isArray(payload.snapshot)?payload.snapshot:[];
  el.innerHTML='<div class="small muted">'+esc(payload.asset||marketDataState.asset)+' · '+esc(payload.schema||'mbo')+' · '+rows.length+' snapshot records</div>'+marketDataRowsTable(rows,'depth');
}

async function loadMarketUniverse(){
  const summary=document.querySelector('#mdUniverseSummary');
  const table=document.querySelector('#mdUniverseTable');
  if(!summary||!table) return;
  const result=await marketDataFetch('/api/market-universe');
  if(!result.ok){summary.innerHTML='<p class="neg">Catalog unavailable: '+esc(result.error)+'</p>';table.innerHTML='';return;}
  const data=result.data||{}, counts=data.counts||{}, rows=Array.isArray(data.instruments)?data.instruments:[];
  const probe=data.source_probe||{}, probeCounts=probe.counts||{};
  const probeRows=Array.isArray(probe.results)?probe.results:[], probeById={};
  probeRows.forEach(function(row){probeById[row.instrument_id]=row;});
  const hybrid=data.hybrid_probe||{}, hybridRows=Array.isArray(hybrid.results)?hybrid.results:[], hybridById={};
  hybridRows.forEach(function(row){(hybridById[row.instrument_id]||(hybridById[row.instrument_id]=[])).push(row);});
  const listing=data.listing_crosswalk||{}, listingRows=Array.isArray(listing.results)?listing.results:[], listingById={};
  listingRows.forEach(function(row){listingById[row.instrument_id]=row;});
  const providerCandidatesById={};
  const keys=[['Catalogued','catalogued_count'],['Public listings matched','exchange_listing_identity_verified_count'],['Entitlement verified','entitlement_verified_count'],['Source connected','source_connected_count'],['History qualified','historical_bars_qualified_count'],['Live qualified','live_bars_qualified_count'],['Pulse enabled','pulse_enabled_count'],['Strategy qualified','strategy_qualified_count']];
  summary.innerHTML=keys.map(function(pair){return '<div class="tile"><div class="k">'+esc(pair[0])+'</div><div class="v">'+esc(counts[pair[1]]==null?'—':counts[pair[1]])+'</div></div>';}).join('')+
    '<div class="tile"><div class="k">Yahoo responses</div><div class="v">'+esc(probeCounts.response_received_count==null?'—':probeCounts.response_received_count)+' / '+esc(probe.requested_count==null?'—':probe.requested_count)+'</div></div>'+
    '<div class="tile"><div class="k">Yahoo symbol matches</div><div class="v">'+esc(probeCounts.provider_symbol_match_count==null?'—':probeCounts.provider_symbol_match_count)+'</div></div>'+
    '<div class="tile"><div class="k">Public listing identity</div><div class="v">'+esc(listing.matched_count==null?'—':listing.matched_count)+' / '+esc(listing.requested_count==null?'—':listing.requested_count)+' · '+esc(listing.status||'NOT_RUN')+'</div></div>'+
    '<div class="tile"><div class="k">Hybrid provider probe</div><div class="v">'+esc(hybrid.status||'NOT_RUN')+'</div></div>'+
    '<div class="small muted" style="grid-column:1/-1">Snapshot '+esc(data.retrieved_at||'unknown')+'. Public listing identity is exchange metadata only; it does not verify provider mapping, data entitlement, historical/live feeds, Pulse readiness, strategy qualification, or execution authority. Yahoo probe '+esc(probe.status||'NOT_RUN')+' · updated '+esc(probe.probe_updated_at||'—')+'. Hybrid report '+esc(hybrid.status||'NOT_RUN')+' · updated '+esc(hybrid.probe_updated_at||'—')+'.</div>';
  table.innerHTML=rows.length?'<table><thead><tr><th>Instrument ID</th><th>Symbol</th><th>Name</th><th>Venue</th><th>Public listing identity</th><th>Provider candidates</th><th>Yahoo history probe</th><th>Hybrid provider results</th><th>State</th><th>History preview</th></tr></thead><tbody>'+rows.map(function(row){
    const candidates=(Array.isArray(row.provider_symbol_candidates)?row.provider_symbol_candidates:[]).filter(function(candidate){return candidate&&typeof candidate.provider==='string'&&candidate.provider;});
    const providers=candidates.map(function(candidate){return String(candidate.provider).toLowerCase();});
    providerCandidatesById[row.instrument_id]=providers;
    const mappings=candidates.map(function(candidate){return esc((candidate.provider||'')+': '+(candidate.symbol||'')+' · '+(candidate.mapping_status||'UNKNOWN'));}).join('<br>');
    const preferredProvider=providers.indexOf('yahoo')>=0?'yahoo':'';
    const providerOptions=(providers.indexOf('yahoo')>=0?'':'<option value="" selected disabled>Choose provider</option>')+candidates.map(function(candidate){
      const provider=String(candidate.provider).toLowerCase();
      const label=String(candidate.provider)+' · '+String(candidate.mapping_status||'UNKNOWN');
      return '<option value="'+esc(provider)+'" '+(provider===preferredProvider?'selected':'')+'>'+esc(label)+'</option>';
    }).join('');
    const probeRow=probeById[row.instrument_id]||{};
    const listingRow=listingById[row.instrument_id]||{};
    const listingText=listingRow.status?String(listingRow.status)+' · '+String(listing.status||'UNKNOWN'):'not verified';
    const probeText=probeRow.probe_status?String(probeRow.probe_status)+' · '+String(probeRow.row_count||0)+' rows · symbol '+String(probeRow.provider_symbol_match_status||'UNKNOWN')+' · identity '+String(probeRow.canonical_identity_status||'UNKNOWN'):'not probed';
    const hybridText=(hybridById[row.instrument_id]||[]).map(function(item){return String(item.provider||'')+': '+String(item.probe_status||'UNKNOWN')+(item.error_code?' ('+String(item.error_code)+')':'');}).join(' · ')||'not probed';
    const historyChoice=candidates.length?'<label class="small muted">Provider <select data-market-history-provider="'+esc(row.instrument_id||'')+'">'+providerOptions+'</select></label> ':'<span class="small muted">No declared provider</span> ';
    return '<tr><td><code>'+esc(row.instrument_id||'')+'</code></td><td><b>'+esc(row.display_symbol||'')+'</b></td><td>'+esc(row.name||'')+'</td><td>'+esc(row.venue||'')+'</td><td>'+esc(listingText)+'</td><td>'+mappings+'</td><td>'+esc(probeText)+'</td><td>'+esc(hybridText)+'</td><td>'+esc(row.source_connection||'')+' · '+(row.pulse_enabled?'Pulse enabled':'disabled')+'</td><td>'+historyChoice+'<button type="button" class="secondary" data-market-history="'+esc(row.instrument_id||'')+'" '+(candidates.length?'':'disabled')+'>Fetch daily sample</button><div class="small muted" data-market-history-result="'+esc(row.instrument_id||'')+'">No request yet.</div></td></tr>';
  }).join('')+'</tbody></table>':'<p class="empty">No catalog rows.</p>';
  table.querySelectorAll('[data-market-history]').forEach(function(button){
    button.onclick=async function(){
      const instrumentId=String(button.getAttribute('data-market-history')||'');
      const output=table.querySelector('[data-market-history-result="'+CSS.escape(instrumentId)+'"]');
      if(!instrumentId||!output) return;
      const providerControl=table.querySelector('[data-market-history-provider="'+CSS.escape(instrumentId)+'"]');
      const provider=String(providerControl&&providerControl.value||'').toLowerCase();
      if(!providerCandidatesById[instrumentId]||providerCandidatesById[instrumentId].indexOf(provider)<0){output.textContent='History unavailable: select a provider declared for this instrument.';return;}
      button.disabled=true; output.textContent='Fetching a bounded daily page from '+provider+'…';
      const end=Math.floor(Date.now()/1000), start=end-90*86400;
      const query=new URLSearchParams({start_ts:String(start),end_ts:String(end),interval_seconds:'86400',limit:'20',provider:provider});
      const result=await marketDataFetch('/api/market-history/'+encodeURIComponent(instrumentId)+'?'+query.toString());
      button.disabled=false;
      if(!result.ok){output.textContent='History unavailable from '+provider+': '+String(result.error||'request failed');return;}
      const payload=result.data||{}, receipt=payload.receipt||{}, bars=Array.isArray(payload.bars)?payload.bars:[];
      const sample=bars.slice(-5).map(function(bar){return new Date(Number(bar.ts)*1000).toISOString().slice(0,10)+' close '+marketDataFmt(bar.c,4);}).join(' · ');
      output.textContent=String(payload.provider||provider)+' · '+String(payload.qualification||'UNQUALIFIED')+' · '+String(receipt.row_count||0)+' rows · mapping '+String(receipt.provider_mapping_status||'UNKNOWN')+' · symbol '+String(receipt.provider_symbol_match_status||'UNKNOWN')+' · identity '+String(receipt.identity_status||'UNKNOWN')+' · entitlement '+String(receipt.entitlement_status||'UNKNOWN')+' · session '+String(receipt.session_validation_status||'UNKNOWN')+(sample?' · '+sample:' · no bars')+(payload.page&&payload.page.next_start_ts?' · more history available':'');
    };
  });
}

async function loadMarketData(force=false){
  if(view!=='market-data') return;
  const assets=(typeof last!=='undefined'&&last&&Array.isArray(last.assets))?last.assets:[];
  if(!marketDataState.asset&&assets.length) marketDataState.asset=String(assets[0].symbol||'').toUpperCase();
  if(!marketDataState.asset) return;
  const requestAsset=marketDataState.asset, requestSchema=marketDataState.schema;
  const key=requestAsset+'|'+requestSchema;
  if(marketDataLoading){marketDataPendingLoad=true;marketDataForcePending=marketDataForcePending||force;return;}
  if(force){delete marketDataState.unavailable[key];delete marketDataState.results[key];}
  const known=marketDataState.unavailable[key]||{ticks:false,depth:false};
  if(!force&&known.ticks&&known.depth){
    const cached=marketDataState.results[key];
    if(cached&&view==='market-data') marketDataRender(cached[0],cached[1],cached[2],cached[3]);
    return;
  }
  marketDataLoading=true;
  marketDataPendingLoad=false;
  const busy=document.querySelector('#mdBusy');
  if(busy) busy.textContent='loading…';
  try{
    const base='/api/market-data/'+encodeURIComponent(requestAsset);
    const [capResult,healthResult]=await Promise.all([
      marketDataFetch(base+'/capabilities'),marketDataFetch('/healthz')
    ]);
    const caps=capResult.ok?(capResult.data?.capabilities||{}):{};
    const depthCapability=requestSchema==='mbo'?'mbo':'mbp_10';
    const ticksUnavailable=known.ticks||(capResult.ok&&caps.ticks===false);
    const depthUnavailable=known.depth||(capResult.ok&&caps[depthCapability]===false);
    const unavailable=(message)=>({ok:false,unavailable:true,error:message});
    const [tickResult,depthResult]=await Promise.all([
      ticksUnavailable?Promise.resolve(unavailable('Configured provider does not expose authentic trade ticks.')):
        marketDataFetch(base+'/ticks?limit=300'),
      depthUnavailable?Promise.resolve(unavailable('Configured provider does not expose '+requestSchema+' order-book events.')):
        marketDataFetch(base+'/depth?schema='+encodeURIComponent(requestSchema)+'&limit=200')
    ]);
    if(requestAsset!==marketDataState.asset||requestSchema!==marketDataState.schema){marketDataPendingLoad=true;return;}
    const nextUnavailable={
      ticks:ticksUnavailable||tickResult.status===409,
      depth:depthUnavailable||depthResult.status===409
    };
    if(nextUnavailable.ticks||nextUnavailable.depth) marketDataState.unavailable[key]=nextUnavailable;
    else delete marketDataState.unavailable[key];
    const results=[capResult,tickResult,depthResult,healthResult];
    marketDataState.results[key]=results;
    if(view==='market-data') marketDataRender(...results);
  }finally{
    marketDataLoading=false;
    const b=document.querySelector('#mdBusy');
    if(b) b.textContent='';
    if(marketDataPendingLoad&&view==='market-data'){
      marketDataPendingLoad=false;
      const retryForce=marketDataForcePending;marketDataForcePending=false;
      setTimeout(()=>loadMarketData(retryForce),0);
    }
  }
}

async function marketDataSnapshot(){
  const btn=document.querySelector('#mdSnapshot');
  const requestAsset=marketDataState.asset;
  if(btn) btn.disabled=true;
  marketDataState.snapshotError='';
  try{
    const snapshot=await marketDataAdminPost('/admin/market-data/mbo-snapshot',{asset:requestAsset,timeout:5.0});
    if(requestAsset!==marketDataState.asset) return;
    marketDataState.snapshot=snapshot;
  }catch(e){
    if(requestAsset!==marketDataState.asset) return;
    marketDataState.snapshot=null;
    marketDataState.snapshotError='MBO snapshot failed: '+String(e&&e.message||e)+'. If authentication is missing, set the engine token with the Token button.';
  }finally{
    if(btn&&btn.isConnected) btn.disabled=false;
    if(requestAsset===marketDataState.asset) marketDataRenderSnapshot();
  }
}

function wireMarketData(){
  const asset=document.querySelector('#mdAsset');
  if(asset) asset.onchange=function(){
    marketDataState.asset=String(asset.value||'').toUpperCase();
    marketDataState.snapshot=null; marketDataState.snapshotError='';
    loadMarketData(true);
  };
  const schema=document.querySelector('#mdSchema');
  if(schema) schema.onchange=function(){
    marketDataState.schema=String(schema.value||'mbp-10');
    loadMarketData(true);
  };
  const refresh=document.querySelector('#mdRefresh');
  if(refresh) refresh.onclick=function(){loadMarketData(true);loadMarketUniverse();};
  const snapshot=document.querySelector('#mdSnapshot');
  if(snapshot) snapshot.onclick=marketDataSnapshot;
  loadMarketUniverse();
  loadMarketData();
}

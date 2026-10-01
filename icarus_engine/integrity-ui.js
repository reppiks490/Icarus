/* ICARUS Export / Data Integrity panel. Read-only; MCP receipts are written by the authenticated engine API. */
let integrityLoading=false;

function integrityHtml(){
  return '<section class="card c12"><h2>Export / Data Integrity &amp; MCP <span class="sub">export checklist · corpus · repairs · fully-provenanced MCP receipts</span></h2>'+
    '<div id="integrityStatus" class="small muted">Loading integrity state…</div></section>'+
    '<section class="card c12"><h2>Export intake &amp; corpus</h2><div id="integrityCorpus" class="tiles"></div></section>'+
    '<section class="card c12"><h2>Export checklist</h2><div id="integrityChecklist" class="scroll"></div></section>'+
    '<section class="card c12"><h2>Repair / audit state</h2><div id="integrityRepairs" class="scroll"></div></section>'+
    '<section class="card c12"><h2>MCP change ledger <span class="sub">material MCP work must appear here with exact provenance</span></h2>'+
    '<div class="toolbar"><button id="integrityRefresh">Refresh</button><span class="small muted">Audit-only. These records never authorize execution or alter strategy/broker state.</span></div>'+
    '<div id="integrityEvents" class="scroll" style="max-height:620px"></div></section>';
}

function integrityChip(value){
  const s=String(value||'unknown'), low=s.toLowerCase();
  const cls=/blocked|failed|critical/.test(low)?'r':/pending|active|warning|waiv|branch_only|integrated_branch|reconcil/.test(low)?'w':/repair|verified|merged|satisf|observed/.test(low)?'b':'';
  return '<span class="chip '+cls+'">'+esc(s)+'</span>';
}

function integrityTable(rows,columns){
  if(!rows||!rows.length) return '<p class="empty">No records.</p>';
  const head=columns.map(function(c){return '<th>'+esc(c[0])+'</th>';}).join('');
  const body=rows.map(function(row){
    return '<tr>'+columns.map(function(c){const v=c[1](row);return '<td>'+(v==null?'—':v)+'</td>';}).join('')+'</tr>';
  }).join('');
  return '<table><thead><tr>'+head+'</tr></thead><tbody>'+body+'</tbody></table>';
}

function integrityCommitLink(row){
  const repo=String(row.source_repo||''), sha=String(row.source_commit||'');
  if(!/^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(repo)||!/^[0-9a-f]{40}$/i.test(sha))
    return esc(repo+' · '+sha);
  const href='https://github.com/'+repo+'/commit/'+sha;
  return '<a href="'+esc(href)+'" target="_blank" rel="noopener noreferrer"><code>'+esc(sha.slice(0,12))+'</code></a>';
}

async function integrityGet(path){
  const token=localStorage.getItem('icarus-engine-token')||'';
  const response=await fetch(path,{cache:'no-store',headers:{'Authorization':'Bearer '+token}});
  const data=await response.json().catch(function(){return {};});
  if(!response.ok) throw new Error(data.detail||data.error||('HTTP '+response.status));
  return data;
}

function integrityRender(data){
  const policy=data.policy||{}, intake=data.export_intake||{}, corpus=intake.historical_corpus||{}, n20=intake.nq_20m_pair||{};
  const status=document.querySelector('#integrityStatus');
  if(status){
    status.innerHTML='Mirror contract '+integrityChip(policy.mcp_mirror_required?'ENFORCED':'MISSING')+
      ' · execution '+integrityChip(data.execution_authorized===false?'DISABLED':'INVALID')+
      ' · runtime MCP receipts <b class="tnum">'+esc(data.runtime_event_count||0)+'</b>'+
      (data.journal_errors?' · <span class="neg">invalid journal rows '+esc(data.journal_errors)+'</span>':'')+
      (data.manifest_error?' · <span class="neg">manifest '+esc(data.manifest_error)+'</span>':'');
  }

  const corpusEl=document.querySelector('#integrityCorpus');
  if(corpusEl){
    const tiles=[
      ['Uploaded filenames',intake.observed_filenames],['Unique payloads',intake.unique_payloads],['Byte duplicates',intake.duplicate_payloads],
      ['NQ observed / unique',intake.nq_observed==null?'—':intake.nq_observed+' / '+intake.nq_unique],
      ['ES observed / unique',intake.es_observed==null?'—':intake.es_observed+' / '+intake.es_unique],
      ['NQ 20m aligned bars',n20.aligned_bars],['ZIP archives',corpus.zip_archives],['Physical files',corpus.physical_files],
      ['Usable CSV members',corpus.usable_csv_members],['Distinct contents',corpus.byte_distinct_contents],
      ['Corpus records',corpus.records==null?'—':Number(corpus.records).toLocaleString()]
    ];
    corpusEl.innerHTML=tiles.map(function(x){
      return '<div class="tile"><div class="k">'+esc(x[0])+'</div><div class="v tnum" style="font-size:17px">'+esc(x[1]==null?'—':x[1])+'</div></div>';
    }).join('');
  }

  const checklist=document.querySelector('#integrityChecklist');
  if(checklist) checklist.innerHTML=integrityTable(data.checklist||[],[
    ['Item',function(r){return '<b>'+esc(r.id||'')+'</b>'; }],
    ['Status',function(r){return integrityChip(r.status);}],
    ['Scope',function(r){return esc(r.title||'');}],
    ['Current evidence / remaining work',function(r){return '<span style="white-space:normal">'+esc(r.detail||'')+'</span>';}]
  ]);

  const repairs=document.querySelector('#integrityRepairs');
  if(repairs) repairs.innerHTML=integrityTable(data.repairs||[],[
    ['Area',function(r){return '<b>'+esc(r.id||r.area||'')+'</b>'; }],
    ['Status',function(r){return integrityChip(r.status);}],
    ['Change',function(r){return '<span style="white-space:normal">'+esc(r.summary||'')+'</span>'; }],
    ['Evidence / provenance',function(r){
      const evidence=Array.isArray(r.evidence)?r.evidence.join(' · '):String(r.evidence||'');
      const commits=Array.isArray(r.source_commits)?r.source_commits.join(', '):'';
      return '<span class="small muted" style="white-space:normal">'+esc(evidence+(commits?' · '+commits:''))+'</span>';
    }]
  ]);

  const eventsEl=document.querySelector('#integrityEvents');
  if(eventsEl){
    const events=(data.events||[]).slice().reverse();
    eventsEl.innerHTML=integrityTable(events,[
      ['Recorded',function(r){return esc(r.recorded_at||'—');}],
      ['Change',function(r){return integrityChip(r.kind)+' '+integrityChip(r.status)+'<br><b>'+esc(r.area||'')+'</b>'; }],
      ['Summary',function(r){return '<span style="white-space:normal">'+esc(r.summary||'')+'</span>'; }],
      ['Source',function(r){return '<span class="small">'+esc(r.source_repo||'')+'<br>'+esc(r.source_branch||'')+'<br>'+integrityCommitLink(r)+'</span>'; }],
      ['Verification / interface',function(r){
        const ev=Array.isArray(r.evidence)&&r.evidence.length?'<br><b>Evidence:</b> '+esc(r.evidence.join(' · ')):'';
        return '<span class="small" style="white-space:normal"><b>Verification:</b> '+esc(r.verification||'')+
          '<br><b>Interface:</b> '+esc(r.interface_effect||'')+ev+'<br><b>Execution:</b> <span class="neg">NO</span></span>';
      }]
    ]);
  }
}

async function loadIntegrity(){
  if(integrityLoading||view!=='integrity') return;
  integrityLoading=true;
  try{
    const data=await integrityGet('/api/integrity');
    if(view==='integrity') integrityRender(data);
  }catch(e){
    const el=document.querySelector('#integrityStatus');
    if(el) el.textContent='Integrity state unavailable: '+e.message;
  }finally{integrityLoading=false;}
}

function wireIntegrity(){
  const refresh=document.querySelector('#integrityRefresh');
  if(refresh) refresh.onclick=loadIntegrity;
  loadIntegrity();
}

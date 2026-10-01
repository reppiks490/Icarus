(function(){
  'use strict';
  let timer = null;
  const h = function(v){ return String(v == null ? '' : v).replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];}); };
  const pct = function(v){ return v == null || isNaN(v) ? '—' : (Number(v)*100).toFixed(1)+'%'; };
  const num = function(v,d){ return v == null || isNaN(v) ? '—' : Number(v).toFixed(d == null ? 3 : d); };
  const chip = function(v){
    const s=String(v||'').toUpperCase();
    const k=(s==='ACTIVE'||s==='GREEN'||s==='QUALIFIED')?'b':(s==='ERROR'||s==='FAILED'||s==='REJECTED')?'r':'w';
    return '<span class="chip '+k+'">'+h(s||'UNKNOWN')+'</span>';
  };

  function pantheonHtml(){
    return '<section class="card c12" id="pantheonPanel">'+
      '<h2>PANTHEON / AETHER <span class="sub">falsification · epistemics · constraints · monetization · bounded swarm · SHADOW ONLY</span></h2>'+
      '<div class="empty">loading PANTHEON research state…</div></section>';
  }

  function render(state){
    const el=document.querySelector('#pantheonPanel'); if(!el) return;
    const latest=state.latest;
    const catalog=state.engine_catalog||{};
    const engineRows=Object.entries(catalog).map(function(kv){
      return '<tr><td><b>'+h(kv[0])+'</b></td><td>'+h((kv[1]||{}).mode||'')+'</td><td class="small muted">'+h((kv[1]||{}).ownership||'independent faculty')+'</td></tr>';
    }).join('');
    if(!latest){
      el.innerHTML='<h2>PANTHEON / AETHER <span class="sub">SHADOW ONLY · execution_authorized=false</span></h2>'+
        '<div class="tiles"><div class="tile"><div class="k">Observations</div><div class="v tnum">'+h((state.counts||{}).observations||0)+'</div></div>'+
        '<div class="tile"><div class="k">Claims</div><div class="v tnum">'+h((state.counts||{}).claims||0)+'</div></div>'+
        '<div class="tile"><div class="k">Sentinel cells</div><div class="v tnum">'+h((state.counts||{}).sentinel_cells||0)+'</div></div>'+
        '<div class="tile"><div class="k">Authority</div><div class="v">NONE</div><div class="small muted">research/shadow only</div></div></div>'+
        '<div class="empty" style="margin-top:12px">No PANTHEON observations yet. The engine catalog is live, but every faculty abstains until evidence is explicitly ingested.</div>'+
        '<div class="scroll"><table><thead><tr><th>Faculty</th><th>Mode</th><th>Boundary</th></tr></thead><tbody>'+engineRows+'</tbody></table></div>';
      return;
    }
    const an=latest.analysis||{}, f=an.faculties||{}, ae=an.aether||{}, field=ae.field||{}, exportsState=an.exports||{};
    const sibylExports=Array.isArray(exportsState.sibyl_evidence)?exportsState.sibyl_evidence:[];
    const facultyRows=Object.entries(f).map(function(kv){
      const row=kv[1]||{};
      let key='—';
      if(kv[0]==='nullspace') key='debt '+num(row.causal_debt,3)+' · pressure '+pct(row.repayment_pressure);
      else if(kv[0]==='godel') key='ident '+pct(row.identifiability)+' · worlds '+num(row.effective_world_count,2)+(row.epistemic_blindspot?' · BLINDSPOT':'');
      else if(kv[0]==='ananke') key='asym '+num(row.asymmetry,3)+' · collapse '+pct(row.reachable_space_collapse);
      else if(kv[0]==='nemesis') key='survival '+pct(row.survival_score)+(row.edge_half_life_seconds!=null?' · half-life '+num(row.edge_half_life_seconds,1)+'s':' · half-life unmeasured');
      else if(kv[0]==='ex_nihilo') key='surprise '+pct(row.ontology_surprise);
      else if(kv[0]==='archon') key='conflict '+pct(row.contradiction);
      else if(kv[0]==='socrates') key='priority '+pct(row.question_priority)+' · '+h((row.question_queue||[]).length)+' queued';
      else if(kv[0]==='mint') key=row.best_candidate?('best '+h(row.best_candidate.name)+' · stress net '+num(row.best_candidate.stress_expected_net,2)):'no positive candidate';
      return '<tr><td><b>'+h(String(kv[0]).toUpperCase())+'</b></td><td>'+chip(row.status||'active')+'</td><td>'+key+'</td><td class="small muted">'+h(row.reason||row.semantics||'')+'</td></tr>';
    }).join('');
    const agents=(ae.agents||[]).map(function(a){
      return '<tr><td class="tnum">'+h(a.agent_id||'')+'</td><td><b>'+h(a.role||'')+'</b></td><td>'+h(a.claim_scope||'')+'</td><td class="tnum">'+h(a.ttl_seconds||0)+'s</td><td><span class="chip">NO CAPITAL AUTHORITY</span></td></tr>';
    }).join('');
    const claims=(latest.claims||[]).map(function(c){
      return '<tr><td class="tnum">'+h(c.claim_id||'')+'</td><td>'+h(c.kind||'')+'</td><td>'+chip(c.stage||'')+'</td><td class="small muted">'+h(JSON.stringify(c.payload||{}))+'</td></tr>';
    }).join('');
    el.innerHTML='<style>.pan-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px}.pan-field{border:1px solid var(--ring);border-radius:12px;padding:10px;background:var(--surface-2)}</style>'+
      '<h2>PANTHEON / AETHER <span class="sub">distributed research ecology · execution_authorized=false</span></h2>'+
      '<div class="tiles" style="margin-top:0">'+
        '<div class="tile"><div class="k">Asset / horizon</div><div class="v">'+h(latest.asset)+' · '+h(latest.horizon_ms)+'ms</div></div>'+
        '<div class="tile"><div class="k">AETHER</div><div class="v">'+chip(ae.status)+'</div><div class="small muted">'+h(ae.cognitive_mass||0)+' ephemeral agents</div></div>'+
        '<div class="tile"><div class="k">Field energy</div><div class="v tnum">'+pct(field.energy)+'</div></div>'+
        '<div class="tile"><div class="k">Data quality</div><div class="v tnum">'+pct(field.data_quality)+'</div></div>'+
        '<div class="tile"><div class="k">Contradiction</div><div class="v tnum">'+pct(field.contradiction)+'</div></div>'+
        '<div class="tile"><div class="k">Sentinel cells</div><div class="v tnum">'+h((state.counts||{}).sentinel_cells||0)+'</div></div>'+
        '<div class="tile"><div class="k">SIBYL exports</div><div class="v tnum">'+h(sibylExports.length)+'</div><div class="small muted">confidence-gated structural evidence only</div></div>'+
        '<div class="tile"><div class="k">Authority</div><div class="v">SHADOW ONLY</div></div>'+
      '</div>'+
      '<div class="pan-grid" style="margin-top:12px">'+
        '<div class="pan-field"><div class="k">Profit field</div><b>'+pct(field.profit)+'</b></div>'+
        '<div class="pan-field"><div class="k">Causal debt</div><b>'+pct(field.causal_debt)+'</b></div>'+
        '<div class="pan-field"><div class="k">Novelty</div><b>'+pct(field.novelty)+'</b></div>'+
        '<div class="pan-field"><div class="k">Uncertainty</div><b>'+pct(field.uncertainty)+'</b></div>'+
        '<div class="pan-field"><div class="k">Risk</div><b>'+pct(field.risk)+'</b></div>'+
      '</div>'+
      '<h3 class="small" style="margin:16px 0 8px">Independent faculties — disagreement preserved</h3>'+
      '<div class="scroll"><table><thead><tr><th>Faculty</th><th>Status</th><th>Key state</th><th>Semantics</th></tr></thead><tbody>'+facultyRows+'</tbody></table></div>'+
      '<div class="small muted" style="margin-top:10px">Diversity lock: blind first pass · peer conclusions hidden until commitment · forced consensus disabled.</div>'+
      '<h3 class="small" style="margin:16px 0 8px">SOCRATES research queue</h3>'+
      '<div class="scroll"><table><thead><tr><th>Priority</th><th>Question</th></tr></thead><tbody>'+
      (((f.socrates||{}).question_queue||[]).map(function(q){return '<tr><td class="tnum">'+pct(q.priority)+'</td><td>'+h(q.question||'')+'</td></tr>';}).join('')||'<tr><td colspan="2" class="empty">No research question cleared the current priority floor.</td></tr>')+
      '</tbody></table></div>'+
      '<h3 class="small" style="margin:16px 0 8px">SIBYL structural evidence bridge</h3>'+
      '<div class="scroll"><table><thead><tr><th>Domain</th><th>Direction</th><th>Magnitude</th><th>Confidence</th><th>Horizon</th></tr></thead><tbody>'+
      (sibylExports.map(function(x){return '<tr><td>'+h(x.domain||'')+'</td><td class="tnum">'+num(x.direction,3)+'</td><td class="tnum">'+num(x.magnitude,3)+'</td><td class="tnum">'+pct(x.confidence)+'</td><td class="tnum">'+h(x.horizon_seconds||0)+'s</td></tr>';}).join('')||'<tr><td colspan="5" class="empty">No structurally directional evidence cleared GÖDEL/NEMESIS/data-quality gating.</td></tr>')+
      '</tbody></table></div>'+
      '<h3 class="small" style="margin:16px 0 8px">AETHER ephemeral swarm</h3>'+
      '<div class="scroll"><table><thead><tr><th>Agent</th><th>Role</th><th>Scope</th><th>TTL</th><th>Authority</th></tr></thead><tbody>'+(agents||'<tr><td colspan="5" class="empty">Field below activation threshold; no expensive swarm spawned.</td></tr>')+'</tbody></table></div>'+
      '<h3 class="small" style="margin:16px 0 8px">Durable claims</h3>'+
      '<div class="scroll"><table><thead><tr><th>Claim</th><th>Kind</th><th>Stage</th><th>Payload</th></tr></thead><tbody>'+(claims||'<tr><td colspan="4" class="empty">No durable claim survived the current observation.</td></tr>')+'</tbody></table></div>'+
      '<div class="small muted" style="margin-top:12px">AETHER agents are disposable research workers. Claims are durable; orders are not. PANTHEON cannot place orders, change sizing, bypass the hard Risk Kernel, or promote itself to production.</div>';
  }

  async function loadPantheon(){
    const el=document.querySelector('#pantheonPanel'); if(!el) return;
    try{
      const tok=localStorage.getItem('icarus-engine-token')||'icarus';
      const r=await fetch('/api/pantheon',{cache:'no-store',headers:{'Authorization':'Bearer '+tok}});
      const state=await r.json();
      if(!r.ok) throw new Error(state.detail||('HTTP '+r.status));
      render(state);
    }catch(err){
      el.innerHTML='<h2>PANTHEON / AETHER</h2><div class="empty">research fabric unavailable: '+h(err.message||err)+'</div>';
    }
  }

  function wirePantheon(){
    loadPantheon();
    if(timer) clearInterval(timer);
    timer=setInterval(function(){
      if((location.hash||'#overview').slice(1)==='pantheon') loadPantheon();
    },5000);
  }

  window.pantheonHtml=pantheonHtml;
  window.wirePantheon=wirePantheon;
  window.loadPantheon=loadPantheon;
})();
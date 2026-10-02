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
    const an=latest.analysis||{}, f=an.faculties||{}, ae=an.aether||{}, field=ae.field||{}, exportsState=an.exports||{}, eco=state.ecology||{};
    const sibylExports=Array.isArray(exportsState.sibyl_evidence)?exportsState.sibyl_evidence:[];
    const alphaWeb=Array.isArray(eco.alpha_food_web)?eco.alpha_food_web:[];
    const interactions=Array.isArray(eco.interactions)?eco.interactions:[];
    const genesis=Array.isArray(eco.cognitive_genesis_candidates)?eco.cognitive_genesis_candidates:[];
    const facultyRows=Object.entries(f).map(function(kv){
      const row=kv[1]||{};
      let key='—';
      if(kv[0]==='nullspace') key='debt '+num(row.causal_debt,3)+' · '+h(row.debt_state||'open')+' · pressure '+pct(row.repayment_pressure);
      else if(kv[0]==='godel') key='ident '+pct(row.identifiability)+' · worlds '+num(row.effective_world_count,2)+(row.epistemic_blindspot?' · BLINDSPOT':'');
      else if(kv[0]==='ananke') key='asym '+num(row.asymmetry,3)+' · collapse '+pct(row.reachable_space_collapse);
      else if(kv[0]==='nemesis') key='survival '+pct(row.survival_score)+(row.edge_half_life_seconds!=null?' · half-life '+num(row.edge_half_life_seconds,1)+'s':' · half-life unmeasured');
      else if(kv[0]==='ex_nihilo') key='surprise '+pct(row.ontology_surprise);
      else if(kv[0]==='echo') key=(row.lineage_verified===false?'lineage UNVERIFIED · ':'')+'echo risk '+pct(row.echo_risk)+' · independent support '+pct(row.effective_independent_support)+(row.consensus_illusion_candidate?' · ILLUSION CANDIDATE':'');
      else if(kv[0]==='veritas') key=row.status==='active'?('certificate '+h(row.mechanism_id||'')+' · '+h(row.direction||'unknown')+' · reconciliation PENDING'):'no mechanism certificate';
      else if(kv[0]==='lethe') key='trust '+pct(row.effective_memory_trust)+' · stale '+pct(row.stale_memory_pressure)+' · resurrect '+pct(row.resurrection_pressure);
      else if(kv[0]==='atlas') key='geometry '+h(row.geometry_state||'')+' · boundary '+pct(row.boundary_pressure)+' · novelty '+pct(row.topological_novelty)+(row.current_basin?(' · basin '+h(row.current_basin.regime||'')):'');
      else if(kv[0]==='aporia') key='wait '+h(row.action||'unavailable')+' · value '+pct(row.information_value_pressure)+(row.best_observation?(' · '+h(row.best_observation.observation)+' '+num(row.best_observation.net_information_value,2)):'');
      else if(kv[0]==='axiom') key='certificate '+h(row.certificate_state||'')+' · complete '+pct(row.proof_completeness)+' · blockers '+h([].concat(row.failed_gates||[],row.unproven_gates||[]).join(', ')||'none');
      else if(kv[0]==='autognosis') key='self-failure '+pct(row.self_failure_pressure)+' · trust '+pct(row.self_trust_surface)+' · '+h(row.research_posture||'unavailable')+(row.dominant_failure_mode?(' · '+h(row.dominant_failure_mode)):'');
      else if(kv[0]==='archon') key='conflict '+pct(row.contradiction)+' · echo '+pct(row.echo_risk);
      else if(kv[0]==='socrates') key='priority '+pct(row.question_priority)+' · '+h((row.question_queue||[]).length)+' questions · '+h((row.hypothesis_queue||[]).length)+' hypotheses';
      else if(kv[0]==='mint') key=row.best_candidate?('best '+h(row.best_candidate.name)+' · stress net '+num(row.best_candidate.stress_expected_net,2)):'no positive candidate';
      return '<tr><td><b>'+h(String(kv[0]).toUpperCase())+'</b></td><td>'+chip(row.status||'active')+'</td><td>'+key+'</td><td class="small muted">'+h(row.reason||row.semantics||'')+'</td></tr>';
    }).join('');
    const agents=(ae.agents||[]).map(function(a){
      return '<tr><td class="tnum">'+h(a.agent_id||'')+'</td><td><b>'+h(a.role||'')+'</b></td><td>'+h(a.claim_scope||'')+'</td><td class="tnum">'+h(a.ttl_seconds||0)+'s</td><td><span class="chip">NO CAPITAL AUTHORITY</span></td></tr>';
    }).join('');
    const claims=(latest.claims||[]).map(function(c){
      return '<tr><td class="tnum">'+h(c.claim_id||'')+'</td><td>'+h(c.kind||'')+'</td><td>'+chip(c.stage||'')+'</td><td class="small muted">'+h(JSON.stringify(c.payload||{}))+'</td></tr>';
    }).join('');
    const agentClaims=(latest.agent_claims||[]).map(function(c){
      const q=c.claim||{};
      return '<tr><td><b>'+h(c.role||'')+'</b><div class="small muted tnum">'+h(c.agent_id||'')+'</div></td><td>'+h(q.direction||'unknown')+'</td><td class="tnum">'+pct(q.confidence)+'</td><td>'+h(q.thesis||'')+'</td><td class="small muted">'+h(q.falsifier||'')+'</td></tr>';
    }).join('');
    const deliberation=latest.deliberation||{};
    const veritasState=latest.veritas_reconciliation||{};
    const veritasPayload=veritasState.reconciliation||{};
    const veritasScore=veritasPayload.score||{};
    const veritasFaculty=f.veritas||{};
    el.innerHTML='<style>.pan-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px}.pan-field{border:1px solid var(--ring);border-radius:12px;padding:10px;background:var(--surface-2)}</style>'+
      '<h2>PANTHEON / AETHER <span class="sub">distributed research ecology · execution_authorized=false</span></h2>'+
      '<div class="tiles" style="margin-top:0">'+
        '<div class="tile"><div class="k">Asset / horizon</div><div class="v">'+h(latest.asset)+' · '+h(latest.horizon_ms)+'ms</div></div>'+
        '<div class="tile"><div class="k">AETHER</div><div class="v">'+chip(ae.status)+'</div><div class="small muted">'+h(ae.cognitive_mass||0)+' ephemeral agents</div></div>'+
        '<div class="tile"><div class="k">Field energy</div><div class="v tnum">'+pct(field.energy)+'</div></div>'+
        '<div class="tile"><div class="k">Data quality</div><div class="v tnum">'+pct(field.data_quality)+'</div></div>'+
        '<div class="tile"><div class="k">Contradiction</div><div class="v tnum">'+pct(field.contradiction)+'</div></div>'+
        '<div class="tile"><div class="k">Sentinel cells</div><div class="v tnum">'+h((state.counts||{}).sentinel_cells||0)+'</div></div>'+
        '<div class="tile"><div class="k">SIBYL exports</div><div class="v tnum">'+h(sibylExports.length)+'</div><div class="small muted">gated structural evidence only</div></div>'+
        '<div class="tile"><div class="k">Species</div><div class="v tnum">'+h(eco.species_count||0)+'</div><div class="small muted">'+h(eco.claim_outcome_count||0)+' observed outcomes</div></div>'+
        '<div class="tile"><div class="k">VERITAS</div><div class="v">'+h(veritasState.status==='reconciled'?(veritasScore.classification||'reconciled'):(veritasFaculty.status==='active'?'PENDING':'ABSTAIN'))+'</div><div class="small muted">'+(veritasState.status==='reconciled'?('fidelity '+pct(veritasScore.mechanism_fidelity)):'right reasons audit')+'</div></div>'+
        '<div class="tile"><div class="k">Extinct</div><div class="v tnum">'+h((eco.extinct_species||[]).length)+'</div></div>'+
        '<div class="tile"><div class="k">Authority</div><div class="v">SHADOW ONLY</div></div>'+
      '</div>'+
      '<div class="pan-grid" style="margin-top:12px">'+
        '<div class="pan-field"><div class="k">Profit field</div><b>'+pct(field.profit)+'</b></div>'+
        '<div class="pan-field"><div class="k">Causal debt</div><b>'+pct(field.causal_debt)+'</b></div>'+
        '<div class="pan-field"><div class="k">Novelty</div><b>'+pct(field.novelty)+'</b></div>'+
        '<div class="pan-field"><div class="k">Uncertainty</div><b>'+pct(field.uncertainty)+'</b></div>'+
        '<div class="pan-field"><div class="k">Echo risk</div><b>'+pct(field.echo_risk)+'</b></div>'+
        '<div class="pan-field"><div class="k">Memory staleness</div><b>'+pct(field.stale_memory_pressure)+'</b></div>'+
        '<div class="pan-field"><div class="k">Resurrection pressure</div><b>'+pct(field.resurrection_pressure)+'</b></div>'+
        '<div class="pan-field"><div class="k">Proof gap</div><b>'+pct(field.proof_gap)+'</b></div>'+
        '<div class="pan-field"><div class="k">Value of waiting</div><b>'+pct(field.information_value_pressure)+'</b><div class="small muted">'+h(field.value_of_waiting_action||'unavailable')+'</div></div>'+
        '<div class="pan-field"><div class="k">Topology pressure</div><b>'+pct(field.topology_pressure)+'</b></div>'+
        '<div class="pan-field"><div class="k">Self-failure pressure</div><b>'+pct(field.self_failure_pressure)+'</b><div class="small muted">'+h(field.self_model_posture||'unavailable')+'</div></div>'+
        '<div class="pan-field"><div class="k">APEX lineage</div><b>'+h(apexLineage.status||'UNAVAILABLE')+'</b><div class="small muted">'+h(apexLineage.lineage_owner||'no verified root map')+'</div></div>'+
        '<div class="pan-field"><div class="k">Risk</div><b>'+pct(field.risk)+'</b></div>'+
      '</div>'+
      '<h3 class="small" style="margin:16px 0 8px">Independent faculties — disagreement preserved</h3>'+
      '<div class="scroll"><table><thead><tr><th>Faculty</th><th>Status</th><th>Key state</th><th>Semantics</th></tr></thead><tbody>'+facultyRows+'</tbody></table></div>'+
      '<div class="small muted" style="margin-top:10px">Diversity lock: blind first pass · peer conclusions hidden until commitment · forced consensus disabled.</div>'+
      '<h3 class="small" style="margin:16px 0 8px">VERITAS right-for-right-reasons audit</h3>'+
      '<div class="scroll"><table><thead><tr><th>Mechanism</th><th>Predicted</th><th>Realized</th><th>Fidelity</th><th>Classification</th><th>Reinforcement</th></tr></thead><tbody>'+
      (veritasFaculty.status==='active'
        ? '<tr><td>'+h(veritasFaculty.mechanism_id||'')+'</td><td>'+h(veritasFaculty.direction||'unknown')+'</td><td>'+h(veritasScore.realized_direction||'pending')+'</td><td class="tnum">'+(veritasState.status==='reconciled'?pct(veritasScore.mechanism_fidelity):'—')+'</td><td>'+h(veritasScore.classification||'pending')+'</td><td>'+chip(veritasScore.reinforcement_eligible?'ELIGIBLE':'QUARANTINED / PENDING')+'</td></tr>'
        : '<tr><td colspan="6" class="empty">No immutable mechanism certificate on the latest observation.</td></tr>')+
      '</tbody></table></div>'+
      '<div class="small muted" style="margin-top:8px">Directional success alone is not learning credit. A correct endpoint with failed mechanism signatures is quarantined as right-for-wrong-reasons.</div>'+
      '<h3 class="small" style="margin:16px 0 8px">SOCRATES research queue</h3>'+
      '<div class="scroll"><table><thead><tr><th>Priority</th><th>Question</th><th>Hypothesis / falsifier</th></tr></thead><tbody>'+
      (((f.socrates||{}).question_queue||[]).map(function(q,i){const hyp=((f.socrates||{}).hypothesis_queue||[])[i]||{};return '<tr><td class="tnum">'+pct(q.priority)+'</td><td>'+h(q.question||'')+'</td><td class="small">'+h(hyp.hypothesis||'')+'<div class="muted">'+h(hyp.falsifier||'')+'</div></td></tr>';}).join('')||'<tr><td colspan="3" class="empty">No research question cleared the current priority floor.</td></tr>')+
      '</tbody></table></div>'+
      '<h3 class="small" style="margin:16px 0 8px">SIBYL structural evidence bridge</h3>'+
      '<div class="scroll"><table><thead><tr><th>Domain</th><th>Direction</th><th>Magnitude</th><th>Confidence</th><th>Horizon</th></tr></thead><tbody>'+
      (sibylExports.map(function(x){return '<tr><td>'+h(x.domain||'')+'</td><td class="tnum">'+num(x.direction,3)+'</td><td class="tnum">'+num(x.magnitude,3)+'</td><td class="tnum">'+pct(x.confidence)+'</td><td class="tnum">'+h(x.horizon_seconds||0)+'s</td></tr>';}).join('')||'<tr><td colspan="5" class="empty">No structural evidence cleared GÖDEL / NEMESIS / data-quality gating.</td></tr>')+
      '</tbody></table></div>'+
      '<h3 class="small" style="margin:16px 0 8px">AETHER ephemeral swarm</h3>'+
      '<div class="scroll"><table><thead><tr><th>Agent</th><th>Role</th><th>Scope</th><th>TTL</th><th>Authority</th></tr></thead><tbody>'+(agents||'<tr><td colspan="5" class="empty">Field below activation threshold; no expensive swarm spawned.</td></tr>')+'</tbody></table></div>'+
      '<h3 class="small" style="margin:16px 0 8px">AETHER blind first-pass claims</h3>'+
      '<div class="small muted" style="margin-bottom:8px">submitted '+h(deliberation.submitted_claims||0)+' · ready '+h(deliberation.ready_for_deliberation?'YES':'NO')+' · disagreement '+pct(deliberation.disagreement_index)+' · claim-evidence echo '+pct(deliberation.claim_evidence_echo_risk)+' · effective agents '+num(deliberation.effective_independent_agent_count,2)+'/'+h(deliberation.expected_agent_claims||0)+(deliberation.claim_consensus_illusion_candidate?' · CONSENSUS ILLUSION CANDIDATE':'')+' · forced consensus OFF</div>'+
      '<div class="scroll"><table><thead><tr><th>Independent role</th><th>Direction</th><th>Confidence</th><th>Thesis</th><th>Falsifier</th></tr></thead><tbody>'+(agentClaims||'<tr><td colspan="5" class="empty">No independent AETHER claims committed yet.</td></tr>')+'</tbody></table></div>'+
      '<h3 class="small" style="margin:16px 0 8px">AETHER alpha food web</h3>'+
      '<div class="scroll"><table><thead><tr><th>Species</th><th>Kind</th><th>Stage</th><th>Fitness</th><th>Evidence</th><th>Alpha mass</th></tr></thead><tbody>'+
      (alphaWeb.map(function(x){return '<tr><td class="tnum">'+h(x.species_id||'')+'</td><td>'+h(x.kind||'')+'</td><td>'+chip(x.stage||'')+'</td><td class="tnum">'+num(x.fitness_credit,3)+'</td><td class="tnum">'+h(x.evidence_count||0)+'</td><td class="tnum">'+num(x.alpha_mass,3)+'</td></tr>';}).join('')||'<tr><td colspan="6" class="empty">No species has accumulated positive observed shadow fitness yet.</td></tr>')+
      '</tbody></table></div>'+
      '<h3 class="small" style="margin:16px 0 8px">Ecology interactions</h3>'+
      '<div class="scroll"><table><thead><tr><th>Type</th><th>Participants</th><th>Basis</th></tr></thead><tbody>'+
      (interactions.map(function(x){const who=x.type==='predation'?((x.predator||'')+' → '+(x.prey||'')):x.type==='parasitic_drag'?((x.parasite||'')+' ⇢ '+(x.host||'')):((x.species||[]).join(' + '));return '<tr><td>'+chip(x.type||'')+'</td><td class="tnum">'+h(who)+'</td><td class="small muted">'+h(x.basis||'')+'</td></tr>';}).join('')||'<tr><td colspan="3" class="empty">No predation, symbiosis, or parasitic-drag relationship has enough observed fitness yet.</td></tr>')+
      '</tbody></table></div>'+
      '<h3 class="small" style="margin:16px 0 8px">Cognitive genesis</h3>'+
      '<div class="scroll"><table><thead><tr><th>Species</th><th>Asset</th><th>Reason</th><th>Next action</th></tr></thead><tbody>'+
      (genesis.map(function(x){return '<tr><td class="tnum">'+h(x.species_id||'')+'</td><td>'+h(x.asset||'')+'</td><td class="small">'+h(x.reason||'')+'</td><td class="small muted">'+h(x.recommended_action||'')+'</td></tr>';}).join('')||'<tr><td colspan="4" class="empty">No ontology species has survived enough observed outcomes to justify a missing-engine study.</td></tr>')+
      '</tbody></table></div>'+
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
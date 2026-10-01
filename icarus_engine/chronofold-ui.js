(function(){
  'use strict';
  let loading=false, timer=null, selected='';
  const h=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
  const n=(v,d=3)=>v==null||!Number.isFinite(Number(v))?'—':Number(v).toFixed(d);
  const pct=v=>v==null||!Number.isFinite(Number(v))?'—':(Number(v)*100).toFixed(1)+'%';
  const chip=s=>'<span class="chip">'+h(s)+'</span>';

  function chronofoldHtml(A){
    const opts=(A||[]).map(a=>'<option value="'+h(a.symbol)+'">'+h(a.continuous_symbol||a.symbol)+'</option>').join('');
    return '<section class="card c12" id="chronofoldPanel"><h2>ICARUS Ξ · CHRONOFOLD <span class="sub">causal navigation research plane</span></h2>'+
      '<div class="toolbar"><label class="small">Asset <select id="cfAsset">'+opts+'</select></label><button id="cfRefresh">Refresh</button><span class="small muted">research/shadow only · no broker authority</span></div>'+
      '<div class="empty" style="margin-top:12px">initializing Chronofold causal spacetime…</div></section>';
  }

  function tiles(rows){return '<div class="tiles">'+rows.map(x=>'<div class="tile"><div class="k">'+h(x[0])+'</div><div class="v">'+h(x[1])+'</div>'+(x[2]?'<div class="small muted">'+h(x[2])+'</div>':'')+'</div>').join('')+'</div>';}
  function renderChronofold(data){
    const el=document.querySelector('#chronofoldPanel'); if(!el)return;
    const ch=data.chronon||{}, mt=data.multitime||{}, g=data.geometry||{}, cone=data.causal_cone||{}, den=data.density_state||{}, ph=data.phase_transition||{}, mv=data.multiverse||{}, frac=data.reality_fracture||{}, gnc=data.gnc||{}, laws=data.symbolic_physics||{};
    const probs=den.probabilities||{}, clusters=mv.cluster_weights||{};
    const leaders=(cone.leaders||[]).slice(0,8).map((x,i)=>'<tr><td>'+(i+1)+'</td><td><b>'+h(x.asset)+'</b></td><td class="tnum">'+n(x.lagged_association,4)+'</td><td>'+h(x.direction)+'</td><td class="tnum">'+h(x.samples)+'</td></tr>').join('');
    const shadows=(data.counterfactual_shadows||[]).map(x=>'<tr><td>'+h(x.removed_force)+'</td><td class="tnum">'+pct(x.estimated_contribution)+'</td><td class="tnum">'+pct(x.shadow_expected_return)+'</td><td>diagnostic only</td></tr>').join('');
    const scales=((data.renormalization||{}).scales||[]).map(x=>'<tr><td>'+h(x.block)+' χ</td><td class="tnum">'+n(x.mean,7)+'</td><td class="tnum">'+n(x.volatility,7)+'</td></tr>').join('');
    const theories=(laws.theory_population||[]).map((x,i)=>'<tr><td>'+(i+1)+'</td><td>'+h((x.terms||[]).join(' + '))+'</td><td class="tnum">'+n(x.fitness,6)+'</td><td class="tnum">'+n(x.mse,6)+'</td></tr>').join('');
    el.innerHTML='<h2>ICARUS Ξ · CHRONOFOLD <span class="sub">'+h(data.asset||'—')+' · '+h(data.schema_version||'')+'</span></h2>'+
      '<div class="toolbar"><label class="small">Asset <select id="cfAsset"></select></label><button id="cfRefresh">Refresh</button>'+chip((data.time_boundary||{}).causal_integrity||'UNKNOWN')+'<span class="small muted">physics = mathematical analogue · no future leakage · no execution authority</span></div>'+
      tiles([
        ['Market proper time',n(ch.market_proper_time,3)+' χ','informational time, not wall clock'],
        ['Chronon activity',pct((ch.activity||{}).activity),'surprise + volatility + causal/event change'],
        ['Temporal shear',n(mt.temporal_shear,3),'desynchronization across internal clocks'],
        ['State curvature',n(g.curvature,4),'trajectory bending on learned state manifold'],
        ['Regime entropy',pct(den.normalized_entropy),'uncertainty across incompatible hypotheses'],
        ['Phase state',ph.state||'—','order '+n(ph.order_parameter,3)+' · Δ '+n(ph.transition_velocity,4)],
        ['Reality fracture',frac.reality_fracture?'ACTIVE':'clear',frac.distance_sigma==null?'warming':'distance '+n(frac.distance_sigma,2)+'σ'],
        ['Unknown mass',pct(data.epistemic_unknown_mass),'explicit epistemic uncertainty'],
        ['GNC guidance',gnc.guidance||'NO_EDGE','confidence '+pct(gnc.confidence)+' · '+(gnc.control||'SHADOW_ONLY')]
      ])+
      '<div class="tiles" style="margin-top:12px">'+
        '<div class="tile"><div class="k">Density state</div><div class="v">UP '+pct(probs.UP)+' · FLAT '+pct(probs.FLAT)+' · DOWN '+pct(probs.DOWN)+'</div><div class="small muted">quantum-inspired representation; no quantum-market claim</div></div>'+
        '<div class="tile"><div class="k">Reachable multiverse</div><div class="v">UP '+pct(clusters.UP)+' · FLAT '+pct(clusters.FLAT)+' · DOWN '+pct(clusters.DOWN)+'</div><div class="small muted">'+h(mv.scenarios||0)+' paths · '+h(mv.horizon_chronons||0)+' χ horizon · not calibrated probabilities</div></div>'+
        '<div class="tile"><div class="k">Koopman mode</div><div class="v">'+h((data.koopman||{}).mode||'WARMING')+'</div><div class="small muted">λ '+n((data.koopman||{}).eigenvalue,5)+'</div></div>'+
        '<div class="tile"><div class="k">Scale stability</div><div class="v">'+pct((data.renormalization||{}).scale_stability)+'</div><div class="small muted">structure surviving coarse-graining</div></div>'+
      '</div>'+
      '<section class="card c12" style="margin-top:12px"><h2>Causal cone <span class="sub">lagged association, not structural causality</span></h2><div class="scroll"><table><thead><tr><th>#</th><th>Leader</th><th>lag-1</th><th>relation</th><th>N</th></tr></thead><tbody>'+(leaders||'<tr><td colspan="5" class="empty">causal graph warming</td></tr>')+'</tbody></table></div></section>'+
      '<section class="card c12" style="margin-top:12px"><h2>Counterfactual shadow market</h2><div class="scroll"><table><thead><tr><th>Removed force</th><th>estimated contribution</th><th>shadow return</th><th>claim</th></tr></thead><tbody>'+(shadows||'<tr><td colspan="4" class="empty">shadow market warming</td></tr>')+'</tbody></table></div></section>'+
      '<div class="grid" style="margin-top:12px"><section class="card c6"><h2>Renormalization flow</h2><div class="scroll"><table><thead><tr><th>scale</th><th>mean</th><th>volatility</th></tr></thead><tbody>'+(scales||'<tr><td colspan="3" class="empty">warming</td></tr>')+'</tbody></table></div></section>'+
      '<section class="card c6"><h2>Darwinian law population</h2><div class="scroll"><table><thead><tr><th>#</th><th>terms</th><th>fitness</th><th>MSE</th></tr></thead><tbody>'+(theories||'<tr><td colspan="4" class="empty">symbolic law discovery warming</td></tr>')+'</tbody></table></div></section></div>'+
      '<section class="card c12" style="margin-top:12px"><h2>Truth contract</h2><div class="small muted">Chronofold uses physics, quantum and spacecraft concepts as mathematical machinery only. It does not claim literal market gravity, quantum causation, time travel, structural causal proof, calibrated scenario probabilities, future knowledge, broker authority, or production decision authority.</div></section>';
    const sel=el.querySelector('#cfAsset');
    const assets=(window.last&&window.last.assets)||[];
    sel.innerHTML=assets.map(a=>'<option value="'+h(a.symbol)+'" '+(a.symbol===data.asset?'selected':'')+'>'+h(a.continuous_symbol||a.symbol)+'</option>').join('');
    selected=data.asset||selected; sel.onchange=()=>{selected=sel.value;loadChronofold();}; el.querySelector('#cfRefresh').onclick=loadChronofold;
  }

  async function loadChronofold(){
    if(loading)return; const panel=document.querySelector('#chronofoldPanel'); if(!panel)return; loading=true;
    try{ const token=localStorage.getItem('icarus-engine-token')||'icarus'; const q=selected?'?asset='+encodeURIComponent(selected):''; const r=await fetch('/api/chronofold'+q,{cache:'no-store',headers:{'Authorization':'Bearer '+token}}); const d=await r.json(); if(!r.ok)throw new Error(d.detail||d.error||('HTTP '+r.status)); renderChronofold(d); }
    catch(err){ panel.innerHTML='<h2>ICARUS Ξ · CHRONOFOLD</h2><div class="empty">Chronofold unavailable: '+h(err.message||err)+'</div>'; }
    finally{loading=false;}
  }
  function wireChronofold(){ const sel=document.querySelector('#cfAsset'); if(sel){selected=sel.value||selected;sel.onchange=()=>{selected=sel.value;loadChronofold();};} const btn=document.querySelector('#cfRefresh');if(btn)btn.onclick=loadChronofold;loadChronofold();if(timer)clearInterval(timer);timer=setInterval(()=>{if((location.hash||'#overview').slice(1)==='chronofold')loadChronofold();},2500);}
  window.chronofoldHtml=chronofoldHtml; window.wireChronofold=wireChronofold; window.loadChronofold=loadChronofold;
})();

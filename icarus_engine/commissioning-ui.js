(function(){
  'use strict';
  let loading=false, pendingLoad=false, timer=null, selected='', assetsCache=[];
  const h=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
  const n=(v,d=3)=>v==null||!Number.isFinite(Number(v))?'—':Number(v).toFixed(d);
  const pct=v=>v==null||!Number.isFinite(Number(v))?'—':(Number(v)*100).toFixed(1)+'%';
  const cls=v=>v===true?'b':v===false?'r':'w';

  function commissioningHtml(A){
    assetsCache=Array.isArray(A)?A:[];
    const opts=['<option value="">ALL ASSETS</option>'].concat(assetsCache.map(a=>'<option value="'+h(a.symbol)+'">'+h(a.continuous_symbol||a.symbol)+'</option>')).join('');
    return '<section class="card c12" id="commissioningPanel"><h2>ICARUS SCIENTIFIC COMMISSIONING <span class="sub">falsification · calibration · ablation · replay · stress</span></h2>'+
      '<div class="toolbar"><label class="small">Scope <select id="scAsset">'+opts+'</select></label><button id="scCapture">Freeze forecast</button><button id="scSettle">Settle ready</button><button id="scTick">Run cycle</button><button id="scRefresh">Refresh</button><span class="small muted">append-only · shadow-only · cannot arm execution</span></div>'+
      '<div class="empty">loading commissioning ledger…</div></section>';
  }

  async function control(action,target){
    const token=localStorage.getItem('icarus-engine-token')||'icarus';
    const body={action,reason:'commissioning-panel'};
    if(target)body.target=target;
    const r=await fetch('/admin/engine-control',{method:'POST',headers:{'Content-Type':'application/json','Authorization':'Bearer '+token},body:JSON.stringify(body)});
    const d=await r.json(); if(!r.ok)throw new Error(d.detail||d.error||('HTTP '+r.status)); return d;
  }

  function tile(k,v,s){return '<div class="tile"><div class="k">'+h(k)+'</div><div class="v">'+h(v)+'</div>'+(s?'<div class="small muted">'+h(s)+'</div>':'')+'</div>';}
  function render(data){
    const el=document.querySelector('#commissioningPanel'); if(!el)return;
    const ledger=data.ledger||{}, m=data.metrics||{}, gate=data.promotion_gate||{}, cal=m.calibration||{}, bg=data.background||{};
    const checks=Object.entries(gate.checks||{}).map(([k,v])=>'<tr><td>'+h(k.replaceAll('_',' '))+'</td><td><span class="chip '+cls(v)+'">'+(v?'PASS':'NOT YET')+'</span></td></tr>').join('');
    const variants=(m.variants||[]).map((x,i)=>'<tr><td>'+(i+1)+'</td><td><b>'+h(x.variant)+'</b></td><td class="tnum">'+h(x.n)+'</td><td class="tnum">'+n(x.rmse,6)+'</td><td class="tnum">'+n(x.mae,6)+'</td><td class="tnum">'+pct(x.direction_accuracy)+'</td></tr>').join('');
    const regimes=(m.regimes||[]).map(x=>'<tr><td>'+h(x.phase_state)+'</td><td>'+h(x.koopman_mode)+'</td><td class="tnum">'+h(x.n)+'</td><td class="tnum">'+pct(x.direction_accuracy)+'</td><td class="tnum">'+n(x.rmse,6)+'</td></tr>').join('');
    const stress=(data.adversarial_matrix||[]).map(x=>'<tr><td><b>'+h(x.scenario)+'</b></td><td>'+h(x.required_behavior)+'</td><td><span class="chip '+cls(x.contract_pass)+'">'+(x.contract_pass?'PASS':'FAIL')+'</span></td></tr>').join('');
    const replay=((data.replay_contract||{}).requirements||[]).map(x=>'<li>'+h(x)+'</li>').join('');
    const opts=['<option value="">ALL ASSETS</option>'].concat(assetsCache.map(a=>'<option value="'+h(a.symbol)+'" '+(a.symbol===data.asset?'selected':'')+'>'+h(a.continuous_symbol||a.symbol)+'</option>')).join('');
    el.innerHTML='<h2>ICARUS SCIENTIFIC COMMISSIONING <span class="sub">'+h(data.asset||'ALL ASSETS')+' · '+h(data.status||'unknown').toUpperCase()+'</span></h2>'+
      '<div class="toolbar"><label class="small">Scope <select id="scAsset">'+opts+'</select></label><button id="scCapture">Freeze forecast</button><button id="scSettle">Settle ready</button><button id="scTick">Run cycle</button><button id="scRefresh">Refresh</button><span class="chip '+(data.status==='green'?'b':'r')+'">LEDGER '+h(data.status||'unknown').toUpperCase()+'</span><span class="small muted">background '+(bg.running?'RUNNING':'STOPPED')+' · every '+n(bg.interval_seconds,0)+'s</span></div>'+
      '<div class="tiles">'+
        tile('Frozen predictions',ledger.predictions??0,'immutable forecast receipts')+
        tile('Settled',ledger.settled??0,'outcomes written separately')+
        tile('Pending',ledger.pending??0,'waiting for target Chronon')+
        tile('Direction accuracy',pct(m.direction_accuracy),'out-of-sample only')+
        tile('RMSE',n(m.rmse,6),'forecast return error')+
        tile('Brier score',n(m.brier_score,4),'3-branch calibration loss')+
        tile('Interval coverage',pct(m.interval_coverage),'p05–p95 realized coverage')+
        tile('Calibration error',pct(cal.expected_calibration_error),'confidence vs realized frequency')+
        tile('Unknown↔error corr',n(m.unknown_error_correlation,3),'should rise when epistemic risk rises')+
        tile('Promotion gate',gate.research_influence_eligible?'RESEARCH ELIGIBLE':'NOT YET','never grants execution authority')+
      '</div>'+
      '<section class="card c12" style="margin-top:12px"><h2>Promotion gate <span class="sub">research influence only</span></h2><div class="scroll"><table><thead><tr><th>Check</th><th>Status</th></tr></thead><tbody>'+checks+'</tbody></table></div><div class="small muted" style="margin-top:8px">'+h(gate.policy||'')+'</div></section>'+
      '<div class="grid" style="margin-top:12px"><section class="card c6"><h2>Ablation / counterfactual tournament</h2><div class="scroll"><table><thead><tr><th>#</th><th>Variant</th><th>N</th><th>RMSE</th><th>MAE</th><th>Direction</th></tr></thead><tbody>'+(variants||'<tr><td colspan="6" class="empty">waiting for settled predictions</td></tr>')+'</tbody></table></div></section>'+
      '<section class="card c6"><h2>Regime decomposition</h2><div class="scroll"><table><thead><tr><th>Phase</th><th>Koopman</th><th>N</th><th>Direction</th><th>RMSE</th></tr></thead><tbody>'+(regimes||'<tr><td colspan="5" class="empty">waiting for settled predictions</td></tr>')+'</tbody></table></div></section></div>'+
      '<section class="card c12" style="margin-top:12px"><h2>Adversarial commissioning matrix</h2><div class="scroll"><table><thead><tr><th>Scenario</th><th>Required behavior</th><th>Contract</th></tr></thead><tbody>'+(stress||'<tr><td colspan="3" class="empty">freeze at least one forecast first</td></tr>')+'</tbody></table></div></section>'+
      '<section class="card c12" style="margin-top:12px"><h2>Causal replay contract</h2><ul class="small">'+replay+'</ul><div class="small muted">Future observations are forbidden. Prediction receipts are committed before outcomes. Offline smoothing must remain explicitly separated from live/replay feature construction.</div></section>'+
      '<section class="card c12" style="margin-top:12px"><h2>Authority boundary</h2><div class="small muted">Scientific Commissioning may qualify Chronofold for additional shadow/research influence only. execution_authorized=false · production_decision_authorized=false · broker_authority=false.</div></section>';
    wire();
  }

  async function loadCommissioning(){
    const panel=document.querySelector('#commissioningPanel'); if(!panel)return;
    if(loading){pendingLoad=true;return;}
    const requestAsset=selected;
    loading=true; pendingLoad=false;
    try{
      const token=localStorage.getItem('icarus-engine-token')||'icarus';
      const q=requestAsset?'?asset='+encodeURIComponent(requestAsset):'';
      const r=await fetch('/api/commissioning'+q,{cache:'no-store',headers:{'Authorization':'Bearer '+token}});
      const d=await r.json();
      if(!r.ok)throw new Error(d.detail||d.error||('HTTP '+r.status));
      if(requestAsset!==selected){pendingLoad=true;return;}
      render(d);
    }catch(err){if(requestAsset===selected)panel.innerHTML='<h2>ICARUS SCIENTIFIC COMMISSIONING</h2><div class="empty">Commissioning unavailable: '+h(err.message||err)+'</div>';}
    finally{
      loading=false;
      if(pendingLoad&&(location.hash||'#overview').slice(1)==='commissioning'){pendingLoad=false;setTimeout(loadCommissioning,0);}
    }
  }

  function wire(){
    const sel=document.querySelector('#scAsset'); if(sel){sel.value=selected;sel.onchange=()=>{selected=sel.value;loadCommissioning();};}
    const ref=document.querySelector('#scRefresh');if(ref)ref.onclick=loadCommissioning;
    const cap=document.querySelector('#scCapture');if(cap)cap.onclick=async()=>{if(!selected){alert('Select one asset to freeze a forecast.');return;}cap.disabled=true;try{await control('commissioning.capture',selected);await loadCommissioning();}catch(e){alert(e.message||e);}finally{cap.disabled=false;}};
    const set=document.querySelector('#scSettle');if(set)set.onclick=async()=>{set.disabled=true;try{await control(selected?'commissioning.settle_asset':'commissioning.settle_all',selected);await loadCommissioning();}catch(e){alert(e.message||e);}finally{set.disabled=false;}};
    const tick=document.querySelector('#scTick');if(tick)tick.onclick=async()=>{tick.disabled=true;try{await control('commissioning.tick','');await loadCommissioning();}catch(e){alert(e.message||e);}finally{tick.disabled=false;}};
  }

  function wireCommissioning(){wire();loadCommissioning();if(timer)clearInterval(timer);timer=setInterval(()=>{if((location.hash||'#overview').slice(1)==='commissioning')loadCommissioning();},5000);}
  window.commissioningHtml=commissioningHtml;
  window.wireCommissioning=wireCommissioning;
  window.loadCommissioning=loadCommissioning;
})();

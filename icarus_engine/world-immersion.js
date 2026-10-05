(()=>{
  'use strict';
  const root=document.documentElement;
  const reduced=window.matchMedia('(prefers-reduced-motion: reduce)');
  let scrollFrame=0,pointerFrame=0,viewObserver=null,viewMutation=null,viewResizeObserver=null,depthFrame=null,focusOrbit=null,ambient=null,topology=null,topologyTimer=0,viewFlashTimer=0,viewGateTimer=0,chapterTimer=0,focusTimer=0,scrollEnergyTimer=0,lastScrollY=0,lastScrollAt=0,currentView='overview',currentPhase='crown',viewHistory=[],initialized=false;

  const motionAllowed=()=>root.dataset.motion==='live'&&root.dataset.experience==='cinematic'&&!!root.dataset.world&&!document.hidden&&!reduced.matches&&root.dataset.introActive!=='true';
  const phaseLabels={crown:'CROWN',descent:'DESCENT',depth:'DEPTH',abyss:'ABYSS'};
  const phaseLore={
    divine:{crown:'ASCENSION',descent:'THRESHOLD',depth:'SANCTUM',abyss:'DOMINION'},
    void:{crown:'BREACH',descent:'FRACTURE',depth:'NULL FIELD',abyss:'EVENT HORIZON'},
    astral:{crown:'ORBIT',descent:'DRIFT',depth:'AETHER',abyss:'HORIZON'}
  };
  const viewMeta={
    overview:['OVERVIEW','◇'],asset:['ASSET','◈'],system:['SYSTEM','⌬'],golive:['GO LIVE','▲'],agent:['AGENT','◎'],
    inputs:['INPUTS','≡'],backtest:['BACKTEST','∿'],research:['RESEARCH','∆'],sources:['FINANCIAL / DATA','⌁'],
    'market-data':['MARKET DATA','⋮'],brain:['ADAPTIVE BRAIN','◉'],evolution:['MCP EVOLUTION','↟'],
    parallax:['PARALLAX / DREAMSTATE','⟁'],possibility:['ICARUS Ψ','Ψ'],pantheon:['PANTHEON / AETHER','✦'],
    sibyl:['SIBYL Ω','Ω'],apex:['APEX Ω','⌬'],ascendancy:['ASCENDANCY','↑'],learning:['LEARNING FABRIC','∞'],
    chronofold:['ICARUS Ξ','Ξ'],commissioning:['COMMISSIONING','◫'],integrity:['DATA INTEGRITY','◆'],
    'engine-control':['ENGINE CONTROL','⌘'],commands:['COMMANDS','⌗'],log:['ENGINE LOG','▥'],autopilot:['TACTICAL AUTOPILOT','➤']
  };

  function buildDepthFrame(){
    if(depthFrame||!document.body)return;
    depthFrame=document.createElement('div');
    depthFrame.className='world-depth-frame';
    depthFrame.setAttribute('aria-hidden','true');
    depthFrame.innerHTML=`<div class="world-depth-rail left"><i></i><b></b><b></b><b></b><b></b></div>
      <div class="world-depth-rail right"><i></i><b></b><b></b><b></b><b></b></div>
      <div class="world-depth-readout"><span>WORLD DEPTH</span><strong data-world-depth-label>CROWN</strong><em data-world-view-label>OVERVIEW</em><small data-world-view-index>01 / 01</small></div>
      <div class="world-corner-sigil top-left">I</div><div class="world-corner-sigil bottom-right">∞</div>
      <div class="world-view-gate"><i data-world-view-glyph>◇</i><span data-world-gate-label>OVERVIEW</span></div>
      <div class="world-depth-atmosphere"><i class="near"></i><i class="mid"></i><i class="far"></i><b></b></div>
      <div class="world-chapter-title" aria-hidden="true"><i data-world-chapter-index>01</i><strong data-world-chapter-title>CROWN</strong><span data-world-chapter-lore>ASCENSION</span></div>
      <div class="world-nav-trail" aria-hidden="true"></div>
      <div class="world-mobile-hud"><i data-world-mobile-glyph>◇</i><span data-world-mobile-view>OVERVIEW</span><b data-world-mobile-phase>CROWN</b><small data-world-mobile-index>01/01</small></div>`;
    document.body.appendChild(depthFrame);
  }
  function updateDepthFrame(phase,depth){
    if(!depthFrame)return;
    depthFrame.style.setProperty('--world-depth-progress',(depth*100).toFixed(2)+'%');
    const phaseText=phaseLabels[phase]||String(phase||'').toUpperCase();
    depthFrame.querySelector('[data-world-depth-label]').textContent=phaseText;
    const phases=['crown','descent','depth','abyss'],phaseIndex=Math.max(0,phases.indexOf(phase));
    const chapterTitle=depthFrame.querySelector('[data-world-chapter-title]'),chapterLore=depthFrame.querySelector('[data-world-chapter-lore]'),chapterIndex=depthFrame.querySelector('[data-world-chapter-index]');
    if(chapterTitle)chapterTitle.textContent=phaseText;
    if(chapterLore)chapterLore.textContent=(phaseLore[root.dataset.world]||phaseLore.divine)[phase]||'';
    if(chapterIndex)chapterIndex.textContent=String(phaseIndex+1).padStart(2,'0');
    const mobilePhase=depthFrame.querySelector('[data-world-mobile-phase]');if(mobilePhase)mobilePhase.textContent=phaseText;
    for(const rail of depthFrame.querySelectorAll('.world-depth-rail')){
      [...rail.querySelectorAll('b')].forEach((node,index)=>node.classList.toggle('active',depth>=index/3-.015));
    }
    if(phase!==currentPhase){
      if(motionAllowed()){
        clearTimeout(chapterTimer);depthFrame.dataset.chapter=phase;
        depthFrame.classList.remove('world-chapter-shift');void depthFrame.offsetWidth;depthFrame.classList.add('world-chapter-shift');
        chapterTimer=setTimeout(()=>depthFrame?.classList.remove('world-chapter-shift'),820);
      }
      currentPhase=phase;
    }
  }

  function writeScrollDepth(){
    scrollFrame=0;
    const doc=document.documentElement;
    const max=Math.max(1,doc.scrollHeight-window.innerHeight);
    const y=Math.max(0,window.scrollY||doc.scrollTop||0);
    const now=performance.now();
    if(lastScrollAt&&Math.abs(y-lastScrollY)>.5&&motionAllowed()){
      const dt=Math.max(8,now-lastScrollAt),velocity=Math.abs(y-lastScrollY)/dt;
      const energy=Math.max(0,Math.min(1,velocity/2.4));
      const direction=y>lastScrollY?1:-1;
      root.dataset.scrollDirection=direction>0?'down':'up';
      root.style.setProperty('--world-scroll-glow',(energy*18).toFixed(2)+'px');
      root.style.setProperty('--world-scroll-energy',energy.toFixed(3));
      root.style.setProperty('--world-scroll-lean',(direction*energy*4.5).toFixed(2)+'px');
      root.style.setProperty('--world-scroll-shear',(direction*energy*.22).toFixed(3)+'deg');
      clearTimeout(scrollEnergyTimer);
      scrollEnergyTimer=setTimeout(()=>{
        root.style.setProperty('--world-scroll-glow','0px');
        root.style.setProperty('--world-scroll-energy','0');
        root.style.setProperty('--world-scroll-lean','0px');
        root.style.setProperty('--world-scroll-shear','0deg');
      },150);
    }
    lastScrollY=y;lastScrollAt=now;
    const depth=Math.max(0,Math.min(1,y/max));
    root.style.setProperty('--world-scroll',depth.toFixed(4));
    root.style.setProperty('--world-scroll-shift',(-(window.innerWidth<760?18:34)*depth).toFixed(2)+'px');
    root.style.setProperty('--world-light-y',(12+depth*30).toFixed(2)+'%');
    const phase=depth<.08?'crown':depth<.45?'descent':depth<.78?'depth':'abyss';
    root.dataset.scrollPhase=phase;
    updateDepthFrame(phase,depth);
    updateScrollFocus();
  }
  function queueScroll(){
    if(!scrollFrame)scrollFrame=requestAnimationFrame(writeScrollDepth);
  }

  function ensurePointerLens(){
    if(pointerLens||!document.body)return;
    pointerLens=document.createElement('div');pointerLens.className='world-pointer-lens';pointerLens.setAttribute('aria-hidden','true');
    pointerLens.innerHTML='<i></i><b></b>';document.body.appendChild(pointerLens);
  }
  function writePointer(x,y,cx=null,cy=null){
    pointerFrame=0;
    const px=Math.max(-.5,Math.min(.5,x)),py=Math.max(-.5,Math.min(.5,y));
    root.style.setProperty('--world-pointer-x',px.toFixed(4));
    root.style.setProperty('--world-pointer-y',py.toFixed(4));
    root.style.setProperty('--world-pointer-shift-x',(-px*14).toFixed(2)+'px');
    root.style.setProperty('--world-pointer-shift-y',(-py*9).toFixed(2)+'px');
    root.style.setProperty('--world-light-x',(50+px*18).toFixed(2)+'%');
    if(pointerLens&&cx!=null&&cy!=null){
      pointerLens.style.transform=`translate3d(${cx.toFixed(1)}px,${cy.toFixed(1)}px,0)`;
      pointerLens.classList.add('active');
    }
  }
  function pointerMove(event){
    if(event.pointerType==='touch'||!motionAllowed()){pointerLens?.classList.remove('active');return;}
    ensurePointerLens();
    const x=event.clientX/Math.max(1,window.innerWidth)-.5;
    const y=event.clientY/Math.max(1,window.innerHeight)-.5;
    if(pointerFrame)cancelAnimationFrame(pointerFrame);
    pointerFrame=requestAnimationFrame(()=>writePointer(x,y,event.clientX,event.clientY));
  }
  function pointerLeave(){
    pointerLens?.classList.remove('active');
    if(pointerFrame)cancelAnimationFrame(pointerFrame);
    pointerFrame=requestAnimationFrame(()=>writePointer(0,0));
  }

  function reveal(element){
    if(!element?.isConnected||element.dataset.worldDepthSeen==='1')return;
    element.dataset.worldDepthSeen='1';
    if(!motionAllowed())return;
    element.classList.remove('world-depth-enter');
    void element.offsetWidth;
    element.classList.add('world-depth-enter');
    const clear=()=>element.classList.remove('world-depth-enter');
    element.addEventListener('animationend',clear,{once:true});
    setTimeout(clear,900);
  }
  function panelKind(element){
    const label=(element.querySelector(':scope > h2,:scope > summary,:scope h2')?.textContent||'').toUpperCase();
    if(/PORTFOLIO|EQUITY|PAPER FILLS|CLOSED TRADES|POSITION|P&L/.test(label))return 'capital';
    if(/RESEARCH|ADAPTIVE BRAIN|PARALLAX|DREAMSTATE|PANTHEON|SIBYL|APEX|ASCENDANCY|LEARNING|EVOLUTION|ICARUS Ψ|ICARUS Ξ/.test(label))return 'research';
    if(/MARKET DATA|FINANCIAL|DATA INTEGRITY|INPUTS|SOURCE|FEED/.test(label))return 'data';
    if(/SYSTEM|ENGINE|GO-LIVE|GO LIVE|COMMISSION|COMMAND|LOG|AUTOPILOT|AGENT/.test(label))return 'control';
    return 'instrument';
  }
  function decorateSurface(element){
    if(!element?.matches?.('.card,.asset,.group'))return;
    element.dataset.worldPanelKind=panelKind(element);
    if(!element.querySelector(':scope > .world-surface-sigil')){
      const sigil=document.createElement('span');sigil.className='world-surface-sigil';sigil.setAttribute('aria-hidden','true');
      sigil.innerHTML='<i></i><b></b>';element.appendChild(sigil);
    }
    if(!element.querySelector(':scope > .world-panel-index')){
      const index=document.createElement('span');index.className='world-panel-index';index.setAttribute('aria-hidden','true');
      element.appendChild(index);
    }
  }
  function numberPanels(majors){
    const total=Math.max(1,majors.length);
    majors.forEach((panel,index)=>{
      panel.dataset.worldPanelOrdinal=String(index+1);
      const readout=panel.querySelector(':scope > .world-panel-index');
      if(readout)readout.textContent='P'+String(index+1).padStart(2,'0')+' / '+String(total).padStart(2,'0')+' · '+String(panel.dataset.worldPanelKind||'instrument').toUpperCase();
    });
  }
  function observePanel(element){
    if(!element)return;
    decorateSurface(element);
    if(element.dataset.worldDepthObserved==='1')return;
    element.dataset.worldDepthObserved='1';
    if(viewObserver)viewObserver.observe(element);
    else reveal(element);
  }
  function ensureAmbient(){
    const view=document.getElementById('view');
    if(!view)return;
    if(ambient?.isConnected&&ambient.parentElement===view)return;
    ambient=document.createElement('div');ambient.className='world-view-ambient';ambient.setAttribute('aria-hidden','true');
    ambient.innerHTML='<i></i>'.repeat(12);view.prepend(ambient);
  }
  function ensureTopology(){
    const view=document.getElementById('view');
    if(!view)return;
    if(topology?.isConnected&&topology.parentElement===view)return;
    topology=document.createElementNS('http://www.w3.org/2000/svg','svg');
    topology.setAttribute('class','world-topology');
    topology.setAttribute('aria-hidden','true');
    topology.setAttribute('preserveAspectRatio','none');
    const links=document.createElementNS('http://www.w3.org/2000/svg','g');links.setAttribute('class','world-topology-links');
    const nodes=document.createElementNS('http://www.w3.org/2000/svg','g');nodes.setAttribute('class','world-topology-nodes');
    topology.append(links,nodes);view.prepend(topology);
  }
  function ensureSectionRadar(){
    if(sectionRadar?.isConnected)return;
    sectionRadar=document.createElement('nav');sectionRadar.className='world-section-radar';sectionRadar.setAttribute('aria-label','Section map');
    sectionRadar.innerHTML='<header><i>SECTION MAP</i><b data-world-radar-count>00</b></header><div data-world-radar-nodes></div>';
    sectionRadar.addEventListener('click',event=>{
      const item=event.target.closest?.('[data-radar-node]');if(!item)return;
      const panel=document.querySelector(`#view [data-world-topology-node="${item.dataset.radarNode}"]`);
      if(!panel)return;
      panel.scrollIntoView({behavior:motionAllowed()?'smooth':'auto',block:'center'});
      panel.classList.remove('world-radar-arrival');void panel.offsetWidth;panel.classList.add('world-radar-arrival');
      setTimeout(()=>panel?.classList.remove('world-radar-arrival'),900);
    });
    document.body.appendChild(sectionRadar);
  }
  function radarLabel(panel){
    return (panel.querySelector(':scope > h2,:scope > summary,:scope h2')?.textContent||panel.dataset.worldPanelKind||'INSTRUMENT')
      .replace(/\s+/g,' ').trim().toUpperCase().slice(0,28);
  }
  function rebuildSectionRadar(points){
    ensureSectionRadar();if(!sectionRadar)return;
    const host=sectionRadar.querySelector('[data-world-radar-nodes]'),count=sectionRadar.querySelector('[data-world-radar-count]');
    host.replaceChildren();if(count)count.textContent=String(points.length).padStart(2,'0');
    for(const p of points.slice(0,12)){
      const item=document.createElement('button');item.type='button';item.dataset.radarNode=String(p.index);item.dataset.kind=p.el.dataset.worldPanelKind||'instrument';
      const labelText=radarLabel(p.el);item.setAttribute('aria-label','Jump to '+labelText);
      const dot=document.createElement('i'),label=document.createElement('b');label.textContent=labelText;
      item.append(dot,label);host.appendChild(item);
    }
  }
  function updateSectionRadar(activeId){
    if(!sectionRadar)return;
    sectionRadar.querySelectorAll('[data-radar-node]').forEach(el=>el.classList.toggle('active',String(activeId??'')===el.dataset.radarNode));
  }
  function topologyPath(a,b){
    const dx=b.x-a.x,dy=b.y-a.y,curve=Math.max(-42,Math.min(42,dx*.08));
    const c1x=a.x+dx*.38,c2x=a.x+dx*.62,c1y=a.y+dy*.34-curve,c2y=a.y+dy*.66+curve;
    return `M ${a.x.toFixed(1)} ${a.y.toFixed(1)} C ${c1x.toFixed(1)} ${c1y.toFixed(1)}, ${c2x.toFixed(1)} ${c2y.toFixed(1)}, ${b.x.toFixed(1)} ${b.y.toFixed(1)}`;
  }
  function rebuildTopology(){
    topologyTimer=0;ensureTopology();
    const view=document.getElementById('view');if(!view||!topology)return;
    const links=topology.querySelector('.world-topology-links'),nodeLayer=topology.querySelector('.world-topology-nodes');
    links.replaceChildren();nodeLayer.replaceChildren();
    const viewRect=view.getBoundingClientRect(),width=Math.max(1,view.scrollWidth),height=Math.max(1,view.scrollHeight);
    topology.setAttribute('viewBox',`0 0 ${width} ${height}`);
    view.querySelectorAll('[data-world-topology-node]').forEach(el=>delete el.dataset.worldTopologyNode);
    const elements=[...view.querySelectorAll(':scope > :is(.card,.asset,.group), :scope > .assets > .asset')]
      .filter(el=>{const r=el.getBoundingClientRect();return r.width>40&&r.height>28;})
      .slice(0,18);
    const points=elements.map((el,index)=>{
      el.dataset.worldTopologyNode=String(index);
      const r=el.getBoundingClientRect();
      return {index,el,x:r.left-viewRect.left+view.scrollLeft+r.width/2,y:r.top-viewRect.top+view.scrollTop+r.height/2};
    }).sort((a,b)=>a.y-b.y||a.x-b.x);
    rebuildSectionRadar(points);
    if(points.length<2)return;
    const edgeKeys=new Set(),edges=[];
    const addEdge=(a,b)=>{
      if(!a||!b||a.index===b.index||edges.length>=24)return;
      const lo=Math.min(a.index,b.index),hi=Math.max(a.index,b.index),key=lo+':'+hi;
      if(edgeKeys.has(key))return;edgeKeys.add(key);edges.push([a,b]);
    };
    for(let i=0;i<points.length-1;i++)addEdge(points[i],points[i+1]);
    for(let i=0;i<points.length;i++){
      let nearest=null,best=Infinity;
      for(let j=i+1;j<points.length;j++){
        const dx=points[j].x-points[i].x,dy=points[j].y-points[i].y,score=Math.hypot(dx*.72,dy);
        if(score<best){best=score;nearest=points[j];}
      }
      if(best<Math.max(320,width*.42))addEdge(points[i],nearest);
    }
    for(const [a,b] of edges){
      const path=document.createElementNS('http://www.w3.org/2000/svg','path');
      path.setAttribute('d',topologyPath(a,b));path.setAttribute('pathLength','1');
      path.dataset.from=String(a.index);path.dataset.to=String(b.index);links.appendChild(path);
    }
    for(const p of points){
      const node=document.createElementNS('http://www.w3.org/2000/svg','circle');
      node.setAttribute('cx',p.x.toFixed(1));node.setAttribute('cy',p.y.toFixed(1));node.setAttribute('r','2.2');
      node.dataset.node=String(p.index);nodeLayer.appendChild(node);
    }
    updateScrollFocus();
  }
  function scheduleTopology(){
    clearTimeout(topologyTimer);topologyTimer=setTimeout(()=>requestAnimationFrame(rebuildTopology),80);
  }
  function topologyHighlight(target){
    if(!topology)return;
    const radarId=target?.closest?.('[data-radar-node]')?.dataset.radarNode;
    const panel=target?.closest?.('[data-world-topology-node]'),id=radarId??panel?.dataset.worldTopologyNode;
    topology.querySelectorAll('.active').forEach(el=>el.classList.remove('active'));
    if(id==null||!motionAllowed()){updateSectionRadar(null);return;}
    topology.querySelectorAll(`path[data-from="${id}"],path[data-to="${id}"],circle[data-node="${id}"]`).forEach(el=>el.classList.add('active'));
    updateSectionRadar(id);
  }
  function updateScrollFocus(){
    const panels=[...document.querySelectorAll('#view [data-world-topology-node]')].slice(0,18);
    for(const panel of panels)panel.classList.remove('world-scroll-focus');
    topology?.querySelectorAll('.scroll-active').forEach(el=>el.classList.remove('scroll-active'));
    if(!topology||!motionAllowed()||window.innerWidth<1100||!panels.length){updateSectionRadar(null);return;}
    const targetY=window.innerHeight*.48;
    let best=null,bestDistance=Infinity;
    for(const panel of panels){
      const r=panel.getBoundingClientRect();
      if(r.bottom<0||r.top>window.innerHeight)continue;
      const distance=Math.abs((r.top+r.bottom)/2-targetY);
      if(distance<bestDistance){best=panel;bestDistance=distance;}
    }
    if(!best){updateSectionRadar(null);return;}
    best.classList.add('world-scroll-focus');
    const id=best.dataset.worldTopologyNode;
    topology.querySelectorAll(`path[data-from="${id}"],path[data-to="${id}"],circle[data-node="${id}"]`).forEach(el=>el.classList.add('scroll-active'));
    updateSectionRadar(id);
  }
  function classifyReadouts(){
    const states=[...document.querySelectorAll('#view .empty')].slice(0,96);
    for(const el of states){
      const text=(el.textContent||'').trim().toUpperCase();
      el.classList.remove('world-loading-state','world-unavailable-state','world-error-state');
      if(el.classList.contains('neg')||/\b(ERROR|FAILED|FAILURE|INVALID)\b/.test(text))el.classList.add('world-error-state');
      else if(/\b(LOADING|WAITING|WARMING|INITIALIZING|CHECKING|COLLECTING|FETCHING|PREPARING)\b/.test(text))el.classList.add('world-loading-state');
      else if(/\b(UNAVAILABLE|UNMEASURED|NO DATA|NO CURRENT|NO ACTIVE|NOT AVAILABLE)\b/.test(text))el.classList.add('world-unavailable-state');
    }
  }
  function refresh(){
    ensureAmbient();ensureTopology();ensureSectionRadar();classifyReadouts();
    const majors=[...document.querySelectorAll('#view > :is(.card,.asset,.hero,.group), #view > .assets > .asset')];
    const view=document.getElementById('view');
    if(view)view.classList.toggle('world-sparse-view',majors.length<=2&&view.scrollHeight<window.innerHeight*1.35);
    majors.forEach(decorateSurface);numberPanels(majors);
    const nested=[...document.querySelectorAll('#view :is(.tile,.px-box,.psi-box,.pan-field,.brain-agent,.brain-sub,.brain-lane,.evo-sub)')];
    [...new Set([...majors,...nested])].slice(0,80).forEach(observePanel);
    writeScrollDepth();scheduleTopology();
  }
  function installObserver(){
    if('IntersectionObserver' in window){
      viewObserver=new IntersectionObserver(entries=>{
        for(const entry of entries){
          if(entry.isIntersecting){
            reveal(entry.target);
            viewObserver.unobserve(entry.target);
          }
        }
      },{root:null,rootMargin:'72px 0px -8% 0px',threshold:.08});
    }
    refresh();
    const view=document.getElementById('view');
    if(view&&'MutationObserver' in window){
      const decorativeNode=node=>node?.nodeType===1&&(
        node.matches?.('.world-topology,.world-view-ambient,.world-surface-sigil,.world-impact')||
        node.closest?.('.world-topology')
      );
      viewMutation=new MutationObserver(records=>{
        const meaningful=records.some(record=>{
          if(record.target?.nodeType===1&&record.target.closest?.('.world-topology'))return false;
          return [...record.addedNodes,...record.removedNodes].some(node=>!decorativeNode(node));
        });
        if(meaningful)requestAnimationFrame(refresh);
      });
      viewMutation.observe(view,{childList:true,subtree:true});
    }
    if(view&&'ResizeObserver' in window){
      viewResizeObserver=new ResizeObserver(()=>scheduleTopology());
      viewResizeObserver.observe(view);
    }
  }

  function ensureFocusOrbit(){
    if(focusOrbit||!document.body)return;
    focusOrbit=document.createElement('div');focusOrbit.className='world-focus-orbit';focusOrbit.setAttribute('aria-hidden','true');
    focusOrbit.innerHTML='<i></i><b></b>';document.body.appendChild(focusOrbit);
  }
  function positionFocusOrbit(target){
    if(!focusOrbit||!target?.isConnected||!motionAllowed()){focusOrbit?.classList.remove('active');return;}
    const r=target.getBoundingClientRect();
    if(!r.width||!r.height){focusOrbit.classList.remove('active');return;}
    const pad=Math.min(9,Math.max(5,Math.min(r.width,r.height)*.12));
    const w=Math.min(window.innerWidth-4,r.width+pad*2),h=Math.min(window.innerHeight-4,r.height+pad*2);
    const x=Math.max(2,Math.min(window.innerWidth-w-2,r.left-pad));
    const y=Math.max(2,Math.min(window.innerHeight-h-2,r.top-pad));
    focusOrbit.style.setProperty('--focus-x',x.toFixed(1)+'px');
    focusOrbit.style.setProperty('--focus-y',y.toFixed(1)+'px');
    focusOrbit.style.setProperty('--focus-w',w.toFixed(1)+'px');
    focusOrbit.style.setProperty('--focus-h',h.toFixed(1)+'px');
    focusOrbit.classList.add('active');
  }
  function focusIn(event){
    const target=event.target.closest?.('button,a,input,select,textarea,summary,[tabindex]');
    if(!target||target.closest?.('.world-intro'))return;
    ensureFocusOrbit();positionFocusOrbit(target);
    clearTimeout(focusTimer);focusTimer=setTimeout(()=>positionFocusOrbit(target),40);
  }
  function focusOut(){
    clearTimeout(focusTimer);focusTimer=setTimeout(()=>{if(!document.activeElement?.matches?.('button,a,input,select,textarea,summary,[tabindex]'))focusOrbit?.classList.remove('active');},30);
  }

  function interactionImpact(event){
    if(!motionAllowed())return;
    const target=event.target.closest?.('button,.tab,.card,.asset,.tile,.group>summary,.node,.badge');
    if(!target||target.closest?.('.world-intro')||target.matches(':disabled'))return;
    const rect=target.getBoundingClientRect();
    if(!rect.width||!rect.height)return;
    target.classList.add('world-impact-host');
    const impact=document.createElement('span');
    impact.className='world-impact';
    impact.dataset.kind=target.matches('.tab')?'gate':target.matches('.card,.asset,.tile,.group>summary')?'facet':target.matches('.node,.badge')?'signal':'pulse';
    impact.setAttribute('aria-hidden','true');
    impact.style.setProperty('--impact-x',Math.max(0,Math.min(100,(event.clientX-rect.left)/rect.width*100)).toFixed(1)+'%');
    impact.style.setProperty('--impact-y',Math.max(0,Math.min(100,(event.clientY-rect.top)/rect.height*100)).toFixed(1)+'%');
    target.appendChild(impact);
    const panel=target.closest?.('[data-world-topology-node]');
    const nodeId=target.closest?.('[data-radar-node]')?.dataset.radarNode??panel?.dataset.worldTopologyNode;
    if(topology&&nodeId!=null){
      const linked=[...topology.querySelectorAll(`path[data-from="${nodeId}"],path[data-to="${nodeId}"],circle[data-node="${nodeId}"]`)];
      linked.forEach(el=>el.classList.add('impact'));
      topology.classList.remove('world-topology-impact');void topology.getBoundingClientRect();topology.classList.add('world-topology-impact');
      setTimeout(()=>{linked.forEach(el=>el.classList.remove('impact'));topology?.classList.remove('world-topology-impact');},720);
    }
    let cleaned=false;
    const cleanup=()=>{
      if(cleaned)return;cleaned=true;impact.remove();
      if(!target.querySelector('.world-impact'))target.classList.remove('world-impact-host');
    };
    impact.addEventListener('animationend',cleanup,{once:true});
    setTimeout(cleanup,800);
  }

  function centerActiveTab(){
    requestAnimationFrame(()=>requestAnimationFrame(()=>{
      const tabs=document.getElementById('tabs'),active=tabs?.querySelector('.tab.active');
      if(!tabs||!active||tabs.scrollWidth<=tabs.clientWidth+2)return;
      const left=Math.max(0,active.offsetLeft-(tabs.clientWidth-active.offsetWidth)/2);
      tabs.scrollTo({left,behavior:motionAllowed()?'smooth':'auto'});
      tabs.classList.remove('world-nav-settle');void tabs.offsetWidth;tabs.classList.add('world-nav-settle');
      setTimeout(()=>tabs?.classList.remove('world-nav-settle'),520);
    }));
  }
  function renderViewHistory(next,meta,raw){
    if(raw!==currentView){
      viewHistory=viewHistory.filter(item=>item.key!==next);
      viewHistory.push({key:next,label:meta[0],glyph:meta[1]});
      viewHistory=viewHistory.slice(-4);
    } else if(!viewHistory.length) viewHistory=[{key:next,label:meta[0],glyph:meta[1]}];
    const trail=depthFrame?.querySelector('.world-nav-trail');
    if(trail){
      trail.replaceChildren(...viewHistory.map((item,index)=>{
        const span=document.createElement('span');span.dataset.view=item.key;span.dataset.current=index===viewHistory.length-1?'true':'false';
        span.innerHTML=`<i>${item.glyph}</i><b>${item.label}</b>`;return span;
      }));
    }
    for(const tab of document.querySelectorAll('#tabs .tab[data-v]')){
      const key=(tab.dataset.v||'').startsWith('asset:')?'asset':tab.dataset.v;
      tab.classList.toggle('world-visited',viewHistory.some(item=>item.key===key));
    }
  }
  function view(name='overview'){
    const raw=String(name||'overview'),next=(raw.startsWith('asset:')?'asset':raw).replace(/[^a-z0-9-]/gi,'-').toLowerCase();
    const meta=viewMeta[next]||[next.replace(/-/g,' ').toUpperCase(),'◇'];
    root.dataset.worldView=next||'overview';
    renderViewHistory(next,meta,raw);
    if(depthFrame){
      depthFrame.querySelector('[data-world-view-label]').textContent=meta[0];
      const glyph=depthFrame.querySelector('[data-world-view-glyph]'),label=depthFrame.querySelector('[data-world-gate-label]');
      const mobileGlyph=depthFrame.querySelector('[data-world-mobile-glyph]'),mobileView=depthFrame.querySelector('[data-world-mobile-view]');
      if(glyph)glyph.textContent=meta[1];if(label)label.textContent=meta[0];
      if(mobileGlyph)mobileGlyph.textContent=meta[1];if(mobileView)mobileView.textContent=meta[0];
      const tabs=[...document.querySelectorAll('#tabs .tab[data-v]')],tabIndex=tabs.findIndex(tab=>tab.dataset.v===raw||tab.dataset.v===next);
      const indexText=(tabIndex>=0?String(tabIndex+1).padStart(2,'0'):'--')+' / '+String(Math.max(1,tabs.length)).padStart(2,'0');
      const viewIndex=depthFrame.querySelector('[data-world-view-index]'),mobileIndex=depthFrame.querySelector('[data-world-mobile-index]');
      if(viewIndex)viewIndex.textContent=indexText;if(mobileIndex)mobileIndex.textContent=indexText.replace(/\s/g,'');
      if(raw!==currentView&&motionAllowed()){
        clearTimeout(viewFlashTimer);clearTimeout(viewGateTimer);
        depthFrame.classList.remove('world-view-shift','world-view-gate-active');void depthFrame.offsetWidth;
        depthFrame.classList.add('world-view-shift','world-view-gate-active');
        viewFlashTimer=setTimeout(()=>depthFrame?.classList.remove('world-view-shift'),760);
        viewGateTimer=setTimeout(()=>depthFrame?.classList.remove('world-view-gate-active'),980);
      }
    }
    currentView=raw;
    refresh();
    centerActiveTab();
  }

  function sync(){
    if(!motionAllowed()){
      root.style.setProperty('--world-pointer-x','0');
      root.style.setProperty('--world-pointer-y','0');
      root.style.setProperty('--world-pointer-shift-x','0px');
      root.style.setProperty('--world-pointer-shift-y','0px');
      root.style.setProperty('--world-light-x','50%');
      root.style.setProperty('--world-scroll-glow','0px');
      root.style.setProperty('--world-scroll-energy','0');
      root.style.setProperty('--world-scroll-lean','0px');
      root.style.setProperty('--world-scroll-shear','0deg');
      focusOrbit?.classList.remove('active');pointerLens?.classList.remove('active');topologyHighlight(null);sectionRadar?.classList.remove('active');
    } else if(document.activeElement?.matches?.('button,a,input,select,textarea,summary,[tabindex]')) {
      positionFocusOrbit(document.activeElement);topologyHighlight(document.activeElement);
    }
    queueScroll();scheduleTopology();
  }

  function init(){
    if(initialized)return;
    initialized=true;
    root.dataset.worldImmersion='ready';
    buildDepthFrame();ensureFocusOrbit();ensurePointerLens();
    window.addEventListener('scroll',()=>{queueScroll();if(focusOrbit?.classList.contains('active'))positionFocusOrbit(document.activeElement);},{passive:true});
    window.addEventListener('resize',()=>{queueScroll();scheduleTopology();if(focusOrbit?.classList.contains('active'))positionFocusOrbit(document.activeElement);},{passive:true});
    window.addEventListener('pointermove',pointerMove,{passive:true});
    document.addEventListener('pointerleave',pointerLeave,{passive:true});
    document.addEventListener('pointerdown',interactionImpact,{passive:true,capture:true});
    document.addEventListener('pointerover',event=>topologyHighlight(event.target),{passive:true});
    document.addEventListener('pointerout',event=>{if(!event.relatedTarget?.closest?.('[data-world-topology-node]'))topologyHighlight(null);},{passive:true});
    document.addEventListener('focusin',event=>{focusIn(event);topologyHighlight(event.target);},true);
    document.addEventListener('focusout',event=>{focusOut(event);setTimeout(()=>topologyHighlight(document.activeElement),0);},true);
    document.addEventListener('visibilitychange',sync);
    reduced.addEventListener?.('change',sync);
    installObserver();
    view((location.hash||'#overview').slice(1)||'overview');
    sync();
  }

  window.IcarusWorldImmersion=Object.freeze({init,refresh,sync,view});
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init,{once:true});
  else init();
})();
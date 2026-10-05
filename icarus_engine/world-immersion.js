(()=>{
  'use strict';
  const root=document.documentElement;
  const reduced=window.matchMedia('(prefers-reduced-motion: reduce)');
  let scrollFrame=0,pointerFrame=0,viewObserver=null,viewMutation=null,depthFrame=null,focusOrbit=null,ambient=null,viewFlashTimer=0,viewGateTimer=0,chapterTimer=0,focusTimer=0,scrollEnergyTimer=0,lastScrollY=0,lastScrollAt=0,currentView='overview',currentPhase='crown',initialized=false;

  const motionAllowed=()=>root.dataset.motion==='live'&&root.dataset.experience==='cinematic'&&!!root.dataset.world&&!document.hidden&&!reduced.matches&&root.dataset.introActive!=='true';
  const phaseLabels={crown:'CROWN',descent:'DESCENT',depth:'DEPTH',abyss:'ABYSS'};
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
      <div class="world-mobile-hud"><i data-world-mobile-glyph>◇</i><span data-world-mobile-view>OVERVIEW</span><b data-world-mobile-phase>CROWN</b><small data-world-mobile-index>01/01</small></div>`;
    document.body.appendChild(depthFrame);
  }
  function updateDepthFrame(phase,depth){
    if(!depthFrame)return;
    depthFrame.style.setProperty('--world-depth-progress',(depth*100).toFixed(2)+'%');
    const phaseText=phaseLabels[phase]||String(phase||'').toUpperCase();
    depthFrame.querySelector('[data-world-depth-label]').textContent=phaseText;
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
      root.dataset.scrollDirection=y>lastScrollY?'down':'up';
      root.style.setProperty('--world-scroll-glow',(energy*18).toFixed(2)+'px');
      root.style.setProperty('--world-scroll-energy',energy.toFixed(3));
      clearTimeout(scrollEnergyTimer);
      scrollEnergyTimer=setTimeout(()=>{
        root.style.setProperty('--world-scroll-glow','0px');
        root.style.setProperty('--world-scroll-energy','0');
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
  }
  function queueScroll(){
    if(!scrollFrame)scrollFrame=requestAnimationFrame(writeScrollDepth);
  }

  function writePointer(x,y){
    pointerFrame=0;
    const px=Math.max(-.5,Math.min(.5,x)),py=Math.max(-.5,Math.min(.5,y));
    root.style.setProperty('--world-pointer-x',px.toFixed(4));
    root.style.setProperty('--world-pointer-y',py.toFixed(4));
    root.style.setProperty('--world-pointer-shift-x',(-px*14).toFixed(2)+'px');
    root.style.setProperty('--world-pointer-shift-y',(-py*9).toFixed(2)+'px');
    root.style.setProperty('--world-light-x',(50+px*18).toFixed(2)+'%');
  }
  function pointerMove(event){
    if(event.pointerType==='touch'||!motionAllowed())return;
    const x=event.clientX/Math.max(1,window.innerWidth)-.5;
    const y=event.clientY/Math.max(1,window.innerHeight)-.5;
    if(pointerFrame)cancelAnimationFrame(pointerFrame);
    pointerFrame=requestAnimationFrame(()=>writePointer(x,y));
  }
  function pointerLeave(){
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
  function decorateSurface(element){
    if(!element?.matches?.('.card,.asset,.group')||element.querySelector(':scope > .world-surface-sigil'))return;
    const sigil=document.createElement('span');sigil.className='world-surface-sigil';sigil.setAttribute('aria-hidden','true');
    sigil.innerHTML='<i></i><b></b>';element.appendChild(sigil);
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
  function refresh(){
    ensureAmbient();
    const majors=[...document.querySelectorAll('#view > :is(.card,.asset,.hero,.group), #view > .assets > .asset')];
    majors.forEach(decorateSurface);
    const nested=[...document.querySelectorAll('#view :is(.tile,.px-box,.psi-box,.pan-field,.brain-agent,.brain-sub,.brain-lane,.evo-sub)')];
    [...new Set([...majors,...nested])].slice(0,80).forEach(observePanel);
    writeScrollDepth();
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
      viewMutation=new MutationObserver(records=>{
        if(records.some(record=>record.addedNodes.length||record.removedNodes.length))requestAnimationFrame(refresh);
      });
      viewMutation.observe(view,{childList:true,subtree:true});
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
  function view(name='overview'){
    const raw=String(name||'overview'),next=(raw.startsWith('asset:')?'asset':raw).replace(/[^a-z0-9-]/gi,'-').toLowerCase();
    const meta=viewMeta[next]||[next.replace(/-/g,' ').toUpperCase(),'◇'];
    root.dataset.worldView=next||'overview';
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
      focusOrbit?.classList.remove('active');
    } else if(document.activeElement?.matches?.('button,a,input,select,textarea,summary,[tabindex]')) {
      positionFocusOrbit(document.activeElement);
    }
    queueScroll();
  }

  function init(){
    if(initialized)return;
    initialized=true;
    root.dataset.worldImmersion='ready';
    buildDepthFrame();ensureFocusOrbit();
    window.addEventListener('scroll',()=>{queueScroll();if(focusOrbit?.classList.contains('active'))positionFocusOrbit(document.activeElement);},{passive:true});
    window.addEventListener('resize',()=>{queueScroll();if(focusOrbit?.classList.contains('active'))positionFocusOrbit(document.activeElement);},{passive:true});
    window.addEventListener('pointermove',pointerMove,{passive:true});
    document.addEventListener('pointerleave',pointerLeave,{passive:true});
    document.addEventListener('pointerdown',interactionImpact,{passive:true,capture:true});
    document.addEventListener('focusin',focusIn,true);
    document.addEventListener('focusout',focusOut,true);
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
(()=>{
  'use strict';
  const root=document.documentElement;
  const reduced=window.matchMedia('(prefers-reduced-motion: reduce)');
  let scrollFrame=0,pointerFrame=0,viewObserver=null,viewMutation=null,initialized=false;

  const motionAllowed=()=>root.dataset.motion==='live'&&root.dataset.experience==='cinematic'&&!!root.dataset.world&&!document.hidden&&!reduced.matches&&root.dataset.introActive!=='true';

  function writeScrollDepth(){
    scrollFrame=0;
    const doc=document.documentElement;
    const max=Math.max(1,doc.scrollHeight-window.innerHeight);
    const y=Math.max(0,window.scrollY||doc.scrollTop||0);
    const depth=Math.max(0,Math.min(1,y/max));
    root.style.setProperty('--world-scroll',depth.toFixed(4));
    root.style.setProperty('--world-scroll-shift',(-(window.innerWidth<760?18:34)*depth).toFixed(2)+'px');
    root.style.setProperty('--world-light-y',(12+depth*30).toFixed(2)+'%');
    root.dataset.scrollPhase=depth<.08?'crown':depth<.45?'descent':depth<.78?'depth':'abyss';
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
  function observePanel(element){
    if(!element||element.dataset.worldDepthObserved==='1')return;
    element.dataset.worldDepthObserved='1';
    if(viewObserver)viewObserver.observe(element);
    else reveal(element);
  }
  function refresh(){
    document.querySelectorAll('#view > :is(.card,.asset,.hero,.group), #view > .assets > .asset').forEach(observePanel);
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
      viewMutation.observe(view,{childList:true});
    }
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

  function sync(){
    if(!motionAllowed()){
      root.style.setProperty('--world-pointer-x','0');
      root.style.setProperty('--world-pointer-y','0');
      root.style.setProperty('--world-pointer-shift-x','0px');
      root.style.setProperty('--world-pointer-shift-y','0px');
      root.style.setProperty('--world-light-x','50%');
    }
    queueScroll();
  }

  function init(){
    if(initialized)return;
    initialized=true;
    root.dataset.worldImmersion='ready';
    window.addEventListener('scroll',queueScroll,{passive:true});
    window.addEventListener('resize',queueScroll,{passive:true});
    window.addEventListener('pointermove',pointerMove,{passive:true});
    document.addEventListener('pointerleave',pointerLeave,{passive:true});
    document.addEventListener('pointerdown',interactionImpact,{passive:true,capture:true});
    document.addEventListener('visibilitychange',sync);
    reduced.addEventListener?.('change',sync);
    installObserver();
    sync();
  }

  window.IcarusWorldImmersion=Object.freeze({init,refresh,sync});
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init,{once:true});
  else init();
})();
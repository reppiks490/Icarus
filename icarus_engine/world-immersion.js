/* SANCTUM: decorative page-wide scenery. No market reads, writes or values. */
(() => {
  'use strict';
  const root=document.documentElement, TAU=Math.PI*2;
  const palettes={divine:['231,197,133','128,171,210'],void:['241,64,104','170,91,164'],astral:['124,209,246','162,118,244']};
  const animations=new Set(),echoes=new Map(),observed=new Set(),seen=new Set();
  let environment,canvas,ctx,observer,view,rail,width=0,height=0,scroll=0,targetScroll=0,scrollMax=1;
  let pointer={x:0,y:0},camera={x:0,y:0},world='',route='',scanQueued=false,detail='rich';
  const allowed=()=>root.dataset.motion==='live'&&root.dataset.experience==='cinematic'&&!!palettes[root.dataset.world]&&!document.hidden&&root.dataset.introActive!=='true';
  const clamp=(n,a,b)=>Math.max(a,Math.min(b,n)),rgba=(rgb,a)=>`rgba(${rgb},${a})`;
  function animate(el,frames,options,cleanup=()=>{}) {
    if(!el?.animate){cleanup();return null;}
    const animation=el.animate(frames,options);animations.add(animation);
    const done=()=>{animations.delete(animation);cleanup();};animation.onfinish=done;animation.oncancel=done;
    return animation;
  }
  function reveal(el,index=0) {
    const key=route+'|'+(el.id||el.dataset.sym||el.dataset.immersionIndex);
    if(seen.has(key))return;seen.add(key);
    if(!allowed()||el.closest('[inert]'))return;
    el.classList.add('immersion-arrival');
    animate(el,[{transform:'translateY(16px)'},{transform:'translateY(0)'}],{duration:850,delay:Math.min(index*45,180),easing:'cubic-bezier(.16,1,.3,1)'},()=>el.classList.remove('immersion-arrival'));
    const heading=el.querySelector('h2,.ah');
    if(heading)animate(heading,[{opacity:.4,transform:'translateX(8px)'},{opacity:1,transform:'translateX(0)'}],{duration:700,easing:'ease-out'});
    // Move surfaces only; never interpolate a financial value or chart coordinate.
    [...el.querySelectorAll('.tiles > .tile,.hud > .tile')].slice(0,8).forEach((tile,i)=>animate(tile,[{transform:'translateY(6px)'},{transform:'translateY(0)'}],{duration:650,delay:i*30,easing:'cubic-bezier(.16,1,.3,1)'}));
  }
  function scan() {
    scanQueued=false;if(!view)return;
    scrollMax=Math.max(1,document.documentElement.scrollHeight-innerHeight);
    for(const el of observed)if(!el.isConnected){observer?.unobserve(el);observed.delete(el);}
    for(const [i,el] of [...view.querySelectorAll('.card,.asset')].entries()) {
      if(observed.has(el))continue;observed.add(el);el.classList.add('immersion-panel');el.dataset.immersionIndex=String(i);el.dataset.glassCut=String(i%4);
      if(observer)observer.observe(el);else reveal(el);
    }
  }
  function queueScan() {if(!scanQueued){scanQueued=true;queueMicrotask(scan);}}
  function resize(nextDetail=detail) {
    detail=nextDetail;if(!canvas)return;
    width=innerWidth;height=innerHeight;
    const ratio=Math.min(detail==='light'?.65:1,1536/Math.max(1,width),1000/Math.max(1,height));
    canvas.width=Math.max(1,Math.round(width*ratio));canvas.height=Math.max(1,Math.round(height*ratio));
    ctx?.setTransform(ratio,0,0,ratio,0,0);scrollMax=Math.max(1,document.documentElement.scrollHeight-innerHeight);
  }
  function position() {
    if(!environment)return;
    const depth=clamp(scroll/scrollMax,0,1);
    environment.style.setProperty('--descent',depth.toFixed(4));
    environment.style.setProperty('--camera-x',(camera.x*16).toFixed(2)+'px');environment.style.setProperty('--camera-y',(camera.y*12-depth*48).toFixed(2)+'px');
    if(rail){rail.style.setProperty('--descent',depth);rail.querySelector('b').textContent=String(1+Math.min(2,Math.floor(depth*3))).padStart(2,'0');}
  }
  function init() {
    if(environment)return;
    environment=document.createElement('div');environment.className='immersion-environment';environment.setAttribute('aria-hidden','true');environment.hidden=true;
    environment.innerHTML='<div class="immersion-landscape"></div><div class="immersion-vault"></div><canvas class="immersion-canvas"></canvas><div class="immersion-vignette"></div><div class="immersion-grain"></div>';
    document.body.prepend(environment);canvas=environment.querySelector('canvas');ctx=canvas.getContext('2d');
    rail=document.createElement('div');rail.className='immersion-rail';rail.setAttribute('aria-hidden','true');rail.innerHTML='<i></i><span>SANCTUM / <b>01</b></span>';document.body.append(rail);
    view=document.getElementById('view');route=location.hash;
    if('IntersectionObserver' in window)observer=new IntersectionObserver(entries=>{let i=0;for(const entry of entries)if(entry.isIntersecting)reveal(entry.target,i++);},{threshold:.08});
    if(view)new MutationObserver(records=>{if(records.some(r=>[...r.addedNodes].some(n=>n.nodeType===1)))queueScan();}).observe(view,{childList:true,subtree:true});
    window.addEventListener('resize',()=>resize(),{passive:true});
    window.addEventListener('scroll',()=>{targetScroll=window.scrollY;if(!allowed()){scroll=targetScroll;position();}},{passive:true});
    document.addEventListener('pointermove',event=>{if(event.pointerType!=='touch'&&allowed())pointer={x:event.clientX/Math.max(1,innerWidth)-.5,y:event.clientY/Math.max(1,innerHeight)-.5};},{passive:true});
    document.addEventListener('pointerleave',()=>{pointer={x:0,y:0};},{passive:true});
    document.addEventListener('click',event=>{
      if(!allowed())return;
      const target=event.target.closest?.('button,a,summary,.asset,[role="tab"]');
      if(!target||target.closest('[disabled],[aria-disabled="true"],.world-intro'))return;
      if(echoes.size>=4){const [old,animation]=echoes.entries().next().value;animation?.cancel();old.remove();echoes.delete(old);}
      const box=target.getBoundingClientRect(),echo=document.createElement('i');echo.className='immersion-echo';echo.setAttribute('aria-hidden','true');
      echo.style.left=(event.detail?event.clientX:box.x+box.width/2)+'px';echo.style.top=(event.detail?event.clientY:box.y+box.height/2)+'px';document.body.append(echo);
      const animation=animate(echo,[{opacity:.6,transform:'translate(-50%,-50%) scale(.15) rotate(-35deg)'},{opacity:0,transform:'translate(-50%,-50%) scale(1.3) rotate(30deg)'}],{duration:780,easing:'cubic-bezier(.16,1,.3,1)'},()=>{echo.remove();echoes.delete(echo);});
      if(animation)echoes.set(echo,animation);
    },{passive:true});
    resize();scan();
  }
  function refresh(active) {
    if(!environment)return;
    const hasWorld=!!palettes[root.dataset.world];environment.hidden=!hasWorld||root.dataset.experience==='focus';
    root.dataset.immersion=environment.hidden?'off':active?'live':'still';
    if(world!==root.dataset.world){world=root.dataset.world;environment.style.setProperty('--environment-art',hasWorld?`url('/worlds/${world}.webp')`:'none');}
    if(route!==location.hash){route=location.hash;seen.clear();scan();}
    if(!active){
      for(const animation of [...animations])animation.cancel();
      pointer={x:0,y:0};camera={x:0,y:0};scroll=targetScroll=window.scrollY;position();ctx?.clearRect(0,0,width,height);
    }
  }
  function enterView() {route=location.hash;seen.clear();queueScan();if(observer)for(const el of observed){observer.unobserve(el);observer.observe(el);}}
  function frame(time,dt,nextDetail) {
    if(!environment||environment.hidden||!allowed())return;
    if(detail!==nextDetail)resize(nextDetail);
    scroll+=(targetScroll-scroll)*.09;camera.x+=(pointer.x-camera.x)*.045;camera.y+=(pointer.y-camera.y)*.045;position();
    if(!ctx||!width||!height)return;
    ctx.clearRect(0,0,width,height);
    const [primary,secondary]=palettes[world]||palettes.divine,depth=scroll/Math.max(1,height),lean=detail==='light';
    const cx=width*(.76+Math.sin(depth*.38)*.16)+camera.x*24,cy=height*(.48+Math.cos(depth*.32)*.12)+camera.y*18;
    ctx.save();ctx.globalCompositeOperation='screen';
    for(let band=0;band<(lean?3:6);band++) {
      const phase=time*(world==='void'?.09:.035)+band*.45+depth*.3,radius=Math.min(width,height)*(.44+band*.085),squash=.23+Math.sin(depth*.35+band*.2)*.08;
      ctx.beginPath();
      for(let step=0;step<=96;step++) {
        const a=step/96*TAU,z=Math.sin(a+phase),x=cx+Math.cos(a)*radius,y=cy+Math.sin(a)*radius*squash+Math.cos(a)*radius*Math.sin(phase)*.45+z*12;
        if(!step)ctx.moveTo(x,y);else ctx.lineTo(x,y);
      }
      const gradient=ctx.createLinearGradient(cx-radius,cy-radius,cx+radius,cy+radius);
      gradient.addColorStop(0,rgba(primary,.01));gradient.addColorStop(.45,rgba(band%2?secondary:primary,.20));gradient.addColorStop(.72,rgba(primary,.035));gradient.addColorStop(1,rgba(secondary,.15));
      ctx.strokeStyle=gradient;ctx.lineWidth=band%2?.7:1.4;ctx.stroke();
    }
    for(let i=0;i<(lean?22:55);i++) {
      const seed=(i*137.508)%997/997,z=.25+(i%7)/9,x=((seed*width+Math.sin(time*.13+i)*20+camera.x*z*36)%width+width)%width;
      const y=((i*89.17-time*(world==='void'?8:3)*z-scroll*z*.15)%height+height)%height,alpha=.12+Math.sin(time*.4+i)*.06;
      ctx.fillStyle=rgba(i%3?primary:secondary,alpha);ctx.beginPath();ctx.arc(x,y,.5+z*.9,0,TAU);ctx.fill();
      if(i%9===0){ctx.fillRect(x-5,y-.3,10,.6);ctx.fillRect(x-.3,y-5,.6,10);}
    }
    ctx.restore();
  }
  function introMarkup(world) {
    const names={divine:'DIVINE ASCENSION',void:'CRIMSON VOID',astral:'ASTRAL DREAMSCAPE'};
    return `<div class="sanctum-film" aria-hidden="true"><div class="sanctum-shot"><div class="sanctum-world" style="background-image:url('/worlds/${world}.webp')"></div><div class="sanctum-haze"></div></div><canvas class="intro-loom"></canvas><div class="sanctum-aperture"></div><div class="sanctum-letterbox"></div><div class="sanctum-frame"></div><div class="sanctum-coordinate"><span>ICARUS / ${names[world]}</span><span>FORM BECOMES INFINITY</span></div><div class="sanctum-prologue"><span>A WORLD BEYOND THE ORDINARY</span><b>Awaken.</b></div><div class="sanctum-wordmark"><small>DIVINE PROVIDENCE</small><strong>${'ICARUS'.split('').map((letter,i)=>`<span style="--letter:${i}">${letter}</span>`).join('')}</strong><em>The horizon belongs to you.</em></div><div class="sanctum-filmgrain"></div></div>`;
  }
  function drawIntro(ctx,w,h,time,duration,world) {
    if(!w||!h||!duration)return;
    const progress=clamp(time/duration,0,1),[primary,secondary]=palettes[world]||palettes.divine,cx=w*.5,cy=h*.46;
    ctx.save();ctx.globalCompositeOperation='screen';
    const flight=progress*3.8,ease=1-Math.pow(1-clamp(progress/.7,0,1),3),fade=1-clamp((progress-.67)/.2,0,1);
    for(let ring=0;ring<7;ring++) {
      const z=((ring/7-flight*.23)%1+1)%1,r=Math.min(w,h)*(.045+Math.pow(z,2.6)*1.8),rotation=Math.sin(time*.075)*.11;
      ctx.save();ctx.translate(cx,cy);ctx.rotate(rotation+(ring%2?.09:0));
      const alpha=Math.min(.55,z*.45)*fade;ctx.strokeStyle=rgba(primary,alpha);ctx.lineWidth=1.2;ctx.beginPath();
      for(let side=0;side<=8;side++){const a=side/8*TAU+Math.PI/8,x=Math.cos(a)*r,y=Math.sin(a)*r*.83;if(!side)ctx.moveTo(x,y);else ctx.lineTo(x,y);}ctx.stroke();
      ctx.strokeStyle=rgba(secondary,alpha*.4);ctx.beginPath();ctx.ellipse(0,0,r*1.02,r*.845,0,0,TAU);ctx.stroke();
      for(let side=0;side<8;side++){
        const a=side/8*TAU+Math.PI/8;ctx.save();ctx.rotate(a);
        const beam=ctx.createLinearGradient(r*.75,0,r,0);beam.addColorStop(0,rgba(primary,0));beam.addColorStop(1,rgba(primary,alpha));ctx.fillStyle=beam;
        ctx.beginPath();ctx.moveTo(r*.72,-1);ctx.lineTo(r,-3);ctx.lineTo(r,3);ctx.closePath();ctx.fill();ctx.restore();
      }
      ctx.restore();
    }
    for(let i=0;i<90;i++) {
      const a=i*2.399963,z=(i/90+flight*.09)%1,r=Math.pow(z,1.7)*Math.hypot(w,h)*.7,x=cx+Math.cos(a)*r,y=cy+Math.sin(a)*r*.67,alpha=(.1+z*.55)*(1-progress*.75);
      ctx.strokeStyle=rgba(i%5?primary:secondary,alpha);ctx.lineWidth=.4+z*.9;ctx.beginPath();ctx.moveTo(x,y);ctx.lineTo(x+(x-cx)*(.007+ease*.012),y+(y-cy)*(.007+ease*.012));ctx.stroke();
    }
    const radiance=ctx.createRadialGradient(cx,cy,0,cx,cy,Math.min(w,h)*(.12+ease*.4));
    radiance.addColorStop(0,rgba(primary,.1*Math.sin(progress*Math.PI)));radiance.addColorStop(.3,rgba(secondary,.035));radiance.addColorStop(1,rgba(primary,0));ctx.fillStyle=radiance;ctx.fillRect(0,0,w,h);ctx.restore();
  }
  window.IcarusImmersion=Object.freeze({init,refresh,resize,frame,enterView,introMarkup,drawIntro});
})();

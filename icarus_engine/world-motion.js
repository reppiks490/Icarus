/* Decorative presentation only. No market API, engine state, or order controls. */
(() => {
  'use strict';
  const root = document.documentElement;
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
  let scene, canvas, ctx, aura, qualityReduced=false, slowFrames=0, requestedDetail='', frame = 0, last = 0, elapsed = 0, width = 0, height = 0;
  let visible = true, particles = [], pointer = {x:0, y:0}, eased = {x:0, y:0};
  let introFrame = 0, introLast = 0, introElapsed = 0;
  let intro = null, introTimer = 0, introReturnFocus = null, inertSiblings = [];
  const colors = {divine:[205,165,82], void:[255,80,108], astral:[137,192,255]};
  const rand = (a,b) => a + Math.random() * (b-a);
  const permitted = () => scene && !intro && !scene.hidden && visible && !document.hidden &&
    root.dataset.experience === 'cinematic' && root.dataset.motion !== 'off' && !reduced.matches && !!colors[root.dataset.world];
  const detail=()=>root.dataset.visualDetail==='light'||((root.dataset.visualDetail||'adaptive')==='adaptive'&&(qualityReduced||width<640))?'light':'rich';
  function resize() {
    if (!scene || !ctx) return;
    const box = scene.getBoundingClientRect();
    width = box.width; height = box.height;
    root.dataset.visualResolved=detail();
    const dpr = Math.min(window.devicePixelRatio || 1, detail()==='light'?1:1.5);
    canvas.width = Math.round(width*dpr); canvas.height = Math.round(height*dpr);
    ctx.setTransform(dpr,0,0,dpr,0,0);
    particles = Array.from({length: detail()==='light'?32:70}, () => ({
      x:Math.random(), y:Math.random(), z:rand(.2,1), phase:rand(0,Math.PI*2), speed:rand(.008,.035)
    }));
  }
  function draw(now) {
    frame = 0;
    if (!permitted() || !ctx) { last=0; return; }
    frame = requestAnimationFrame(draw);
    if (last && now-last < 30) return; // bounded to approximately 30 fps
    if(last&&(root.dataset.visualDetail||'adaptive')==='adaptive'&&!qualityReduced) {
      slowFrames=now-last>70?slowFrames+1:Math.max(0,slowFrames-.25);
      if(slowFrames>=8){qualityReduced=true;resize();aura?.pause();}
    }
    const dt = last ? Math.min((now-last)/1000,.06) : 0; last=now; elapsed+=dt;
    eased.x += (pointer.x-eased.x)*.065; eased.y += (pointer.y-eased.y)*.065;
    scene.style.setProperty('--scene-x', eased.x.toFixed(3));
    scene.style.setProperty('--scene-y', eased.y.toFixed(3));
    ctx.clearRect(0,0,width,height);
    aura?.draw(elapsed,root.dataset.world,width,height,eased,detail());
    const world = root.dataset.world, rgb = colors[world].join(',');
    // Three depth planes, flowing trajectories, soft bloom and star glints.
    for (const p of particles) {
      p.y -= p.speed * dt * (world === 'void' ? 2 : .6);
      if (p.y < -.06) { p.y=1.06; p.x=Math.random(); }
      const sway = Math.sin(elapsed*(world === 'void' ? .7 : .22)+p.phase) * 12*p.z;
      const x = p.x*width+sway+eased.x*20*p.z, y=p.y*height+eased.y*12*p.z;
      const radius = .6+p.z*1.6;
      const opacity = .2+(Math.sin(elapsed*.6+p.phase)+1)*.2;
      const glow = ctx.createRadialGradient(x,y,0,x,y,radius*6);
      glow.addColorStop(0,`rgba(${rgb},${opacity})`); glow.addColorStop(1,`rgba(${rgb},0)`);
      ctx.fillStyle=glow; ctx.fillRect(x-radius*6,y-radius*6,radius*12,radius*12);
      ctx.fillStyle=`rgba(${rgb},${opacity+.15})`; ctx.beginPath(); ctx.arc(x,y,radius,0,Math.PI*2); ctx.fill();
      if (world === 'astral' && p.z > .82) {
        ctx.strokeStyle=`rgba(${rgb},${opacity*.7})`; ctx.lineWidth=.6;
        ctx.beginPath(); ctx.moveTo(x-5,y); ctx.lineTo(x+5,y); ctx.moveTo(x,y-5); ctx.lineTo(x,y+5); ctx.stroke();
      }
      if (world === 'void' && p.z > .7) {
        ctx.strokeStyle=`rgba(${rgb},.2)`; ctx.beginPath(); ctx.moveTo(x,y); ctx.lineTo(x-2,y+9*p.z); ctx.stroke();
      }
    }
    window.IcarusWorldCinema?.draw(ctx,width,height,elapsed,dt,{pointer:eased,detail:detail()});
    // Slow moving broad light shafts remain behind the content, not on charts.
    if (world !== 'void') {
      ctx.save(); ctx.globalCompositeOperation='screen';
      for (let i=0;i<3;i++) {
        const x=width*(.58+i*.15)+Math.sin(elapsed*.11+i)*25;
        const g=ctx.createLinearGradient(x,0,x+80,height);
        g.addColorStop(0,`rgba(${rgb},.09)`); g.addColorStop(1,`rgba(${rgb},0)`);
        ctx.fillStyle=g; ctx.beginPath(); ctx.moveTo(x,0); ctx.lineTo(x+22,0); ctx.lineTo(x+130,height); ctx.lineTo(x-70,height); ctx.fill();
      }
      ctx.restore();
    }
  }
  function refresh() {
    if (!scene) return;
    if(requestedDetail!==root.dataset.visualDetail){requestedDetail=root.dataset.visualDetail;qualityReduced=false;slowFrames=0;resize();}
    if(detail()==='light')aura?.pause();
    window.IcarusWorldCinema?.sync(!!intro || (permitted() && !!ctx));
    if (permitted()) { if (!frame) { resize(); last=0; frame=requestAnimationFrame(draw); } }
    else {
      cancelAnimationFrame(frame); frame=0; last=0; aura?.pause();
      ctx?.clearRect(0,0,width,height);
      pointer={x:0,y:0}; eased={x:0,y:0};
      scene.style.setProperty('--scene-x','0'); scene.style.setProperty('--scene-y','0');
    }
    if (intro && (root.dataset.motion === 'off' || reduced.matches)) closeIntro();
  }
  function closeIntro() {
    if (!intro) return;
    clearTimeout(introTimer); cancelAnimationFrame(introFrame); introFrame=0; introLast=0; introElapsed=0;
    intro.remove(); intro=null;root.dataset.introActive='false';
    document.removeEventListener('keydown', introKey, true);
    for (const [el, wasInert] of inertSiblings) el.inert = wasInert;
    inertSiblings = [];
    if (introReturnFocus?.isConnected) introReturnFocus.focus({preventScroll:true});
    introReturnFocus=null;
    refresh();
  }
  function introKey(event) {
    if (event.key === 'Escape') { event.preventDefault(); event.stopImmediatePropagation(); closeIntro(); }
    if (event.key === 'Tab' && intro) {
      event.preventDefault(); intro.querySelector('button').focus();
    }
  }
  function playIntro() {
    if (intro || reduced.matches || root.dataset.motion === 'off') return;
    root.dataset.introActive='true';
    introReturnFocus = document.activeElement;
    intro = document.createElement('div'); intro.className='world-intro';
    const duration = root.dataset.introLength === '12' ? 12000 : 20000;
    intro.style.setProperty('--intro-duration',duration+'ms');
    intro.dataset.introWorld = colors[root.dataset.theme] ? root.dataset.theme : 'divine';
    intro.setAttribute('role','dialog'); intro.setAttribute('aria-modal','true'); intro.setAttribute('aria-label','ICARUS cinematic introduction');
    intro.innerHTML=`<button type="button" class="intro-skip">Skip intro <span>Esc</span></button>
      <div class="intro-theater" aria-hidden="true"><div class="intro-backdrop"></div><canvas class="intro-loom"></canvas>
        <div class="intro-rays"></div><div class="intro-dust"></div>
        <div class="intro-system"><div class="intro-eclipse"></div>
          <i class="intro-ring r1"></i><i class="intro-ring r2"></i><i class="intro-ring r3"></i><i class="intro-ring r4"></i>
          <div class="intro-wing left"><b></b><b></b><b></b><b></b><b></b></div>
          <div class="intro-wing right"><b></b><b></b><b></b><b></b><b></b></div>
          <div class="intro-crown"><svg viewBox="0 0 100 110" aria-hidden="true"><path d="M18 31L31 42L50 14L69 42L82 31L73 65H27Z" fill="none" stroke="currentColor" stroke-width="2"/><path d="M30 73H70M36 81H64" fill="none" stroke="currentColor" stroke-width="2"/><path d="M50 32L58 48L50 62L42 48Z" fill="currentColor"/><circle cx="50" cy="5" r="2" fill="currentColor"/><path d="M50 88V105M44 97L50 105L56 97" fill="none" stroke="currentColor" stroke-width="2"/></svg></div>
        </div>
        <div class="intro-chapters"><span>FORM / AWAKENING</span><span>LIGHT / CONVERGENCE</span><span>INFINITY / REVEALED</span></div>
        <div class="intro-title"><span>THE ONE ABOVE ALL</span><strong>ICARUS</strong><em>Enter your dominion.</em></div>
      </div><p class="intro-note">Cinematic introduction · decorative sequence</p>`;
    inertSiblings = Array.from(document.body.children).map(el => [el, el.inert]);
    for (const [el] of inertSiblings) el.inert = true;
    document.body.appendChild(intro);
    refresh();
    intro.querySelector('button').addEventListener('click',closeIntro);
    intro.querySelector('button').focus({preventScroll:true});
    document.addEventListener('keydown',introKey,true);
    const introCanvas=intro.querySelector('.intro-loom'), introCtx=introCanvas.getContext('2d');
    const animateIntro=now=>{
      introFrame=0;
      if(!intro || document.hidden) return;
      introFrame=requestAnimationFrame(animateIntro);
      if(introLast && now-introLast<30)return;
      const dt=introLast ? Math.min((now-introLast)/1000,.06) : 0;
      introLast=now;introElapsed+=dt;
      const w=intro.clientWidth,h=intro.clientHeight,dpr=Math.min(devicePixelRatio||1,1.25);
      if(introCanvas.width!==Math.round(w*dpr)||introCanvas.height!==Math.round(h*dpr)) {
        introCanvas.width=Math.round(w*dpr);introCanvas.height=Math.round(h*dpr);introCtx.setTransform(dpr,0,0,dpr,0,0);
      }
      introCtx.clearRect(0,0,w,h);
      window.IcarusWorldCinema?.draw(introCtx,w,h,introElapsed,dt,{intro:true,detail:detail(),pointer:{x:Math.sin(introElapsed*.18)*.35,y:Math.cos(introElapsed*.13)*.18}});
    };
    if(introCtx)introFrame=requestAnimationFrame(animateIntro);
    introTimer=setTimeout(closeIntro,duration);
  }
  function init(element) {
    if (scene) return;
    scene=element; canvas=document.createElement('canvas'); canvas.className='world-atmosphere'; canvas.setAttribute('aria-hidden','true');
    scene.prepend(canvas); ctx=canvas.getContext('2d');
    scene.dataset.renderer=ctx ? 'canvas' : 'static';
    aura=ctx ? window.IcarusWorldAura?.create(scene) : null;
    window.IcarusWorldCinema?.init(scene);
    scene.addEventListener('pointermove', event => {
      if (event.pointerType === 'touch' || !permitted()) return;
      const r=scene.getBoundingClientRect(); pointer={x:(event.clientX-r.left)/r.width-.5,y:(event.clientY-r.top)/r.height-.5};
    },{passive:true});
    scene.addEventListener('pointerleave',()=>{pointer={x:0,y:0};},{passive:true});
    if ('ResizeObserver' in window) new ResizeObserver(resize).observe(scene);
    else window.addEventListener('resize',resize,{passive:true});
    if ('IntersectionObserver' in window) new IntersectionObserver(entries=>{visible=entries[0].isIntersecting;refresh();}).observe(scene);
    document.addEventListener('visibilitychange',()=>{ if (document.hidden) closeIntro(); refresh(); });
    reduced.addEventListener('change',refresh);
    resize();
  }
  function startup() {
    // Once per browser tab session, never on polling, route changes or theme switches.
    try { if (sessionStorage.getItem('icarus-intro-seen')) return; sessionStorage.setItem('icarus-intro-seen','1'); }
    catch (_) { return; } // No surprise repeated intros when storage is blocked.
    if (root.dataset.experience !== 'focus') playIntro();
  }
  window.IcarusWorldMotion=Object.freeze({init,refresh,playIntro,startup});
})();

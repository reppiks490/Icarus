/* Eclipse Loom: original projected geometry and synthesized sound. Presentation only. */
(() => {
  'use strict';
  const root = document.documentElement;
  const TAU = Math.PI * 2;
  const clamp = n => Math.max(0, Math.min(1, n));
  const ease = n => { n=clamp(n); return n*n*(3-2*n); };
  let audio, master, enabled=false, audible=false, previousTime=null, noise;
  let sceneElement,litPanel=null,panelFrame=0,panelPointer=null;
  const worldTransitions=new Set();
  const voices = new Set(), entrances = new Set(), enteredCharts = new Set(), chartSurfaces = new WeakSet();
  const palettes = {
    divine:['#f5ce7a','#fff5d6','#82ddff'],
    void:['#ff315d','#ffb4d0','#d66dff'],
    astral:['#73e5ff','#e2e4ff','#9570ff']
  };
  function line(ctx, points, color, width=1) {
    ctx.beginPath(); ctx.moveTo(...points[0]);
    for (const p of points.slice(1)) ctx.lineTo(...p);
    ctx.strokeStyle=color; ctx.lineWidth=width; ctx.stroke();
  }
  function project(x,y,z,rx,ry,rz,cx,cy,size) {
    let yy=y*Math.cos(rx)-z*Math.sin(rx),zz=y*Math.sin(rx)+z*Math.cos(rx);
    let xx=x*Math.cos(ry)+zz*Math.sin(ry);zz=-x*Math.sin(ry)+zz*Math.cos(ry);
    const u=xx*Math.cos(rz)-yy*Math.sin(rz),v=xx*Math.sin(rz)+yy*Math.cos(rz);
    const depth=3.6/(3.6+zz);
    return [cx+u*size*depth,cy+v*size*depth,zz];
  }
  function draw(ctx,w,h,t,dt,{intro=false,pointer={x:0,y:0},detail='rich'}={}) {
    if(!ctx || !w || !h) return;
    const world=root.dataset.world || 'divine';
    const [color,light,other]=palettes[world]||palettes.divine;
    const mobile=w<700,lean=detail==='light';
    const cameraX=Math.max(-.5,Math.min(.5,Number(pointer.x)||0)),cameraY=Math.max(-.5,Math.min(.5,Number(pointer.y)||0));
    const cx=intro?w*.5:mobile?w*.5:w*.76;
    const cy=intro?h*.44:mobile?h*.71:h*.47;
    const size=Math.min(w*(intro?.24:mobile?.33:.19),h*(mobile?.23:.34));
    const cycle=world==='void'?16:world==='astral'?30:24,phase=t%cycle;
    const fold=ease((phase-cycle*.44)/(cycle*.15))*(1-ease((phase-cycle*.635)/(cycle*.178)));
    const breath=1+Math.sin(t*.48)*.025;
    const bloom=size*(1.5+fold*.5);
    ctx.save();
    // Light threads are curved geometry, never a distortion of financial data.
    ctx.globalCompositeOperation='screen';
    for(let j=0;j<7;j++) {
      ctx.beginPath();
      for(let i=0;i<=48;i++) {
        const u=i/48,x=u*w;
        const y=cy+Math.sin(u*5+t*.17+j*.45)*h*.12+(j-3)*h*.037;
        if(i===0)ctx.moveTo(x,y);else ctx.lineTo(x,y);
      }
      const ribbon=ctx.createLinearGradient(0,0,w,0);
      ribbon.addColorStop(0,color+'00');ribbon.addColorStop(.4,color+'08');ribbon.addColorStop(.8,(j%2?other:color)+'24');ribbon.addColorStop(1,color+'00');
      ctx.strokeStyle=ribbon;ctx.lineWidth=8+j*4;ctx.stroke();
    }
    const halo=ctx.createRadialGradient(cx,cy,size*.17,cx,cy,bloom);
    halo.addColorStop(0,color+'22');halo.addColorStop(.30,color+'08');halo.addColorStop(.64,other+'16');halo.addColorStop(1,color+'00');
    ctx.fillStyle=halo;ctx.fillRect(cx-bloom,cy-bloom,bloom*2,bloom*2);
    ctx.globalCompositeOperation='source-over';
    // A dark, opaque aperture gives the glass and light a common vanishing point.
    const core=ctx.createRadialGradient(cx-size*.1,cy-size*.12,0,cx,cy,size*.45);
    core.addColorStop(0,world==='void'?'#100718':'#0a0c1822');core.addColorStop(.75,world==='void'?'#070711':'#07071116');core.addColorStop(1,'#07071100');
    ctx.fillStyle=core;ctx.beginPath();ctx.arc(cx,cy,size*.45,0,TAU);ctx.fill();
    const viewProject=(x,y,z,rx,ry,rz)=>project(x,y,z,rx+cameraY*.3,ry+cameraX*.4,rz,cx,cy,size);
    // Distinct structures share a camera and bounded geometry budget.
    const facets=[];
    for(let band=0;band<(world==='astral'?0:3);band++) {
      const count=lean?16:24,radius=(.66+band*.24)*(1-fold*.38)*breath;
      const rx=world==='void'?1.12+band*.09:.20+band*.7+Math.sin(t*.08+band)*.14;
      const ry=world==='void'?.2+Math.sin(t*.06)*.2:t*(band%2?-.04:.035)+band*1.2;
      const rz=t*(world==='void'?-.16:.035)+band*.8;
      for(let i=0;i<count;i++) {
        const a=i*TAU/count,span=.075+fold*.04;
        const lift=Math.sin(i*1.7+t*.4+band)*.04+fold*(i%2?.20:-.20);
        const length=world==='divine'?.34+Math.sin(a*2+t*.1)*.08:.14;
        const pts=[[radius,a-span,lift], [radius+length+fold*.12,a,lift+.04], [radius,a+span,lift], [radius-.035,a,lift-.07]]
          .map(([r,theta,z])=>viewProject(Math.cos(theta)*r,Math.sin(theta)*r,z,rx,ry,rz));
        facets.push({pts,z:pts.reduce((n,p)=>n+p[2],0)/4,band,i});
      }
    }
    facets.sort((a,b)=>b.z-a.z);
    for(const f of facets) {
      const opacity=Math.round(38+clamp((1-f.z)/2)*95).toString(16).padStart(2,'0');
      ctx.beginPath();ctx.moveTo(f.pts[0][0],f.pts[0][1]);
      for(const p of f.pts.slice(1))ctx.lineTo(p[0],p[1]);ctx.closePath();
      const gradient=ctx.createLinearGradient(f.pts[0][0],f.pts[0][1],f.pts[2][0]+1,f.pts[2][1]+1);
      gradient.addColorStop(0,(f.band===1?other:color)+'05');gradient.addColorStop(.5,(f.band===1?other:color)+opacity);gradient.addColorStop(1,'#090a1899');
      ctx.fillStyle=gradient;ctx.fill();ctx.strokeStyle=(f.band===1?other:light)+opacity;ctx.lineWidth=.65;ctx.stroke();
      if(f.i%4===0)line(ctx,[f.pts[0].slice(0,2),f.pts[1].slice(0,2)],light+'bb',1.3);
    }
    if(world==='divine') {
      // Vaulted luminous arches unfold around the glass core.
      for(let arch=0;arch<(lean?3:5);arch++) {
        const angle=arch*TAU/5+t*.025,radius=.85+fold*.18,points=[];
        for(let i=0;i<=36;i++) {
          const a=i*Math.PI/36;
          points.push(viewProject(Math.cos(a)*radius,-Math.sin(a)*1.65+.65,0,.12,angle,0).slice(0,2));
        }
        line(ctx,points,light+(arch%2?'75':'bb'),arch===2?1.6:.8);
        const foot=viewProject(-radius,.65,0,.12,angle,0),tip=viewProject(-radius,1.03,0,.12,angle,0);
        line(ctx,[foot.slice(0,2),tip.slice(0,2)],color+'88',1);
      }
    } else if(world==='void') {
      // Counter-wound accretion strands wrap an opaque event horizon.
      for(let ring=0;ring<(lean?3:6);ring++) {
        const points=[];
        for(let i=0;i<=80;i++) {
          const a=i*TAU/80+t*(ring%2?.14:-.1),r=.65+ring*.09+Math.sin(a*3+t*.2)*.035;
          points.push(viewProject(Math.cos(a)*r,Math.sin(a)*r,Math.sin(a*2+t*.3)*.03,1.13,.14,ring*.12).slice(0,2));
        }
        line(ctx,points,(ring%2?other:color)+(ring%2?'70':'aa'),ring===2?2:.8);
      }
      const dark=ctx.createRadialGradient(cx,cy,0,cx,cy,size*.35);
      dark.addColorStop(0,'#030207');dark.addColorStop(.87,'#040208');dark.addColorStop(1,'#04020800');
      ctx.fillStyle=dark;ctx.beginPath();ctx.arc(cx,cy,size*.35,0,TAU);ctx.fill();
      ctx.strokeStyle=light+'99';ctx.lineWidth=.9;ctx.beginPath();ctx.ellipse(cx,cy,size*.35,size*.32,-.18,0,TAU);ctx.stroke();
    } else {
      // Moving star atlas and helical meridian: decorative geometry only.
      const stars=[],count=lean?24:40;
      for(let i=0;i<count;i++) {
        const y=1-(i/(count-1))*2,r=Math.sqrt(Math.max(0,1-y*y)),a=i*2.39996;
        stars.push(viewProject(Math.cos(a)*r*1.12,y*1.12,Math.sin(a)*r*1.12,t*.07,t*.11,.2));
      }
      for(let i=0;i<count;i++)for(const step of [5,8]) {
        const j=(i+step)%count,p=stars[i],q=stars[j];
        if(Math.hypot(p[0]-q[0],p[1]-q[1])<size*.85)line(ctx,[p.slice(0,2),q.slice(0,2)],(step===5?color:other)+'66',.8);
      }
      stars.sort((a,b)=>b[2]-a[2]);
      for(let i=0;i<stars.length;i++) {
        const [x,y,z]=stars[i],r=1.2+(1-z)*.65;
        ctx.fillStyle=i%3?light:other;ctx.shadowColor=color;ctx.shadowBlur=lean?0:10;
        ctx.beginPath();ctx.arc(x,y,r,0,TAU);ctx.fill();ctx.shadowBlur=0;
        if(i%7===0){line(ctx,[[x-5,y],[x+5,y]],light+'88',.7);line(ctx,[[x,y-5],[x,y+5]],light+'88',.7);}
      }
      const helix=[];
      for(let i=0;i<=100;i++) {
        const a=i*.12+t*.12,y=(i/100-.5)*2.4;
        helix.push(viewProject(Math.cos(a)*.87,y,Math.sin(a)*.87,.22,t*.11,.2).slice(0,2));
      }
      line(ctx,helix,other+'aa',1.2);
    }
    // Orbit inscriptions are geometric ticks, not borrowed symbols or fake numbers.
    for(let ring=0;ring<2;ring++) {
      const radius=1.25+ring*.14;
      for(let i=0;i<(lean?40:80);i++) {
        const a=i*TAU/(lean?40:80)+t*(ring?-.022:.027),r=radius+(i%5===0?.045:.014);
        const p=viewProject(Math.cos(a)*radius,Math.sin(a)*radius,0,.35+ring*.4,.2,0);
        const q=viewProject(Math.cos(a)*r,Math.sin(a)*r,0,.35+ring*.4,.2,0);
        line(ctx,[p.slice(0,2),q.slice(0,2)],color+(i%5===0?'88':'35'),.7);
      }
    }
    // Each world has its own focal form rather than a shared opaque centerpiece.
    if(world==='divine') {
      const vertices=[[0,-.43-fold*.1,0],[.2,0,0],[0,0,.2],[-.2,0,0],[0,0,-.2],[0,.43+fold*.1,0]]
        .map(([x,y,z])=>viewProject(x,y,z,.18,t*.24,.06));
      const faces=[];
      for(let i=1;i<=4;i++)for(const tip of [0,5]) {
        const points=[vertices[tip],vertices[i],vertices[i%4+1]];
        faces.push({points,z:points.reduce((sum,p)=>sum+p[2],0)/3});
      }
      faces.sort((a,b)=>b.z-a.z);
      for(const {points} of faces) {
        ctx.beginPath();ctx.moveTo(points[0][0],points[0][1]);for(const p of points.slice(1))ctx.lineTo(p[0],p[1]);ctx.closePath();
        const g=ctx.createLinearGradient(points[0][0],points[0][1],points[1][0]+1,points[1][1]+1);
        g.addColorStop(0,light+'ee');g.addColorStop(.5,color+'99');g.addColorStop(1,'#423b3188');
        ctx.fillStyle=g;ctx.fill();ctx.strokeStyle=light;ctx.lineWidth=.8;ctx.stroke();
      }
    } else if(world==='astral') {
      ctx.save();ctx.globalCompositeOperation='screen';ctx.shadowColor=color;ctx.shadowBlur=lean?0:18;
      for(let i=0;i<4;i++) {
        const a=t*.08+i*Math.PI/4,r=(i%2?.1:.2)*size;
        line(ctx,[[cx-Math.cos(a)*r,cy-Math.sin(a)*r],[cx+Math.cos(a)*r,cy+Math.sin(a)*r]],light+'bb',i%2?.7:1.2);
      }
      ctx.fillStyle=light;ctx.beginPath();ctx.arc(cx,cy,2.8+Math.sin(t*.7)*.5,0,TAU);ctx.fill();ctx.restore();
    }
    // Traveling sparks follow curved paths through the instrument rather than falling randomly.
    ctx.globalCompositeOperation='screen';
    for(let i=0;i<36;i++) {
      const a=i*2.39996+t*.13,r=(.4+((t*.065+i*.037)%1)*1.2)*size;
      const x=cx+Math.cos(a)*r,y=cy+Math.sin(a)*r*.6;
      ctx.fillStyle=(i%3?color:light)+'bb';ctx.beginPath();ctx.arc(x,y,i%5===0?1.8: .8,0,TAU);ctx.fill();
    }
    if(fold>.02) {
      ctx.globalAlpha=fold*.34;
      ctx.strokeStyle=light;ctx.lineWidth=1;
      ctx.beginPath();ctx.ellipse(cx,cy,size*(1.7-fold*.6),size*(.21+fold*.05),-.2,0,TAU);ctx.stroke();
      line(ctx,[[cx-size*1.65,cy],[cx+size*1.65,cy]],color,.8);
    }
    ctx.restore();
    if(audible && previousTime!==null && t-previousTime<.2) {
      const start=Math.floor(t/cycle)*cycle;
      if(previousTime<start+cycle*.44&&t>=start+cycle*.44) sound('fold');
      if(previousTime<start+cycle*.635&&t>=start+cycle*.635) sound('release');
    }
    previousTime=t;
  }
  const motionAllowed=()=>root.dataset.motion==='live'&&root.dataset.experience==='cinematic'&&!!root.dataset.world&&!document.hidden;
  function clearPanel() {
    cancelAnimationFrame(panelFrame);panelFrame=0;panelPointer=null;
    if(litPanel){litPanel.classList.remove('world-lit');for(const prop of ['--panel-x','--panel-y','--panel-tilt-x','--panel-tilt-y','--panel-dx','--panel-dy','--panel-depth-x','--panel-depth-y'])litPanel.style.removeProperty(prop);litPanel=null;}
  }
  function init(element) {
    if(sceneElement)return;sceneElement=element;
    const view=document.getElementById('view');
    view?.addEventListener('pointermove',event=>{
      if(event.pointerType==='touch'||!motionAllowed()||root.dataset.introActive==='true')return;
      const panel=event.target.closest?.('.card,.asset,.group,.tile,.px-box,.psi-box,.pan-field,.brain-agent,.brain-sub,.brain-lane,.evo-sub');
      if(!panel||!view.contains(panel)){clearPanel();return;}
      if(litPanel!==panel){clearPanel();litPanel=panel;panel.classList.add('world-lit');}
      panelPointer={x:event.clientX,y:event.clientY};
      if(!panelFrame)panelFrame=requestAnimationFrame(()=>{
        panelFrame=0;if(!litPanel?.isConnected||!panelPointer||!motionAllowed()){clearPanel();return;}
        const r=litPanel.getBoundingClientRect();
        const px=Math.max(0,Math.min(100,(panelPointer.x-r.left)/Math.max(1,r.width)*100));
        const py=Math.max(0,Math.min(100,(panelPointer.y-r.top)/Math.max(1,r.height)*100));
        const nx=(px-50)/50,ny=(py-50)/50;
        litPanel.style.setProperty('--panel-x',px.toFixed(1)+'%');
        litPanel.style.setProperty('--panel-y',py.toFixed(1)+'%');
        litPanel.style.setProperty('--panel-tilt-x',((-ny)*.6).toFixed(3)+'deg');
        litPanel.style.setProperty('--panel-tilt-y',(nx*.75).toFixed(3)+'deg');
        litPanel.style.setProperty('--panel-dx',(nx*3.8).toFixed(2)+'px');
        litPanel.style.setProperty('--panel-dy',(ny*2.9).toFixed(2)+'px');
        litPanel.style.setProperty('--panel-depth-x',(nx*7.2).toFixed(2)+'px');
        litPanel.style.setProperty('--panel-depth-y',(ny*5.4).toFixed(2)+'px');
      });
    },{passive:true});
    view?.addEventListener('pointerleave',clearPanel,{passive:true});
  }
  function transitionWorld(element,from) {
    for(const animation of worldTransitions)animation.cancel();worldTransitions.clear();
    element.querySelectorAll('.world-veil').forEach(el=>el.remove());
    if(!motionAllowed()||root.dataset.introActive==='true')return;
    const animate=(target,keyframes,options,remove=false)=>{
      if(!target.animate){if(remove)target.remove();return;}
      const animation=target.animate(keyframes,options);worldTransitions.add(animation);
      let cleaned=false;
      const cleanup=()=>{
        if(cleaned)return;cleaned=true;
        worldTransitions.delete(animation);if(remove)target.remove();
      };
      animation.onfinish=cleanup;animation.oncancel=cleanup;
      // Some headless/hidden compositor paths delay Web Animations finish events.
      // A bounded DOM cleanup prevents decorative veils from ever becoming stale.
      if(remove)setTimeout(cleanup,(Number(options?.delay)||0)+(Number(options?.duration)||0)+90);
    };
    const to=root.dataset.world||'divine';
    if(palettes[from]) {
      const veil=document.createElement('div');veil.className='world-veil';veil.dataset.worldTransition=to;veil.setAttribute('aria-hidden','true');
      veil.style.backgroundImage=`url('/worlds/${from}.webp')`;element.appendChild(veil);
      const veilFrames=to==='void'
        ? [{opacity:.82,clipPath:'polygon(0 0,100% 0,100% 100%,0 100%)',transform:'translateX(0) skewX(0deg)',filter:'contrast(1.08)'},{opacity:.28,clipPath:'polygon(0 0,72% 0,46% 100%,0 100%)',transform:'translateX(-12px) skewX(-5deg)',filter:'contrast(1.3) brightness(.78)'},{opacity:0,clipPath:'polygon(0 0,4% 0,0 100%,0 100%)',transform:'translateX(-28px) skewX(-9deg)',filter:'contrast(1.45) brightness(.5)'}]
        : to==='astral'
          ? [{opacity:.78,clipPath:'ellipse(112% 88% at 50% 50%)',transform:'scale(1)',filter:'blur(0px) saturate(1)'},{opacity:.35,clipPath:'ellipse(58% 42% at 50% 48%)',transform:'scale(1.06) rotate(.4deg)',filter:'blur(1px) saturate(1.18)'},{opacity:0,clipPath:'ellipse(4% 2% at 50% 48%)',transform:'scale(1.12) rotate(1deg)',filter:'blur(5px) saturate(.65)'}]
          : [{opacity:.74,clipPath:'circle(150% at 50% 42%)',transform:'scale(1.02)',filter:'brightness(.86)'},{opacity:.34,clipPath:'circle(58% at 50% 42%)',transform:'scale(.995)',filter:'brightness(1.18)'},{opacity:0,clipPath:'circle(0% at 50% 42%)',transform:'scale(.98)',filter:'brightness(1.35)'}];
      animate(veil,veilFrames,{duration:to==='void'?920:to==='astral'?1180:1050,easing:'cubic-bezier(.2,.7,.2,1)'},true);
    }
    const heading=element.querySelector('h1'),title=heading.textContent;
    heading.setAttribute('aria-label',title);heading.replaceChildren();
    title.split(' ').forEach((word,i)=>{
      const span=document.createElement('span');span.className='world-word';span.textContent=word;span.setAttribute('aria-hidden','true');heading.append(span,document.createTextNode(' '));
      const wordFrames=to==='void'
        ? [{opacity:.12,transform:'translateX(-18px) skewX(-10deg)',filter:'blur(2px) contrast(1.25)'},{opacity:1,transform:'translateX(0) skewX(0)',filter:'none'}]
        : to==='astral'
          ? [{opacity:.12,transform:'translateY(9px) scale(.92) rotateX(22deg)',filter:'blur(5px) saturate(.7)'},{opacity:1,transform:'translateY(0) scale(1) rotateX(0)',filter:'none'}]
          : [{opacity:.2,transform:'translateY(16px) scale(.96)',filter:'brightness(.72) blur(2px)'},{opacity:1,transform:'translateY(0) scale(1)',filter:'none'}];
      animate(span,wordFrames,{duration:to==='void'?680:to==='astral'?900:820,delay:i*(to==='void'?45:70),easing:'cubic-bezier(.2,.7,.2,1)'});
    });
    const caption=element.querySelector('#worldCaption');
    if(caption)animate(caption,[{opacity:.3,transform:'translateY(6px)'},{opacity:1,transform:'translateY(0)'}],{duration:850,easing:'ease-out'});
  }
  function sound(kind) {
    if(!enabled||!audible||!audio||audio.state!=='running'||document.hidden) return;
    const now=audio.currentTime;
    const envelope=(source,peak,duration,filter) => {
      const gain=audio.createGain();gain.gain.setValueAtTime(.0001,now);gain.gain.exponentialRampToValueAtTime(peak,now+.01);gain.gain.exponentialRampToValueAtTime(.0001,now+duration);
      if(filter){source.connect(filter);filter.connect(gain);}else source.connect(gain);
      gain.connect(master);voices.add(source);
      source.onended=()=>{source.disconnect();filter?.disconnect();gain.disconnect();voices.delete(source);};
      source.start(now);source.stop(now+duration+.02);
    };
    if(kind==='fold') {
      const source=audio.createBufferSource();source.buffer=noise;
      const filter=audio.createBiquadFilter();filter.type='bandpass';filter.frequency.setValueAtTime(1800,now);filter.frequency.exponentialRampToValueAtTime(250,now+.25);filter.Q.value=.7;
      envelope(source,.18,.32,filter);
    } else {
      for(const [freq,peak] of [[146.83,.075],[220,.05],[329.63,.025],[587.33,.012]]) {
        const oscillator=audio.createOscillator();oscillator.type='sine';oscillator.frequency.value=freq;envelope(oscillator,peak,1.2);
      }
      const source=audio.createBufferSource();source.buffer=noise;envelope(source,.018,.3);
    }
  }
  function sync(active) {
    audible=!!active;previousTime=null;
    if(master&&audio) master.gain.setTargetAtTime(enabled && audible ? .35 : 0,audio.currentTime,.025);
    if(!active) for(const source of voices) {try {source.stop();}catch(_) { /* already ended */ }}
    if(!motionAllowed()||root.dataset.introActive==='true') {
      clearPanel();
      document.querySelectorAll('.world-chart-surface.world-chart-hover').forEach(el=>{el.classList.remove('world-chart-hover');el.style.removeProperty('--chart-hover-x');el.style.removeProperty('--chart-hover-y');});
      for(const animation of worldTransitions)animation.cancel();worldTransitions.clear();
      for(const animation of entrances) animation.cancel();entrances.clear();
    }
  }
  async function toggleSound(button) {
    if(enabled) {enabled=false;sync(audible);button.textContent='Enable celestial sound';button.setAttribute('aria-pressed','false');return;}
    button.disabled=true;
    try {
      const Audio=window.AudioContext||window.webkitAudioContext;
      if(!Audio) throw Error('Audio unavailable');
      if(!audio) {
        audio=new Audio();master=audio.createGain();master.gain.value=0;master.connect(audio.destination);
        noise=audio.createBuffer(1,Math.ceil(audio.sampleRate*.4),audio.sampleRate);
        const channel=noise.getChannelData(0);for(let i=0;i<channel.length;i++)channel[i]=Math.random()*2-1;
      }
      await audio.resume();
      if(audio.state!=='running') throw Error('Audio suspended');
      enabled=true;sync(audible);button.textContent='Mute celestial sound';button.setAttribute('aria-pressed','true');
    } catch(_) {button.textContent='Sound unavailable · retry';button.setAttribute('aria-pressed','false');}
    finally {button.disabled=false;}
  }
  function enterView() {
    enteredCharts.clear();
    for(const animation of entrances) animation.cancel();entrances.clear();
    if(root.dataset.motion!=='live'||root.dataset.experience!=='cinematic'||!root.dataset.world||document.hidden) return;
    const panels=[...document.querySelectorAll('#view > .card, #view > .asset, #view > .hero')].slice(0,18);
    const animate=(el,frames,options)=>{
      if(!el.animate)return;
      const animation=el.animate(frames,options);entrances.add(animation);
      animation.onfinish=()=>entrances.delete(animation);animation.oncancel=()=>entrances.delete(animation);
    };
    panels.forEach((el,i)=>{
      // Small entrance movement; chart geometry and displayed values are never interpolated.
      animate(el,[{opacity:.65,transform:'translateY(9px)'},{opacity:1,transform:'translateY(0)'}],{duration:600,delay:Math.min(i*45,360),easing:'cubic-bezier(.2,.7,.2,1)'});
      const heading=el.querySelector('h2');
      if(heading)animate(heading,[{opacity:.55,transform:'translateX(-5px)'},{opacity:1,transform:'translateX(0)'}],{duration:700,delay:Math.min(i*45,360),easing:'ease-out'});
    });
  }
  function installChartSurface(element) {
    if(chartSurfaces.has(element))return;
    chartSurfaces.add(element);
    element.classList?.add('world-chart-surface');
    const clear=()=>{
      element.classList?.remove('world-chart-hover');
      element.style?.removeProperty('--chart-hover-x');element.style?.removeProperty('--chart-hover-y');
    };
    element.addEventListener?.('pointermove',event=>{
      if(event.pointerType==='touch'||!motionAllowed()||root.dataset.introActive==='true')return clear();
      const r=element.getBoundingClientRect();
      if(!r.width||!r.height)return clear();
      const x=Math.max(0,Math.min(100,(event.clientX-r.left)/r.width*100));
      const y=Math.max(0,Math.min(100,(event.clientY-r.top)/r.height*100));
      element.style.setProperty('--chart-hover-x',x.toFixed(2)+'%');
      element.style.setProperty('--chart-hover-y',y.toFixed(2)+'%');
      element.classList?.add('world-chart-hover');
    },{passive:true});
    element.addEventListener?.('pointerleave',clear,{passive:true});
  }
  function enterChart(symbol, element) {
    if (!element?.isConnected || !element.querySelector('svg')) return;
    installChartSurface(element);
    if (enteredCharts.has(symbol)) return;
    enteredCharts.add(symbol);
    if (root.dataset.motion !== 'live' || root.dataset.experience !== 'cinematic' || !root.dataset.world || document.hidden || !element.animate) return;
    element.classList?.remove('world-chart-scan-active');void element.offsetWidth;element.classList?.add('world-chart-scan-active');
    setTimeout(()=>element?.classList?.remove('world-chart-scan-active'),900);
    const animation=element.animate([{opacity:.72,filter:'brightness(.82)'},{opacity:1,filter:'none'}],{duration:650,easing:'ease-out'});
    entrances.add(animation);
    animation.onfinish=()=>entrances.delete(animation);animation.oncancel=()=>entrances.delete(animation);
  }
  window.IcarusWorldCinema=Object.freeze({draw,sync,toggleSound,enterView,enterChart,init,transitionWorld});
})();

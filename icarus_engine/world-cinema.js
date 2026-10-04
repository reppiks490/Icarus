/* Eclipse Loom: original projected geometry and synthesized sound. Presentation only. */
(() => {
  'use strict';
  const root = document.documentElement;
  const TAU = Math.PI * 2;
  const clamp = n => Math.max(0, Math.min(1, n));
  const ease = n => { n=clamp(n); return n*n*(3-2*n); };
  let audio, master, enabled=false, audible=false, previousTime=null, noise;
  const voices = new Set(), entrances = new Set(), enteredCharts = new Set();
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
  function draw(ctx,w,h,t,dt,{intro=false}={}) {
    if(!ctx || !w || !h) return;
    const world=root.dataset.world || 'divine';
    const [color,light,other]=palettes[world]||palettes.divine;
    const mobile=w<700;
    const cx=intro?w*.5:mobile?w*.5:w*.76;
    const cy=intro?h*.44:mobile?h*.71:h*.47;
    const size=Math.min(w*(intro?.24:mobile?.33:.19),h*(mobile?.23:.34));
    const phase=t%18;
    const fold=ease((phase-8)/2.7)*(1-ease((phase-11.4)/3.2));
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
    core.addColorStop(0,'#181527');core.addColorStop(.75,'#070711');core.addColorStop(1,'#07071100');
    ctx.fillStyle=core;ctx.beginPath();ctx.arc(cx,cy,size*.45,0,TAU);ctx.fill();
    // Glass tesserae: 72 independently projected facets, depth-sorted every frame.
    const facets=[];
    for(let band=0;band<3;band++) {
      const count=24,radius=(.66+band*.24)*(1-fold*.38)*breath;
      const rx=.45+band*.55+Math.sin(t*.1+band)*.2;
      const ry=t*(band%2?-.085:.065)+band*1.2;
      const rz=t*.045+band*.8;
      for(let i=0;i<count;i++) {
        const a=i*TAU/count,span=.075+fold*.04;
        const lift=Math.sin(i*1.7+t*.4+band)*.04+fold*(i%2?.20:-.20);
        const pts=[[radius,a-span,lift], [radius+.17+fold*.12,a,lift+.04], [radius,a+span,lift], [radius-.035,a,lift-.07]]
          .map(([r,theta,z])=>project(Math.cos(theta)*r,Math.sin(theta)*r,z,rx,ry,rz,cx,cy,size));
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
    // Orbit inscriptions are geometric ticks, not borrowed symbols or fake numbers.
    for(let ring=0;ring<2;ring++) {
      const radius=1.25+ring*.14;
      for(let i=0;i<80;i++) {
        const a=i*TAU/80+t*(ring?-.022:.027),r=radius+(i%5===0?.045:.014);
        const p=project(Math.cos(a)*radius,Math.sin(a)*radius,0,.35+ring*.4,.2,0,cx,cy,size);
        const q=project(Math.cos(a)*r,Math.sin(a)*r,0,.35+ring*.4,.2,0,cx,cy,size);
        line(ctx,[p.slice(0,2),q.slice(0,2)],color+(i%5===0?'88':'35'),.7);
      }
    }
    // A suspended geometric seed slowly opens into a four-dimensional-looking lattice.
    const points=[];
    for(let i=0;i<8;i++) points.push(project((i&1?.19:-.19)*(1-fold*.7),(i&2?.19:-.19)*(1+fold*1.8),(i&4?.19:-.19),t*.22,t*.17,t*.06,cx,cy,size));
    ctx.shadowColor=color;ctx.shadowBlur=10;
    for(let i=0;i<8;i++)for(const bit of [1,2,4])if(!(i&bit))line(ctx,[points[i].slice(0,2),points[i|bit].slice(0,2)],light+'cc',1);
    ctx.shadowBlur=0;
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
      const cycle=Math.floor(t/18)*18;
      if(previousTime<cycle+8&&t>=cycle+8) sound('fold');
      if(previousTime<cycle+11.4&&t>=cycle+11.4) sound('release');
    }
    previousTime=t;
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
    if(root.dataset.motion==='off'||root.dataset.experience!=='cinematic'||document.hidden) {
      for(const animation of entrances) animation.cancel();entrances.clear();
    }
  }
  async function toggleSound(button) {
    if(enabled) {enabled=false;sync(audible);button.textContent='Enable celestial sound';button.setAttribute('aria-pressed','false');return;}
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
  function enterChart(symbol, element) {
    if (!element?.isConnected || !element.querySelector('svg') || enteredCharts.has(symbol)) return;
    enteredCharts.add(symbol);
    if (root.dataset.motion !== 'live' || root.dataset.experience !== 'cinematic' || !root.dataset.world || document.hidden || !element.animate) return;
    const animation=element.animate([{opacity:.72},{opacity:1}],{duration:650,easing:'ease-out'});
    entrances.add(animation);
    animation.onfinish=()=>entrances.delete(animation);animation.oncancel=()=>entrances.delete(animation);
  }
  window.IcarusWorldCinema=Object.freeze({draw,sync,toggleSound,enterView,enterChart});
})();

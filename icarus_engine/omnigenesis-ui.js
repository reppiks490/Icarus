/* ICARUS OMNIGENESIS ∞ — authenticated cinematic research observatory.
 * All study nodes represent REAL research ledger records. Surrounding geometry
 * is atmospheric animation only, never simulated market evidence or live agents.
 */
(function () {
  'use strict';
  var active = null;
  var cached = null;
  var inFlight = null;

  function safe(text) {
    return String(text === null || text === undefined ? '' : text).replace(/[&<>"]/g, function (c) {
      return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];
    });
  }
  function codeHash(s) {
    var h = 2166136261; s = String(s);
    for (var i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); }
    return h >>> 0;
  }
  function rnd(seed) {
    var a = seed >>> 0;
    return function () {
      a += 0x6D2B79F5;
      var t = a;
      t = Math.imul(t ^ t >>> 15, t | 1);
      t ^= t + Math.imul(t ^ t >>> 7, t | 61);
      return ((t ^ t >>> 14) >>> 0) / 4294967296;
    };
  }
  function clamp(v, lo, hi) { return Math.min(hi, Math.max(lo, v)); }

  function omnigenesisHtml() {
    return '<section class="og-root" id="og-root" aria-label="OMNIGENESIS scientific research observatory">' +
      '<div class="og-head"><div><div class="og-kicker">ICARUS ΩG • SCIENTIFIC CIVILIZATION</div>' +
      '<h2>OMNIGENESIS <span>∞</span></h2>' +
      '<div class="og-subtitle">MATHEMATICAL FOUNDRY / EXPERIMENTAL REALITY / SCIENTIFIC MEMORY</div></div>' +
      '<div class="og-status">RESEARCH-ONLY<br>NO EXECUTION AUTHORITY</div></div>' +
      '<div class="og-body"><div class="og-overlay" aria-hidden="true"></div>' +
      '<canvas id="og-canvas" class="og-canvas" aria-label="Animated projected 3D scientific model network; movement is presentation only"></canvas>' +
      '<div class="og-data">' +
      '<div class="og-metric"><div class="og-metric-label">Scientific records</div><div class="og-metric-value" id="og-count">—</div><div class="og-metric-note">Immutable research records</div></div>' +
      '<div class="og-metric"><div class="og-metric-label">Exploratory studies (recent)</div><div class="og-metric-value" id="og-exploratory">—</div><div class="og-metric-note">Unqualified until independent verification</div></div>' +
      '<div class="og-metric"><div class="og-metric-label">Rejected studies (recent)</div><div class="og-metric-value" id="og-rejected">—</div><div class="og-metric-note">Failure knowledge preserved</div></div>' +
      '</div><div class="og-coordinates" id="og-coordinates">SCIENCE // LOADING<br>DATA LINK // VERIFYING<br>FRAME RATE // —</div>' +
      '<div class="og-selection"><div class="og-selection-title">SCIENCE NODE / INSPECT</div>' +
      '<div class="og-selection-detail" id="og-selected">Select a recorded research study or artifact. Ambient geometry is decorative.</div></div>' +
      '<div class="og-viewmodes" role="group" aria-label="Research animation mode">' +
      '<button class="og-mode" type="button" data-og-mode="cosmos" aria-pressed="true">COSMOS</button>' +
      '<button class="og-mode" type="button" data-og-mode="lattice" aria-pressed="false">LATTICE</button>' +
      '<button class="og-mode" type="button" data-og-mode="helix" aria-pressed="false">HELIX</button>' +
      '<button class="og-mode" type="button" data-og-mode="rift" aria-pressed="false">RIFT</button>' +
      '</div><div class="og-footer"><span id="og-data-status">SOURCE: RESEARCH LEDGER ONLY</span>' +
      '<span><em>DECORATIVE MOTION</em> ≠ MODEL ACTIVITY</span></div></div>' +
      '<div class="og-table"><div><strong>Scientific authority:</strong> APEX / DAEDALUS gates are independent. No auto-promotion.</div>' +
      '<div>Research telemetry is fetched from the authenticated local ICARUS API.</div></div></section>';
  }

  function createScene(root) {
    var canvas = root.querySelector('#og-canvas'), ctx = canvas.getContext('2d', {alpha: true});
    if (!ctx) { root.querySelector('#og-selected').textContent = 'Canvas 2D unavailable in this browser.'; return null; }
    var reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    var random = rnd(0x1CA4A55);
    var dust = [];
    for (var i = 0; i < 280; i++) {
      dust.push({
        x: (random() - .5) * 1500, y: (random() - .5) * 1000,
        z: (random() - .5) * 1300,
        radius: .3 + random() * 1.1,
        speed: .06 + random() * .35,
        phase: random() * Math.PI * 2,
        warm: random() > .77
      });
    }
    var nodes = [], mode = 'cosmos', w = 1, h = 1, scale = 1, angle = 0,
      panX = 0, panY = 0, zoom = 1, mouseX = 0, mouseY = 0, drag = null,
      frame = 0, lastFrame = 0, fps = 0, fpsFrames = 0, fpsClock = 0, rafId = 0,
      selectedNode = null, destroyed = false, time = 0, visible = true;

    function resize() {
      if (!canvas.isConnected || destroyed) return;
      var box = canvas.getBoundingClientRect();
      w = Math.max(1, box.width); h = Math.max(1, box.height);
      scale = Math.min(1.75, window.devicePixelRatio || 1);
      canvas.width = Math.round(w * scale);
      canvas.height = Math.round(h * scale);
      ctx.setTransform(scale, 0, 0, scale, 0, 0);
    }
    var observer = new ResizeObserver(resize);
    observer.observe(canvas);
    resize();

    function project(x, y, z, rotate) {
      var rx = rotate * .39 + mouseX * .13;
      var ry = rotate + mouseY * .08;
      var ca = Math.cos(ry), sa = Math.sin(ry);
      var x1 = x * ca - z * sa;
      var z1 = x * sa + z * ca;
      var cb = Math.cos(rx), sb = Math.sin(rx);
      var y2 = y * cb - z1 * sb;
      var z2 = y * sb + z1 * cb;
      var perspective = (700 / Math.max(110, 760 + z2)) * zoom;
      return {x: w * .56 + panX + x1 * perspective,
              y: h * .49 + panY + y2 * perspective, z: z2,
              perspective: perspective};
    }
    function line(points, color, alpha, width, glow) {
      if (points.length < 2) return;
      ctx.save();
      ctx.strokeStyle = color;
      ctx.globalAlpha = alpha;
      ctx.lineWidth = width;
      ctx.shadowColor = color;
      ctx.shadowBlur = glow;
      ctx.beginPath();
      ctx.moveTo(points[0].x, points[0].y);
      for (var i=1; i<points.length; i++) ctx.lineTo(points[i].x, points[i].y);
      ctx.stroke();
      ctx.restore();
    }
    function ring(radius, tilt, spin, palette, alpha, detail) {
      var pts = [];
      for (var i=0; i<=detail; i++) {
        var a = i / detail * Math.PI * 2;
        var zz = Math.sin(a) * radius * Math.sin(tilt);
        var yy = Math.sin(a) * radius * Math.cos(tilt);
        pts.push(project(Math.cos(a + spin * .23) * radius, yy, zz, angle + spin));
      }
      line(pts, palette, alpha, .7 + Math.max(.6, radius / 300), 5);
      var dot = pts[Math.floor((time * 13 + tilt * 12) % detail)];
      ctx.save();ctx.fillStyle=palette;ctx.shadowColor=palette;ctx.shadowBlur=16;
      ctx.beginPath();ctx.arc(dot.x, dot.y, 2.4, 0, Math.PI*2);ctx.fill();ctx.restore();
    }
    function dustfield() {
      for (var i=0; i<dust.length; i++) {
        var d=dust[i], a=angle*d.speed + d.phase;
        var pos=project(d.x*Math.cos(a)-d.z*Math.sin(a),
                        d.y+Math.sin(time*.7 + d.phase)*17,
                        d.x*Math.sin(a)+d.z*Math.cos(a), 0);
        if (pos.x<0 || pos.x>w || pos.y<0 || pos.y>h || pos.z < -650) continue;
        ctx.save();ctx.globalAlpha=clamp(.18+(1-pos.z/900)*.42, .09, .74);
        ctx.fillStyle=d.warm?'#ffcaa8':'#f56a9d';
        ctx.beginPath();ctx.arc(pos.x,pos.y,d.radius*clamp(pos.perspective,.3,2),0,Math.PI*2);ctx.fill();
        ctx.restore();
      }
    }
    function flowField() {
      // Continuously rotating 3D surfaces: presentation only, not agent telemetry.
      var base = mode === 'lattice' ? 260 : mode === 'helix' ? 230 : mode === 'rift' ? 300 : 250;
      for (var band=0; band<7; band++) {
        var curve=[];
        for (var i=0; i<=90; i++) {
          var t=i/90*Math.PI*2;
          var phase=t*(mode==='helix'?3.5:1.0)+band*.9+time*.36;
          var radius=base*(.68+.14*Math.sin(6*t+band)+.08*Math.sin(time*.9+band));
          var z=mode==='helix' ? (i/90-.5)*580 :
                mode==='rift' ? Math.cos(t*3+time*.6+band)*150 :
                Math.sin(t*2+band+time*.5)*90;
          var xx=mode==='lattice'?(Math.sin(phase)*radius):Math.cos(phase)*radius;
          var yy=mode==='lattice'?(Math.cos(phase*2)*radius*.57):Math.sin(phase)*radius*.57;
          curve.push(project(xx,yy,z+Math.sin(phase*2)*30,angle*.33+band*.27));
        }
        line(curve, band%3===0?'#ecba8f':band%2===0?'#e0458a':'#c82052',
             .20 + .08*Math.sin(time+band), band%3===0?1.3:.7, band%3===0?12:4);
      }
      for (var i=0; i<5; i++) {
        ring(104+i*34, .25+i*.47, time*(i%2===0?1:-1)*.19+i,
             i%3===0?'#d8b995':i%2===0?'#f65c87':'#902c64',
             .24+.08*Math.sin(time+i), 105);
      }
    }
    function genesisCore() {
      var center=project(0,0,0,angle);
      var breathe=1 + (reduced?0:Math.sin(time*2.4)*.08);
      var g=ctx.createRadialGradient(center.x,center.y,2,center.x,center.y,120*zoom);
      g.addColorStop(0,'#fff7edbd');g.addColorStop(.06,'#ff759ab0');
      g.addColorStop(.2,'#e9317270');g.addColorStop(1,'#ad244400');
      ctx.fillStyle=g;ctx.beginPath();ctx.arc(center.x,center.y,120*zoom,0,Math.PI*2);ctx.fill();
      ctx.save();ctx.translate(center.x,center.y);ctx.rotate(time*.9);
      for(var k=0;k<10;k++){
        ctx.rotate(Math.PI/5);ctx.fillStyle=k%2===0?'#ff5d92aa':'#e8bf8a89';
        ctx.beginPath();ctx.moveTo(0,-12*breathe*zoom);ctx.lineTo(4,-4);
        ctx.lineTo(0,6);ctx.lineTo(-4,-4);ctx.closePath();ctx.fill();
      }
      ctx.restore();
      ctx.save();ctx.fillStyle='#ffece5';ctx.shadowColor='#ff4c7c';ctx.shadowBlur=26;
      ctx.beginPath();ctx.arc(center.x,center.y,5*breathe*zoom,0,Math.PI*2);ctx.fill();ctx.restore();
    }
    function researchNodes() {
      var positions=[], rot=angle*.42;
      for(var i=0;i<nodes.length;i++){
        var n=nodes[i];
        var z=n.z+(reduced?0:Math.sin(time*.7+n.phase)*21);
        var pos=project(n.x,n.y,z,rot);
        positions.push({n:n,pos:pos});
      }
      positions.sort(function(a,b){return b.pos.z-a.pos.z;});
      var center=project(0,0,0,angle);
      positions.forEach(function(item){
        var n=item.n,p=item.pos;
        var supported=n.data.status==='EXPLORATORY';
        var color=n.data.scientific_kind==='ARTIFACT'?'#9ac4ff':supported?'#f7d8a4':'#ff3c75';
        ctx.save();
        ctx.strokeStyle=color;ctx.globalAlpha=.24;ctx.lineWidth=.6;
        ctx.beginPath();ctx.moveTo(center.x,center.y);ctx.lineTo(p.x,p.y);ctx.stroke();
        ctx.restore();
        var size=clamp(6*p.perspective,3,12);
        ctx.save();ctx.strokeStyle=color;ctx.lineWidth=1.2;ctx.shadowColor=color;ctx.shadowBlur=18;
        ctx.beginPath();ctx.arc(p.x,p.y,size*1.9+(reduced?0:Math.sin(time*2.2+n.phase)*2),0,Math.PI*2);
        ctx.globalAlpha=.45;ctx.stroke();ctx.globalAlpha=1;
        ctx.fillStyle=color;ctx.beginPath();ctx.arc(p.x,p.y,size,0,Math.PI*2);ctx.fill();
        ctx.restore();
      });
      return positions;
    }
    function render(now) {
      if(destroyed || !canvas.isConnected){stop();return;}
      if(!visible){rafId=0;return;}
      if(!lastFrame) lastFrame=now;
      var delta=Math.min(.05,Math.max(0,(now-lastFrame)/1000));lastFrame=now;
      if(!reduced){time+=delta;angle+=delta*(mode==='rift'?.17:.10);}
      frame++;fpsFrames++;
      if(now-fpsClock>=1000){fps=Math.round(fpsFrames*1000/Math.max(1,now-fpsClock));fpsFrames=0;fpsClock=now;updateCoordinates();}
      ctx.clearRect(0,0,w,h);
      dustfield();flowField();genesisCore();
      activePositions=researchNodes();
      if(!reduced)rafId=requestAnimationFrame(render);
    }
    var activePositions=[];
    function updateCoordinates() {
      var field=root.querySelector('#og-coordinates');
      if(!field) return;
      field.innerHTML='SCIENCE // '+(nodes.length?'RECORDS FOUND':'NO STUDIES')+
        '<br>DISPLAY // '+mode.toUpperCase()+
        '<br>NODE COUNT // '+nodes.length+
        '<br>RENDER // '+(reduced?'REDUCED MOTION':fps+' FPS')+
        '<br>ENGINE // SHADOW ONLY'+
        '<br><strong>AUTHORITY: NONE</strong>';
    }
    function stop() {destroyed=true;cancelAnimationFrame(rafId);observer.disconnect();document.removeEventListener('visibilitychange',visibility);root.removeEventListener('pointerdown',onDown);root.removeEventListener('pointerup',onUp);root.removeEventListener('pointermove',onMove);root.removeEventListener('wheel',onWheel); }
    function visibility() {
      visible=!document.hidden;
      if(visible&&!destroyed){lastFrame=0;fpsClock=performance.now();fpsFrames=0;rafId=requestAnimationFrame(render);}
    }
    document.addEventListener('visibilitychange',visibility);
    function updateRows(rows) {
      nodes=(Array.isArray(rows)?rows:[]).slice(0,100).map(function(r,i){
        var hash=codeHash(r.study_id), t=i*2.39996322972865;
        var radial=130+Math.sqrt(i+1)*34+(hash%19);
        return {data:r,phase:(hash%1000)/159.15,
          x:Math.cos(t)*radial, y:Math.sin(t)*radial*.65,
          z:Math.sin(t*.83)*radial*.48, seed:hash};
      });
      updateCoordinates();
      if(reduced)render(performance.now());
    }
    function onDown(ev){
      if(ev.target !== canvas) return;
      drag={x:ev.clientX,y:ev.clientY,px:panX,py:panY,a:angle};
      canvas.setPointerCapture(ev.pointerId);
    }
    function onMove(ev){
      if(!drag) return;
      var dx=ev.clientX-drag.x,dy=ev.clientY-drag.y;
      if(ev.shiftKey){panX=drag.px+dx;panY=drag.py+dy;}
      else{angle=drag.a+dx*.005;mouseY=clamp(dy*.01,-2,2);}
      if(reduced)render(performance.now());
    }
    function onUp(ev){
      if(!drag)return;
      var distance=Math.hypot(ev.clientX-drag.x,ev.clientY-drag.y);
      drag=null;
      if(distance>8)return;
      var box=canvas.getBoundingClientRect(),px=ev.clientX-box.left,py=ev.clientY-box.top;
      var candidate=null,best=23;
      activePositions.forEach(function(n){
        var d=Math.hypot(px-n.pos.x,py-n.pos.y);
        if(d<best){best=d;candidate=n.n.data;}
      });
      if(candidate){
        selectedNode=candidate.study_id;
        var delta=Number(candidate.holdout_brier_improvement);
        root.querySelector('#og-selected').textContent=
          'STUDY '+candidate.study_id.slice(0,14)+
          ' | ASSET '+candidate.asset+
          ' | '+candidate.status+
          ' | DATASET '+candidate.dataset_id+
          ' | ΔBRIER '+(Number.isFinite(delta)?delta.toFixed(6):'UNAVAILABLE')+
          ' | RESEARCH ONLY';
      }
    }
    function onWheel(ev){
      if(ev.target!==canvas)return;
      ev.preventDefault();
      zoom=clamp(zoom*(ev.deltaY<0?1.08:.92),.44,2.6);
      if(reduced)render(performance.now());
    }
    root.addEventListener('pointerdown',onDown);
    root.addEventListener('pointermove',onMove);
    root.addEventListener('pointerup',onUp);
    root.addEventListener('wheel',onWheel,{passive:false});
    root.querySelectorAll('[data-og-mode]').forEach(function(button){
      button.addEventListener('click',function(){
        mode=button.getAttribute('data-og-mode');
        root.querySelectorAll('[data-og-mode]').forEach(function(b){
          b.setAttribute('aria-pressed', String(b===button));
        });
        updateCoordinates();
        if(reduced)render(performance.now());
      });
    });
    rafId=requestAnimationFrame(render);
    return {root:root,stop:stop,updateRows:updateRows};
  }

  function researchRows(snapshot) {
    var rows=(snapshot.recent_studies||[]).slice(0,100).map(function(s){
      return Object.assign({scientific_kind:'STUDY'},s);
    });
    (snapshot.recent_artifacts||[]).slice(0,100).forEach(function(a){
      if(!a || !a.research_only) return;
      rows.push({
        study_id:a.artifact_id,
        asset:a.kind.toUpperCase(),
        dataset_id:a.title,
        status:a.status,
        scientific_kind:'ARTIFACT',
        holdout_brier_improvement:null
      });
    });
    return rows.slice(0,100);
  }

  function loadOmnigenesis() {
    var root=document.getElementById('og-root');
    if(!root || !active || active.root!==root) return Promise.resolve();
    if(inFlight)return inFlight;
    if(!window.IcarusClient || typeof window.IcarusClient.request!=='function') {
      root.querySelector('#og-data-status').textContent='AUTHENTICATED ICARUS CLIENT UNAVAILABLE';
      return Promise.resolve();
    }
    inFlight=window.IcarusClient.request('/api/omnigenesis', {cache:'no-store'}).then(function(response){
      if(!response.ok)throw new Error('Research API HTTP '+response.status);
      return response.json();
    }).then(function(snapshot){
      if(!snapshot || snapshot.schema_version!=='icarus-omnigenesis-snapshot-v1' ||
         snapshot.status!=='RESEARCH_ONLY' ||
         !snapshot.authority || snapshot.authority.execution_authorized!==false ||
         snapshot.authority.production_decision_authorized!==false ||
         !Array.isArray(snapshot.recent_studies)) {
        throw new Error('Invalid research-only snapshot');
      }
      cached=snapshot;
      if(active && active.root===root && root.isConnected) {
        root.querySelector('#og-count').textContent=String(snapshot.study_count+(snapshot.artifact_count||0));
        root.querySelector('#og-exploratory').textContent=String(snapshot.recent_studies.filter(function(s){return s.status==='EXPLORATORY';}).length);
        root.querySelector('#og-rejected').textContent=String(snapshot.recent_studies.filter(function(s){return s.status==='REJECTED';}).length);
        root.querySelector('#og-data-status').textContent='LOCAL LEDGER VERIFIED / '+researchRows(snapshot).length+' DISPLAYED RECORDS';
        active.updateRows(researchRows(snapshot));
      }
    }).catch(function(e){
      if(active && active.root===root && root.isConnected) {
        root.querySelector('#og-data-status').textContent='RESEARCH LEDGER UNAVAILABLE';
        root.querySelector('#og-selected').textContent='Research snapshot could not be verified: '+(e.message||String(e));
      }
    }).finally(function(){inFlight=null;});
    return inFlight;
  }

  function wireOmnigenesis() {
    var root=document.getElementById('og-root');
    if(!root) return;
    if(active && active.root===root)return;
    if(active)active.stop();
    active=createScene(root);
    if(!active)return;
    if(cached){active.updateRows(researchRows(cached));}
    loadOmnigenesis();
  }
  window.omnigenesisHtml=omnigenesisHtml;
  window.wireOmnigenesis=wireOmnigenesis;
  window.loadOmnigenesis=loadOmnigenesis;
})();
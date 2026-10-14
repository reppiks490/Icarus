/* Original cosmic sculpture. Presentation only; the existing caller owns time and scheduling. */
(() => {
  'use strict';
  const root=document.documentElement, previousAura=window.IcarusWorldAura, previousCinema=window.IcarusWorldCinema;
  const reduced=window.matchMedia('(prefers-reduced-motion: reduce)'), forced=window.matchMedia('(forced-colors: active)');
  const worlds={divine:0,void:1,astral:2}, palettes={divine:['#f7dfac','#fff9df'],void:['#e96c96','#ffd8c6'],astral:['#91bddd','#e7efef']};
  const motion=()=>!document.hidden&&!reduced.matches&&!forced.matches&&root.dataset.motion!=='off';
  const finite=n=>Number.isFinite(n), clamp=(n,a,b)=>Math.max(a,Math.min(b,n));
  const vertex='attribute vec2 aPosition; void main(){gl_Position=vec4(aPosition,0.0,1.0);}';
  const fragment=`
    #ifdef GL_FRAGMENT_PRECISION_HIGH
    precision highp float;
    #else
    precision mediump float;
    #endif
    uniform vec2 uResolution,uPointer;
    uniform float uTime,uWorld,uMobile,uIntro,uProgress;
    const float PI=3.14159265;
    float hash(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);}
    float noise(vec2 p){
      vec2 i=floor(p),f=fract(p);f=f*f*(3.0-2.0*f);
      return mix(mix(hash(i),hash(i+vec2(1.,0.)),f.x),mix(hash(i+vec2(0.,1.)),hash(i+vec2(1.)),f.x),f.y);
    }
    float fbm(vec2 p){float n=0.,a=.5;for(int i=0;i<4;i++){n+=noise(p)*a;p=mat2(1.7,-1.2,1.2,1.7)*p+7.9;a*=.5;}return n;}
    vec3 cool(){return uWorld<.5?vec3(.18,.31,.46):uWorld<1.5?vec3(.31,.09,.39):vec3(.045,.39,.38);}
    vec3 warm(){return uWorld<.5?vec3(1.,.69,.28):uWorld<1.5?vec3(.99,.31,.20):vec3(.94,.55,.25);}
    vec3 pearl(){return uWorld<.5?vec3(1.,.96,.79):uWorld<1.5?vec3(1.,.81,.75):vec3(.84,.98,.93);}
    vec3 cloud(vec2 p,float t){
      vec2 flow=vec2(t*.006,-t*.004);
      vec2 warp=vec2(fbm(p*2.4+flow),fbm(p*2.4-flow+5.3));
      float n=fbm(p*4.+warp*2.4+flow),filament=fbm(p*10.+warp*2.7-flow);
      float depth=fbm(p*20.+warp*3.1);
      float thread=pow(max(0.,1.-abs(filament-.5)*8.),3.);
      vec3 gas=mix(vec3(.095,.035,.20),cool()*1.7,smoothstep(.36,.76,n));
      gas=mix(gas,warm()*.95,smoothstep(.48,.78,warp.y)*smoothstep(.42,.75,n));
      float density=smoothstep(.25,.79,n)*(.25+filament*.95);
      gas*=density;
      gas+=mix(cool()*1.8,pearl(),depth)*thread*density*.25;
      return gas;
    }
    // A true open quadratic surface: curved normals, taper and material coordinates
    // remain attached to the same body as the camera crosses it.
    vec4 foil(vec2 p,vec2 a,vec2 b,vec2 c,float width,float phase,float t){
      vec2 ab=b-a,bc=c-b,acc=bc-ab;
      float s=clamp(dot(p-a,c-a)/dot(c-a,c-a),.001,.999);
      for(int i=0;i<4;i++){
        vec2 q=a+2.*ab*s+acc*s*s,d=2.*(ab+acc*s);
        s=clamp(s-dot(q-p,d)/max(dot(d,d)+2.*dot(q-p,acc),.035),0.,1.);
      }
      vec2 q=a+2.*ab*s+acc*s*s,tangent=normalize(ab+acc*s),normal=vec2(-tangent.y,tangent.x);
      float taper=.045+.955*pow(max(sin(PI*s),0.),.62);
      float w=width*taper,across=dot(p-q,normal)/max(w,.004);
      float ends=smoothstep(0.,.025,s)*(1.-smoothstep(.965,1.,s));
      float aa=max(1.4/uResolution.y,.0015),distanceToEdge=(abs(across)-1.)*w;
      float cover=(1.-smoothstep(-aa,aa,distanceToEdge))*ends;
      float curvature=sqrt(max(1.-across*across,0.));
      vec3 N=normalize(vec3(normal*clamp(across,-1.,1.),curvature+.03));
      // Staggered enamel shingles compress naturally at the grazing sides.
      float v=asin(clamp(across,-.998,.998))/PI*9.0+phase;
      float row=floor(v),u=s*55.+phase+mod(row,2.)*.5;
      vec2 cell=vec2(fract(u)-.5,fract(v));
      float ridge=cell.y-(.20+.72*cell.x*cell.x);
      float seam=exp(-abs(ridge)*65.)*smoothstep(-.86,-.38,across)*(1.-smoothstep(.84,.99,abs(across)));
      float facet=smoothstep(.04,.45,cell.y)*(1.-smoothstep(.36,.92,cell.y));
      float relief=sin(cell.x*PI*2.)*facet*.24;
      N=normalize(N+vec3(tangent*relief-normal*facet*.055,facet*.16));
      vec3 L=normalize(vec3(-.42,.66,1.1)),V=vec3(0.,0.,1.);
      float diffuse=.18+.82*max(0.,dot(N,L));
      float spec=pow(max(0.,dot(N,normalize(L+V))),54.);
      float fresnel=pow(1.-max(N.z,0.),2.2);
      float illumination=.65+.35*sin(s*5.-t*.10+phase);
      vec3 iridescence=.5+.5*cos(vec3(.3,2.3,4.4)+across*5.+s*4.+phase);
      vec3 body=mix(vec3(.048,.027,.088),cool()*.67,smoothstep(-.4,.8,across));
      body=mix(body,warm()*.35,smoothstep(.45,.8,s)*.65);
      vec3 material=body*diffuse+mix(pearl(),warm(),.4)*spec*.32;
      material+=iridescence*(fresnel*.17+facet*.04)*illumination;
      material+=mix(pearl(),warm(),cell.x+.5)*seam*(.21+spec*.56)*illumination;
      // Subsurface fold and a thin continuous warm edge define actual thickness.
      material+=warm()*exp(-abs(across+.72)*16.)*.115;
      float rim=exp(-abs(distanceToEdge)*min(350.,uResolution.y*.78))*ends;
      float inner=exp(-abs(distanceToEdge+.010)*180.)*cover;
      vec3 edge=mix(pearl(),warm(),smoothstep(-.5,.7,across))*(rim*(.47+.34*illumination)+inner*.13);
      material+=edge;
      float sheen=exp(-pow((s-(.39+.17*sin(t*.065+phase)))*11.,2.));
      material+=pearl()*sheen*spec*.22;
      return vec4(material,clamp(cover+rim*.5,0.,1.));
    }
    void composite(inout vec3 color,inout float opacity,vec4 layer){
      color=mix(color,layer.rgb,layer.a);opacity=max(opacity,layer.a*.96);
    }
    void main(){
      vec2 uv=gl_FragCoord.xy/uResolution;
      vec2 center=mix(vec2(mix(.76,.5,uMobile),mix(.52,.31,uMobile)),vec2(.5,.54),uIntro);
      vec2 p=(uv-center)*vec2(uResolution.x/uResolution.y,1.);
      float t=uTime,finale=uIntro*smoothstep(.71,.9,uProgress);
      vec2 camera=vec2(sin(t*.085),cos(t*.074))*.013+uPointer*vec2(.025,.020);
      vec2 far=p+camera*.25;
      vec2 near=p+camera;
      near.y+=uIntro*(smoothstep(.18,.70,uProgress)-.45)*.13;
      near.x-=finale*.12;
      vec3 color=cloud(far,t)*1.55;
      float opacity=.43+smoothstep(.12,.45,length(color))*.25;
      // A distant off-axis star illuminates the sculpture instead of closing it into a ring.
      vec2 lightPos=mix(vec2(.31,.19),vec2(-.31,.19),finale);
      float rr=length(far-lightPos),radius=mix(.072,.20,finale);
      float granular=fbm((far-lightPos)*27.+vec2(t*.01,0.));
      float disc=1.-smoothstep(radius-.004,radius+.004,rr);
      float corona=exp(-max(rr-radius,0.)*13.)*.24+exp(-max(rr-radius,0.)*45.)*.24;
      color+=warm()*corona*(.35+finale*.7);
      color=mix(color,mix(warm(),pearl(),.48+granular*.46),disc*(.72+finale*.28));
      opacity=max(opacity,disc*.96);
      // The rear feather, the upper folded sail and the near crop have distinct transforms.
      vec2 sweep=near+vec2(sin(t*.065)*.012,cos(t*.081)*.009);
      vec4 rear=foil(sweep,vec2(-.69,.70),vec2(-.23,-.44),vec2(1.02,.36),.090,2.7,t);
      composite(color,opacity,rear);
      vec4 sail=foil(sweep+vec2(.01,-.02),vec2(-.10,.81),vec2(.09,.16),vec2(1.08,.22),.142,.8,t);
      composite(color,opacity,sail);
      // A smaller overlapping petal gives the upper edge a feathered, asymmetric crest.
      vec4 crest=foil(sweep,vec2(.17,.76),vec2(.29,.31),vec2(.87,.35),.057,4.3,t);
      composite(color,opacity,crest);
      vec2 front=near+vec2(sin(t*.093)*.018,cos(t*.068)*.016);
      vec4 lower=foil(front,vec2(-.82,-.54),vec2(-.13,-.23),vec2(.93,-.71),.119,5.2,t);
      composite(color,opacity,lower);
      float occlusion=max(max(rear.a,sail.a),max(crest.a,lower.a));
      // Depth-separated motes: sparse bright rear points and soft near bokeh.
      for(int i=0;i<3;i++){
        float layer=float(i)+1.;vec2 grid=(p+camera*layer+vec2(t*.003*layer,-t*.004*layer))*mix(58.,17.,float(i)/2.);
        vec2 id=floor(grid),f=fract(grid)-.5;
        float seed=hash(id+layer*19.7),star=exp(-dot(f,f)*mix(620.,70.,float(i)/2.))*step(.984,seed);
        float flicker=.74+.26*sin(t*(.19+seed*.23)+seed*19.);
        color+=mix(pearl(),cool()*1.7,float(i)/2.)*star*flicker*(1.-occlusion*.86)*.65;
      }
      if(uIntro>.5){
        float ignition=1.-smoothstep(.08,.26,uProgress);
        float column=exp(-pow((p.x+.16*sin(p.y*2.))*4.5,2.));
        float streak=pow(max(0.,sin(p.x*105.+noise(vec2(p.x*8.,0.))*8.)),18.);
        float ascent=smoothstep(-.7,.4,p.y+uProgress*3.);
        vec3 shafts=mix(warm(),cool()*1.8,smoothstep(-.3,.2,p.x))*(column*.25+streak*.17)*ascent;
        color=mix(color*.52,color,1.-ignition)+shafts*ignition;
        opacity=max(opacity,ignition*.67);
      }
      float vignette=1.-smoothstep(.3,1.4,length(p*vec2(.75,1.)));
      color*=.80+.20*vignette;
      color+=vec3((hash(gl_FragCoord.xy+floor(t*4.))-.5)*.006);
      float safe=mix(smoothstep(.29,.64,uv.x),1.-smoothstep(.29,.72,uv.y),uMobile);
      safe=mix(safe,1.,uIntro);
      float reveal=mix(1.,smoothstep(0.,.075,uProgress),uIntro);
      gl_FragColor=vec4(clamp(color,0.,1.),opacity*safe*reveal);
    }`;

  function create(scene,{intro=false}={}) {
    const canvas=document.createElement('canvas');canvas.className='world-aura reference-nebula'+(intro?' reference-intro':'');
    canvas.setAttribute('aria-hidden','true');canvas.style.opacity='0';scene.prepend(canvas);
    let gl,program,buffer,uniforms,ready=false,lost=false,disposed=false,last=-Infinity,lastWorld='',fallback;
    const shaders=[];
    function release(){
      if(gl&&!lost){if(program)gl.deleteProgram(program);if(buffer)gl.deleteBuffer(buffer);for(const s of shaders)gl.deleteShader(s);}
      shaders.length=0;program=null;buffer=null;ready=false;
    }
    function backup(){if(!fallback)try{fallback=previousAura?.create(scene);}catch(_){}canvas.style.opacity='0';}
    function setup(){
      if(disposed)return;
      try {
        gl=gl||canvas.getContext('webgl',{alpha:true,antialias:false,depth:false,stencil:false,premultipliedAlpha:false,powerPreference:'low-power'});
        if(!gl)throw Error('WebGL unavailable');
        for(const [type,source] of [[gl.VERTEX_SHADER,vertex],[gl.FRAGMENT_SHADER,fragment]]){
          const shader=gl.createShader(type);if(!shader)throw Error('Shader unavailable');
          shaders.push(shader);gl.shaderSource(shader,source);gl.compileShader(shader);
          if(!gl.getShaderParameter(shader,gl.COMPILE_STATUS))throw Error('Shader compilation unavailable');
        }
        program=gl.createProgram();if(!program)throw Error('Program unavailable');
        for(const shader of shaders)gl.attachShader(program,shader);gl.linkProgram(program);
        if(!gl.getProgramParameter(program,gl.LINK_STATUS))throw Error('Program linking unavailable');
        gl.useProgram(program);buffer=gl.createBuffer();if(!buffer)throw Error('Buffer unavailable');
        gl.bindBuffer(gl.ARRAY_BUFFER,buffer);gl.bufferData(gl.ARRAY_BUFFER,new Float32Array([-1,-1,1,-1,-1,1,-1,1,1,-1,1,1]),gl.STATIC_DRAW);
        const position=gl.getAttribLocation(program,'aPosition');if(position<0)throw Error('Attribute unavailable');
        gl.enableVertexAttribArray(position);gl.vertexAttribPointer(position,2,gl.FLOAT,false,0,0);
        uniforms=Object.fromEntries(['uResolution','uPointer','uTime','uWorld','uMobile','uIntro','uProgress'].map(n=>[n,gl.getUniformLocation(program,n)]));
        gl.clearColor(0,0,0,0);ready=true;last=-Infinity;canvas.dataset.state='ready';
        if(!scene.children || !Array.from(scene.children).includes(canvas))scene.prepend(canvas);
      }catch(_){release();canvas.dataset.state='fallback';canvas.remove();backup();}
    }
    function pause(){last=-Infinity;canvas.style.opacity='0';fallback?.pause();if(ready&&!lost)try{gl.clear(gl.COLOR_BUFFER_BIT);}catch(_){} }
    function draw(time,world,width,height,pointer={},detail='rich'){
      if(disposed)return;
      if(!motion()||(!intro&&root.dataset.experience!=='cinematic')||scene.hidden||detail==='light')return pause();
      if(!finite(time)||!finite(width)||!finite(height)||width<=0||height<=0||!(world in worlds))return pause();
      if(!ready||lost){fallback?.draw(time,world,width,height,pointer,detail);return;}
      if(world===lastWorld&&time>=last&&time-last<1/30)return;last=time;lastWorld=world;
      try {
        const ratio=Math.min(.85,960/width,560/height),w=clamp(Math.round(width*ratio),1,960),h=clamp(Math.round(height*ratio),1,560);
        if(canvas.width!==w||canvas.height!==h){canvas.width=w;canvas.height=h;gl.viewport(0,0,w,h);}
        gl.useProgram(program);gl.uniform2f(uniforms.uResolution,w,h);
        gl.uniform2f(uniforms.uPointer,finite(pointer?.x)?clamp(pointer.x,-.5,.5):0,finite(pointer?.y)?clamp(pointer.y,-.5,.5):0);
        // A bounded, continuous ambient phase also supports mediump-only mobile GPUs.
        gl.uniform1f(uniforms.uTime,intro?time:Math.sin(time/900)*900);gl.uniform1f(uniforms.uWorld,worlds[world]);gl.uniform1f(uniforms.uMobile,width<700?1:0);
        gl.uniform1f(uniforms.uIntro,intro?1:0);gl.uniform1f(uniforms.uProgress,intro?clamp(time/(root.dataset.introLength==='12'?12:20),0,1):0);
        gl.drawArrays(gl.TRIANGLES,0,6);canvas.style.opacity='1';
      }catch(_){release();canvas.dataset.state='fallback';canvas.remove();backup();fallback?.draw(time,world,width,height,pointer,detail);}
    }
    const onLost=event=>{event.preventDefault();lost=true;release();last=-Infinity;canvas.dataset.state='lost';backup();};
    const onRestored=()=>{if(disposed)return;lost=false;fallback?.dispose();fallback=null;setup();};
    canvas.addEventListener('webglcontextlost',onLost);canvas.addEventListener('webglcontextrestored',onRestored);setup();
    function dispose(){if(disposed)return;disposed=true;release();fallback?.dispose();fallback=null;canvas.removeEventListener('webglcontextlost',onLost);canvas.removeEventListener('webglcontextrestored',onRestored);canvas.remove();}
    return Object.freeze({draw,pause,dispose,get active(){return ready&&!lost&&!disposed&&canvas.style.opacity==='1';}});
  }

  function profile(ctx,w,h,time,world,intro){
    if(!ctx||!w||!h)return;
    const [color,pearl]=palettes[world]||palettes.astral;
    const x=intro?w*.5:w<700?w*.5:w*.78,y=intro?h*.46:w<700?h*.73:h*.48;
    const r=Math.min(w*(intro?.5:.47),h*.4);
    // Two broad folded feathers keep real depth on touch screens without a GPU pass.
    ctx.save();
    for(let layer=0;layer<2;layer++){
      const points=[],count=32;
      for(let i=0;i<=count;i++){
        const u=i/count,along=(u-.5)*2.7;
        const bend=Math.sin(u*2.5+layer*1.6+time*.065)*.36;
        const lift=layer===0?-.3:.35;
        const thick=Math.pow(Math.max(0,Math.sin(u*Math.PI)),.75)*(.24+layer*.04)+.015;
        points.push({x:x+along*r,y:y+(bend+lift+along*(layer?-.3:.17))*r,thick:thick*r});
      }
      for(let i=0;i<count;i++){
        const a=points[i],b=points[i+1];
        const shade=ctx.createLinearGradient(a.x,a.y-a.thick,a.x,a.y+a.thick);
        shade.addColorStop(0,pearl+'bb');shade.addColorStop(.08,color+'52');
        shade.addColorStop(.36,'#171a29ee');shade.addColorStop(.79,'#090b17e8');shade.addColorStop(1,color+'7a');
        ctx.beginPath();ctx.moveTo(a.x,a.y-a.thick);ctx.lineTo(b.x,b.y-b.thick);
        ctx.lineTo(b.x,b.y+b.thick);ctx.lineTo(a.x,a.y+a.thick);ctx.closePath();
        ctx.fillStyle=shade;ctx.fill();
        if(i%2===0){
          const sheen=.2+.35*Math.pow(Math.max(0,Math.cos(i*.16-time*.18-layer)),8);
          ctx.strokeStyle=pearl+Math.round(sheen*255).toString(16).padStart(2,'0');ctx.lineWidth=.75;
          ctx.beginPath();ctx.moveTo(a.x,a.y-a.thick);
          ctx.bezierCurveTo(a.x+r*.06,a.y-a.thick*.15,a.x+r*.04,a.y+a.thick*.3,a.x+r*.09,a.y+a.thick*.75);ctx.stroke();
        }
      }
      for(const side of [-1,1]){
        ctx.beginPath();points.forEach((p,i)=>i?ctx.lineTo(p.x,p.y+p.thick*side):ctx.moveTo(p.x,p.y+p.thick*side));
        ctx.strokeStyle=pearl+(side<0?'9c':'48');ctx.lineWidth=.8;ctx.stroke();
      }
    }
    ctx.restore();
  }
  let heroRenderer,introRenderer,introTheater,introObserver,introStartedAt;
  function clearIntro(){
    introRenderer?.dispose();introRenderer=null;introTheater=null;introStartedAt=undefined;
    introObserver?.disconnect();introObserver=null;
  }
  function drawCinema(ctx,w,h,time,dt,options={}){
    const world=root.dataset.world in worlds?root.dataset.world:'divine';
    if(options.intro&&motion()){
      const theater=document.querySelector('.world-intro .intro-theater');
      const now=window.performance?.now()??time*1000;
      if(theater&&theater!==introTheater){
        clearIntro();introTheater=theater;introStartedAt=now;
        if(typeof MutationObserver!=='undefined'){
          introObserver=new MutationObserver(()=>{if(!introTheater?.isConnected)clearIntro();});
          introObserver.observe(document.body,{childList:true});
        }
      }
      // Scene physics retain the caller's bounded dt; the opening follows its real duration.
      if(theater)time=clamp((now-introStartedAt)/1000,0,root.dataset.introLength==='12'?12:20);
      if(theater&&options.detail!=='light'){
        if(!introRenderer)introRenderer=create(theater,{intro:true});
        introRenderer.draw(time,world,w,h,options.pointer,options.detail);
      }else{introRenderer?.pause();profile(ctx,w,h,time,world,true);}
    }else if(!options.intro&&motion()&&options.detail==='light')profile(ctx,w,h,time,world,false);
    else if(!motion())introRenderer?.pause();
    if(introTheater&&!introTheater.isConnected)clearIntro();
    // Existing geometry becomes a fine secondary light layer when the sculpted material is active.
    const sculpted=(options.intro?introRenderer:heroRenderer)?.active;
    if(sculpted&&ctx){ctx.save();ctx.globalAlpha=(finite(ctx.globalAlpha)?ctx.globalAlpha:1)*(options.intro?.2:.42);}
    previousCinema?.draw(ctx,w,h,time,dt,options);
    if(sculpted&&ctx)ctx.restore();
  }
  window.IcarusReferenceChoreography=Object.freeze({create});
  window.IcarusWorldAura=Object.freeze({create(scene){heroRenderer=create(scene);return heroRenderer;}});
  if(previousCinema)window.IcarusWorldCinema=Object.freeze({...previousCinema,draw:drawCinema});
})();

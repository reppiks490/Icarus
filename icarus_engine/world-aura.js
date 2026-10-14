/* Optional local GPU atmosphere. Its caller owns scheduling and motion gates. */
(() => {
  'use strict';
  const vertex=`attribute vec2 aPosition; void main(){gl_Position=vec4(aPosition,0.0,1.0);}`;
  const fragment=`
    precision mediump float;
    uniform vec2 uResolution;
    uniform vec2 uCenter;
    uniform float uTime;
    uniform float uWorld;
    uniform float uMobile;
    uniform float uView;
    float hash(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);}
    float noise(vec2 p){
      vec2 i=floor(p),f=fract(p);f=f*f*(3.0-2.0*f);
      return mix(mix(hash(i),hash(i+vec2(1.0,0.0)),f.x),mix(hash(i+vec2(0.0,1.0)),hash(i+vec2(1.0)),f.x),f.y);
    }
    float mist(vec2 p){float n=0.0;float a=.5;for(int i=0;i<3;i++){n+=noise(p)*a;p=p*2.03+11.7;a*=.5;}return n;}
    float band(float d,float sharp){return exp(-abs(d)*sharp);}
    void main(){
      vec2 uv=gl_FragCoord.xy/uResolution;
      vec2 p=(uv-uCenter)*vec2(uResolution.x/uResolution.y,1.0);
      float r=max(length(p),.002),a=atan(p.y,p.x),t=uTime,v=uView;
      float fog=mist(p*4.0+vec2(t*.025,-t*.017)+vec2(v*.17,-v*.11));
      float rim=band(r-.205-fog*.01,90.0);
      float glow=0.0;vec3 color=vec3(1.0);

      if(uWorld<.5){
        float rays=pow(max(0.0,sin(a*(23.0+v*1.35)+t*.08+fog*3.0+v*.41)),9.0);
        float outer=band(r-.335+sin(a*(6.0+v*.18)-t*.035+v*.27)*.006,58.0);
        float crown=pow(max(0.0,cos(a*6.0-t*.045)),22.0)*exp(-r*1.4);
        float arch=band(abs(p.x)-(.31+.045*cos(p.y*7.0+t*.04)),43.0)*(1.0-smoothstep(.1,.72,abs(p.y)));
        float horizon=band(p.y+.12+sin(p.x*(5.0+v*.12)+t*.025)*.008,52.0)*(1.0-smoothstep(.18,.9,abs(p.x)));
        float viewRing=band(r-(.40+.012*sin(a*(2.0+mod(v,3.0))+v*.8)),74.0);
        glow=(rays*.15+rim*.42+outer*.20+crown*.11+arch*.07+horizon*.045+viewRing*.045)*(.42+fog)*exp(-r*.82);
        vec3 gold=mix(vec3(.82,.47,.12),vec3(1.0,.93,.72),rim+outer*.45);
        color=mix(gold,vec3(.55,.94,.88),clamp(horizon*.35+fog*.08,0.0,.24));
      }else if(uWorld<1.5){
        float twist=pow(max(0.0,sin(a*3.0-log(r)*5.0-t*.24+fog*3.0)),5.0);
        float disk=band(p.y+sin(p.x*8.0+t*.1)*.024,22.0);
        float lens=band(r-.31-sin(a*4.0+t*.08)*.008,70.0);
        float fracture=pow(max(0.0,sin((p.x*(1.7+v*.035)-p.y)*24.0+fog*6.0-t*.09+v*.7)),18.0)*(1.0-smoothstep(.12,.72,r));
        float eclipse=band(r-.145,120.0);
        float viewCut=pow(max(0.0,sin((p.x+p.y*.7)*(10.0+v)+v*1.4)),24.0)*(1.0-smoothstep(.22,.78,r));
        glow=(twist*.19+disk*.12+rim*.31+lens*.20+fracture*.08+eclipse*.16+viewCut*.045)*(1.0-smoothstep(.18,.82,r));
        color=mix(vec3(.37,.015,.13),vec3(1.0,.08,.27),clamp(fog+rim*.34+lens*.25,0.0,1.0));
      }else{
        float wave=sin(p.x*13.0+sin(p.y*6.0+t*.13)*2.0+t*.12);
        float curtain=pow(max(0.0,wave),4.0)*(.3+fog);
        vec2 ep=vec2(p.x,p.y*1.55);
        float orbit=band(length(ep)-.31-sin(a*(3.0+v*.09)+t*.035+v*.33)*.005,62.0);
        float filament=band(sin(p.x*(7.0+v*.13)+p.y*4.0+t*.07+v*.5)*.10+p.y*.34,34.0)*(1.0-smoothstep(.2,.78,r));
        vec2 cell=floor((p+vec2(t*.001,-t*.0006))*42.0);
        float stars=pow(hash(cell),28.0)*(1.0-smoothstep(.15,.9,r));
        float viewOrbit=band(length(vec2(p.x,p.y*(1.2+mod(v,3.0)*.08)))-(.42+sin(v)*.012),82.0);
        glow=(curtain*.24+rim*.14+orbit*.19+filament*.07+stars*.12+viewOrbit*.045)*(1.0-smoothstep(.12,.86,r));
        color=mix(vec3(.31,.13,.78),vec3(.20,.90,1.0),clamp(fog*.72+wave*.13+orbit*.26+stars*.18,0.0,1.0));
      }

      float mask=mix(smoothstep(.24,.64,uv.x),1.0-smoothstep(.38,.72,uv.y),uMobile);
      float vignette=1.0-smoothstep(.62,1.05,length((uv-.5)*vec2(1.15,1.0)));
      gl_FragColor=vec4(color,clamp(glow*mask*(.72+.28*vignette),0.0,.58));
    }`;
  function create(scene) {
    const canvas=document.createElement('canvas');canvas.className='world-aura';canvas.setAttribute('aria-hidden','true');scene.prepend(canvas);
    let gl,program,buffer,uniforms,ready=false,lost=false,last=-1,disposed=false;
    const shaders=[];
    const release=()=>{
      if(gl&&!lost){if(program)gl.deleteProgram(program);if(buffer)gl.deleteBuffer(buffer);for(const s of shaders)gl.deleteShader(s);}
      shaders.length=0;program=null;buffer=null;ready=false;
    };
    function setup() {
      if(disposed)return;
      try {
        gl=gl||canvas.getContext('webgl',{alpha:true,antialias:false,depth:false,stencil:false,premultipliedAlpha:false,powerPreference:'low-power'});
        if(!gl)throw Error('WebGL unavailable');
        for(const [type,source] of [[gl.VERTEX_SHADER,vertex],[gl.FRAGMENT_SHADER,fragment]]) {
          const shader=gl.createShader(type);if(!shader)throw Error('Shader unavailable');
          shaders.push(shader);gl.shaderSource(shader,source);gl.compileShader(shader);
          if(!gl.getShaderParameter(shader,gl.COMPILE_STATUS))throw Error('Shader compilation unavailable');
        }
        program=gl.createProgram();if(!program)throw Error('Program unavailable');
        for(const shader of shaders)gl.attachShader(program,shader);
        gl.linkProgram(program);if(!gl.getProgramParameter(program,gl.LINK_STATUS))throw Error('Program linking unavailable');
        gl.useProgram(program);buffer=gl.createBuffer();if(!buffer)throw Error('Buffer unavailable');
        gl.bindBuffer(gl.ARRAY_BUFFER,buffer);gl.bufferData(gl.ARRAY_BUFFER,new Float32Array([-1,-1,1,-1,-1,1,-1,1,1,-1,1,1]),gl.STATIC_DRAW);
        const position=gl.getAttribLocation(program,'aPosition');gl.enableVertexAttribArray(position);gl.vertexAttribPointer(position,2,gl.FLOAT,false,0,0);
        uniforms=Object.fromEntries(['uResolution','uCenter','uTime','uWorld','uMobile','uView'].map(name=>[name,gl.getUniformLocation(program,name)]));
        gl.clearColor(0,0,0,0);ready=true;last=-1;canvas.dataset.state='ready';
      }catch(_){release();canvas.dataset.state='fallback';canvas.style.opacity='0';}
    }
    const onLost=event=>{event.preventDefault();lost=true;release();canvas.dataset.state='lost';canvas.style.opacity='0';};
    const onRestored=()=>{lost=false;setup();};
    canvas.addEventListener('webglcontextlost',onLost);canvas.addEventListener('webglcontextrestored',onRestored);setup();
    function pause(){last=-1;canvas.style.opacity='0';if(ready&&!lost)gl.clear(gl.COLOR_BUFFER_BIT);}
    function draw(time,world,width,height,pointer={x:0,y:0},detail='rich') {
      if(!ready||lost||disposed||!width||!height)return;
      if(detail==='light'){pause();return;}
      if(last>=0&&time-last<1/15)return;last=time;
      const ratio=Math.min(.65,900/width,480/height),w=Math.max(1,Math.round(width*ratio)),h=Math.max(1,Math.round(height*ratio));
      if(canvas.width!==w||canvas.height!==h){canvas.width=w;canvas.height=h;gl.viewport(0,0,w,h);}
      const mobile=width<700;gl.useProgram(program);gl.uniform2f(uniforms.uResolution,w,h);
      gl.uniform2f(uniforms.uCenter,(mobile?.5:.76)+pointer.x*.012,1-(mobile?.71:.47)-pointer.y*.012);
      const view=root.dataset.worldView||'overview';
      const viewCode=['research','sources','market-data'].includes(view)?1:
        ['brain','learning','evolution'].includes(view)?2:
        ['parallax','possibility','sibyl','chronofold'].includes(view)?3:
        ['pantheon','apex','ascendancy'].includes(view)?4:
        ['system','integrity','engine-control','commissioning','commands','log','autopilot'].includes(view)?5:0;
      gl.uniform1f(uniforms.uTime,time%600);gl.uniform1f(uniforms.uWorld,world==='void'?1:world==='astral'?2:0);gl.uniform1f(uniforms.uMobile,mobile?1:0);gl.uniform1f(uniforms.uView,viewCode);
      gl.drawArrays(gl.TRIANGLES,0,6);canvas.style.opacity='1';
    }
    function dispose(){if(disposed)return;release();disposed=true;canvas.removeEventListener('webglcontextlost',onLost);canvas.removeEventListener('webglcontextrestored',onRestored);canvas.remove();}
    return Object.freeze({draw,pause,dispose});
  }
  window.IcarusWorldAura=Object.freeze({create});
})();

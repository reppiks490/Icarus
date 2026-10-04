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
    float hash(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);}
    float noise(vec2 p){
      vec2 i=floor(p),f=fract(p);f=f*f*(3.0-2.0*f);
      return mix(mix(hash(i),hash(i+vec2(1.0,0.0)),f.x),mix(hash(i+vec2(0.0,1.0)),hash(i+vec2(1.0)),f.x),f.y);
    }
    float mist(vec2 p){float n=0.0;float a=.5;for(int i=0;i<3;i++){n+=noise(p)*a;p=p*2.03+11.7;a*=.5;}return n;}
    void main(){
      vec2 uv=gl_FragCoord.xy/uResolution;
      vec2 p=(uv-uCenter)*vec2(uResolution.x/uResolution.y,1.0);
      float r=max(length(p),.002),a=atan(p.y,p.x),t=uTime;
      float fog=mist(p*4.0+vec2(t*.025,-t*.017));
      float rim=exp(-abs(r-.205-fog*.01)*90.0);
      float glow=0.0;vec3 color;
      if(uWorld<.5){
        float rays=pow(max(0.0,sin(a*23.0+t*.08+fog*3.0)),9.0);
        glow=(rays*.20+rim*.46)*(.4+fog)*exp(-r*1.2);
        color=mix(vec3(.94,.56,.17),vec3(1.0,.93,.68),rim);
      }else if(uWorld<1.5){
        float twist=pow(max(0.0,sin(a*3.0-log(r)*5.0-t*.24+fog*3.0)),5.0);
        float disk=exp(-abs(p.y+sin(p.x*8.0+t*.1)*.024)*22.0);
        glow=(twist*.23+disk*.15+rim*.36)*(1.0-smoothstep(.2,.75,r));
        color=mix(vec3(.51,.04,.26),vec3(1.0,.08,.23),fog+rim*.3);
      }else{
        float wave=sin(p.x*13.0+sin(p.y*6.0+t*.13)*2.0+t*.12);
        float curtain=pow(max(0.0,wave),4.0)*(.3+fog);
        glow=(curtain*.3+rim*.17)*(1.0-smoothstep(.15,.8,r));
        color=mix(vec3(.36,.17,.9),vec3(.18,.89,1.0),fog*.9+wave*.2);
      }
      float mask=mix(smoothstep(.24,.64,uv.x),1.0-smoothstep(.38,.72,uv.y),uMobile);
      gl_FragColor=vec4(color,clamp(glow*mask,0.0,.55));
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
        uniforms=Object.fromEntries(['uResolution','uCenter','uTime','uWorld','uMobile'].map(name=>[name,gl.getUniformLocation(program,name)]));
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
      gl.uniform1f(uniforms.uTime,time%600);gl.uniform1f(uniforms.uWorld,world==='void'?1:world==='astral'?2:0);gl.uniform1f(uniforms.uMobile,mobile?1:0);
      gl.drawArrays(gl.TRIANGLES,0,6);canvas.style.opacity='1';
    }
    function dispose(){if(disposed)return;release();disposed=true;canvas.removeEventListener('webglcontextlost',onLost);canvas.removeEventListener('webglcontextrestored',onRestored);canvas.remove();}
    return Object.freeze({draw,pause,dispose});
  }
  window.IcarusWorldAura=Object.freeze({create});
})();

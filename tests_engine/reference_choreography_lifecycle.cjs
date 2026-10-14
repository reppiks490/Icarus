'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const sourcePath = path.join(__dirname, '../icarus_engine/reference-choreography.js');
const cases = [];
const test = (name,run) => cases.push({name,run});

function fixture(options = {}) {
  const records = {draws:0, clears:0, deleted:[], uniforms:[], fallbackCreates:0,
    fallbackDraws:0, fallbackPauses:0, fallbackDisposes:0, cinemaDraws:0, cinemaTimes:[], profiles:0};
  const root = {dataset:{experience:'cinematic', motion:'live', world:'astral', introLength:'20'}};
  const reduced = {matches:false};
  const forced = {matches:false};
  const observers = [];
  const clock = {now:0};
  const gl = {VERTEX_SHADER:1, FRAGMENT_SHADER:2, COMPILE_STATUS:3, LINK_STATUS:4,
    ARRAY_BUFFER:5, STATIC_DRAW:6, FLOAT:7, TRIANGLES:8, COLOR_BUFFER_BIT:9,
    createShader:()=>({kind:'shader'}), shaderSource(){}, compileShader(){},
    getShaderParameter:()=>!options.compileFailure, deleteShader:o=>records.deleted.push(o),
    createProgram:()=>({kind:'program'}), attachShader(){}, linkProgram(){},
    getProgramParameter:()=>!options.linkFailure, deleteProgram:o=>records.deleted.push(o),
    useProgram(){}, createBuffer:()=>({kind:'buffer'}), deleteBuffer:o=>records.deleted.push(o),
    bindBuffer(){}, bufferData(){}, getAttribLocation:()=>0, enableVertexAttribArray(){},
    vertexAttribPointer(){}, getUniformLocation:(_,name)=>name,
    uniform2f:(name,x,y)=>records.uniforms.push([name,x,y]),
    uniform1f:(name,x)=>records.uniforms.push([name,x]), viewport(){}, clearColor(){},
    clear:()=>records.clears++, drawArrays(){if(options.drawFailure)throw Error('GPU draw failed');records.draws++;}};
  const canvases = [];
  function container() {
    return {children:[], isConnected:true, hidden:false, prepend(c){this.children.unshift(c);c.parent=this;}};
  }
  const scene = container(), theater = container(), overlay = container();
  const document = {documentElement:root, hidden:false, body:container(),
    querySelector:selector=>selector.includes('intro-theater') && overlay.isConnected ? theater : null,
    createElement(tag) {
      assert.equal(tag,'canvas');
      const c = {style:{}, dataset:{}, width:0,height:0, className:'',events:new Map(),
        setAttribute(){}, getContext:()=>options.noGPU?null:gl,
        addEventListener:(name,callback)=>c.events.set(name,callback),
        removeEventListener:name=>c.events.delete(name),
        remove(){if(this.parent)this.parent.children=this.parent.children.filter(x=>x!==this);this.isConnected=false;}};
      canvases.push(c);return c;
    }};
  const cinema = Object.freeze({draw:(_ctx,_w,_h,time)=>{records.cinemaDraws++;records.cinemaTimes.push(time);}, sync:()=>17, init:()=>29});
  const oldAura = Object.freeze({create:()=>{records.fallbackCreates++;return {
    draw:()=>records.fallbackDraws++,pause:()=>records.fallbackPauses++,dispose:()=>records.fallbackDisposes++};}});
  const window = {IcarusWorldAura:oldAura, IcarusWorldCinema:cinema, performance:{now:()=>clock.now},
    matchMedia:query=>query.includes('forced-colors')?forced:reduced};
  class Observer {
    constructor(callback){this.callback=callback;this.disconnected=false;observers.push(this);}
    observe(target,settings){assert.equal(target,document.body);assert.equal(settings.childList,true);assert.ok(!settings.subtree);}
    disconnect(){this.disconnected=true;}
  }
  const forbidden = ()=>assert.fail('Presentation renderer must not schedule, request, store or play audio');
  vm.runInNewContext(fs.existsSync(sourcePath)?fs.readFileSync(sourcePath,'utf8'):'',
    {window,document,MutationObserver:Observer,Float32Array,Math,Object,Number,
      requestAnimationFrame:forbidden,fetch:forbidden,AudioContext:forbidden,localStorage:{getItem:forbidden,setItem:forbidden}});
  assert.equal(typeof window.IcarusReferenceChoreography?.create,'function','Missing reference choreography renderer');
  const ctx = {save(){},restore(){},beginPath(){},moveTo(){},lineTo(){},bezierCurveTo(){},closePath(){},
    fill(){records.profiles++;},stroke(){},createLinearGradient:()=>({addColorStop(){}})};
  return {records,root,reduced,forced,document,scene,theater,overlay,observers,canvases,window,cinema,ctx,clock,
    create:()=>window.IcarusWorldAura.create(scene),
    removeIntro(){overlay.isConnected=false;theater.isConnected=false;for(const o of observers)if(!o.disconnected)o.callback([]);}};
}

test('exports frozen renderer and preserves the original cinema interface',()=>{
  const f=fixture();assert.ok(Object.isFrozen(f.window.IcarusReferenceChoreography));
  assert.ok(Object.isFrozen(f.window.IcarusWorldAura));assert.ok(Object.isFrozen(f.window.IcarusWorldCinema));
  assert.equal(f.window.IcarusWorldCinema.sync,f.cinema.sync);assert.equal(f.window.IcarusWorldCinema.init,f.cinema.init);
  assert.ok(Object.isFrozen(f.create()));
});
test('caller controls rendering, with bounded pixels and a thirty fps cap',()=>{
  const f=fixture(),r=f.create();assert.equal(f.records.draws,0);
  r.draw(0,'astral',2400,1400);r.draw(.01,'astral',2400,1400);r.draw(.04,'astral',2400,1400);
  assert.equal(f.records.draws,2);assert.ok(f.canvases[0].width<=960);assert.ok(f.canvases[0].height<=560);
  assert.equal(f.records.fallbackCreates,0);
});
test('light detail clears and stops the rich renderer',()=>{
  const f=fixture(),r=f.create();r.draw(0,'astral',900,500);r.draw(1,'astral',900,500,{},'light');
  assert.equal(f.records.draws,1);assert.ok(f.records.clears>0);assert.equal(f.canvases[0].style.opacity,'0');
});
for(const gate of ['hidden','reduced','forced','focus','balanced','off'])test(gate+' stops rich scene draws',()=>{
  const f=fixture(),r=f.create();r.draw(0,'astral',900,500);
  if(gate==='hidden')f.document.hidden=true;else if(gate==='reduced')f.reduced.matches=true;
  else if(gate==='forced')f.forced.matches=true;
  else if(gate==='off')f.root.dataset.motion='off';else f.root.dataset.experience=gate;
  r.draw(1,'astral',900,500);assert.equal(f.records.draws,1);assert.equal(f.canvases[0].style.opacity,'0');
});
test('pause clears output and a same-time resume can repaint',()=>{
  const f=fixture(),r=f.create();r.draw(3,'astral',900,500);r.pause();r.draw(3,'astral',900,500);
  assert.equal(f.records.draws,2);
});
test('nonfinite or empty geometry never reaches GPU uniforms',()=>{
  const f=fixture(),r=f.create();for(const args of [[NaN,'astral',900,500],[0,'astral',Infinity,500],[0,'astral',900,0],[0,'unknown',900,500]])r.draw(...args);
  assert.equal(f.records.draws,0);r.draw(0,'astral',900,500,{x:Infinity,y:NaN});
  assert.ok(f.records.uniforms.every(u=>u.slice(1).every(Number.isFinite)));
});
test('theme switch renders immediately even at the same caller time',()=>{
  const f=fixture(),r=f.create();for(const w of ['divine','void','astral'])r.draw(0,w,900,500);
  assert.equal(f.records.draws,3);assert.deepEqual(f.records.uniforms.filter(u=>u[0]==='uWorld').map(u=>u[1]),[0,1,2]);
});
test('GPU absence uses the original fallback only once and removes failed canvas',()=>{
  const f=fixture({noGPU:true}),r=f.create();r.draw(0,'astral',900,500);r.draw(1,'astral',900,500);
  assert.equal(f.records.fallbackCreates,1);assert.equal(f.records.fallbackDraws,2);assert.equal(f.scene.children.length,0);
  r.pause();r.dispose();r.dispose();assert.equal(f.records.fallbackDisposes,1);
});
for(const failure of ['compileFailure','linkFailure'])test(failure+' releases allocated resources before fallback',()=>{
  const f=fixture({[failure]:true}),r=f.create();r.draw(0,'astral',900,500);
  assert.equal(f.records.fallbackDraws,1);assert.ok(f.records.deleted.some(o=>o.kind==='shader'));
  assert.equal(f.records.draws,0);assert.equal(f.scene.children.length,0);
});
test('draw errors recover through the original fallback without escaping',()=>{
  const f=fixture({drawFailure:true}),r=f.create();assert.doesNotThrow(()=>r.draw(0,'astral',900,500));
  assert.equal(f.records.fallbackCreates,1);assert.equal(f.records.fallbackDraws,1);
});
test('lost context stops drawing and restored context disposes fallback before repaint',()=>{
  const f=fixture(),r=f.create();r.draw(0,'astral',900,500);const c=f.canvases[0];let prevented=false;
  c.events.get('webglcontextlost')({preventDefault(){prevented=true;}});r.draw(1,'astral',900,500);
  assert.ok(prevented);assert.equal(f.records.draws,1);assert.equal(f.records.fallbackDraws,1);
  c.events.get('webglcontextrestored')();r.draw(2,'astral',900,500);
  assert.equal(f.records.draws,2);assert.equal(f.records.fallbackDisposes,1);
});
test('dispose twice releases each live resource once and removes listeners',()=>{
  const f=fixture(),r=f.create();r.draw(0,'astral',900,500);r.dispose();const count=f.records.deleted.length;
  r.dispose();r.draw(1,'astral',900,500);assert.equal(f.records.deleted.length,count);
  assert.equal(f.records.draws,1);assert.equal(f.scene.children.length,0);assert.equal(f.canvases[0].events.size,0);
  assert.equal(count,4);
});
test('intro creates one lazy local renderer and body removal releases it',()=>{
  const f=fixture();const draw=f.window.IcarusWorldCinema.draw;
  draw(f.ctx,900,500,0,.03,{intro:true,detail:'rich'});f.clock.now=40;draw(f.ctx,900,500,.04,.03,{intro:true,detail:'rich'});
  assert.equal(f.canvases.length,1);assert.equal(f.records.draws,2);assert.equal(f.records.cinemaDraws,2);
  assert.equal(f.observers.length,1);f.removeIntro();assert.equal(f.theater.children.length,0);
  assert.ok(f.observers[0].disconnected);assert.equal(f.records.deleted.length,4);
});
test('explicit balanced intro remains permitted while scene GPU stays stopped',()=>{
  const f=fixture();f.root.dataset.experience='balanced';f.create().draw(0,'astral',900,500);
  f.window.IcarusWorldCinema.draw(f.ctx,900,500,1,.03,{intro:true,detail:'rich'});
  assert.equal(f.records.draws,1);
});
test('light intro keeps meaningful curved 2D depth without creating GPU canvas',()=>{
  const f=fixture();f.window.IcarusWorldCinema.draw(f.ctx,390,650,1,.03,{intro:true,detail:'light'});
  assert.equal(f.canvases.length,0);assert.ok(f.records.profiles>0);assert.equal(f.records.cinemaDraws,1);
});
test('motion-disabled intro does not create a rich canvas',()=>{
  const f=fixture();f.reduced.matches=true;f.window.IcarusWorldCinema.draw(f.ctx,900,500,1,.03,{intro:true,detail:'rich'});
  assert.equal(f.canvases.length,0);
});

test('slow frames still reach the intro finale using monotonic presentation time',()=>{
  const f=fixture(),draw=f.window.IcarusWorldCinema.draw;
  f.root.dataset.introLength='12';
  draw(f.ctx,900,500,0,.03,{intro:true,detail:'rich'});
  f.clock.now=11000;
  draw(f.ctx,900,500,.06,.06,{intro:true,detail:'rich'});
  const progress=f.records.uniforms.filter(u=>u[0]==='uProgress').at(-1)[1];
  assert.ok(progress>.90&&progress<1,'finale must survive a slow frame clock');
  assert.equal(f.records.cinemaTimes.at(-1),11,'the geometry shares the presentation clock');
});

let passed=0;
for(const {name,run} of cases) {
  try {run();passed++;}catch(error){process.stderr.write(name+': '+error.stack+'\n');process.exitCode=1;}
}
process.stdout.write(JSON.stringify({passed})+'\n');

const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const src=fs.readFileSync(process.argv[2],'utf8');
const body=src.match(/  function topologyPath\(a,b\)\{[\s\S]*?(?=  function scheduleTopology)/)?.[0];
assert.ok(body,'topology source missing');
const setup=String.raw`
class El{
 constructor(x=0,y=0,w=200,h=100){this.children=[];this.dataset={};this.attrs={};this.r={left:x,top:y,width:w,height:h};this.isConnected=true;this.classList={remove(){}};}
 getBoundingClientRect(){return this.r;}
 setAttribute(k,v){this.attrs[k]=v;}
 getAttribute(k){return this.attrs[k]??null;}
 appendChild(e){e.parent=this;this.children.push(e);return e;}
 replaceChildren(){for(const e of this.children)e.parent=null;this.children=[];}
 remove(){if(this.parent){this.parent.children=this.parent.children.filter(x=>x!==this);this.parent=null;}}
}
const links=new El(),nodes=new El(),topology=new El(),view=new El(0,0,1000,1000);
topology.querySelector=s=>s.includes('links')?links:nodes;
let panels=[new El(0,0),new El(0,200),new El(100,400)];
view.querySelectorAll=s=>s==='[data-world-topology-node]'?panels.filter(e=>e.dataset.worldTopologyNode!==undefined):panels;
view.scrollWidth=1000;view.scrollHeight=1000;view.scrollLeft=view.scrollTop=0;
const document={getElementById:()=>view,createElementNS:()=>new El()};
const window={scrollX:0,scrollY:0};
let topologyTimer=0,topologyPanelGeometry=new Map(),topologyRadarRect=null,sectionRadar=null,scrollFocusPanel=null,scrollFocusId=null,topologyHighlightTarget=null,topologyHighlightKey=null,lastPointerClientX=null,lastPointerClientY=null;
const observed=[],unobserved=[];const viewResizeObserver={observe:e=>observed.push(e),unobserve:e=>unobserved.push(e)};
function ensureTopology(){} function rebuildSectionRadar(){} function restoreTopologyActivities(){} function updateScrollFocus(){} function motionAllowed(){return false;} function topologyHighlight(){}
`;
const checks=String.raw`
const getEdge=()=>links.children.find(e=>e.dataset.from==='0'&&e.dataset.to==='1');
const getNode=()=>nodes.children.find(e=>e.dataset.node==='0');
rebuildTopology();const edge=getEdge(),node=getNode(),firstD=edge.getAttribute('d');
rebuildTopology();assert.equal(getEdge(),edge,'unchanged edge identity');assert.equal(getNode(),node,'unchanged node identity');assert.equal(observed.length,3,'no duplicate observation');
panels[0].r.left=50;rebuildTopology();assert.equal(getEdge(),edge,'geometry change keeps edge identity');assert.notEqual(edge.getAttribute('d'),firstD,'geometry is updated');
const removed=panels[0];panels[0]=new El(50,0);rebuildTopology();assert.notEqual(getEdge(),edge,'replacement endpoint invalidates edge');assert.notEqual(getNode(),node,'replacement panel invalidates node');assert.ok(unobserved.includes(removed),'old panel unobserved');assert.equal(observed.length,4);
panels=[panels[0]];rebuildTopology();assert.equal(links.children.length,0);assert.equal(nodes.children.length,0);
console.log('PASS stable graph, geometry, replacement, observer and empty graph assertions');
`;
vm.runInNewContext(setup+body+checks,{assert,console},{timeout:1000});

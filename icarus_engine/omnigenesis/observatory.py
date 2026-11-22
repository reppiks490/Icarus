"""Phase 7: truthful, self-contained animated *offline* research observatory.

Produces a static HTML report from an immutable derived snapshot. The graph
contains ONLY actual stored study records. Animation represents presentation
motion, not real-time trading, agent activity, or live model evolution.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping


def render_observatory(snapshot: Mapping, output: str | Path) -> Path:
    if (not isinstance(snapshot, Mapping)
            or snapshot.get("schema_version") != "icarus-omnigenesis-snapshot-v1"
            or snapshot.get("status") != "RESEARCH_ONLY"
            or snapshot.get("authority", {}).get("execution_authorized") is not False):
        raise ValueError("invalid research-only snapshot")
    rows = snapshot.get("recent_studies")
    if not isinstance(rows, list) or len(rows) > 100:
        raise ValueError("invalid bounded research rows")
    for row in rows:
        if not isinstance(row, Mapping) or set(row) != {
            "study_id", "dataset_id", "asset", "status",
            "holdout_brier_improvement"
        }:
            raise ValueError("unexpected study data in snapshot")
    document = {
        "snapshot": dict(snapshot),
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "live": False,
    }
    # Escape HTML-sensitive bytes even inside a nonexecuting JSON script tag.
    safe = json.dumps(document, sort_keys=True, allow_nan=False).replace(
        "<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026"
    )
    html = r'''<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>ICARUS OMNIGENESIS — Research Observatory</title>
<style>
:root{color-scheme:dark;--text:#f3e9ed;--muted:#aaa0a8;--red:#ff3d69;--gold:#ffd191}
*{box-sizing:border-box}
body{margin:0;background:radial-gradient(ellipse at 64% 14%,#2d0c1d 0%,#100c12 33%,#050609 75%);color:var(--text);font-family:system-ui,-apple-system,Segoe UI,sans-serif;min-height:100vh}
header{padding:27px clamp(19px,4vw,55px) 16px;display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:16px;border-bottom:1px solid #ffffff18}
.eyebrow{font-size:11px;letter-spacing:.32em;color:var(--gold);text-transform:uppercase;font-weight:700}
h1{font-size:clamp(24px,4vw,43px);font-weight:750;letter-spacing:.09em;margin:6px 0 2px}
.subtitle{color:var(--muted);font-size:13px;line-height:1.6}
.stamp{border:1px solid #ff4b6a66;background:#470d2133;padding:10px 14px;border-radius:8px;color:#ffc8d4;font-size:12px;letter-spacing:.07em}
main{display:grid;grid-template-columns:minmax(240px,320px) minmax(0,1fr);gap:18px;padding:20px clamp(16px,3vw,48px) 26px}
aside,.view{border:1px solid #ffffff19;background:#090a11a9;box-shadow:0 12px 50px #0009;border-radius:14px;overflow:hidden}
aside{padding:23px;align-self:start}
.label{font-size:11px;color:var(--muted);letter-spacing:.14em;text-transform:uppercase}
.number{font-size:40px;line-height:1.25;font-weight:750;letter-spacing:-.04em;margin:8px 0}
.metric{padding:15px 0;border-bottom:1px solid #ffffff12}
.metric:last-child{border:0}
#selected{font-size:13px;line-height:1.8;overflow-wrap:anywhere;min-height:88px;color:#dfd2db}
.view{position:relative;min-height:520px}
#network{display:block;width:100%;height:min(72vh,740px);min-height:520px;touch-action:none;cursor:grab}
#network:active{cursor:grabbing}
.viewlabel{position:absolute;top:22px;left:24px;pointer-events:none}
.viewhint{position:absolute;bottom:20px;left:24px;pointer-events:none;color:#a8a0ad;font-size:12px}
footer{padding:0 clamp(16px,3vw,48px) 28px;color:#99909e;font-size:12px;line-height:1.7}
em{font-style:normal;color:var(--gold)}
@media(max-width:820px){main{grid-template-columns:1fr}aside{display:grid;grid-template-columns:1fr 1fr;gap:0 18px}.view{min-height:410px}#network{min-height:410px;height:52vh}}
@media(max-width:480px){aside{display:block}header{padding-top:18px}#network{height:50vh}}
</style></head><body>
<header>
<div><div class="eyebrow">ICARUS • Computational Science</div>
<h1>OMNIGENESIS <span style="color:#ff537f">∞</span></h1>
<div class="subtitle">Scientific memory / experimental evidence / model discovery</div></div>
<div class="stamp">OFFLINE SNAPSHOT — NO LIVE DATA</div>
</header>
<main>
<aside>
<div class="metric"><div class="label">Recorded studies</div><div class="number" id="count">0</div></div>
<div class="metric"><div class="label">Exploratory / Rejected</div><div class="number" id="outcomes">0 / 0</div></div>
<div class="metric"><div class="label">Release authority</div><div style="margin:9px 0;color:#ff9db5;font-weight:650">RESEARCH ONLY</div><div class="subtitle">No broker, execution, or model-promotion privileges.</div></div>
<div class="metric"><div class="label">Selected study</div><div id="selected">Choose a real recorded study node to inspect its summary.</div></div>
<div class="metric"><div class="label">Exported at</div><div class="subtitle" id="exported"></div></div>
</aside>
<section class="view">
<div class="viewlabel"><div class="eyebrow">Actual evidence graph</div><div class="subtitle">Each orbiting node is one recorded study</div></div>
<canvas id="network" role="img" aria-label="Animated graph of actual OMNIGENESIS study records"></canvas>
<div class="viewhint">Drag to pan · Scroll to zoom · Tap a study to inspect</div>
</section></main>
<footer>
This is a <em>derived offline export</em>. Decorative motion is not model learning, real-time research,
market movement, or agent activity. Exploratory findings are not validated trading signals.
Independent APEX/DAEDALUS review and explicit authorization remain required for future integration.
</footer>
<script type="application/json" id="snapshot-data">__SNAPSHOT__</script>
<script>
(function(){
"use strict";
const data=JSON.parse(document.getElementById("snapshot-data").textContent);
const snapshot=data.snapshot;
const studies=snapshot.recent_studies;
const count=document.getElementById("count");
const outcomes=document.getElementById("outcomes");
const selected=document.getElementById("selected");
count.textContent=String(snapshot.study_count);
outcomes.textContent=String(studies.filter(x=>x.status==="EXPLORATORY").length)+" / "+String(studies.filter(x=>x.status==="REJECTED").length);
document.getElementById("exported").textContent=data.exported_at;
const canvas=document.getElementById("network");
const ctx=canvas.getContext("2d");
const motion=!window.matchMedia("(prefers-reduced-motion: reduce)").matches;
let W=1,H=1,dpr=1,zoom=1,panX=0,panY=0,drag=null,elapsed=0;
const nodes=studies.map((s,i)=>({s:s,a:i*2.399963229728653,r:92+Math.sqrt(i)*28,offset:i%7*.6,rad:5.5+(i%3)}));
function resize(){
const box=canvas.getBoundingClientRect();
W=box.width;H=box.height;dpr=Math.min(window.devicePixelRatio||1,2);
canvas.width=Math.round(W*dpr);canvas.height=Math.round(H*dpr);
ctx.setTransform(dpr,0,0,dpr,0,0);
}
new ResizeObserver(resize).observe(canvas);resize();
function position(n,t){
const a=n.a+(motion?t*(.004+(.0004*(n.rad%3))):0);
return {x:Math.cos(a)*n.r,y:Math.sin(a)*n.r*.68};
}
function render(t){
elapsed=motion?t*.001:0;
ctx.clearRect(0,0,W,H);
const cx=W/2+panX,cy=H/2+panY;
ctx.save();ctx.translate(cx,cy);ctx.scale(zoom,zoom);
const halo=ctx.createRadialGradient(0,0,8,0,0,260);
halo.addColorStop(0,"#ed346244");halo.addColorStop(1,"#ed346200");
ctx.fillStyle=halo;ctx.beginPath();ctx.arc(0,0,260,0,Math.PI*2);ctx.fill();
if(!nodes.length){
ctx.textAlign="center";ctx.fillStyle="#b9a9b8";ctx.font="14px system-ui";
ctx.fillText("No studies recorded. Run a local experiment to populate this graph.",0,0);
}else{
for(const n of nodes){
const p=position(n,elapsed);
ctx.beginPath();ctx.moveTo(0,0);ctx.lineTo(p.x,p.y);
ctx.strokeStyle="#e4486c28";ctx.lineWidth=1;ctx.stroke();
}
const pulse=motion?Math.sin(elapsed*1.4)*2.5:0;
ctx.beginPath();ctx.arc(0,0,19+pulse,0,Math.PI*2);ctx.fillStyle="#ff487b";ctx.shadowColor="#ff477e";ctx.shadowBlur=29;ctx.fill();ctx.shadowBlur=0;
ctx.textAlign="center";ctx.fillStyle="#ffffff";ctx.font="bold 9px system-ui";ctx.fillText("Ω",0,3);
for(const n of nodes){
const p=position(n,elapsed),approved=n.s.status==="EXPLORATORY";
ctx.beginPath();ctx.arc(p.x,p.y,n.rad,0,Math.PI*2);
ctx.fillStyle=approved?"#ffd091":"#fa4b75";
ctx.shadowColor=approved?"#ffd091":"#ff3d69";ctx.shadowBlur=11;
ctx.fill();ctx.shadowBlur=0;
}
}
ctx.restore();
if(motion)requestAnimationFrame(render);
}
requestAnimationFrame(render);
function toWorld(e){
const b=canvas.getBoundingClientRect();
return{x:(e.clientX-b.left-W/2-panX)/zoom,y:(e.clientY-b.top-H/2-panY)/zoom};
}
canvas.addEventListener("pointerdown",e=>{drag={x:e.clientX,y:e.clientY,px:panX,py:panY};canvas.setPointerCapture(e.pointerId);});
canvas.addEventListener("pointermove",e=>{if(drag){panX=drag.px+(e.clientX-drag.x);panY=drag.py+(e.clientY-drag.y);if(!motion)render(0);}});
canvas.addEventListener("pointerup",e=>{
if(!drag)return;let dist=Math.hypot(e.clientX-drag.x,e.clientY-drag.y);drag=null;
if(dist>7)return;
const p=toWorld(e);
const target=nodes.find(n=>{const xy=position(n,elapsed);return Math.hypot(p.x-xy.x,p.y-xy.y)<Math.max(18,n.rad+8);});
if(target){
const s=target.s;
selected.textContent="ID: "+s.study_id+" | Asset: "+s.asset+" | Dataset: "+s.dataset_id+" | Status: "+s.status+" | Holdout ΔBrier: "+Number(s.holdout_brier_improvement).toFixed(6);
}
});
canvas.addEventListener("wheel",e=>{e.preventDefault();zoom=Math.max(.4,Math.min(3,zoom*(e.deltaY<0?1.08:.92)));if(!motion)render(0);},{passive:false});
})();
</script></body></html>'''
    html = html.replace("__SNAPSHOT__", safe)
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    return path

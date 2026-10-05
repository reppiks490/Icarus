// Run only against a feed-free preview. No write requests are allowed.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const {mkdirSync}=require('node:fs');
const output=process.env.ICARUS_BROWSER_OUTPUT||'/tmp/icarus-depth-previews';mkdirSync(output,{recursive:true});
(async()=>{
const browser=await chromium.launch({headless:true,args:['--enable-unsafe-swiftshader'],...(process.env.ICARUS_BROWSER_BINARY?{executablePath:process.env.ICARUS_BROWSER_BINARY}:{})});
const context=await browser.newContext({viewport:{width:1440,height:1000}}),errors=[],writes=[];
context.on('page',p=>p.on('pageerror',e=>errors.push(e.message)));
context.on('request',r=>{if(r.method()!=='GET')writes.push(r.url());});
const page=await context.newPage();
await page.addInitScript(()=>{
 sessionStorage.setItem('icarus-intro-seen','1');window.auraDraws=0;
 const draw=WebGLRenderingContext.prototype.drawArrays;
 WebGLRenderingContext.prototype.drawArrays=function(...args){window.auraDraws++;return draw.apply(this,args);};
});
await page.goto(process.env.ICARUS_PREVIEW_URL||'http://127.0.0.1:8879');
await page.locator('.world-aura').waitFor({state:'attached'});
await page.locator('.experience-settings summary').click();await page.locator('#experienceVisualDetail').selectOption('rich');
await page.waitForTimeout(300);
const aura=page.locator('.world-aura'),state=await aura.getAttribute('data-state');
if(process.env.ICARUS_REQUIRE_WEBGL==='1')assert.equal(state,'ready','Actual shader compilation must pass');
let restored=false;
if(state==='ready'){
 assert.ok(await page.evaluate(()=>window.auraDraws)>0);
 assert.equal(await aura.evaluate(c=>c.getContext('webgl').getError()),0);
 assert.ok(await aura.evaluate(c=>c.width<=900&&c.height<=480));
 await page.locator('#experienceVisualDetail').selectOption('light');await page.waitForTimeout(150);
 const calls=await page.evaluate(()=>window.auraDraws);await page.waitForTimeout(200);
 assert.equal(await page.evaluate(()=>window.auraDraws),calls,'Light mode must stop GPU rendering');
 assert.equal(await aura.evaluate(c=>c.style.opacity),'0');
 await page.locator('#experienceVisualDetail').selectOption('rich');await page.waitForTimeout(200);
 const ext=await aura.evaluate(c=>{window.lossExtension=c.getContext('webgl').getExtension('WEBGL_lose_context');if(window.lossExtension)window.lossExtension.loseContext();return !!window.lossExtension;});
 if(ext){
  await page.waitForFunction(()=>document.querySelector('.world-aura').dataset.state==='lost');
  const before=await page.locator('.world-atmosphere').evaluate(c=>c.toDataURL());await page.waitForTimeout(180);
  assert.notEqual(await page.locator('.world-atmosphere').evaluate(c=>c.toDataURL()),before,'CPU scene must continue after GPU loss');
  await page.evaluate(()=>window.lossExtension.restoreContext());
  await page.waitForFunction(()=>document.querySelector('.world-aura').dataset.state==='ready');await page.waitForTimeout(200);
  assert.equal(await aura.evaluate(c=>c.getContext('webgl').getError()),0);restored=true;
 }
}
await page.locator('.experience-settings summary').click();
for(const theme of ['void','astral','divine']){
 await page.locator(`[data-world-choice="${theme}"]`).click();
 await page.waitForFunction(()=>document.querySelectorAll('.world-veil').length===0,null,{timeout:2500});
 assert.ok(await page.locator('#worldTitle .world-word').count()>0);
 await page.screenshot({path:`${output}/depth-${theme}.png`});
}
// Rapid switching must not leave transparent overlays or stale accessible names.
await page.evaluate(()=>{for(const id of ['void','astral','void','divine'])document.querySelector(`[data-world-choice="${id}"]`).click();});
await page.waitForFunction(()=>document.querySelectorAll('.world-veil').length===0,null,{timeout:2500});
const card=page.locator('#view > .card').first();
await card.evaluate(el=>{
 const r=el.getBoundingClientRect();
 const target=el.querySelector('h2')||el;
 target.dispatchEvent(new PointerEvent('pointermove',{bubbles:true,pointerType:'mouse',clientX:r.left+r.width*.38,clientY:r.top+Math.min(36,r.height*.28)}));
 target.dispatchEvent(new PointerEvent('pointerover',{bubbles:true,pointerType:'mouse',clientX:r.left+r.width*.38,clientY:r.top+Math.min(36,r.height*.28)}));
});
await page.waitForTimeout(150);
assert.equal(await card.locator(':scope > .world-surface-sigil').count(),1);
assert.equal(await card.locator(':scope > .world-surface-sigil').evaluate(el=>getComputedStyle(el).position),'absolute');
assert.ok(await card.evaluate(el=>el.style.getPropertyValue('--panel-x')));
assert.ok(await card.evaluate(el=>el.style.getPropertyValue('--panel-tilt-y')));
assert.equal(await page.locator('html').getAttribute('data-world-immersion'),'ready');
assert.equal(await page.locator('.world-depth-frame').count(),1);
assert.equal(await page.locator('.world-depth-atmosphere').count(),1);
assert.equal(await page.locator('.world-depth-atmosphere > i').count(),3);
assert.equal(await page.locator('.world-depth-atmosphere > b').count(),1);
assert.equal(await page.locator('.world-view-ambient').count(),1);
assert.equal(await page.locator('.world-view-ambient i').count(),12);
assert.equal(await page.locator('.world-view-ambient').evaluate(el=>getComputedStyle(el).position),'absolute');
await page.waitForFunction(()=>document.querySelectorAll('.world-topology path').length>0);
assert.equal(await page.locator('.world-topology').count(),1);
assert.ok((await page.locator('.world-topology path').count())<=24);
assert.ok((await page.locator('.world-topology circle').count())<=18);
assert.ok((await page.locator('.world-topology path.active').count())>0);
assert.equal(await page.locator('.world-topology').evaluate(el=>getComputedStyle(el).position),'absolute');
assert.equal(await page.locator('html').getAttribute('data-world-view'),'overview');
const overviewIndex=(await page.locator('[data-world-view-index]').textContent()).trim();
assert.match(overviewIndex,/^\d{2} \/ \d{2}$/);
if(await page.locator('#view .tile').count()) assert.equal(await page.locator('#view .tile').first().getAttribute('data-world-depth-observed'),'1');
// Rapid deliberate navigation must clean its transient gate/impact DOM rather than accumulate effects.
await page.locator('[data-v="system"]').click();
await page.waitForFunction(()=>document.documentElement.dataset.worldView==='system');
assert.equal((await page.locator('[data-world-gate-label]').textContent()).trim(),'SYSTEM');
assert.notEqual((await page.locator('[data-world-view-index]').textContent()).trim(),overviewIndex);
await page.locator('[data-v="overview"]').click();
await page.waitForFunction(()=>document.documentElement.dataset.worldView==='overview');
await page.waitForTimeout(1100);
assert.equal(await page.locator('.world-impact').count(),0);
assert.equal(await page.locator('.world-depth-frame').evaluate(el=>el.classList.contains('world-view-gate-active')),false);
assert.equal(await page.locator('html').getAttribute('data-world-view'),'overview');
await page.locator('#btnPal').focus();
await page.waitForFunction(()=>document.querySelector('.world-focus-orbit')?.classList.contains('active'));
assert.equal(await page.locator('.world-focus-orbit').evaluate(el=>el.classList.contains('active')),true);
assert.equal(await page.locator('.top').evaluate(el=>getComputedStyle(el).position),'sticky');
const longEnough=await page.evaluate(()=>document.documentElement.scrollHeight>innerHeight*1.25);
if(longEnough){
 await page.evaluate(()=>window.scrollTo({top:document.documentElement.scrollHeight,left:0,behavior:'instant'}));
 await page.waitForFunction(()=>window.scrollY>=(document.documentElement.scrollHeight-window.innerHeight)*.75);
 await page.waitForFunction(()=>document.documentElement.dataset.scrollPhase==='abyss');
 const stickyTop=await page.locator('.top').evaluate(el=>el.getBoundingClientRect().top);
 assert.ok(Math.abs(stickyTop)<2,'Sticky header must remain pinned on long scroll');
 assert.equal(await page.locator('html').getAttribute('data-scroll-phase'),'abyss');
 assert.equal(await page.locator('[data-world-depth-label]').textContent(),'ABYSS');
 assert.equal(await page.locator('.world-depth-frame').getAttribute('data-chapter'),'abyss');
 await page.waitForFunction(()=>document.querySelectorAll('#view .world-scroll-focus').length>0);
 assert.ok((await page.locator('.world-topology .scroll-active').count())>0);
 await page.screenshot({path:`${output}/depth-lower-page.png`});
 await page.evaluate(()=>window.scrollTo({top:0,left:0,behavior:'instant'}));
 await page.waitForFunction(()=>window.scrollY===0);
}
await page.locator('.experience-settings summary').click();await page.locator('#experienceMotion').selectOption('off');
await page.waitForTimeout(50);assert.equal(await page.locator('.world-lit').count(),0);
assert.equal(await page.locator('.world-focus-orbit').evaluate(el=>el.classList.contains('active')),false);
await page.locator('#experienceTheme').selectOption('void');
assert.equal(await page.locator('#worldTitle').getAttribute('aria-label'),'Market Destroyer.');
assert.equal(await page.locator('.world-veil').count(),0);
await page.locator('#experienceMotion').selectOption('system');await page.locator('#experienceVisualDetail').selectOption('adaptive');
await page.locator('.experience-settings summary').click();
await page.setViewportSize({width:390,height:844});await page.waitForTimeout(250);
assert.equal(await page.locator('html').getAttribute('data-visual-resolved'),'light');
assert.equal(await page.locator('.world-mobile-hud').isVisible(),true);
assert.ok(Number(await page.locator('.world-depth-frame').evaluate(el=>getComputedStyle(el).opacity))>0);
assert.equal((await page.locator('[data-world-mobile-view]').textContent()).trim(),'OVERVIEW');
assert.match((await page.locator('[data-world-mobile-index]').textContent()).trim(),/^\d{2}\/\d{2}$/);
assert.equal(await page.locator('.world-depth-rail').first().isVisible(),false);
assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
await page.screenshot({path:`${output}/depth-mobile.png`,fullPage:true});
await page.locator('.experience-settings summary').click();
await page.locator('#experienceReplay').click();await page.keyboard.press('Escape');assert.equal(await page.locator('#view').evaluate(e=>e.inert),false);
await page.emulateMedia({reducedMotion:'reduce'});await page.locator('#experienceReplay').click();assert.equal(await page.locator('.world-intro').count(),0);
// Missing WebGL is a supported rendering path, independently of available canvas2D.
const fallback=await context.newPage();
await fallback.addInitScript(()=>{sessionStorage.setItem('icarus-intro-seen','1');const original=HTMLCanvasElement.prototype.getContext;HTMLCanvasElement.prototype.getContext=function(type,...args){return type==='webgl'?null:original.call(this,type,...args);};});
await fallback.goto(process.env.ICARUS_PREVIEW_URL||'http://127.0.0.1:8879');
assert.equal(await fallback.locator('.world-aura').getAttribute('data-state'),'fallback');
assert.equal(await fallback.locator('.world-scene').getAttribute('data-renderer'),'canvas');
await fallback.locator('[data-world-choice="astral"]').click();await fallback.locator('[data-v="system"]').click();
await fallback.waitForFunction(()=>document.documentElement.dataset.worldView==='system');
assert.equal(await fallback.locator('html').getAttribute('data-world-view'),'system');
assert.equal((await fallback.locator('[data-world-gate-label]').textContent()).trim(),'SYSTEM');
assert.equal((await fallback.locator('[data-world-view-glyph]').textContent()).trim(),'⌬');
await fallback.close();
// Simulated sustained slow frames must trigger Adaptive's one-way quality reduction.
const slow=await context.newPage();
await slow.addInitScript(()=>{
 sessionStorage.setItem('icarus-intro-seen','1');
 let next=1;const timers=new Map();
 window.requestAnimationFrame=callback=>{const id=next++;timers.set(id,setTimeout(()=>{timers.delete(id);callback(performance.now());},95));return id;};
 window.cancelAnimationFrame=id=>{clearTimeout(timers.get(id));timers.delete(id);};
});
await slow.goto(process.env.ICARUS_PREVIEW_URL||'http://127.0.0.1:8879');
await slow.waitForFunction(()=>document.documentElement.dataset.visualResolved==='light');
assert.equal(await slow.locator('html').getAttribute('data-visual-detail'),'adaptive');
assert.equal(await slow.locator('.world-aura').evaluate(c=>c.style.opacity),'0');
await slow.close();
console.log(JSON.stringify({adaptiveSlowFrames:'light',shader:state,contextRestored:restored,errors,writes,mobile:'light',rapidTransitions:'clean'}));
await browser.close();assert.deepEqual(errors,[]);assert.deepEqual(writes,[]);
})().catch(e=>{console.error(e);process.exit(1);});

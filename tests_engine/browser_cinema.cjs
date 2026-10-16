// Run against a feed-free server. Exercises real Chromium animation and failure paths.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const {mkdirSync}=require('node:fs');
const output=process.env.ICARUS_BROWSER_OUTPUT||'/tmp/icarus-cinema-previews';mkdirSync(output,{recursive:true});
(async()=>{
const browser=await chromium.launch({headless:true,args:['--enable-unsafe-swiftshader'],...(process.env.ICARUS_BROWSER_BINARY?{executablePath:process.env.ICARUS_BROWSER_BINARY}:{})});
const context=await browser.newContext({viewport:{width:1440,height:1000}});
const page=await context.newPage(),errors=[],writes=[];
async function stableCanvasFrame(canvas){
 let previous=await canvas.evaluate(c=>c.toDataURL()),stable=0;
 for(let attempt=0;attempt<20;attempt++){
  await page.waitForTimeout(100);
  const current=await canvas.evaluate(c=>c.toDataURL());
  if(current===previous){stable++;if(stable>=2)return current;}else{stable=0;previous=current;}
 }
 return previous;
}
context.on('page',p=>p.on('pageerror',e=>errors.push(e.message)));page.on('pageerror',e=>errors.push(e.message));
context.on('request',r=>{if(r.method()!=='GET')writes.push(r.url());});
await page.addInitScript(()=>{
  sessionStorage.setItem('icarus-intro-seen','1');
  const Audio=window.AudioContext;window.audioCreated=0;window.audioGains=[];
  if(Audio)window.AudioContext=class extends Audio{
    constructor(...args){super(...args);window.audioCreated++;}
    createGain(){const node=super.createGain(),original=node.gain.setTargetAtTime.bind(node.gain);node.gain.setTargetAtTime=(value,...args)=>{window.audioGains.push(value);return original(value,...args);};return node;}
  };
});
await page.goto(process.env.ICARUS_PREVIEW_URL||'http://127.0.0.1:8879');
await page.locator('.world-scene[data-renderer="canvas"]').waitFor();
await page.waitForTimeout(700);
const canvas=page.locator('.world-atmosphere');
const before=await canvas.evaluate(c=>c.toDataURL());let sceneAnimated=false;
for(let attempt=0;attempt<20;attempt++){
 await page.waitForTimeout(100);
 if(await canvas.evaluate(c=>c.toDataURL())!==before){sceneAnimated=true;break;}
}
assert.ok(sceneAnimated,'The visible scene must actually animate');
assert.equal(await page.evaluate(()=>window.audioCreated),0,'No audio context before opt-in');
await page.locator('.experience-settings summary').click();
for(const mode of ['balanced','focus']){
 await page.locator('#experienceMode').selectOption(mode);
 const a=await stableCanvasFrame(canvas);await page.waitForTimeout(180);
 assert.equal(await canvas.evaluate(c=>c.toDataURL()),a,`${mode} must stop canvas rendering`);
}
await page.locator('#experienceMode').selectOption('cinematic');
await page.locator('.experience-settings summary').click();
const scrollBeforeSettings=await page.evaluate(()=>{window.scrollTo(0,document.body.scrollHeight);return window.scrollY;});
assert.ok(scrollBeforeSettings>0,'The dashboard must scroll before reopening sticky-header settings');
await page.locator('.experience-settings summary').click();
await page.waitForTimeout(80);
// The settings drawer is internally scrollable and its lower controls can sit
// below the visible section. Scroll the drawer itself before interacting with
// the sound opt-in, then verify the target is in the viewport.
const settingsDrawer=page.locator('.experience-settings > div');
await settingsDrawer.evaluate(async el=>{
 // The drawer is still running its entrance transform at this point. Finish
 // that animation before scrolling so Chromium does not resolve the button's
 // hit-test bounds against an intermediate transformed position.
 await Promise.all(el.getAnimations().map(animation=>animation.finished.catch(()=>{})));
 el.querySelector('#experienceSound').scrollIntoView({block:'center',inline:'nearest',behavior:'auto'});
});
await page.locator('#experienceSound').scrollIntoViewIfNeeded();
await page.waitForTimeout(80);
const soundBounds=await page.locator('#experienceSound').boundingBox();
const drawerBounds=await settingsDrawer.boundingBox();
assert.ok(soundBounds&&soundBounds.x>=0&&soundBounds.y>=0&&soundBounds.x+soundBounds.width<=1440&&soundBounds.y+soundBounds.height<=1000,'Sound opt-in must be inside the viewport after scrolling its settings drawer: '+JSON.stringify({soundBounds,drawerBounds}));
assert.ok(drawerBounds&&soundBounds.x>=drawerBounds.x&&soundBounds.y>=drawerBounds.y&&soundBounds.x+soundBounds.width<=drawerBounds.x+drawerBounds.width&&soundBounds.y+soundBounds.height<=drawerBounds.y+drawerBounds.height,'Sound opt-in must be inside the visible settings drawer');
await page.mouse.click(soundBounds.x+soundBounds.width/2,soundBounds.y+soundBounds.height/2);assert.equal(await page.locator('#experienceSound').getAttribute('aria-pressed'),'true');
assert.equal(await page.evaluate(()=>window.audioCreated),1);
await page.locator('#experienceMotion').selectOption('off');
assert.equal(await page.evaluate(()=>window.audioGains.at(-1)),0,'No-motion must mute audio');
assert.equal(await page.locator('#view').evaluate(el=>el.getAnimations({subtree:true}).filter(a=>a.playState==='running').length),0);
await page.locator('#experienceMotion').selectOption('system');
await page.locator('#experienceSound').click();assert.equal(await page.evaluate(()=>window.audioGains.at(-1)),0);
for(const size of ['compact','grand','panorama']){
 await page.locator('#experienceSceneSize').selectOption(size);
 assert.equal(await page.locator('html').getAttribute('data-scene-size'),size);
}
await page.locator('#experienceSceneSize').selectOption('grand');
for(const theme of ['void','astral','divine']){
 await page.locator('#experienceTheme').selectOption(theme);await page.waitForTimeout(80);
 assert.equal(await page.locator('html').getAttribute('data-theme'),theme);
 assert.equal(await page.locator(`.world-veil[data-world-transition="${theme}"]`).count(),1);
 await page.waitForTimeout(70);
}
await page.locator('#experienceLighting').selectOption('original');
assert.equal(await page.locator('html').evaluate(el=>getComputedStyle(el).colorScheme),'light');
await page.locator('#experienceLighting').selectOption('obsidian');
assert.equal(await page.locator('html').evaluate(el=>getComputedStyle(el).colorScheme),'dark');
await page.reload();await page.locator('.world-scene').waitFor();
assert.equal(await page.locator('html').getAttribute('data-lighting'),'obsidian');
assert.equal(await page.locator('#experienceSound').getAttribute('aria-pressed'),'false');
await page.locator('.experience-settings summary').click();
await page.locator('#experienceIntroLength').selectOption('20');
await page.locator('#experienceReplay').click();
assert.equal(await page.locator('.world-intro').evaluate(el=>getComputedStyle(el).animationDuration),'20s');
assert.equal(await page.locator('.intro-vault').count(),1);
assert.equal(await page.locator('.intro-vault i').count(),5);
assert.equal(await page.locator('.intro-glyphs i').count(),8);
assert.equal(await page.locator('.intro-world-emblem').count(),1);
assert.equal(await page.locator('.intro-world-emblem > *').count(),3);
assert.equal(await page.locator('.intro-chapters span').count(),4);
assert.equal((await page.locator('.intro-title span').textContent()).trim(),'THE ONE ABOVE ALL');
assert.equal((await page.locator('.intro-title em').textContent()).trim(),'ENTER THE SANCTUM');
assert.equal((await page.locator('.intro-seal').textContent()).trim(),'CROWN // LIGHT // INFINITY');
assert.deepEqual(await page.locator('.intro-glyphs i').allTextContents(),['◇','Ⅰ','△','☼','∞','◈','⌁','Ⅲ']);
const skipBounds=await page.locator('.intro-skip').boundingBox();
assert.ok(skipBounds&&skipBounds.x>=0&&skipBounds.y>=0&&skipBounds.x+skipBounds.width<=1440&&skipBounds.y+skipBounds.height<=1000,'Intro escape control must stay inside the viewport');
await page.keyboard.press('Tab');assert.equal(await page.locator('.intro-skip').evaluate(el=>el===document.activeElement),true);
await page.keyboard.press('Escape');assert.equal(await page.locator('#view').evaluate(el=>el.inert),false);
await page.locator('#experienceTheme').selectOption('void');
await page.locator('#experienceReplay').click();
assert.equal((await page.locator('.intro-title em').textContent()).trim(),'ENTER THE BREACH');
assert.equal((await page.locator('.intro-seal').textContent()).trim(),'RUPTURE // SILENCE // EMBER');
assert.deepEqual(await page.locator('.intro-glyphs i').allTextContents(),['×','⟁','Ⅱ','⌁','◇','Ⅲ','×','▲']);
await page.keyboard.press('Escape');
await page.locator('#experienceTheme').selectOption('divine');
await page.locator('#experienceReplay').click();
await page.emulateMedia({reducedMotion:'reduce'});
await page.locator('.world-intro').waitFor({state:'detached'});
assert.equal(await page.locator('#view').evaluate(el=>el.inert),false);
await page.locator('#experienceReplay').click();assert.equal(await page.locator('.world-intro').count(),0);
await page.emulateMedia({reducedMotion:'no-preference'});
await page.locator('.experience-settings summary').click();
for(const view of ['system','inputs','backtest','overview'])await page.locator(`[data-v="${view}"]`).click();
// A labeled synthetic SVG is used only to verify presentation preserves exact chart geometry.
const fixture=await page.evaluate(()=>{
 const el=document.createElement('div');el.style.cssText='width:240px;height:90px';el.innerHTML='<svg aria-label="Test fixture"><path d="M0 4 L10 1 L20 8"/></svg>';document.querySelector('#view').append(el);
 const before=el.innerHTML;window.IcarusWorldCinema.enterChart('TEST',el);const count=el.getAnimations().length;
 window.IcarusWorldCinema.enterChart('TEST',el);const second=el.getAnimations().length;
 const r=el.getBoundingClientRect();
 el.dispatchEvent(new PointerEvent('pointermove',{bubbles:true,pointerType:'mouse',clientX:r.left+r.width*.4,clientY:r.top+r.height*.6}));
 const result={same:before===el.innerHTML,first:count,second,surface:el.classList.contains('world-chart-surface'),scan:el.classList.contains('world-chart-scan-active'),hover:el.classList.contains('world-chart-hover'),x:el.style.getPropertyValue('--chart-hover-x'),y:el.style.getPropertyValue('--chart-hover-y')};el.remove();return result;
});
assert.deepEqual(fixture,{same:true,first:1,second:1,surface:true,scan:true,hover:true,x:'40.00%',y:'60.00%'});
await page.evaluate(()=>toast('Visual contract notification',false));
assert.equal(await page.locator('#toast').getAttribute('data-kind'),'ok');
assert.equal(await page.locator('#toast').getAttribute('role'),'status');
assert.equal(await page.locator('#toast').evaluate(el=>el.classList.contains('world-toast-active')),true);
await page.evaluate(()=>{const t=document.querySelector('#toast');t.classList.remove('world-toast-active');t.style.display='none';});
const busy=await page.evaluate(async()=>{
 const b=document.createElement('button');b.textContent='Visual async command';document.body.appendChild(b);
 let release;const hold=new Promise(resolve=>release=resolve);const run=withBusyButton(b,()=>hold);
 const during={busy:b.classList.contains('world-busy'),disabled:b.disabled,aria:b.getAttribute('aria-busy')};
 release('ok');await run;
 const after={busy:b.classList.contains('world-busy'),disabled:b.disabled,aria:b.getAttribute('aria-busy')};b.remove();
 return {during,after};
});
assert.deepEqual(busy,{during:{busy:true,disabled:true,aria:'true'},after:{busy:false,disabled:false,aria:null}});
const readouts=await page.evaluate(()=>{
 const host=document.createElement('section');host.className='card';
 host.innerHTML='<div id="stateLoading" class="empty">loading model state…</div><div id="stateUnavailable" class="empty">UNAVAILABLE — no evidence.</div><div id="stateError" class="empty neg">FAILED integrity check</div>';
 document.querySelector('#view').append(host);window.IcarusWorldImmersion.refresh();
 const result={
  loading:document.querySelector('#stateLoading').classList.contains('world-loading-state'),
  unavailable:document.querySelector('#stateUnavailable').classList.contains('world-unavailable-state'),
  error:document.querySelector('#stateError').classList.contains('world-error-state')
 };host.remove();return result;
});
assert.deepEqual(readouts,{loading:true,unavailable:true,error:true});
await page.setViewportSize({width:390,height:844});await page.waitForTimeout(200);
assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
await page.screenshot({path:`${output}/cinema-mobile.png`,fullPage:true});
const compact=await context.newPage();await compact.setViewportSize({width:800,height:600});
await compact.goto(process.env.ICARUS_PREVIEW_URL||'http://127.0.0.1:8879');
await compact.locator('.experience-settings summary').waitFor();
await compact.evaluate(()=>window.scrollTo(0,document.body.scrollHeight));
await compact.locator('.experience-settings summary').click();
await compact.waitForTimeout(80);
const compactPanel=compact.locator('.experience-settings > div');
await compactPanel.evaluate(el=>Promise.all(el.getAnimations().map(animation=>animation.finished.catch(()=>{}))));
const compactBounds=await compactPanel.boundingBox();
const compactTrigger=await compact.locator('.experience-settings summary').boundingBox();
assert.ok(compactBounds&&compactTrigger&&(compactBounds.y+compactBounds.height<=compactTrigger.y||compactBounds.y>=compactTrigger.y+compactTrigger.height),'Wrapped settings must not cover their trigger: '+JSON.stringify({compactBounds,compactTrigger}));
assert.ok(compactBounds.y+compactBounds.height<=600,'Wrapped settings must remain inside a short viewport: '+JSON.stringify({compactBounds,compactTrigger}));
await compact.close();
// Fault injection: unavailable canvas must preserve navigation and a static visual fallback.
const fallback=await context.newPage();
await fallback.addInitScript(()=>{sessionStorage.setItem('icarus-intro-seen','1');HTMLCanvasElement.prototype.getContext=()=>null;});
await fallback.goto(process.env.ICARUS_PREVIEW_URL||'http://127.0.0.1:8879');
assert.equal(await fallback.locator('.world-scene').getAttribute('data-renderer'),'static');
await fallback.locator('[data-world-choice="void"]').click();await fallback.locator('[data-v="system"]').click();
assert.equal(await fallback.locator('html').getAttribute('data-theme'),'void');
await fallback.locator('.experience-settings summary').click();await fallback.locator('#experienceReplay').click();await fallback.locator('.intro-skip').click();
assert.equal(await fallback.locator('#view').evaluate(el=>el.inert),false);
console.log(JSON.stringify({passed:true,errors,writes,fixture}));
await browser.close();assert.deepEqual(errors,[]);assert.deepEqual(writes,[]);
})().catch(e=>{console.error(e);process.exit(1);});

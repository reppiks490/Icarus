// Optional browser integration check: npm install --no-save playwright, then run against a feed-free preview.
const {chromium} = require('playwright');
const {mkdirSync} = require('node:fs');
const output = process.env.ICARUS_BROWSER_OUTPUT || '/tmp/icarus-world-checks';
mkdirSync(output,{recursive:true});
(async()=>{
const browser=await chromium.launch({headless:true,...(process.env.ICARUS_BROWSER_BINARY ? {executablePath:process.env.ICARUS_BROWSER_BINARY} : {})});
const page=await browser.newPage({viewport:{width:1440,height:1100}});
const errors=[]; const writes=[];
page.on('pageerror',e=>errors.push(e.message));
page.on('request',r=>{if(r.method()!=='GET') writes.push(r.url());});
await page.goto(process.env.ICARUS_PREVIEW_URL || 'http://127.0.0.1:8879');
await page.locator('.intro-skip').waitFor();
await page.waitForTimeout(6800);
await page.screenshot({path:`${output}/intro.png`});
await page.keyboard.press('Escape');
await page.locator('.world-intro').waitFor({state:'detached'});
await page.screenshot({path:`${output}/divine.png`,fullPage:true});
for(const world of ['void','astral','divine']){
 await page.locator(`[data-world-choice="${world}"]`).click();
 await page.waitForTimeout(400);
 if(await page.locator('html').getAttribute('data-theme')!==world) throw Error('Theme switch failed');
 await page.screenshot({path:`${output}/${world}.png`,fullPage:true});
}
await page.reload();
if(await page.locator('.world-intro').count()) throw Error('Intro replayed after reload');
if(await page.locator('html').getAttribute('data-theme')!=='divine') throw Error('Theme lost on reload');
await page.locator('#experienceFocus').click();
if(await page.locator('.world-scene').isVisible()) throw Error('Focus did not hide scene');
await page.locator('#experienceFocus').click();
await page.locator('.experience-settings summary').click();
await page.locator('#experienceMotion').selectOption('off');
await page.locator('#experienceReplay').click();
if(await page.locator('.world-intro').count()) throw Error('Intro ignored no-motion preference');
await page.locator('#experienceMotion').selectOption('system');
await page.locator('#experienceReplay').click();
await page.locator('.intro-skip').click();
await page.locator('#experienceIntroLength').selectOption('12');
await page.locator('#experienceReplay').click();
await page.locator('.world-intro').waitFor({state:'detached',timeout:15000});
if(await page.locator('#view').evaluate(el=>el.inert)) throw Error('Intro left dashboard inert');
await page.locator('#experienceTheme').selectOption('dark');
if(await page.locator('.world-scene').isVisible()) throw Error('Scene remained on legacy theme');
await page.locator('#experienceTheme').selectOption('void');
await page.locator('.experience-settings summary').click();
for(const view of ['system','inputs','backtest','brain','possibility','overview']) {
 await page.locator(`[data-v="${view}"]`).click();
 await page.waitForFunction(v=>document.documentElement.dataset.worldView===v,view);
 if(!await page.locator(`[data-v="${view}"]`).evaluate(el=>el.classList.contains('active'))) throw Error('Navigation failed');
 if(['system','brain','possibility'].includes(view)){
  const watermark=await page.locator('#view').evaluate(el=>getComputedStyle(el,'::after').content);
  if(!watermark||watermark==='none') throw Error('Subsystem watermark missing');
  await page.screenshot({path:`${output}/dense-${view}.png`,fullPage:true});
 }
}
await page.setViewportSize({width:390,height:844});
await page.screenshot({path:`${output}/mobile.png`,fullPage:true});
const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth);
await page.emulateMedia({reducedMotion:'reduce'});
await page.locator('.experience-settings summary').click();
await page.locator('#experienceReplay').click();
if(await page.locator('.world-intro').count()) throw Error('Intro ignored reduced motion');
console.log(JSON.stringify({errors,writes,overflow,theme:await page.locator('html').getAttribute('data-theme'),motion:await page.locator('html').getAttribute('data-motion')}));
await browser.close();
if(errors.length||writes.length||overflow) process.exit(1);
})();

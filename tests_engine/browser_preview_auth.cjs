// Credentials for the isolated, feed-free browser preview; never production defaults.
async function authenticatePreview(context) {
  const token=process.env.ICARUS_BROWSER_PREVIEW_TOKEN ?? 'browser-preview-test-token';
  if(!token) throw new Error('Browser preview token must not be empty');
  const origin=new URL(process.env.ICARUS_PREVIEW_URL || 'http://127.0.0.1:8879').origin;
  await context.addInitScript(({token,origin})=>{
    if(location.origin===origin) localStorage.setItem('icarus-engine-token',token);
  },{token,origin});
}
module.exports={authenticatePreview};

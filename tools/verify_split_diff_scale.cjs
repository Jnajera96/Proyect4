/* Real Split Diff interactions over loopback fixtures; no backend or external HTTP. */
const fs=require('node:fs'),path=require('node:path'),os=require('node:os');
const http=require('node:http'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
const {build}=require(path.join(root,'frontend/node_modules/esbuild'));
const {chromium}=require(require.resolve('playwright',{paths:[path.join(os.homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules')]}));
const output=path.resolve(process.argv[2]||path.join(root,'_tmp/day3-split-diff'));
fs.mkdirSync(output,{recursive:false});
const text=Array.from({length:25},(_,i)=>`diff --git a/file${i}.py b/file${i}.py\n--- a/file${i}.py\n+++ b/file${i}.py\n@@ -1 +1,2 @@\n-old${i}\n+new${i}\n+extra${i}\n`).join('');
(async()=>{
 await build({stdin:{contents:`import React from 'react';import {createRoot} from 'react-dom/client';import {VisorDiff} from './src/components/VisorDiff';createRoot(document.getElementById('root')).render(<VisorDiff texto={${JSON.stringify(text)}}/>);`,resolveDir:path.join(root,'frontend'),loader:'tsx'},bundle:true,format:'iife',platform:'browser',outfile:path.join(output,'app.js')});
 const server=http.createServer((req,res)=>{
  if(req.url==='/'){res.setHeader('Content-Type','text/html');return res.end('<link rel="stylesheet" href="/style.css"><div id="root"></div><script src="/app.js"></script>');}
  if(req.url==='/app.js'){res.setHeader('Content-Type','application/javascript');return res.end(fs.readFileSync(path.join(output,'app.js')));}
  if(req.url==='/style.css'){res.setHeader('Content-Type','text/css');return res.end(fs.readFileSync(path.join(root,'frontend/src/workspace.css')));}
  res.statusCode=204;res.end();
 });
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 let browser;
 const checks=[],errors=[],blocked=[];
 try{
  browser=await chromium.launch({channel:'chrome',headless:true,args:['--disable-background-networking','--disable-component-update','--no-first-run']});
  const context=await browser.newContext();
  const origin=`http://127.0.0.1:${server.address().port}`;
  await context.route('**/*',route=>{if(new URL(route.request().url()).origin===origin)return route.continue();blocked.push(route.request().url());return route.abort();});
  const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));
  await page.goto(origin);
  await page.locator('.modo-unificado .diff-indice a').last().waitFor();
  assert.equal(await page.locator('.diff-indice a').count(),25);checks.push('25-file index rendered');
  const times=[];
  for(let i=0;i<5;i++){
   await page.getByRole('button',{name:'Unificado',exact:true}).click();
   const duration=await page.evaluate(async()=>{
    const start=performance.now();
    [...document.querySelectorAll('button')].find(b=>b.textContent==='Dividido').click();
    await new Promise(requestAnimationFrame);await new Promise(requestAnimationFrame);
    if(!document.querySelector('.modo-dividido'))throw new Error('Split mode not activated');
    return performance.now()-start;
   });
   assert.ok(duration<1000,`Split interaction exceeded 1000ms: ${duration}`);times.push(duration);
  }
  assert.equal(await page.locator('.diff-dividido').count(),25);
  assert.equal(await page.locator('.fila-dividida').count(),50);checks.push('Actual split mode preserves all 25 files and 50 paired rows');
  await page.evaluate(()=>{const original=Element.prototype.scrollIntoView;Element.prototype.scrollIntoView=function(...args){window.__scrollTarget=this.id;return original.apply(this,args);};});
  await page.locator('.diff-indice a').last().click();
  assert.equal(await page.evaluate(()=>window.__scrollTarget),'diff-fichero-24');
  await page.waitForFunction(()=>{const r=document.getElementById('diff-fichero-24').getBoundingClientRect();return r.top<innerHeight&&r.bottom>0;});
  checks.push('Last-file navigation invokes actual scroll and reaches viewport');
  await page.getByRole('button',{name:'Plegar todo',exact:true}).click();
  assert.equal(await page.locator('.diff-dividido').count(),0);
  await page.getByRole('button',{name:'Expandir todo',exact:true}).click();
  assert.equal(await page.locator('.diff-dividido').count(),25);checks.push('Fold and expand preserve complete split view');
  assert.deepEqual(errors,[]);assert.deepEqual(blocked,[]);checks.push('No page errors or external page requests');
  const report={success:true,files:25,split_rows:50,checks,split_switch_ms:times,max_split_switch_ms:Math.max(...times),threshold_ms:1000,browser:browser.version(),external_page_requests:blocked,paid_calls:0,scope:'Local browser fixture, not packaged UI or whole-host network capture'};
  fs.writeFileSync(path.join(output,'report.json'),JSON.stringify(report,null,2)+'\n');
  console.log(JSON.stringify(report,null,2));
 }finally{if(browser)await browser.close();await new Promise(resolve=>server.close(resolve));}
})().catch(error=>{console.error(error);process.exitCode=1;});

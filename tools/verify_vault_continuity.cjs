/* Browser regression against real ProfileRoot/App, with an isolated HTTP fixture. */
const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '..');
const {build} = require(path.join(root, 'frontend/node_modules/esbuild'));
const {chromium} = require(require.resolve('playwright', {paths:[path.join(os.homedir(), '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules')]}));
const output = path.join(root, '_tmp/vault-continuity');
fs.mkdirSync(output, {recursive:true});
const report = {success:false, fixture_only:true, paid_calls:0, checks:[]};
let server, browser, healthReads=0, saves=0;
(async()=>{
  const bundle = await build({stdin:{contents:"import React from 'react';import{createRoot}from'react-dom/client';import{ProfileRoot}from'./src/components/ProfileRoot';createRoot(document.getElementById('root')).render(<ProfileRoot/>);",resolveDir:path.join(root,'frontend'),loader:'tsx'},bundle:true,write:false,outdir:output,platform:'browser',format:'iife',jsx:'automatic'});
  server=http.createServer((req,res)=>{
    const url=new URL(req.url,'http://127.0.0.1');
    const json=data=>{res.writeHead(200,{'Content-Type':'application/json'});res.end(JSON.stringify(data));};
    if(url.pathname==='/auth/status')return json({profile_mode:true,authenticated:true,user:{id:'fixture-user',name:'Fixture'},csrf_token:'fixture-csrf'});
    if(url.pathname==='/auth/vault'){
      if(req.method==='PUT'){saves++;return json({ok:true});}
      return json({has_token:true,model_name:'fixture-model',reviewer_model:'fixture-model',model_base_url:'https://example.org/v1',remote_model_roles:['coder','reviewer'],model_pricing:'[]',budget_limit:1,max_cost_per_run:.1,ledger:{limit:1,consumed:0,reserved:0,available:1}});
    }
    if(url.pathname==='/health'){healthReads++;return json({status:'ok',fase:'fixture'});}
    if(url.pathname==='/projects')return json([{project_id:'fixture-project',name:'Fixture project',repo_path:'C:/fixture/repo',created_at:'2026-10-29T00:00:00Z'}]);
    if(url.pathname==='/runs')return json([]);
    if(url.pathname==='/fixture.js'){res.writeHead(200,{'Content-Type':'text/javascript'});return res.end(bundle.outputFiles.find(f=>f.path.endsWith('.js')).text);}
    res.writeHead(200,{'Content-Type':'text/html'});res.end('<!doctype html><div id="root"></div><script src="/fixture.js"></script>');
  });
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  try{
    browser=await chromium.launch({headless:true,executablePath:path.join(os.homedir(),'AppData/Local/ms-playwright/chromium-1208/chrome-win64/chrome.exe')});
    const page=await browser.newPage({viewport:{width:1440,height:1000}});
    const errors=[];page.on('pageerror',e=>errors.push(e.message));
    await page.goto('http://127.0.0.1:'+server.address().port);
    await page.getByLabel('Instrucción',{exact:true}).fill('Conservar este borrador al configurar la bóveda');
    await page.getByLabel('Proyecto',{exact:true}).selectOption('fixture-project');
    assert.equal(await page.getByText('sin autenticación',{exact:true}).count(),0);
    await page.getByText('sesión autenticada',{exact:true}).waitFor();
    report.checks.push('authenticated profile has no contradictory anonymous badge');
    const before=healthReads;
    await page.getByRole('button',{name:'Configurar bóveda',exact:true}).click();
    await page.getByRole('button',{name:'Guardar bóveda',exact:true}).click();
    await page.getByText('Bóveda guardada. Configuración aplicada a tu perfil.').waitFor();
    assert.equal(saves,1);
    assert.equal(await page.getByLabel('Instrucción',{exact:true}).inputValue(),'Conservar este borrador al configurar la bóveda');
    assert.equal(await page.getByLabel('Proyecto',{exact:true}).inputValue(),'fixture-project');
    report.checks.push('saving vault preserves draft and selected project');
    await page.waitForFunction(n=>window.__AISWE__ && document.querySelector('#proyecto')?.value==='fixture-project',before);
    assert.ok(healthReads>before);
    report.checks.push('configuration save refreshes server health without remounting workspace');
    await page.getByRole('button',{name:'Configurar bóveda',exact:true}).click();
    await page.getByRole('button',{name:'Volver al espacio',exact:true}).click();
    assert.equal(await page.getByLabel('Proyecto',{exact:true}).inputValue(),'fixture-project');
    report.checks.push('closing configuration preserves project');
    assert.deepEqual(errors,[]);report.checks.push('no React runtime errors');
    await page.screenshot({path:path.join(output,'workspace-preserved.png'),fullPage:true});
    report.success=true;
  }finally{
    await browser?.close();server.closeAllConnections();await new Promise(resolve=>server.close(resolve));
    fs.writeFileSync(path.join(output,'report.json'),JSON.stringify(report,null,2));
  }
})().catch(e=>{console.error(e);process.exitCode=1;});

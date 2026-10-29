/* Actual App/HTTP UI fixture: no inference, credentials or user files. */
const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '..');
const {build} = require(path.join(root, 'frontend/node_modules/esbuild'));
const {chromium} = require(require.resolve('playwright', {paths: [path.join(os.homedir(), '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules')]}));
const output = path.join(root, '_tmp/workflow-interactions');
fs.mkdirSync(output, {recursive:true});
const report = {success:false, fixture_only:true, paid_calls:0, checks:[]};
const check = label => {report.checks.push(label); console.log('OK',label);};
let server, browser, refreshMode = 'ok', deletes = 0, reads = 0;
const now = '2026-10-28T12:00:00Z';
const run = {run_id:'fixture-run',trace_id:'fixture-trace',created_at:now,updated_at:now,
  status:'needs_human',next_step:null,plan:null,plan_index:0,
  instruction:{text:'Crea una calculadora',source:'text',confirmed_by_user:true,capture_fidelity:1},
  interpretation:{intent:'modify',confidence:.9,constraints:[],rationale:'Requisitos confirmados de fixture',scope:{repo_path:'C:/fixture/repo'}},
  options:{repo_path:'C:/fixture/repo',mode:'FULL_PROPOSAL',allowed_paths:[],protected_paths:[]},
  outputs:{researcher_output:null,coder_output:null,reviewer_output:null},
  artifacts:{diff:'',changed_files:[]},evidence:{test_runs:[],findings:[]},approvals:[],historical_context:[],
  errors:[{agent:'coder',error_class:'CODER_PRODUCED_NO_CHANGES',message:'Fixture: modelo sin archivos',recoverable:false,at:now}],
  budget:{max_tokens:200000,used_tokens:0,used_input_tokens:0,used_output_tokens:0,max_model_calls:120,used_model_calls:0,max_tool_calls:60,used_tool_calls:0,max_review_cycles:2,review_cycles_used:0,max_seconds:900,elapsed_seconds:0,used_cost:0,max_cost:1},final_report:null};
const summary = {run_id:run.run_id,trace_id:run.trace_id,intent:'modify',status:run.status,created_at:now,updated_at:now,awaiting_approval:false,error_count:1};
let projects = [{project_id:'fixture-project',name:'Fixture project',repo_path:'C:/fixture/repo',created_at:now}];
(async()=>{
  const bundle = await build({stdin:{contents:"import React from 'react';import{createRoot}from'react-dom/client';import{App}from'./src/App';createRoot(document.getElementById('root')).render(<App/>);",resolveDir:path.join(root,'frontend'),loader:'tsx'},bundle:true,write:false,platform:'browser',format:'iife',jsx:'automatic'});
  server = http.createServer((req,res)=>{
    const url = new URL(req.url,'http://127.0.0.1');
    const json = (code,data) => {res.writeHead(code,{'Content-Type':'application/json'});res.end(JSON.stringify(data));};
    if(url.pathname==='/health')return json(200,{status:'ok',fase:'offline fixture'});
    if(url.pathname==='/projects')return json(200,projects);
    if(url.pathname==='/projects/fixture-project'){
      if(req.method==='DELETE'){deletes++; projects=[]; res.writeHead(204);return res.end();}
      return json(200,projects[0]);
    }
    if(url.pathname==='/runs')return json(200,[summary]);
    if(url.pathname==='/runs/fixture-run'){
      reads++;const mode=refreshMode;
      return setTimeout(()=> mode==='error'?json(500,{detail:'Fixture: servidor rechazó la consulta'}):json(200,run),mode==='slow'?700:0);
    }
    if(url.pathname.endsWith('/events')){
      res.writeHead(200,{'Content-Type':'text/event-stream'});
      return res.end(`event: run.done\ndata: ${JSON.stringify({run_id:run.run_id,seq:1,at:now,kind:'run.done',data:{status:run.status}})}\n\n`);
    }
    if(url.pathname==='/fixture.js'){res.writeHead(200,{'Content-Type':'text/javascript'});return res.end(bundle.outputFiles[0].text);}
    res.writeHead(200,{'Content-Type':'text/html'});res.end('<!doctype html><meta charset="utf-8"><div id="root"></div><script src="/fixture.js"></script>');
  });
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  try{
    browser=await chromium.launch({headless:true,executablePath:process.env.AI_SWE_BROWSER_EXECUTABLE || path.join(os.homedir(),'AppData/Local/ms-playwright/chromium-1208/chrome-win64/chrome.exe')});
    const page=await browser.newPage({viewport:{width:1440,height:1000}});const errors=[];
    page.on('pageerror',e=>{errors.push(e.message);console.error('Browser runtime:',e.message);report.runtime_errors=errors;});
    await page.goto('http://127.0.0.1:'+server.address().port);
    await page.getByRole('button',{name:'Abrir ejecución fixture-run',exact:true}).click();
    await page.getByRole('button',{name:'Releer del servidor',exact:true}).waitFor();
    refreshMode='slow';const before=reads;
    await page.getByRole('button',{name:'Releer del servidor',exact:true}).click();
    await page.getByRole('button',{name:'Consultando servidor…',exact:true}).waitFor();
    assert.equal(await page.getByRole('button',{name:'Consultando servidor…',exact:true}).isDisabled(),true);
    await page.getByText(/Consulta completada a las/).waitFor();assert.ok(reads>before);check('manual refresh performs HTTP read, loading and success feedback');
    refreshMode='error';await page.getByRole('button',{name:'Releer del servidor',exact:true}).click();
    await page.getByRole('alert').filter({hasText:'No se pudo completar la consulta'}).waitFor();
    assert.equal(await page.getByText(/Consulta completada a las/).count(),0);check('server error visible without false success');
    refreshMode='ok';await page.getByRole('button',{name:'Releer del servidor',exact:true}).click();
    await page.getByText(/Consulta completada a las/).waitFor();check('refresh recovers after error without retrying model');
    await page.getByRole('button',{name:'Vista general',exact:true}).click();
    const stage=page.getByRole('button',{name:'Inspeccionar etapa: Coder',exact:true});await stage.click();
    const dialog=page.getByRole('dialog');await dialog.getByRole('heading',{name:'Coder',exact:true}).waitFor();
    await dialog.getByText(/Fixture: modelo sin archivos/).waitFor();check('overview stage opens inspector with actual selected-run error');
    await page.keyboard.press('Escape');assert.equal(await dialog.count(),0);
    assert.equal(await stage.evaluate(e=>e===document.activeElement),true);check('Escape closes inspector and restores keyboard focus');
    await page.getByRole('button',{name:'Proyectos',exact:true}).click();
    await page.getByRole('button',{name:'Ver detalle',exact:true}).click();
    await page.getByRole('heading',{name:'Detalle del proyecto',exact:true}).waitFor();
    page.once('dialog',d=>d.dismiss());await page.getByRole('button',{name:'Quitar de la lista',exact:true}).click();
    assert.equal(deletes,0);check('cancelled deregistration sends no DELETE');
    page.once('dialog',d=>d.accept());await page.getByRole('button',{name:'Quitar de la lista',exact:true}).click();
    await page.getByRole('status').filter({hasText:'Proyecto quitado de la lista'}).waitFor();assert.equal(deletes,1);
    assert.equal(await page.getByRole('heading',{name:'Detalle del proyecto',exact:true}).count(),0);check('confirmed deregistration updates list and closes obsolete detail');
    assert.equal(await page.getByRole('button',{name:'Abrir ejecución fixture-run',exact:true}).count(),1);check('run history remains visible after removing project');
    assert.deepEqual(errors,[]);check('no React runtime errors');
    await page.screenshot({path:path.join(output,'projects-after-removal.png'),fullPage:true});report.success=true;
  }finally{await browser?.close();server.closeAllConnections();await new Promise(resolve=>server.close(resolve));fs.writeFileSync(path.join(output,'report.json'),JSON.stringify(report,null,2));}
})().catch(e=>{console.error(e);process.exitCode=1;});

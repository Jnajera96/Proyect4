/* Actual React/HTTP fixture: no GitHub, inference, real PAT or application processes. */
const http=require('node:http'), fs=require('node:fs'), path=require('node:path'), os=require('node:os');
const assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
const {build}=require(path.join(root,'frontend/node_modules/esbuild'));
const {chromium}=require(require.resolve('playwright',{paths:[path.join(os.homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules')]}));
const output=path.join(root,'_tmp/intuitive-browser');fs.mkdirSync(output,{recursive:true});
const report={success:false,fixture_only:true,paid_calls:0,github_mocked:true,checks:[]};
const check=name=>{report.checks.push(name);console.log('OK',name);};
const now='2026-10-29T00:00:00Z';
const project={project_id:'fixture-project',name:'Mi aplicación',repo_path:'C:/fixture/myapp',created_at:now};
const state={run_id:'fixture-run',trace_id:'fixture',created_at:now,updated_at:now,status:'completed',next_step:null,
  instruction:{text:'Crea una página',source:'text',confirmed_by_user:true,capture_fidelity:1},
  options:{repo_path:project.repo_path,mode:'FULL_PROPOSAL',delivery_mode:'github',allowed_paths:[],protected_paths:[]},
  interpretation:{intent:'modify',scope:{repo_path:project.repo_path},confidence:.9,constraints:[],rationale:'Fixture'},
  plan:{subtasks:[]},plan_index:0,outputs:{researcher_output:{findings:[],unknowns:[]},coder_output:{files_changed:[],diff:'fixture diff',rationale:'Página de fixture'},reviewer_output:{decision:'accept',findings:[],required_fixes:[],summary:'Fixture'}},
  artifacts:{diff:'fixture diff',changed_files:[]},evidence:{test_runs:[{target:'pytest.unit',exit_code:0,stdout:'Fixture only',stderr:''}],findings:[]},errors:[],approvals:[{action:'promote_changes',decision:'approved',actor:'fixture',at:now,content_sha256:'fixture'}],
  promotion_receipt:{receipt_id:'fixture',pre_promotion_sha:'a',promoted_sha:'b',head:'a',paths:['index.html'],status:'promoted'},
  final_report:{summary:'Fixture',changes_applied:['index.html'],tests_executed:[],review:'Fixture',pending:[]},
  budget:{max_tokens:100,used_tokens:0,used_input_tokens:0,used_output_tokens:0,max_model_calls:10,used_model_calls:0,max_tool_calls:10,used_tool_calls:0,max_review_cycles:2,review_cycles_used:0,max_seconds:90,elapsed_seconds:0,max_cost:1,used_cost:0}};
const guide={available:true,kind:'web_static',summary_es:'Tu aplicación está lista para usar.',launch_action:'open_browser',command:'start iniciar.bat',instructions:['Tu aplicación está guardada en C:/fixture/myapp.','Abre iniciar.bat con doble clic.'],repo_path:project.repo_path,entrypoint:'index.html',prepared:false,launcher_path:'C:/fixture/myapp/iniciar.bat'};
let server,browser,projects=[],runs=[],prepared=0,launched=0,publications=[],createBody,runBody;
(async()=>{
  const bundle=await build({stdin:{contents:"import React from 'react';import{createRoot}from'react-dom/client';import{App}from'./src/App';createRoot(document.getElementById('root')).render(<App/>);",resolveDir:path.join(root,'frontend'),loader:'tsx'},bundle:true,write:false,platform:'browser',format:'iife',jsx:'automatic'});
  server=http.createServer(async(req,res)=>{
    const url=new URL(req.url,'http://127.0.0.1');let body={};
    if(req.method==='POST'){const chunks=[];for await(const chunk of req)chunks.push(chunk);body=JSON.parse(Buffer.concat(chunks).toString()||'{}');}
    const json=(data,status=200)=>{res.writeHead(status,{'Content-Type':'application/json'});res.end(JSON.stringify(data));};
    if(url.pathname==='/health')return json({status:'ok',fase:'Fixture sin inferencia'});
    if(url.pathname==='/projects'){if(req.method==='POST'){createBody=body;projects=[project];return json(project,201);}return json(projects);}
    if(url.pathname.endsWith('/readiness'))return json({ready:true,checks:[]});
    if(url.pathname==='/runs'){if(req.method==='POST'){runBody=body;runs=[{run_id:state.run_id,trace_id:'fixture',intent:'modify',status:'completed',created_at:now,updated_at:now,error_count:0,awaiting_approval:false}];return json(state,202);}return json(runs);}
    if(url.pathname==='/runs/fixture-run')return json(state);
    if(url.pathname==='/runs/fixture-run/launch-guide')return json(guide);
    if(url.pathname.endsWith('/launch-guide/prepare')){prepared++;guide.prepared=true;return json(guide);}
    if(url.pathname==='/runs/fixture-run/launch'){launched++;return json(guide);}
    if(url.pathname.endsWith('/publish-github')){publications.push(body);return publications.length===1?json({detail:'Error de publicación simulado'},409):json({published:true,url:'https://github.com/fixture-owner/myapp'});}
    if(url.pathname.endsWith('/events')){res.writeHead(200,{'Content-Type':'text/event-stream'});return res.end(`event: run.done\ndata: ${JSON.stringify({run_id:state.run_id,seq:1,at:now,kind:'run.done',data:{status:'completed'}})}\n\n`);}
    if(url.pathname==='/fixture.css'){res.writeHead(200,{'Content-Type':'text/css'});return res.end(['estilos.css','workspace.css'].map(f=>fs.readFileSync(path.join(root,'frontend/src',f),'utf8')).join('\n'));}
    if(url.pathname==='/fixture.js'){res.writeHead(200,{'Content-Type':'text/javascript'});return res.end(bundle.outputFiles[0].text);}
    res.writeHead(200,{'Content-Type':'text/html'});res.end('<!doctype html><meta charset="utf-8"><link rel="stylesheet" href="/fixture.css"><div id="root"></div><script src="/fixture.js"></script>');
  });
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  try{
    browser=await chromium.launch({headless:true,executablePath:path.join(os.homedir(),'AppData/Local/ms-playwright/chromium-1208/chrome-win64/chrome.exe')});
    const page=await browser.newPage({viewport:{width:1440,height:1100}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
    await page.goto('http://127.0.0.1:'+server.address().port);
    assert.equal(await page.getByRole('radio',{name:'Modo local',exact:true}).isChecked(),true);check('local mode is the beginner default');
    const quickStart=page.getByRole('group',{name:'Ideas para empezar'});
    for (const label of ['💡 Calculadora científica con funciones trigonométricas','📅 Calendario interactivo con gestión de eventos','🥗 Contador de calorías con registro de alimentos']) {
      await quickStart.getByRole('button',{name:label,exact:true}).click();
      assert.match(await page.getByLabel('Instrucción',{exact:true}).inputValue(),/^Crea /);
    }
    assert.equal(runs.length,0);check('three quick-start ideas fill the controlled instruction without starting a run');
    await page.locator('summary').filter({hasText:'Elegir o crear una carpeta'}).click();
    await page.getByLabel('Nombre',{exact:true}).fill('Mi aplicación');
    await page.getByLabel('Carpeta de tu aplicación',{exact:true}).fill('C:/fixture/myapp');
    await page.getByRole('button',{name:'Crear carpeta de aplicación',exact:true}).click();
    await page.getByRole('option',{name:/Mi aplicación/}).waitFor({state:'attached'});
    assert.equal(createBody.create_if_missing,true);check('local folder creation delegates internal history without Git commands');
    await page.getByRole('radio',{name:'Modo GitHub',exact:true}).check();
    await page.getByLabel('Instrucción',{exact:true}).fill('Crea una página');
    await page.getByRole('button',{name:'Ejecutar',exact:true}).click();
    await page.getByRole('heading',{name:'Qué hacer con tu código',exact:true}).waitFor();
    await page.getByRole('button',{name:'Abrir en el navegador',exact:true}).waitFor();
    assert.equal(runBody.options.delivery_mode,'github');assert.equal(prepared,1);check('destination is persisted and launcher is prepared only through POST');
    await page.getByRole('button',{name:'Abrir en el navegador',exact:true}).click();
    await page.getByText('Se solicitó abrir tu navegador.',{exact:true}).waitFor();assert.equal(launched,1);check('explicit launch sends action and displays acknowledgement');
    await page.getByRole('button',{name:'Flujo',exact:true}).click();
    await page.getByRole('button',{name:'✏️ Modificar o pedir cambios',exact:true}).click();
    await page.waitForFunction(()=>document.activeElement?.id==='instruccion');
    assert.equal(await page.getByLabel('Proyecto',{exact:true}).inputValue(),project.project_id);
    assert.equal(runs.length,1);check('request changes returns to focused composer with the generated project without executing');
    await page.getByRole('button',{name:'🚀 Subir a GitHub',exact:true}).click();
    const modal=page.getByRole('dialog');
    assert.equal(await modal.getByLabel('Repositorio privado',{exact:true}).isChecked(),true);
    assert.equal(await modal.getByRole('button',{name:'🚀 Publicar en GitHub ahora',exact:true}).isDisabled(),true);check('publication defaults private and requires explicit confirmation');
    await modal.getByLabel('Nombre en GitHub',{exact:true}).fill('myapp');
    await modal.getByLabel('Token de GitHub (PAT)',{exact:true}).fill('synthetic-fixture-pat');
    await modal.getByLabel('Revisé los archivos y quiero enviarlos a mi cuenta de GitHub.').check();
    await modal.getByRole('button',{name:'🚀 Publicar en GitHub ahora',exact:true}).click();
    await modal.getByRole('alert').waitFor();assert.equal(await modal.getByLabel('Token de GitHub (PAT)',{exact:true}).inputValue(),'');check('failed publication is visible and forgets PAT');
    await modal.getByLabel('Token de GitHub (PAT)',{exact:true}).fill('synthetic-fixture-pat');
    await modal.getByRole('button',{name:'🚀 Publicar en GitHub ahora',exact:true}).click();
    await modal.getByRole('link',{name:'Ver proyecto en GitHub',exact:true}).waitFor();
    assert.equal(publications.length,2);assert.equal(publications[1].private,true);
    assert.equal(await modal.getByLabel('Token de GitHub (PAT)',{exact:true}).count(),0);check('mock publication success clears secret and provides verified GitHub link');
    await modal.getByRole('button',{name:'Cerrar',exact:true}).click();
    assert.deepEqual(errors,[]);check('no React runtime errors');
    assert.equal(await page.getByText('NaN',{exact:true}).count(),0);check('fixture provides complete budget counters');
    assert.equal(await page.locator('.hero-antetitulo').evaluate(e=>getComputedStyle(e).textTransform),'none');check('visible heading styles preserve sentence case');
    await page.screenshot({path:path.join(output,'delivery-fixture.png'),fullPage:true});report.success=true;
  }finally{await browser?.close();server.closeAllConnections();await new Promise(resolve=>server.close(resolve));fs.writeFileSync(path.join(output,'report.json'),JSON.stringify(report,null,2));}
})().catch(e=>{console.error(e);process.exitCode=1;});

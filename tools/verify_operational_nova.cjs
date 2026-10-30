/* Real React hooks/components over isolated loopback fixtures; no inference or user files. */
const http=require('node:http'),fs=require('node:fs'),path=require('node:path'),os=require('node:os');
const assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
const {build}=require(path.join(root,'frontend/node_modules/esbuild'));
const {chromium}=require(require.resolve('playwright',{paths:[path.join(os.homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules')]}));
const output=path.join(root,'_tmp/nova-operational-browser');fs.mkdirSync(output,{recursive:true});
const report={success:false,fixture_only:true,paid_calls:0,checks:[]};
const check=label=>{report.checks.push(label);console.log('OK',label);};
let server,browser,head=false,configured=false,initializations=0,starts=0,cancels=0,reads=0,failRead=false,delayRead=0,readSignal;
const streams=new Map();
const state=id=>({run_id:id,status:'running',cancellation:null});
let two=state('two');
const readiness=()=>({ready:head&&configured,checks:[
  {code:'HEAD',ready:head,message:'Falta commit base.',action:head?null:'initialize_head'},
  {code:'BUDGET',ready:configured,message:'Configura bóveda y saldo local.',action:configured?null:'configure_vault'}]});
const emit=(id,seq)=>{const res=streams.get(id);assert.ok(res,'connected SSE');res.write(`id: ${seq}\nevent: run.started\ndata: ${JSON.stringify({run_id:id,seq,kind:'run.started',at:'2026-10-30T00:00:00Z',data:{}})}\n\n`);};
(async()=>{
 const source=`import React from'react';import{createRoot}from'react-dom/client';
 import{useEventosRun}from'./src/hooks/useEventosRun';import{useReadiness}from'./src/hooks/useReadiness';
 import{Compositor}from'./src/components/Compositor';import{CancelarEjecucion}from'./src/components/CancelarEjecucion';
 import{readiness}from'./src/lib/readiness';import{api}from'./src/lib/api';
 function App(){const[id,setId]=React.useState('one');const[snapshot,setSnapshot]=React.useState({run_id:'one',status:'running'});
 const{eventos,errorReconciliacion,reanudar}=useEventosRun(id,setSnapshot);const prep=useReadiness('p','FULL_PROPOSAL');
 const[text,setText]=React.useState('Crea una aplicación');
 return <><p>Fixture aislada sin inferencia</p><p id="snapshot">{snapshot.run_id+':'+snapshot.status}</p>
 <p id="sequences">{eventos.map(e=>e.seq).join(',')}</p>{errorReconciliacion&&<p role="alert">{errorReconciliacion}</p>}
 <button onClick={reanudar}>Reconciliar</button><button onClick={()=>{setId('two');setSnapshot({run_id:'two',status:'running'});}}>Cambiar ejecución</button>
 <Compositor puedeAdministrar={true} salud={null} proyectos={[]} estado={{instruccion:text,projectId:'p',nombreProyecto:'',rutaProyecto:'',allowedPaths:[],protectedPaths:[],origenVoz:null,lanzando:false,registrando:false,errorAccion:null,preparacion:prep.report,comprobandoPreparacion:prep.loading,errorPreparacion:prep.error}}
 acciones={{alCambiarInstruccion:setText,alCambiarProyecto:()=>{},alCambiarNombre:()=>{},alCambiarRuta:()=>{},alCambiarPermitidas:()=>{},alCambiarProtegidas:()=>{},alUsarTranscripcion:()=>{},alRegistrarProyecto:()=>{},alFallo:String,
 alLanzar:()=>fetch('/start',{method:'POST'}),alRevisarPreparacion:prep.recheck,
 alInicializarBase:()=>readiness.initialize('p').then(prep.recheck),alConfigurarProveedor:()=>fetch('/configure',{method:'POST'}).then(prep.recheck)}}/>
 <CancelarEjecucion key={id} estado={snapshot} puedeOperar={true} alActualizar={()=>api.obtenerRun(id).then(setSnapshot)}/></>}
 createRoot(document.getElementById('root')).render(<App/>);`;
 const bundle=await build({stdin:{contents:source,resolveDir:path.join(root,'frontend'),loader:'tsx'},bundle:true,write:false,platform:'browser',format:'iife',jsx:'automatic'});
 server=http.createServer((req,res)=>{
  const url=new URL(req.url,'http://127.0.0.1');const json=(value,status=200)=>{res.writeHead(status,{'Content-Type':'application/json'});res.end(JSON.stringify(value));};
  if(url.pathname.endsWith('/readiness'))return json(readiness());
  if(url.pathname.endsWith('/initialize-head')){assert.equal(req.method,'POST');initializations++;head=true;return json(readiness());}
  if(url.pathname==='/configure'){configured=true;return json({});}
  if(url.pathname==='/start'){starts++;return json({});}
  if(url.pathname.endsWith('/events')){const id=url.pathname.split('/')[2];res.writeHead(200,{'Content-Type':'text/event-stream'});streams.set(id,res);emit(id,1);return;}
  if(url.pathname==='/runs/two/cancel'){cancels++;two={...two,cancellation:{status:'requested',worktree_cleanup:'pending',unresolved_reservations:0}};return json(two,202);}
  if(/^\/runs\/(one|two)$/.test(url.pathname)){reads++;readSignal?.();readSignal=null;const id=url.pathname.split('/')[2],fail=failRead;const result=id==='two'?two:{...state('one'),status:'awaiting_approval'};return setTimeout(()=>json(fail?{detail:'fixture error'}:result,fail?500:200),delayRead);}
  if(url.pathname==='/fixture.js'){res.writeHead(200,{'Content-Type':'text/javascript'});return res.end(bundle.outputFiles[0].text);}
  res.writeHead(200,{'Content-Type':'text/html'});res.end('<!doctype html><meta charset="utf-8"><div id="root"></div><script src="/fixture.js"></script>');
 });
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 try{
  browser=await chromium.launch({headless:true,executablePath:path.join(os.homedir(),'AppData/Local/ms-playwright/chromium-1208/chrome-win64/chrome.exe')});
  const page=await browser.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));page.on('dialog',dialog=>dialog.accept());
  await page.goto('http://127.0.0.1:'+server.address().port);
  await page.getByText('Falta commit base.',{exact:true}).waitFor();assert.equal(await page.getByRole('button',{name:'Ejecutar',exact:true}).isDisabled(),true);check('readiness blocks execution with actionable reasons');
  await page.getByRole('button',{name:'Inicializar commit base en 1 clic',exact:true}).click();
  await page.getByText('Falta commit base.',{exact:true}).waitFor({state:'hidden'});assert.equal(initializations,1);assert.equal(starts,0);check('base initialization is explicit and does not start agents');
  await page.getByRole('button',{name:'Configurar bóveda y presupuesto',exact:true}).click();
  await page.getByRole('button',{name:'Ejecutar',exact:true}).click();assert.equal(starts,1);check('ready state enables explicit execution');
  emit('one',3);emit('one',3);
  await page.locator('#snapshot').filter({hasText:'one:awaiting_approval'}).waitFor();assert.equal(await page.locator('#sequences').textContent(),'3');assert.equal(starts,1);check('SSE gap loads authoritative snapshot, clears stale activity and ignores duplicates');
  failRead=true;emit('one',6);await page.getByRole('alert').filter({hasText:'No se pudo recuperar'}).waitFor();check('snapshot recovery failure is visible');
  failRead=false;await page.getByRole('button',{name:'Reconciliar',exact:true}).click();await page.getByRole('alert').filter({hasText:'No se pudo recuperar'}).waitFor({state:'hidden'});check('manual reconciliation retries a read without restarting agents');
  delayRead=250;const requested=new Promise(resolve=>{readSignal=resolve;});emit('one',9);await requested;
  await page.getByRole('button',{name:'Cambiar ejecución',exact:true}).click();await page.waitForTimeout(350);assert.equal(await page.locator('#snapshot').textContent(),'two:running');delayRead=0;check('late snapshot from previous run cannot overwrite selected run');
  await page.getByRole('button',{name:'Solicitar cancelación',exact:true}).click();await page.getByText(/todavía no hay confirmación de parada/).waitFor();assert.equal(await page.getByText(/Parada confirmada/).count(),0);assert.equal(cancels,1);check('202 cancellation is displayed as requested rather than confirmed');
  two={...two,status:'cancelled',cancellation:{status:'confirmed',worktree_cleanup:'removed',unresolved_reservations:1}};emit('two',3);
  await page.getByText(/Parada confirmada/).waitFor();await page.getByText(/Se conservan 1 reservas/).waitFor();assert.equal(cancels,1);assert.equal(starts,1);check('snapshot confirms cancellation and preserves uncertain-budget warning without duplicate actions');
  assert.deepEqual(errors,[]);check('no React runtime errors');report.success=true;
 }finally{await browser?.close();server.closeAllConnections();await new Promise(resolve=>server.close(resolve));fs.writeFileSync(path.join(output,'report.json'),JSON.stringify(report,null,2));}
})().catch(error=>{console.error(error);process.exitCode=1;});

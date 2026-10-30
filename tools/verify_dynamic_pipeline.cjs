/* Isolated UI/SSE fixture. No backend, inference, credentials, or paid calls.
 * Run: node tools/verify_dynamic_pipeline.cjs [output-directory]
 */
const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '..');
const { build } = require(path.join(root, 'frontend/node_modules/esbuild'));
const { chromium } = require(require.resolve('playwright', { paths: [process.env.AI_SWE_BROWSER_MODULES || path.join(os.homedir(), '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules')] }));
const output = path.resolve(process.argv[2] || path.join(root, '_tmp/dynamic-pipeline-browser'));
fs.mkdirSync(output, { recursive: true });
const report = { success: false, fixture_only: true, paid_calls: 0, checks: [] };
const check = (ok, label) => { assert.ok(ok, label); report.checks.push(label); console.log('OK', label); };
let browser, server;
(async () => {
  const run = {
    run_id: 'fixture-dynamic-only', status: 'running', next_step: null, plan: null, plan_index: 0,
    instruction: { text: 'Construye una calculadora con seno, coseno y tangente', source: 'text', capture_fidelity: 1, confirmed_by_user: false },
    interpretation: { intent: 'modify', confidence: .9, constraints: [], rationale: 'Propuesta base para confirmar\n- Funcionalidades: Seno, coseno y tangente\n- Validaciones: Números finitos\n- Interfaz: Controles etiquetados\n- Pruebas: Casos matemáticos conocidos', scope: { repo_path: 'C:/fixture', allowed_paths: [], protected_paths: [] } },
    options: { repo_path: 'C:/fixture', mode: 'FULL_PROPOSAL' }, artifacts: { diff: '', changed_files: [] },
    outputs: { researcher_output: null, coder_output: null, reviewer_output: null }, evidence: { test_runs: [] }, approvals: [], errors: [], final_report: null,
  };
  const source = `import React from 'react'; import {createRoot} from 'react-dom/client';
    import {useEventosRun} from './src/hooks/useEventosRun';
    import {VistaFlujo} from './src/views/VistaFlujo';
    import {PuertaRequisitos} from './src/components/PuertaRequisitos';
    function App(){const {eventos}=useEventosRun('fixture-dynamic-only');const [gate,setGate]=React.useState(false);
      const [confirmed,setConfirmed]=React.useState(false);const [planOnly,setPlanOnly]=React.useState(false);const state=${JSON.stringify(run)};
      if(planOnly)state.options.mode='PLAN_ONLY';
      if(gate)state.status='awaiting_human_requirements_confirmation';
      return <><p>TEST FIXTURE — no actual model inference</p><button onClick={()=>setGate(true)}>Fixture puerta</button><button onClick={()=>setPlanOnly(!planOnly)}>Fixture cambiar modo</button>
        {gate?<PuertaRequisitos estado={state} alDecidir={()=>setConfirmed(true)} alFallo={e=>String(e)}/>:<VistaFlujo estado={state} eventos={eventos} alPuerta={()=>setGate(true)}/>}
        {confirmed?<p>Fixture confirmada</p>:null}</>}
    createRoot(document.getElementById('root')).render(<App/>);`;
  const bundle = await build({ stdin: { contents: source, resolveDir: path.join(root, 'frontend'), sourcefile: 'dynamic-fixture.tsx', loader: 'tsx' }, bundle: true, write: false, platform: 'browser', format: 'iife', jsx: 'automatic' });
  const timers = new Set();
  const later = (fn, ms) => { const t = setTimeout(() => { timers.delete(t); fn(); }, ms); timers.add(t); };
  let correction;
  server = http.createServer((req, res) => {
    if(req.url.startsWith('/runs/fixture-dynamic-only/events')) {
      res.writeHead(200, {'Content-Type':'text/event-stream','Cache-Control':'no-cache','Connection':'keep-alive'});
      let seq=0;
      const send=(kind,data)=>{const e={kind,seq:++seq,at:new Date().toISOString(),data};res.write('id: '+e.seq+'\nevent: '+kind+'\ndata: '+JSON.stringify(e)+'\n\n');};
      const d={node:'coder',role:'coder',mode:'remote',model:'fixture/Qwen:no-inference',provider:'fixture-only'};
      send('node_started',d);send('model_request_started',d);
      later(()=>{send('model_response_received',d);send('node_completed',d);send('test_target_started',{node:'run_tests',role:'supervisor',target:'pytest.unit'});},1800);
      later(()=>send('test_target_completed',{node:'run_tests',role:'supervisor',target:'pytest.unit',exit_code:5,duration_ms:3200,evidence:{stdout:'FIXTURE no tests ran',stderr:'FIXTURE stderr literal'}}),5200);
      req.on('close',()=>{for(const t of timers)clearTimeout(t);timers.clear();});
    } else if(req.url.includes('/confirm-requirements')) {
      let data='';req.on('data',c=>data+=c);req.on('end',()=>{correction=JSON.parse(data);res.writeHead(200,{'Content-Type':'application/json'});res.end('{}');});
    } else if(req.url==='/fixture.js') {res.writeHead(200,{'Content-Type':'text/javascript'});res.end(bundle.outputFiles[0].text);}
    else {res.writeHead(200,{'Content-Type':'text/html'});res.end('<!doctype html><meta charset="utf-8"><div id="root"></div><script src="/fixture.js"></script>');}
  });
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  try {
    const browserCache=path.join(os.homedir(),'AppData/Local/ms-playwright');
    const installed=fs.readdirSync(browserCache).find(n=>n.startsWith('chromium_headless_shell-'));
    const executablePath=process.env.AI_SWE_BROWSER_EXECUTABLE || (installed && path.join(browserCache,installed,'chrome-headless-shell-win64/chrome-headless-shell.exe'));
    browser=await chromium.launch({headless:true,...(executablePath?{executablePath}:{})});
    const page=await browser.newPage({viewport:{width:1280,height:1000}});
    const errors=[];page.on('pageerror',e=>errors.push(e.message));
    await page.goto('http://127.0.0.1:'+server.address().port);
    await page.getByText(/Esperando respuesta de coder/).waitFor();
    check(true,'actual EventSource fixture renders remote model/provider wait');
    await page.getByRole('button',{name:'Inspeccionar etapa: Pruebas'}).click();
    const dialog=page.getByRole('dialog');
    await dialog.getByText('Ejecutando pytest.unit en el sandbox').waitFor();
    await dialog.getByText(/1 s transcurridos/).first().waitFor();
    check(true,'test inspector updates wall-clock elapsed from actual target-start event');
    await dialog.getByText('Código de salida: 5').waitFor();
    await dialog.getByText('Salida literal de pytest.unit').click();
    check(await dialog.getByText('FIXTURE no tests ran',{exact:true}).isVisible(),'literal target stdout visible');
    check(await dialog.getByText('FIXTURE stderr literal',{exact:true}).isVisible(),'literal target stderr visible');
    check(!(await page.getByText('PASS',{exact:true}).count()),'exit code five is never shown as PASS');
    await page.screenshot({path:path.join(output,'test-inspector.png'),fullPage:true});
    await page.getByRole('button',{name:'Cerrar inspector de etapa'}).click();
    await page.getByRole('button',{name:'Fixture puerta'}).click();
    check(await page.getByText('100%',{exact:true}).isVisible(),'typed capture fidelity rendered as 100% separately');
    check(await page.getByRole('heading',{name:'Características planificadas para tu aplicación',exact:true}).isVisible(),'baseline proposal has a friendly review heading');
    check(await page.getByText('Funcionalidades: Seno, coseno y tangente',{exact:true}).isVisible(),'baseline features are rendered as visible list items');
    await page.getByRole('button',{name:'Confirmar y construir',exact:true}).click();
    await page.getByText('Fixture confirmada').waitFor();
    check(correction.decision==='approved','single confirmation click posts approval without automatic generation');
    await page.getByRole('button',{name:'Fixture cambiar modo',exact:true}).click();
    check(await page.getByRole('button',{name:'Confirmar',exact:true}).isVisible(),'plan-only confirmation does not promise to build code');
    await page.getByRole('button',{name:'Fixture cambiar modo',exact:true}).click();
    await page.getByRole('button',{name:'Ajustar propuesta',exact:true}).click();
    await page.locator('#g1-intent').selectOption('inspect');
    await page.locator('#g1-constraints').fill('Conservar funciones trigonométricas');
    await page.locator('#g1-rationale').fill('Revisión humana de la intención');
    await page.getByRole('button',{name:'Guardar ajustes y confirmar'}).click();
    await page.getByText('Fixture confirmada').waitFor();
    check(correction.intent==='inspect' && correction.constraints[0]==='Conservar funciones trigonométricas','intent and edited requirements reach real HTTP gate handler');
    check(errors.length===0,'no browser runtime errors');report.success=true;
  } finally {await browser?.close();for(const t of timers)clearTimeout(t);await new Promise(resolve=>server.close(resolve));fs.writeFileSync(path.join(output,'report.json'),JSON.stringify(report,null,2));}
})().catch(e=>{console.error(e);process.exitCode=1;});

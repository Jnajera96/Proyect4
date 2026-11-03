/* Real React/browser over local HTTP fixtures. No provider, Langfuse or real audio. */
const fs = require('node:fs'), path = require('node:path'), os = require('node:os');
const http = require('node:http'), assert = require('node:assert/strict');
const root = path.resolve(__dirname, '..');
const { build } = require(path.join(root, 'frontend/node_modules/esbuild'));
const { chromium } = require(require.resolve('playwright', {paths: [
  path.join(os.homedir(), '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules')]}));
const output = path.join(root, '_tmp/local-capabilities-browser');
fs.mkdirSync(output, {recursive: true});
const checks = [], calls = [];
const check = name => { checks.push(name); console.log('OK', name); };
const capabilities = {mcp:{enabled:true,transport:'stdio',tools:['read_file','git_status']},
  tts:{enabled:true,provider:'browser_local_only'},
  observability:{local:true,langfuse_enabled:true,langfuse_configured:true}};
const trace = {run_id:'fixture',trace_id:'fixture',truncated:false,status:'completed',
  usage:{input_tokens:20,output_tokens:10,model_calls:1,used_cost:0.001,cost_available:true},
  events:[{seq:1,kind:'node_completed',at:'2026-11-02T12:00:00Z',data:{node:'coder'}}],
  errors:[],verification_failures:[]};
const graph = {provenance:'EXTRACTED',truncated:false,graphify_integrated:false,errors:[],
  nodes:[{id:'file:app.py',label:'app.py',kind:'file'},
    {id:'file:helper.py',label:'helper.py',kind:'file'},
    {id:'file:other.py',label:'other.py',kind:'file'}],
  edges:[{source:'file:app.py',target:'file:helper.py',kind:'imports'}]};

(async () => {
  await build({stdin:{contents:`import React from 'react';import {createRoot} from 'react-dom/client';
    import {CapacidadesLocales} from './src/components/CapacidadesLocales';
    import {LectorResultado} from './src/components/LectorResultado';
    createRoot(document.getElementById('root')).render(<><CapacidadesLocales runId="fixture"/>
      <LectorResultado texto="Tu aplicación está lista para revisar."/></>);`,
    resolveDir:path.join(root,'frontend'),loader:'tsx'}, bundle:true,format:'iife',
    outfile:path.join(output,'app.js'),platform:'browser'});
  const server = http.createServer((req,res) => {
    if (req.url === '/') {res.setHeader('Content-Type','text/html');return res.end('<div id="root"></div><script src="/app.js"></script>');}
    if (req.url === '/app.js') {res.setHeader('Content-Type','application/javascript');return res.end(fs.readFileSync(path.join(output,'app.js')));}
    if (req.url === '/favicon.ico') {res.statusCode=204;return res.end();}
    calls.push({method:req.method,path:req.url});res.setHeader('Content-Type','application/json');
    if (req.url === '/capabilities/local') return res.end(JSON.stringify(capabilities));
    if (req.url === '/runs/fixture/observability') return res.end(JSON.stringify(trace));
    if (req.url === '/runs/fixture/context-graph') return res.end(JSON.stringify(graph));
    if (req.url === '/runs/fixture/observability/langfuse' && req.method === 'POST') return res.end(JSON.stringify({exported:true,spans:2}));
    res.statusCode=404;res.end('{}');
  });
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  let browser;
  try {
    browser = await chromium.launch({headless:true,channel:'chrome'});
    const page = await browser.newPage({viewport:{width:1100,height:1000},acceptDownloads:true});
    await page.addInitScript(() => {
      window.__voices=[{localService:false,lang:'es',name:'remote'},{localService:true,lang:'es-MX',name:'local'}];
      window.__speech={calls:0,cancels:0};
      Object.defineProperty(window,'SpeechSynthesisUtterance',{value:class {}});
      Object.defineProperty(window,'speechSynthesis',{value:{getVoices:()=>window.__voices,
        cancel(){window.__speech.cancels++;},speak(u){window.__speech.calls++;window.__speech.voice=u.voice;u.onstart?.();}}});
    });
    await page.goto(`http://127.0.0.1:${server.address().port}`);
    await page.getByText('MCP de lectura: habilitado.',{exact:false}).waitFor();
    assert.equal(calls.filter(c=>c.method==='POST').length,0);check('No automatic external export');
    await page.getByRole('button',{name:'Consultar trazas',exact:true}).click();
    await page.getByText('20 tokens de entrada',{exact:false}).waitFor();check('Real trace query and token summary');
    const downloaded = page.waitForEvent('download');
    await page.getByRole('button',{name:'Descargar traza local',exact:true}).click();
    const download = await downloaded;await download.saveAs(path.join(output,'trace.json'));
    assert.deepEqual(JSON.parse(fs.readFileSync(path.join(output,'trace.json'),'utf8')),trace);check('JSON trace download preserves metadata');
    await page.getByRole('button',{name:'Ver relaciones del código',exact:true}).click();
    await page.getByText('file:app.py → file:helper.py (imports)',{exact:true}).waitFor();
    await page.getByLabel('Filtrar relaciones por elemento').selectOption('file:other.py');
    await page.getByText('No hay relaciones extraídas para esta selección.',{exact:true}).waitFor();check('Graph relationships filter is interactive');
    page.once('dialog',dialog=>dialog.accept());
    await page.getByRole('button',{name:'Exportar a Langfuse',exact:true}).click();
    await page.getByText('Langfuse confirmó 2 etapas exportadas.',{exact:true}).waitFor();
    assert.equal(calls.filter(c=>c.method==='POST').length,1);check('Export requires explicit confirmation and reports receipt');
    await page.getByRole('button',{name:'Escuchar resultado',exact:true}).click();
    assert.equal(await page.evaluate(()=>window.__speech.voice.localService),true);check('Voice selection excludes remote voices');
    await page.getByRole('button',{name:'Detener lectura',exact:true}).click();
    assert.equal(await page.getByRole('button',{name:'Detener lectura',exact:true}).isDisabled(),true);check('Stop button ends reading state');
    await page.evaluate(()=>{window.__voices=[{localService:false,lang:'es',name:'remote'}];});
    await page.getByRole('button',{name:'Escuchar resultado',exact:true}).click();
    await page.getByText('No hay voces locales instaladas.',{exact:false}).waitFor();
    assert.equal(await page.evaluate(()=>window.__speech.calls),1);check('Missing local voice refuses remote fallback');
    await page.screenshot({path:path.join(output,'local-capabilities.png'),fullPage:true});
    fs.writeFileSync(path.join(output,'report.json'),JSON.stringify({success:true,fixture_only:true,
      paid_calls:0,real_langfuse:false,real_audio:false,checks,calls},null,2));
  } finally {if(browser) await browser.close();await new Promise(resolve=>server.close(resolve));}
})().catch(error=>{console.error(error);process.exitCode=1;});

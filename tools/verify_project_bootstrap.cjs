/* Offline browser fixture: actual project view and HTTP client, no model calls. */
const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '..');
const { build } = require(path.join(root, 'frontend/node_modules/esbuild'));
const { chromium } = require(require.resolve('playwright', { paths: [process.env.AI_SWE_BROWSER_MODULES || path.join(os.homedir(), '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules')] }));
const output = path.join(root, '_tmp/project-bootstrap-browser');
fs.mkdirSync(output, { recursive: true });
let browser, server;
const requests = [];
(async () => {
  const source = `import React from 'react'; import {createRoot} from 'react-dom/client';
    import {VistaProyectos} from './src/views/VistaProyectos'; import {api} from './src/lib/api';
    function App(){const [name,N]=React.useState('Calendar'),[route,R]=React.useState('C:/fixture/calendar');
      const [projects,P]=React.useState([]),[selected,S]=React.useState('');
      return <><p>Offline fixture</p><p data-testid="selected">{selected}</p>
        <VistaProyectos proyectos={projects} cargando={false} nombre={name} ruta={route}
          alCambiarNombre={N} alCambiarRuta={R} alRegistrar={async create=>{const p=await api.crearProyecto(name,route,create);P([p]);S(p.project_id);}}
          alEjecutarContra={S} alFallo={String} puedeAdministrar={true} errorRegistro={null} registrando={false}/></>}
    createRoot(document.getElementById('root')).render(<App/>);`;
  const bundle = await build({ stdin: { contents: source, resolveDir: path.join(root, 'frontend'), loader: 'tsx' }, bundle: true, write: false, platform: 'browser', format: 'iife', jsx: 'automatic' });
  server = http.createServer((req, res) => {
    if (req.url === '/projects' && req.method === 'POST') {
      let data = ''; req.on('data', c => data += c); req.on('end', () => {
        requests.push(JSON.parse(data)); res.writeHead(201, {'Content-Type':'application/json'});
        res.end(JSON.stringify({project_id:'fixture-created', name:'Calendar', repo_path:'C:/fixture/calendar', created_at:new Date().toISOString()}));
      });
    } else if (req.url === '/fixture.js') { res.writeHead(200, {'Content-Type':'text/javascript'}); res.end(bundle.outputFiles[0].text); }
    else { res.writeHead(200, {'Content-Type':'text/html'}); res.end('<!doctype html><meta charset="utf-8"><div id="root"></div><script src="/fixture.js"></script>'); }
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  try {
    const cache = path.join(os.homedir(), 'AppData/Local/ms-playwright');
    const installed = fs.readdirSync(cache).find(n => n.startsWith('chromium_headless_shell-'));
    const executablePath = process.env.AI_SWE_BROWSER_EXECUTABLE || path.join(cache, installed, 'chrome-headless-shell-win64/chrome-headless-shell.exe');
    browser = await chromium.launch({headless:true, executablePath});
    const page = await browser.newPage(); const errors=[]; page.on('pageerror', e=>errors.push(e.message));
    await page.goto('http://127.0.0.1:' + server.address().port);
    await page.getByRole('button', {name:'Nuevo proyecto Git', exact:true}).click();
    await page.getByRole('note').getByText(/Al crear autorizas crear esta carpeta local vacía/).waitFor();
    await page.getByRole('button', {name:'Crear proyecto Git', exact:true}).click();
    await page.getByTestId('selected').filter({hasText:'fixture-created'}).waitFor();
    assert.equal(requests[0].create_if_missing, true);
    assert.equal(requests[0].repo_path, 'C:/fixture/calendar');
    await page.screenshot({path:path.join(output,'new-project.png'), fullPage:true});
    await page.getByRole('button', {name:'Usar repositorio existente'}).click();
    await Promise.all([
      page.waitForResponse(response => response.url().endsWith('/projects') && response.request().method() === 'POST'),
      page.getByRole('button', {name:'Registrar', exact:true}).click(),
    ]);
    assert.equal(requests[1].create_if_missing, false);
    assert.deepEqual(errors, []);
    fs.writeFileSync(path.join(output,'report.json'), JSON.stringify({passed:true, paid_calls:0, checks:['explicit creation notice','create_if_missing true','local path transmitted','selected returned project','existing registration false','no runtime errors']},null,2));
    console.log('PASS: 6 project creation browser checks');
  } finally { await browser?.close(); await new Promise(resolve=>server.close(resolve)); }
})().catch(e=>{console.error(e);process.exitCode=1;});

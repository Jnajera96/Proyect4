/* Real session view, synthetic archive and strict offline API fixture. */
const assert = require('node:assert/strict');
const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const root = path.resolve(__dirname, '..');
const {build} = require(path.join(root, 'frontend/node_modules/esbuild'));
const {chromium} = require(require.resolve('playwright', {paths:[path.join(os.homedir(), '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules')]}));
const output = path.join(root, '_tmp/continuity-upload');
const report = {success:false, fixture_only:true, paid_calls:0, checks:[]};
let browser, server;
(async () => {
  fs.mkdirSync(output, {recursive:true});
  const built = await build({stdin:{contents:"import React from 'react';import{createRoot}from'react-dom/client';import{VistaSesion}from'./src/views/VistaSesion';createRoot(document.getElementById('root')).render(<VistaSesion sesion='autenticada' profileName='Fixture' rol='admin' credencial={null} conexion='cerrado' salud={null} saludError={false} alCambiarCredencial={()=>{}} alCerrarSesion={()=>{}}/>);",resolveDir:path.join(root,'frontend'),loader:'tsx'},bundle:true,write:false,platform:'browser',format:'iife',jsx:'automatic'});
  const archive = Buffer.from([0xfb, 0xff, 0xff, 0x00]);
  let received;
  server = http.createServer((req,res) => {
    const json = (status,data) => {res.writeHead(status,{'Content-Type':'application/json'});res.end(JSON.stringify(data));};
    if (req.url === '/continuity/status') return json(200,{enabled:false,status:'not_configured'});
    if (req.url === '/continuity/import') {
      let body=''; req.on('data',chunk=>body+=chunk); req.on('end',()=>{
        received=JSON.parse(body);
        const valid = /^[A-Za-z0-9+/]*={0,2}$/.test(received.archive_b64) && received.archive_b64.length % 4 === 0;
        json(valid?200:400, valid?{restored_runs:[{run_id:'fixture-run',status:'awaiting_approval'}]}:{detail:'Base64 estándar requerido'});
      }); return;
    }
    if (req.url === '/fixture.js') {res.writeHead(200,{'Content-Type':'text/javascript'});return res.end(built.outputFiles[0].text);}
    res.writeHead(200,{'Content-Type':'text/html'});res.end('<div id="root"></div><script src="/fixture.js"></script>');
  });
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  try {
    browser=await chromium.launch({headless:true,executablePath:path.join(os.homedir(),'AppData/Local/ms-playwright/chromium-1208/chrome-win64/chrome.exe')});
    const page=await browser.newPage();
    await page.goto('http://127.0.0.1:'+server.address().port);
    await page.locator('input[type=file]').setInputFiles({name:'fixture.aiswe-vault',mimeType:'application/octet-stream',buffer:archive});
    await page.locator('#vault-import-repo').fill('C:/fixture/authorized');
    await page.locator('#vault-import-pass').fill('synthetic-password');
    await page.getByRole('button',{name:'Restaurar sesión',exact:true}).click();
    await page.getByText('Sesión restaurada: 1 ejecución(es) recuperadas sin reejecutar nodos completados.',{exact:true}).waitFor({timeout:5000});
    assert.equal(received.archive_b64,archive.toString('base64'));
    report.checks.push('upload preserves standard Base64 alphabet and padding');
    assert.deepEqual(Buffer.from(received.archive_b64,'base64'),archive);
    report.checks.push('binary archive bytes survive upload unchanged');
    assert.deepEqual(received.repo_mapping,{'*':'C:/fixture/authorized'});
    report.checks.push('explicit repository mapping preserved');
    assert.equal(await page.locator('#vault-import-pass').inputValue(),'');
    report.checks.push('password cleared after successful restore');
    report.success=true;
  } finally {
    await browser?.close(); server.closeAllConnections(); await new Promise(resolve=>server.close(resolve));
  }
})().catch(e=>{report.error=e.message;console.error(e.message);process.exitCode=1;}).finally(()=>fs.writeFileSync(path.join(output,'report.json'),JSON.stringify(report,null,2)));

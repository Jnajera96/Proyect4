/* Real access screen; synthetic HTTP fixture, no real vault or remote provider. */
const http=require('node:http'),fs=require('node:fs'),path=require('node:path'),os=require('node:os');
const assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
const {build}=require(path.join(root,'frontend/node_modules/esbuild'));
const {chromium}=require(require.resolve('playwright',{paths:[path.join(os.homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules')]}));
const output=path.join(root,'_tmp/profile-restore-browser'); fs.mkdirSync(output,{recursive:true});
const report={success:false,fixture_only:true,paid_calls:0,checks:[]};
let server,browser,authenticated=false,requests=[];
(async()=>{
  const built=await build({stdin:{contents:"import React from 'react';import{createRoot}from'react-dom/client';import{ProfileRoot}from'./src/components/ProfileRoot';createRoot(document.getElementById('root')).render(<ProfileRoot/>);",resolveDir:path.join(root,'frontend'),loader:'tsx'},outdir:output,bundle:true,write:false,platform:'browser',format:'iife',jsx:'automatic'});
  server=http.createServer(async(req,res)=>{
    const pathname=new URL(req.url,'http://127.0.0.1').pathname;
    const json=(data,status=200)=>{res.writeHead(status,{'Content-Type':'application/json'});res.end(JSON.stringify(data));};
    if(req.url==='/auth/status')return json({profile_mode:true,authenticated,user:authenticated?{id:'restored-user',name:'Restored'}:undefined,csrf_token:authenticated?'fixture-csrf':undefined});
    if(req.url==='/auth/inspect-vault')return json({profile_name:'Restored',repositories:['C:/origin/one','C:/origin/two']});
    if(req.url==='/auth/import-vault'){
      const chunks=[]; for await(const chunk of req)chunks.push(chunk);
      requests.push(JSON.parse(Buffer.concat(chunks).toString()));
      if(requests.length===1)return json({detail:'Contraseña del respaldo incorrecta'},400);
      authenticated=true; return json({profile_mode:true,authenticated:true,user:{id:'restored-user',name:'Restored'},csrf_token:'fixture-csrf'},201);
    }
    if(req.url==='/health')return json({status:'ok',fase:'fixture'});
    if(pathname==='/projects'||pathname==='/runs')return json([]);
    if(req.url==='/fixture.js'){res.writeHead(200,{'Content-Type':'text/javascript'});return res.end(built.outputFiles.find(f=>f.path.endsWith('.js')).text);}
    res.writeHead(200,{'Content-Type':'text/html'});res.end('<meta charset="utf-8"><div id="root"></div><script src="/fixture.js"></script>');
  });
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  try{
    browser=await chromium.launch({headless:true,executablePath:path.join(os.homedir(),'AppData/Local/ms-playwright/chromium-1208/chrome-win64/chrome.exe')});
    const page=await browser.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
    await page.goto('http://127.0.0.1:'+server.address().port);
    await page.getByRole('button',{name:'Restaurar desde un respaldo',exact:true}).click();
    await page.getByRole('heading',{name:'Restaurar desde un respaldo',exact:true}).waitFor();
    report.checks.push('restore is reachable before registration or login');
    const archive=Buffer.from([251,255,255,0]);
    await page.getByLabel('Archivo de respaldo',{exact:true}).setInputFiles({name:'synthetic.aiswe-vault',mimeType:'application/octet-stream',buffer:archive});
    await page.getByLabel('Contraseña del respaldo',{exact:true}).fill('archive-password');
    await page.getByRole('button',{name:'Leer respaldo',exact:true}).click();
    await page.getByRole('region',{name:'Repositorios del respaldo'}).waitFor();
    report.checks.push('authenticated inspection lists both repositories before restoration');
    await page.getByLabel('Contraseña del respaldo',{exact:true}).fill('changed-password');
    assert.equal(await page.getByRole('button',{name:'Restaurar perfil y entrar',exact:true}).isDisabled(),true);
    assert.equal(await page.getByRole('region',{name:'Repositorios del respaldo'}).count(),0);
    report.checks.push('changing archive password invalidates previous inspection and destinations');
    await page.getByLabel('Contraseña del respaldo',{exact:true}).fill('archive-password');
    await page.getByRole('button',{name:'Leer respaldo',exact:true}).click();
    await page.getByRole('region',{name:'Repositorios del respaldo'}).waitFor();
    await page.getByLabel('Nombre del perfil recuperado',{exact:true}).fill('Restored');
    await page.getByLabel('Nueva contraseña del perfil',{exact:true}).fill('new-device-password');
    await page.getByLabel('Repetir nueva contraseña',{exact:true}).fill('different-password');
    await page.getByLabel('Carpeta autorizada del repositorio 1',{exact:true}).fill('C:/fixture/restored-one');
    await page.getByLabel('Carpeta autorizada del repositorio 2',{exact:true}).fill('C:/fixture/restored-two');
    await page.getByRole('button',{name:'Restaurar perfil y entrar',exact:true}).click();
    await page.getByText('Las contraseñas nuevas no coinciden.',{exact:true}).waitFor();assert.equal(requests.length,0);
    report.checks.push('mismatched passwords rejected without sending archive');
    await page.getByLabel('Repetir nueva contraseña',{exact:true}).fill('new-device-password');
    await page.getByRole('button',{name:'Restaurar perfil y entrar',exact:true}).click();
    await page.getByText('Contraseña del respaldo incorrecta',{exact:true}).waitFor();
    report.checks.push('server rejection remains visible and allows correction');
    await page.getByRole('button',{name:'Restaurar perfil y entrar',exact:true}).click();
    await page.getByRole('banner',{name:'Perfil activo'}).waitFor();
    assert.equal(requests[1].archive_b64,archive.toString('base64'));
    assert.deepEqual(requests[1].repo_mapping,{'C:/origin/one':'C:/fixture/restored-one','C:/origin/two':'C:/fixture/restored-two'});
    assert.equal(await page.getByLabel('Nueva contraseña del perfil',{exact:true}).count(),0);
    report.checks.push('standard Base64 and authorized mapping sent; authenticated screen replaces secrets');
    assert.deepEqual(errors,[]);report.checks.push('no React runtime errors');report.success=true;
  }finally{await browser?.close();server.closeAllConnections();await new Promise(resolve=>server.close(resolve));}
})().catch(e=>{report.error=e.message;console.error(e.message);process.exitCode=1;}).finally(()=>fs.writeFileSync(path.join(output,'report.json'),JSON.stringify(report,null,2)));

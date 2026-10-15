/* Real browser -> HTTP -> LangGraph SQLite checkpoint -> disposable Git repo.
 * Only the model proposal is injected. No seeded run or mocked promotion.
 */
const { spawn, execFileSync } = require('node:child_process');
const { join, resolve } = require('node:path');
const { mkdirSync, writeFileSync, readFileSync, readdirSync } = require('node:fs');
const { createHash } = require('node:crypto');
const os = require('node:os');
const net = require('node:net');
const assert = require('node:assert/strict');
const { chromium } = require(require.resolve('playwright', { paths: [join(os.homedir(), '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules')] }));
const root = resolve(__dirname, '..');
const out = resolve('_tmp/phase-c-promotion', String(Date.now()));
mkdirSync(out, {recursive:true});
const python = join(root, '.venv/Scripts/python.exe');
const key = 'phase-c-synthetic-admin';
const report = { checks: [], scenarios: [], model: 'FakeModelAdapter; real application and promotion' };
const check = (label, condition) => {assert.ok(condition, label); report.checks.push(label); console.log('OK', label);};
const git = (repo, ...args) => execFileSync('git', args, {cwd:repo,encoding:'utf8',windowsHide:true}).trim();
const hash = p => createHash('sha256').update(readFileSync(p)).digest('hex');
const delay = ms => new Promise(r=>setTimeout(r,ms));
async function main() {
  const s=net.createServer(); await new Promise(r=>s.listen(0,'127.0.0.1',r)); const port=s.address().port; await new Promise(r=>s.close(r));
  const base=`http://127.0.0.1:${port}`;
  const log=require('node:fs').openSync(join(out,'server.log'),'a');
  const child=spawn(python,['-B','-m','uvicorn','tools.phase_c_server:factory','--factory','--host','127.0.0.1','--port',String(port),'--no-access-log'],{
    cwd:root,windowsHide:true,stdio:['ignore',log,log],env:{...process.env,PYTHONPATH:join(root,'src'),PYTHONDONTWRITEBYTECODE:'1',AI_SWE_STATE_DB_PATH:join(out,'state.sqlite3'),AI_SWE_WORKSPACE_ROOT:join(out,'workspaces'),AI_SWE_ALLOWED_TEST_TARGETS:'["pytest.unit"]',AI_SWE_API_KEYS:JSON.stringify({[key]:'admin'}),AI_SWE_MODEL_PROVIDER:'fake',AI_SWE_STT_PROVIDER:'fake',AI_SWE_RATE_LIMIT_ENABLED:'false'},
  });
  let browser;
  async function api(path, body) {const r=await fetch(base+path,{method:body?'POST':'GET',headers:{'X-API-Key':key,'Content-Type':'application/json'},body:body?JSON.stringify(body):undefined});assert.ok(r.ok, `${path}: ${r.status} ${await r.clone().text()}`);return r.json();}
  async function status(id, expected) {for(let i=0;i<300;i++){const run=await api('/runs/'+id);if(expected.includes(run.status))return run; if(['failed','needs_human','cancelled','completed'].includes(run.status))throw Error('Unexpected '+run.status+': '+JSON.stringify(run.errors));await delay(200);}throw Error('Timeout '+id);}
  try {
    let ready=false;for(let i=0;i<100;i++){try{if((await fetch(base+'/health')).ok){ready=true;break;}}catch{}await delay(100);}assert.ok(ready,'server ready');
    const browserRoot=join(os.homedir(),'AppData/Local/ms-playwright');
    const installed=readdirSync(browserRoot).find(n=>n.startsWith('chromium_headless_shell-'));
    browser=await chromium.launch({headless:true,executablePath:join(browserRoot,installed,'chrome-headless-shell-win64/chrome-headless-shell.exe')});
    const page=await browser.newPage({viewport:{width:1440,height:900}});
    const errors=[];page.on('pageerror',e=>errors.push(e.message));
    await page.goto(base+'/app/');await page.locator('#api-key').fill(key);await page.locator('#btn-continuar').click();await page.locator('#btn-crear').waitFor();
    for(const decision of ['approved','rejected','modified']) {
      const repo=join(out,decision);mkdirSync(join(repo,'src'),{recursive:true});mkdirSync(join(repo,'tests'));
      writeFileSync(join(repo,'src/app.py'),'def f():\n    return 1\n');
      writeFileSync(join(repo,'tests/test_ok.py'),'from app import f\n\ndef test_return():\n    assert f() == 42\n');
      git(repo,'init','-q');git(repo,'-c','user.name=Verification','-c','user.email=verification@localhost','add','.');git(repo,'-c','user.name=Verification','-c','user.email=verification@localhost','commit','-qm','initial');
      let initialExit=0;
      try {execFileSync(python,['-B','-m','pytest','-q','-p','no:cacheprovider','tests'],{cwd:repo,windowsHide:true,env:{...process.env,PYTHONPATH:join(repo,'src'),PYTHONDONTWRITEBYTECODE:'1'},stdio:'pipe'});}
      catch(e){initialExit=e.status;writeFileSync(join(out,decision+'-initial-tests.log'),e.stdout||'');}
      check(decision+': initial functional test fails before proposed change',initialExit===1);
      const before=hash(join(repo,'src/app.py'));const head=git(repo,'rev-parse','HEAD');
      const project=await api('/projects',{name:'Fase C '+decision,repo_path:repo});
      await page.reload();await page.locator('#api-key').fill(key);await page.locator('#btn-continuar').click();
      await page.locator('#proyecto').selectOption(project.project_id);
      await page.locator('#instruccion').fill('Corrige el valor de retorno de src/app.py a 42');
      const response=page.waitForResponse(r=>r.url()===base+'/runs'&&r.request().method()==='POST');
      await page.locator('#btn-crear').click();const created=await (await response).json();const id=created.run_id;
      await page.locator('#btn-confirmar-requisitos').waitFor();
      check(decision+': requirements gate leaves repository unchanged',hash(join(repo,'src/app.py'))===before&&git(repo,'status','--porcelain')==='');
      await page.locator('#btn-confirmar-requisitos').click();
      let run=await status(id,['awaiting_approval']);await page.locator('#btn-aprobar').waitFor({timeout:60000});
      check(decision+': real tests and reviewer evidence',run.evidence.test_runs.length>0&&run.evidence.test_runs.every(t=>t.exit_code===0)&&!!run.outputs.reviewer_output);
      check(decision+': preapproval repository unchanged',hash(join(repo,'src/app.py'))===before&&git(repo,'status','--porcelain')==='');
      const sandbox=run.artifacts.worktree_path;
      const approvedBytes=readFileSync(join(sandbox,'src/app.py'));
      await page.screenshot({path:join(out,decision+'-gate.png'),fullPage:true});
      if(decision==='modified'){
        await page.locator('#g2-comentarios').fill('Conserva el cambio minimo y vuelve a presentar la evidencia.');
        const requested=page.waitForResponse(r=>r.url()===base+'/runs/'+id+'/approve'&&r.request().method()==='POST');
        await page.getByRole('button',{name:'Solicitar cambios',exact:true}).click();
        const sent=await requested;
        report.request_changes_response={status:sent.status(),body:await sent.json()};
        check('modified: UI request accepted by API contract',sent.ok());
        for(let i=0;i<300;i++){run=await api('/runs/'+id);if(run.status==='awaiting_approval'&&run.approvals.some(a=>a.decision==='modified'))break;await delay(200);}
        check('modified: persisted decision and revision cycle',run.approvals.some(a=>a.decision==='modified')&&run.budget.review_cycles_used>0);
        check('modified: repository remains unchanged',hash(join(repo,'src/app.py'))===before&&git(repo,'status','--porcelain')==='');
        await page.locator('#btn-aprobar').waitFor();await page.locator('#btn-aprobar').click();
      } else if(decision==='approved')await page.locator('#btn-aprobar').click();
      else await page.getByRole('button',{name:'Rechazar',exact:true}).click();
      run=await status(id,decision==='rejected'?['cancelled']:['completed']);
      if(decision==='rejected')check('rejected: original tree and hash preserved',hash(join(repo,'src/app.py'))===before&&git(repo,'status','--porcelain')==='');
      else {
        check(decision+': exact reviewed worktree bytes promoted',readFileSync(join(repo,'src/app.py')).equals(approvedBytes)&&readFileSync(join(repo,'src/app.py'),'utf8').replaceAll('\r\n','\n')==='def f():\n    return 42\n');
        check(decision+': only intended unstaged path changed',git(repo,'diff','--name-only')==='src/app.py'&&git(repo,'diff','--cached','--name-only')==='');
        check(decision+': terminal report has no promotion failure',!!run.final_report&&!run.errors.some(e=>e.error_class==='PROMOTION_FAILED'));
      }
      check(decision+': no implicit commit',git(repo,'rev-parse','HEAD')===head);
      check(decision+': worktree removed at terminal',git(repo,'worktree','list','--porcelain').split('worktree ').length===2);
      await page.waitForFunction(expected=>window.__AISWE__?.status===expected,run.status);
      await page.screenshot({path:join(out,decision+'-terminal.png'),fullPage:true});
      report.scenarios.push({decision,run_id:id,status:run.status,head,before,after:hash(join(repo,'src/app.py')),sandbox,approvals:run.approvals,errors:run.errors});
    }
    check('no browser page errors',errors.length===0);
  } finally {if(browser)await browser.close();child.kill();writeFileSync(join(out,'report.json'),JSON.stringify(report,null,2));console.log('EVIDENCE',out);}
}
main().catch(e=>{console.error(e);process.exitCode=1;});

/* Local Windows installed-mode browser/API verification. No model calls or credentials.
 * node tools/verify_installed_configuration.cjs <new-evidence-directory>
 */
const { spawn } = require('node:child_process');
const { join, resolve } = require('node:path');
const { mkdirSync, writeFileSync, existsSync } = require('node:fs');
const os = require('node:os');
const net = require('node:net');
const assert = require('node:assert/strict');
const root = resolve(__dirname, '..');
if (process.argv.length !== 3) process.exit(2);
const output = resolve(process.argv[2]);
assert.ok(!existsSync(output), 'Use a new evidence directory');
mkdirSync(output, { recursive: true });
const { chromium } = require(require.resolve('playwright', { paths: [
  process.env.AI_SWE_BROWSER_MODULES || join(os.homedir(), '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules'), root,
] }));
const report = { checks: [], inference_calls: 0, success: false };
const check = (name, condition) => { assert.ok(condition, name); report.checks.push(name); console.log('OK', name); };
const sleep = ms => new Promise(r => setTimeout(r, ms));
let browser, server;
async function start() {
  const socket = net.createServer(); await new Promise(r => socket.listen(0, '127.0.0.1', r));
  const port = socket.address().port; await new Promise(r => socket.close(r));
  const env = { ...process.env };
  for (const key of Object.keys(env)) if (key.startsWith('AI_SWE_') || key === 'HF_TOKEN') delete env[key];
  Object.assign(env, { LOCALAPPDATA: join(output, 'user-profile'), AI_SWE_RUNTIME_MODE: 'installed', PYTHONPATH: join(root, 'src') });
  server = spawn(join(root, '.venv/Scripts/python.exe'), ['-m', 'uvicorn', 'ai_swe.api.app:crear_app', '--factory', '--host', '127.0.0.1', '--port', String(port), '--no-access-log'], { cwd: root, env, windowsHide: true, stdio: 'ignore' });
  const base = `http://127.0.0.1:${port}`;
  for (let i = 0; i < 100; i++) {
    try { if ((await fetch(base + '/health')).ok) return base; } catch {}
    await sleep(100);
  }
  throw new Error('Installed-mode server failed to start');
}
async function stop() {
  if (server) {
    const child = server; server = null;
    child.kill(); await Promise.race([new Promise(r => child.once('exit', r)), sleep(3000)]);
  }
}
async function main() {
  let base = await start();
  const health = await (await fetch(base + '/health')).json();
  check('first-run health works without configuration', health.status === 'ok' && health.provider_configuration.status === 'not_configured');
  check('local APIs remain available', (await fetch(base + '/projects')).status === 200 && (await fetch(base + '/runs')).status === 200);
  browser = await chromium.launch({ headless: true, ...(process.env.AI_SWE_BROWSER_EXECUTABLE ? { executablePath: process.env.AI_SWE_BROWSER_EXECUTABLE } : {}) });
  const page = await browser.newPage();
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto(base + '/app/');
  await page.getByRole('status').filter({ hasText: 'Proveedor de IA no configurado' }).waitFor();
  check('UI explains missing provider configuration', await page.getByRole('status').filter({ hasText: 'AI_SWE_MODEL_API_KEY' }).count() === 1);
  await page.screenshot({ path: join(output, 'first-run-provider-missing.png'), fullPage: true });
  check('no browser runtime errors', errors.length === 0);
  await browser.close(); browser = null;
  await stop();
  const config = join(output, 'user-profile/AISWESystem/config/.env');
  writeFileSync(config, 'AI_SWE_MODEL_PROVIDER=openai_compatible\nAI_SWE_MODEL_BASE_URL=https://router.huggingface.co/v1\nAI_SWE_MODEL_NAME=Qwen/Qwen2.5-Coder-32B-Instruct:nscale\nAI_SWE_REMOTE_MODEL_ROLES=["coder","reviewer"]\n');
  base = await start();
  report.hybrid_configuration = (await (await fetch(base + '/health')).json()).provider_configuration;
  const blocked = await fetch(base + '/runs', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ instruction: 'analiza el proyecto' }) });
  report.blocked_response_status = blocked.status;
  report.blocked_response = await blocked.json();
  check('external hybrid profile without token is blocked before enqueue', blocked.status === 503 && report.blocked_response.detail.includes('HF_TOKEN'));
  check('failed request creates no run', (await (await fetch(base + '/runs')).json()).length === 0);
  check('SQLite is external to code', existsSync(join(output, 'user-profile/AISWESystem/data/state.sqlite3')));
  check('config cache logs worktrees directories are external', ['config', 'cache', 'logs', 'worktrees'].every(p => existsSync(join(output, 'user-profile/AISWESystem', p))));
  report.success = true;
}
main().catch(error => { report.error = error.message; process.exitCode = 1; console.error(error.message); })
  .finally(async () => { if (browser) await browser.close(); await stop(); writeFileSync(join(output, 'report.json'), JSON.stringify(report, null, 2)); });

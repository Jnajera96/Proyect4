/* Real browser registration/validation/password visibility/recovery, no inference. */
const { spawn } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const assert = require('node:assert/strict');
const { chromium } = require(require.resolve('playwright', { paths: [
  process.env.AI_SWE_BROWSER_MODULES || path.join(os.homedir(), '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules'),
] }));
const bundle = path.resolve(process.argv[2]);
const output = path.resolve(process.argv[3]);
fs.mkdirSync(output, { recursive: false });
const source = fs.existsSync(path.join(bundle, '.venv/Scripts/python.exe'));
const env = { ...process.env };
for (const key of Object.keys(env)) if (key.startsWith('AI_SWE_') || ['HF_TOKEN', 'PYTHONPATH', 'PYTHONHOME'].includes(key)) delete env[key];
env.LOCALAPPDATA = path.join(output, 'userdata');
env.AI_SWE_PROFILES_ROOT = path.join(output, 'users');
env.AI_SWE_STT_PROVIDER = 'fake';
if (source) env.PYTHONPATH = path.join(bundle, 'src');
const command = source ? [path.join(bundle, '.venv/Scripts/python.exe'), '-m', 'ai_swe.launcher'] :
  [path.join(bundle, 'runtime/python.exe'), '-B', path.join(bundle, 'start.py')];
const server = spawn(command[0], [...command.slice(1), '--no-browser', '--exit-after', '150'],
  { env, cwd: output, windowsHide: true });
let log = ''; server.stderr.on('data', c => { log += c; });
const report = { success: false, checks: [], paid_calls: 0 };
let browser;
const check = (value, label) => { assert.ok(value, label); report.checks.push(label); console.log('OK', label); };
(async () => {
  try {
    const base = await new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(Error('Startup timeout: ' + log)), 45000);
      server.stdout.on('data', c => { const m = c.toString().match(/http:\/\/127\.0\.0\.1:\d+/); if (m) { clearTimeout(timer); resolve(m[0]); } });
      server.once('error', reject);
      server.once('exit', code => { clearTimeout(timer); reject(Error('Server exited: ' + code)); });
    });
    browser = await chromium.launch({ headless: true, executablePath: process.env.AI_SWE_BROWSER_EXECUTABLE });
    const page = await browser.newPage({ viewport: { width: 1280, height: 1000 } });
    const errors = []; page.on('pageerror', error => errors.push(error.message));
    await page.goto(base + '/app/');
    await page.getByRole('button', { name: 'Crear un perfil nuevo', exact: true }).click();
    await page.getByRole('button', { name: 'Crear perfil y entrar', exact: true }).click();
    await page.getByRole('alert').filter({ hasText: 'completa este campo' }).waitFor();
    check(true, 'missing native fields produce visible inline validation');
    await page.locator('[name="name"]').fill('rescue-user');
    await page.locator('[name="password"]').fill('browser-original-password');
    await page.getByRole('button', { name: 'Mostrar contraseña', exact: true }).click();
    check(await page.locator('[name="password"]').getAttribute('type') === 'text', 'password can be revealed');
    await page.getByRole('button', { name: 'Ocultar contraseña', exact: true }).click();
    check(await page.locator('[name="password"]').getAttribute('type') === 'password', 'password can be hidden');
    await page.locator('[name="password_confirmation"]').fill('browser-mismatched-password');
    await page.getByRole('button', { name: 'Crear perfil y entrar', exact: true }).click();
    await page.getByRole('alert').filter({ hasText: 'no coinciden' }).waitFor();
    check(true, 'mismatch prevents registration with a clear message');
    await page.locator('[name="password_confirmation"]').fill('browser-original-password');
    await page.getByRole('button', { name: 'Crear perfil y entrar', exact: true }).click();
    await page.locator('#btn-crear').waitFor();
    check(true, 'registration with a long matching password reaches workspace');
    await page.getByLabel('Contraseña actual', { exact: true }).fill('browser-original-password');
    await page.getByRole('button', { name: 'Generar clave de rescate', exact: true }).click();
    const keyField = page.getByLabel('Clave de rescate generada', { exact: true });
    await keyField.waitFor();
    const rescue = await keyField.inputValue();
    check(rescue.length >= 40, 'reauthenticated setup shows a high-entropy rescue code');
    const saved = await page.evaluate(async () => {
      const auth = await (await fetch('/auth/status')).json();
      return (await fetch('/auth/vault', { method: 'PUT', headers: {
        'Content-Type': 'application/json', 'X-CSRF-Token': auth.csrf_token,
      }, body: JSON.stringify({ hf_token: 'hf_synthetic_recovery_test', budget_limit: 3, max_cost_per_run: 1 }) })).status;
    });
    check(saved === 200, 'vault can be saved after rescue setup');
    await page.getByRole('button', { name: 'Cerrar sesión', exact: true }).click();
    await page.getByRole('button', { name: 'Olvidé mi contraseña', exact: true }).click();
    await page.locator('[name="name"]').fill('rescue-user');
    await page.locator('[name="recovery_code"]').fill(rescue);
    await page.locator('[name="password"]').fill('browser-replacement-password');
    await page.locator('[name="password_confirmation"]').fill('browser-replacement-password');
    await page.getByRole('button', { name: 'Restablecer contraseña', exact: true }).click();
    await page.getByRole('status').filter({ hasText: 'Contraseña actualizada' }).waitFor();
    check(true, 'forgot-password browser flow consumes code and returns to login');
    await page.locator('[name="name"]').fill('rescue-user');
    await page.locator('[name="password"]').fill('browser-replacement-password');
    await page.getByRole('button', { name: 'Entrar', exact: true }).click();
    await page.locator('#btn-crear').waitFor();
    const vault = await page.evaluate(async () => (await fetch('/auth/vault')).json());
    check(vault.has_token === true, 'new password opens the original encrypted vault');
    check(errors.length === 0, 'no browser runtime errors');
    await page.screenshot({ path: path.join(output, 'recovered-workspace.png'), fullPage: true });
    report.success = true;
  } catch (error) { report.error = String(error); process.exitCode = 1; }
  finally {
    if (browser) await browser.close(); server.kill();
    fs.writeFileSync(path.join(output, 'report.json'), JSON.stringify(report, null, 2));
    fs.writeFileSync(path.join(output, 'server.log'), log);
    console.log(JSON.stringify(report));
  }
})();

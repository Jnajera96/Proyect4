/* Browser smoke of the frozen UI. Provider variants are presentation fixtures only.
 * node tools/verify_premium_ui.cjs <exe> <new-evidence-directory>
 */
const { spawn } = require('node:child_process');
const { mkdirSync, existsSync, writeFileSync, statSync } = require('node:fs');
const { resolve, join } = require('node:path');
const os = require('node:os');
const assert = require('node:assert/strict');
const { chromium } = require(require.resolve('playwright', { paths: [
  process.env.AI_SWE_BROWSER_MODULES || join(os.homedir(), '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules'),
] }));
const executable = resolve(process.argv[2]);
const output = resolve(process.argv[3]);
assert.ok(existsSync(executable) && !existsSync(output), 'Existing EXE and new output required');
mkdirSync(output, { recursive: true });
const report = { checks: [], paid_inference_calls: 0, provider_variants: 'UI-only HTTP fixtures, not credential validation', success: false };
const check = (name, condition) => { assert.ok(condition, name); report.checks.push(name); console.log('OK', name); };
const env = { ...process.env };
for (const key of Object.keys(env)) if (key.startsWith('AI_SWE_') || key === 'HF_TOKEN') delete env[key];
env.LOCALAPPDATA = join(output, 'profile');
const entry = statSync(executable).isDirectory()
  ? [join(executable, 'runtime/python.exe'), '-B', join(executable, 'start.py')]
  : [executable];
const server = spawn(entry[0], [...entry.slice(1), '--no-browser', '--exit-after', '50'], { cwd: output, env, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'] });
let launchOutput = '';
server.stderr.on('data', chunk => { launchOutput += chunk.toString(); });
let browser;
async function main() {
  const base = await new Promise((done, fail) => {
    const timer = setTimeout(() => fail(new Error('Launcher startup timeout: ' + launchOutput)), 45000);
    server.stdout.on('data', chunk => {
      const match = chunk.toString().match(/http:\/\/127\.0\.0\.1:\d+/);
      if (match) { clearTimeout(timer); done(match[0]); }
    });
    server.once('error', fail);
    server.once('exit', code => { clearTimeout(timer); fail(new Error('Launcher exited ' + code + ': ' + launchOutput)); });
  });
  browser = await chromium.launch({ headless: true, executablePath: process.env.AI_SWE_BROWSER_EXECUTABLE });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, reducedMotion: 'reduce' });
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  const health = await (await fetch(base + '/health')).json();
  await page.goto(base + '/app/');
  await page.locator('.proveedor-pill.not_configured').waitFor();
  await page.getByRole('status').filter({ hasText: '%LOCALAPPDATA%/AISWESystem/config/.env' }).waitFor();
  check('integrated Antigravity activity navigation present', await page.locator('.navegacion').getByRole('button', { name: 'Actividad', exact: true }).isVisible());
  check('frozen UI explains first-run configuration', await page.getByRole('status').filter({ hasText: '%LOCALAPPDATA%/AISWESystem/config/.env' }).count() === 1);
  check('no decorative waveform at rest', await page.locator('.voz-onda').count() === 0);
  await page.getByRole('button', { name: 'Abrir dictado por voz', exact: true }).click();
  check('microphone toolbar opens existing voice controls', await page.locator('#dictado').getAttribute('open') !== null && await page.getByRole('button', { name: 'Grabar', exact: true }).isVisible());
  const [chooser] = await Promise.all([page.waitForEvent('filechooser'), page.locator('button.boton-audio').click()]);
  await chooser.setFiles({ name: 'ui-smoke.wav', mimeType: 'audio/wav', buffer: Buffer.from('UklGRiQAAABXQVZFZm10IBAAAAABAAEAESsAABErAAABAAgAZGF0YQAAAAA=', 'base64') });
  check('audio toolbar opens native picker and stages audio', await page.getByRole('button', { name: 'Transcribir', exact: true }).isVisible());
  check('choosing audio does not create a run', (await (await fetch(base + '/runs')).json()).length === 0);
  await page.getByRole('button', { name: 'Descartar', exact: true }).click();
  for (const status of ['offline', 'configured']) {
    await page.route('**/health', route => route.fulfill({ json: { ...health, provider_configuration: {
      ...health.provider_configuration, status, missing_fields: [], message: 'Presentation fixture', credential_validated: false, inference_verified: false,
    } } }));
    await page.reload();
    await page.locator('.proveedor-pill.' + status).waitFor();
    await page.locator('.hero').waitFor();
    check(status + ' pill is visible', await page.locator('.proveedor-pill.' + status).isVisible());
    check(status + ' does not show missing-provider notice', await page.locator('.aviso-proveedor').count() === 0);
    if (status === 'configured') check('presence is not represented as verified credit or connectivity', (await page.locator('.proveedor-pill').getAttribute('title')).includes('sin verificar'));
    await page.unroute('**/health');
  }
  await page.reload();
  await page.locator('.proveedor-pill.not_configured').waitFor();
  await page.screenshot({ path: join(output, 'frozen-ui-light.png'), fullPage: true });
  check('native font stack and translucent material present', await page.locator('.cabecera').evaluate(el => getComputedStyle(el).backdropFilter.includes('blur(20px)') && getComputedStyle(document.body).fontFamily.includes('Segoe UI Variable Display')));
  check('reduced motion suppresses active-node animation', await page.evaluate(() => {
    const node = document.createElement('div'); node.className = 'flujo-etapa en-curso';
    node.innerHTML = '<span class="flujo-marca"></span>'; document.body.append(node);
    const stopped = getComputedStyle(node.firstElementChild).animationName === 'none'; node.remove(); return stopped;
  }));
  check('no browser runtime errors', errors.length === 0);
  report.success = true;
}
main().catch(error => { report.error = error.message; process.exitCode = 1; console.error(error); })
  .finally(async () => {
    if (browser) await browser.close();
    if (server.exitCode === null) server.kill();
    writeFileSync(join(output, 'report.json'), JSON.stringify(report, null, 2));
  });

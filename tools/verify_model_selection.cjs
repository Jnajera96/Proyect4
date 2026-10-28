/* Offline browser/API roundtrip against a real signed-Python package. */
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
const env = { ...process.env };
for (const key of Object.keys(env)) {
  if (key.startsWith('AI_SWE_') || ['HF_TOKEN', 'PYTHONPATH', 'PYTHONHOME'].includes(key)) delete env[key];
}
env.LOCALAPPDATA = path.join(output, 'userdata');
env.PATH = path.join(process.env.SYSTEMROOT, 'System32');
const server = spawn(path.join(bundle, 'runtime/python.exe'), [
  '-B', path.join(bundle, 'start.py'), '--no-browser', '--exit-after', '90',
], { env, cwd: output, windowsHide: true });
let log = '';
server.stderr.on('data', chunk => { log += chunk; });
const report = { success: false, checks: [], paid_calls: 0 };
let browser;
function check(value, label) {
  assert.ok(value, label); report.checks.push(label); console.log('OK', label);
}
(async () => {
  try {
    const base = await new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(Error('Startup timeout')), 45000);
      server.stdout.on('data', chunk => {
        const match = chunk.toString().match(/http:\/\/127\.0\.0\.1:\d+/);
        if (match) { clearTimeout(timer); resolve(match[0]); }
      });
      server.once('error', reject);
      server.once('exit', code => { clearTimeout(timer); reject(Error('Early exit: ' + code)); });
    });
    browser = await chromium.launch({ headless: true, executablePath: process.env.AI_SWE_BROWSER_EXECUTABLE });
    const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(base + '/app/');
    await page.getByRole('button', { name: 'Crear un perfil nuevo', exact: true }).click();
    await page.locator('[name="name"]').fill('selector-test');
    await page.locator('[name="password"]').fill('selector-test-password');
    await page.locator('[name="password_confirmation"]').fill('selector-test-password');
    await page.getByRole('button', { name: 'Crear perfil y entrar', exact: true }).click();
    await page.locator('#btn-crear').waitFor();
    const openVault = async () => {
      await page.getByRole('button', { name: 'Configurar bóveda', exact: true }).click();
      await page.locator('#model_name-selector').waitFor();
    };
    await openVault();
    check(await page.locator('#model_name-selector option').count() === 12, 'ten model choices plus empty and custom');
    check(await page.locator('optgroup[label="Validación E2E previa en este proyecto"] option').count() === 2,
      'one historical E2E model per role, not ten unverified claims');
    const selected = 'Qwen/Qwen2.5-Coder-32B-Instruct:nscale';
    await page.locator('#model_name-selector').selectOption(selected);
    await page.getByRole('button', { name: 'Aplicar tarifas del catálogo a los modelos elegidos' }).click();
    const prices = JSON.parse(await page.locator('[name="model_pricing"]').inputValue());
    check(prices.length === 2 && prices[0].input_per_1k === 0.00006, 'published prices converted with routed and response aliases');
    await page.locator('[name="hf_token"]').fill('hf_synthetic_not_a_real_credential');
    await page.locator('[name="budget_limit"]').fill('3');
    await page.locator('[name="roles"][value="coder"]').check();
    await page.locator('[name="roles"][value="reviewer"]').check();
    await page.getByRole('button', { name: 'Guardar bóveda', exact: true }).click();
    await page.getByRole('status').filter({ hasText: 'Bóveda guardada' }).waitFor();
    await openVault();
    check(await page.locator('#model_name-selector').inputValue() === selected &&
      await page.locator('#reviewer_model-selector').inputValue() === '', 'selection and reviewer inheritance persist through real API');
    check(await page.locator('[name="roles"][value="coder"]').isChecked() &&
      await page.locator('[name="roles"][value="reviewer"]').isChecked(), 'remote role choices persist');
    check(await page.locator('[name="hf_token"]').inputValue() === '', 'stored credential is never reflected');
    const coder = 'test-org/custom-coder:test-provider';
    const reviewer = 'test-org/custom-reviewer:test-provider';
    await page.locator('#model_name-selector').selectOption('__custom__');
    await page.locator('#model_name-custom').fill(coder);
    await page.locator('#reviewer_model-selector').selectOption('__custom__');
    await page.locator('#reviewer_model-custom').fill(reviewer);
    const customPrices = JSON.stringify([coder, reviewer].map(model => ({
      model, input_per_1k: 0.001, output_per_1k: 0.002, currency: 'USD',
    })));
    await page.locator('[name="model_pricing"]').fill(customPrices);
    await page.getByRole('button', { name: 'Aplicar tarifas del catálogo a los modelos elegidos' }).click();
    await page.getByRole('status').filter({ hasText: 'necesita sus propias tarifas' }).waitFor();
    check(await page.locator('[name="model_pricing"]').inputValue() === customPrices, 'custom models never receive invented catalog prices');
    await page.getByRole('button', { name: 'Guardar bóveda', exact: true }).click();
    await page.locator('#btn-crear').waitFor();
    await openVault();
    check(await page.locator('#model_name-custom').inputValue() === coder &&
      await page.locator('#reviewer_model-custom').inputValue() === reviewer, 'custom IDs preserved verbatim through save and reopen');
    const runs = await page.evaluate(async () => (await fetch('/runs')).json());
    check(runs.length === 0, 'configuration creates no runs or model calls');
    check(errors.length === 0, 'no browser runtime errors');
    await page.screenshot({ path: path.join(output, 'custom-models.png'), fullPage: true });
    report.success = true;
  } catch (error) {
    report.error = String(error); process.exitCode = 1;
  } finally {
    if (browser) await browser.close();
    server.kill();
    fs.writeFileSync(path.join(output, 'report.json'), JSON.stringify(report, null, 2));
    fs.writeFileSync(path.join(output, 'server.log'), log);
    console.log(JSON.stringify(report));
  }
})();

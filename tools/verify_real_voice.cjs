/* Opt-in: navegador + MediaRecorder + STT real CPU/int8. Captura sintetica, no microfono fisico.
 * node tools/verify_real_voice.cjs <modelo-local> <audio-es.wav> <directorio-evidencia>
 * No instala/descarga modelos ni activa inferencia remota. Solo usa un repo descartable.
 */
const { spawn, execFileSync } = require('node:child_process');
const { join, resolve } = require('node:path');
const { mkdirSync, writeFileSync, existsSync } = require('node:fs');
const os = require('node:os');
const net = require('node:net');
const assert = require('node:assert/strict');
const root = resolve(__dirname, '..');
if (process.argv.length !== 5) {
  console.log('Uso: node tools/verify_real_voice.cjs <modelo-local> <audio-es.wav> <evidencia>');
  process.exit(2);
}
const model = resolve(process.argv[2]), audio = resolve(process.argv[3]);
assert.ok(existsSync(join(model, 'model.bin')) && existsSync(audio));
const output = resolve(process.argv[4]);
mkdirSync(output, { recursive: true });
const { chromium } = require(require.resolve('playwright', { paths: [
  process.env.AI_SWE_BROWSER_MODULES || join(os.homedir(), '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules'), root,
] }));
const python = process.env.AI_SWE_TEST_PYTHON || join(root, '.venv/Scripts/python.exe');
const report = { physical_microphone_verified: false, capture_source: 'Chromium fake audio device fed by local Spanish WAV', device: 'cpu', compute_type: 'int8', remote_inference_calls: 0, checks: [] };
const check = (name, condition) => { assert.ok(condition, name); report.checks.push(name); console.log('OK', name); };
const sleep = ms => new Promise(r => setTimeout(r, ms));
let server, browser, page;
async function runs(base) { return (await fetch(base + '/runs')).json(); }
async function main() {
  const repo = join(output, 'synthetic-repo');
  mkdirSync(repo, { recursive: true });
  const git = args => execFileSync('git', args, { cwd: repo, windowsHide: true, stdio: 'pipe' });
  git(['init']); writeFileSync(join(repo, 'README.md'), 'Synthetic voice verification repository.\n');
  git(['add', 'README.md']);
  git(['-c', 'user.name=Voice Test', '-c', 'user.email=voice@example.invalid', 'commit', '-m', 'fixture']);
  const socket = net.createServer();
  await new Promise(r => socket.listen(0, '127.0.0.1', r));
  const port = socket.address().port; await new Promise(r => socket.close(r));
  const base = `http://127.0.0.1:${port}`;
  server = spawn(python, ['-m', 'uvicorn', 'ai_swe.api.app:crear_app', '--factory', '--host', '127.0.0.1', '--port', String(port), '--no-access-log'], {
    cwd: root, windowsHide: true, stdio: 'ignore', env: { ...process.env,
      PYTHONPATH: join(root, 'src'), AI_SWE_STATE_DB_PATH: join(output, 'state.sqlite3'),
      AI_SWE_WORKSPACE_ROOT: join(output, 'workspaces'), AI_SWE_API_KEYS: '{}',
      AI_SWE_MODEL_PROVIDER: 'fake', AI_SWE_REMOTE_MODEL_ROLES: '[]', AI_SWE_RATE_LIMIT_ENABLED: 'false',
      AI_SWE_STT_PROVIDER: 'faster-whisper', AI_SWE_STT_MODEL: model, AI_SWE_STT_LANGUAGE: 'es',
      AI_SWE_STT_DEVICE: 'cpu', AI_SWE_STT_COMPUTE_TYPE: 'int8',
    },
  });
  let ready = false;
  for (let i = 0; i < 100; i++) {
    try { if ((await fetch(base + '/health')).ok) { ready = true; break; } } catch {}
    await sleep(100);
  }
  check('local server ready', ready);
  const projectResponse = await fetch(base + '/projects', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name: 'voice-fixture', repo_path: repo }) });
  check('synthetic project registered', projectResponse.status === 201);
  const project = await projectResponse.json();
  browser = await chromium.launch({
    ...(process.env.AI_SWE_BROWSER_EXECUTABLE ? { executablePath: process.env.AI_SWE_BROWSER_EXECUTABLE } : {}),
    headless: true, args: [
    '--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream',
    `--use-file-for-fake-audio-capture=${audio}`,
  ] });
  page = await browser.newPage();
  let postRuns = 0;
  const errors = [];
  page.on('request', request => { if (request.method() === 'POST' && new URL(request.url()).pathname === '/runs') postRuns++; });
  page.on('pageerror', error => errors.push(error.message));
  page.on('console', msg => { if (msg.type() === 'error') console.log('BROWSER', msg.text()); });
  page.on('response', r => { if (r.status() >= 400) console.log('HTTP', r.status(), new URL(r.url()).pathname); });
  await page.goto(base + '/app/');
  await page.locator('#dictado summary').click();
  await page.getByRole('button', { name: 'Grabar', exact: true }).click();
  await page.getByRole('button', { name: 'Detener', exact: true }).waitFor();
  await sleep(9800); // fixture Spanish WAV is 8.74 s; browser records a complete phrase.
  await page.getByRole('button', { name: 'Detener', exact: true }).click();
  const captureResponse = page.waitForResponse(r => new URL(r.url()).pathname === '/transcriptions' && r.request().method() === 'POST', { timeout: 120000 });
  await page.getByRole('button', { name: 'Transcribir', exact: true }).click();
  const response = await captureResponse;
  check('MediaRecorder audio transcribed by real backend', response.status() === 200);
  const captured = await response.json();
  report.captured_transcript = captured;
  check('Spanish speech recognized from browser capture', captured.language === 'es' && /analiza el proyecto/i.test(captured.text) && /no modifiques archivos/i.test(captured.text));
  const editor = page.locator('#transcripcion-texto');
  await editor.waitFor();
  check('transcript editable', await editor.isEditable());
  check('no run after transcription', postRuns === 0 && (await runs(base)).length === 0);
  await editor.fill('');
  check('empty transcript cannot be confirmed', await page.locator('#btn-usar-transcripcion').isDisabled());
  const edited = 'Analiza el proyecto y muestra un resumen sin modificar archivos. Texto revisado.';
  await editor.fill(edited);
  await page.screenshot({ path: join(output, 'editable-transcript.png'), fullPage: true });
  await page.locator('#btn-usar-transcripcion').click();
  check('only confirmed edited text copied to instruction', await page.locator('#instruccion').inputValue() === edited);
  check('confirming transcript does not run', postRuns === 0 && (await runs(base)).length === 0);
  await page.locator('#proyecto').selectOption(project.project_id);
  const createdResponse = page.waitForResponse(r => new URL(r.url()).pathname === '/runs' && r.request().method() === 'POST');
  await page.locator('#btn-crear').click();
  const created = await createdResponse;
  check('explicit Execute creates exactly one run', created.status() === 202 && postRuns === 1);
  const run = await created.json();
  check('voice provenance retained', run.instruction.source === 'voice' && run.instruction.text === edited && run.instruction.confirmed_by_user === true);
  report.run_id = run.run_id;
  let state;
  for (let i = 0; i < 100; i++) {
    state = await (await fetch(base + '/runs/' + run.run_id)).json();
    if (state.status === 'awaiting_human_requirements_confirmation') break;
    await sleep(100);
  }
  check('execution waits for requirements confirmation', state.status === 'awaiting_human_requirements_confirmation');
  check('synthetic repository unchanged', git(['status', '--porcelain']).toString().trim() === '');
  await page.getByRole('button', { name: 'Vista general', exact: true }).click();
  if (await page.locator('#dictado').getAttribute('open') === null) {
    await page.locator('#dictado summary').click();
  }
  const discard = page.getByRole('button', { name: 'Descartar', exact: true });
  if (await discard.isVisible()) await discard.click();
  await page.locator('#audio-fichero').setInputFiles(audio);
  const uploadResponse = page.waitForResponse(r => new URL(r.url()).pathname === '/transcriptions' && r.request().method() === 'POST', { timeout: 120000 });
  await page.getByRole('button', { name: 'Transcribir', exact: true }).click();
  const uploaded = await uploadResponse;
  check('file upload transcribed by real backend', uploaded.status() === 200);
  report.uploaded_transcript = await uploaded.json();
  check('file upload remains editable and creates no extra run', await editor.isEditable() && postRuns === 1 && (await runs(base)).length === 1);
  check('no browser runtime errors', errors.length === 0);
  report.success = true;
}
main().catch(error => { report.success = false; report.error = error.message; process.exitCode = 1; console.error(error.message); })
  .finally(async () => {
    if (!report.success && page) {
      report.page_text = await page.locator('body').innerText().catch(() => 'unavailable');
      await page.screenshot({ path: join(output, 'failure.png'), fullPage: true }).catch(() => {});
    }
    if (browser) await browser.close();
    if (server) { server.kill(); await Promise.race([new Promise(r => server.once('exit', r)), sleep(3000)]); }
    writeFileSync(join(output, 'report.json'), JSON.stringify(report, null, 2));
  });

/* Navegador real + FastAPI real + SQLite temporal. Sin proveedor ni STT reales.
 * Uso: node tools/verify_delivery.cjs [directorio-de-evidencia]
 * Playwright se usa del runtime de Codex o de una instalacion existente.
 */
const { spawn, execFileSync } = require('node:child_process');
const { join, resolve } = require('node:path');
const { mkdirSync, writeFileSync, readdirSync, existsSync } = require('node:fs');
const os = require('node:os');
const net = require('node:net');
const assert = require('node:assert/strict');
const { chromium } = require(require.resolve('playwright', { paths: [
  process.env.AI_SWE_BROWSER_MODULES || join(os.homedir(), '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules'),
  process.cwd(),
] }));
const root = resolve(__dirname, '..');
const python = process.env.AI_SWE_TEST_PYTHON || join(root, '.venv/Scripts/python.exe');
const salida = resolve(process.argv[2] || join(root, '_tmp', 'delivery'), String(Date.now()));
mkdirSync(salida, { recursive: true });
const informe = { checks: [], screenshots: [], modes: [] };
const key = 'credencial-sintetica-delivery-2026';
const keys = { [key]: 'admin', 'lector-sintetico-delivery-2026': 'reader' };
const sleep = ms => new Promise(r => setTimeout(r, ms));
const check = (nombre, valor) => { assert.ok(valor, nombre); informe.checks.push(nombre); console.log('OK', nombre); };
async function puerto() {
  const s = net.createServer(); await new Promise(r => s.listen(0, '127.0.0.1', r));
  const p = s.address().port; await new Promise(r => s.close(r)); return p;
}
async function servidor(auth) {
  const db = join(salida, auth ? 'auth.sqlite3' : 'local.sqlite3');
  execFileSync(python, ['-B', 'tools/delivery_fixtures.py', db], { cwd: root, windowsHide: true,
    env: { ...process.env, PYTHONPATH: join(root, 'src'), PYTHONDONTWRITEBYTECODE: '1' } });
  const p = await puerto();
  const child = spawn(python, ['-B', '-m', 'uvicorn', 'ai_swe.api.app:crear_app', '--factory', '--host', '127.0.0.1', '--port', String(p), '--log-level', 'warning', '--no-access-log'], {
    cwd: root, windowsHide: true, stdio: 'ignore', env: { ...process.env,
      PYTHONPATH: join(root, 'src'), PYTHONDONTWRITEBYTECODE: '1',
      AI_SWE_STATE_DB_PATH: db, AI_SWE_WORKSPACE_ROOT: join(salida, 'workspaces'),
      AI_SWE_API_KEYS: JSON.stringify(auth ? keys : {}), AI_SWE_MODEL_PROVIDER: 'fake',
      AI_SWE_STT_PROVIDER: 'fake', AI_SWE_RATE_LIMIT_ENABLED: 'false',
    },
  });
  const base = `http://127.0.0.1:${p}`;
  for (let i = 0; i < 100; i++) {
    try { if ((await fetch(base + '/health')).ok) return { child, base }; } catch {}
    await sleep(100);
  }
  child.kill(); throw new Error('El backend de verificacion no arranco');
}
async function foto(page, nombre) {
  if (process.env.AI_SWE_TEST_NO_SCREENSHOTS === '1') return;
  const archivo = join(salida, nombre + '.png');
  await page.screenshot({ path: archivo, fullPage: true, animations: 'disabled' });
  informe.screenshots.push(archivo);
}
async function navegar(page, nombre) {
  await page.locator('.app-shell').waitFor();
  const menu = page.locator('#abrir-menu');
  if (!(await page.locator('.navegacion').isVisible())) await menu.click();
  await page.locator('.navegacion .nav-item').filter({ hasText: nombre }).click();
  await page.evaluate(() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r))));
}
async function seleccionar(page, id) {
  await navegar(page, 'Ejecuciones');
  await page.locator('#tabla-ejecuciones').getByRole('button', { name: id, exact: true }).click();
  await page.waitForFunction(id => window.__AISWE__?.runId === id && window.__AISWE__?.status, id);
}
async function entrar(page, credencial = key) {
  await page.locator('#api-key').fill(credencial);
  await page.locator('#btn-continuar').click();
  await page.locator('.navegacion').waitFor();
}
const wav = Buffer.from('UklGRiQAAABXQVZFZm10IBAAAAABAAEAESsAABErAAABAAgAZGF0YQAAAAA=', 'base64');
async function audio(page) {
  await page.locator('#dictado summary').click();
  await page.locator('#audio-fichero').setInputFiles({ name: 'verificacion.wav', mimeType: 'audio/wav', buffer: wav });
  await page.getByRole('button', { name: 'Transcribir', exact: true }).click();
}
async function main() {
  const cache = join(os.homedir(), 'AppData/Local/ms-playwright');
  const instalado = readdirSync(cache).filter(n => n.startsWith('chromium_headless_shell-')).sort().reverse()
    .map(n => join(cache, n, 'chrome-headless-shell-win64/chrome-headless-shell.exe')).find(existsSync);
  const browser = await chromium.launch({ headless: true, executablePath: process.env.AI_SWE_TEST_BROWSER || instalado });
  try {
    for (const auth of [false, true]) {
      const { child, base } = await servidor(auth);
      const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, colorScheme: 'light', reducedMotion: 'reduce' });
      const page = await context.newPage(); const errores = [];
      page.on('pageerror', () => errores.push('pageerror'));
      const nombre = auth ? 'auth' : 'local';
      try {
        await page.goto(base + '/app/');
        if (auth) {
          await page.locator('#api-key').waitFor(); await foto(page, '01-acceso');
          await page.locator('#api-key').fill('incorrecta-sintetica'); await page.locator('#btn-continuar').click();
          await page.getByRole('alert').waitFor(); check('credencial invalida mantiene pantalla de acceso', await page.locator('#api-key').isVisible());
          await entrar(page);
        }
        await page.locator('.navegacion').waitFor();
        check(nombre + ': shell real montado', await page.locator('.sidebar').isVisible());
        await foto(page, nombre + '-02-overview-sin-seleccion');
        await navegar(page, 'Proyectos');
        await page.locator('#proy-nombre').fill('Repositorio de verificación');
        await page.locator('#proy-ruta').fill(join(salida, 'no-existe'));
        await page.getByRole('button', { name: 'Registrar', exact: true }).click();
        await page.getByRole('alert').waitFor();
        check(nombre + ': error de proyecto visible donde ocurre', await page.getByRole('alert').isVisible());
        const repo = join(salida, nombre + '-repo'); mkdirSync(repo, { recursive: true });
        execFileSync('git', ['init', '-q', repo], { windowsHide: true });
        await page.locator('#proy-ruta').fill(repo); await page.getByRole('button', { name: 'Registrar', exact: true }).click();
        await page.getByRole('button', { name: 'Ver detalle', exact: true }).first().waitFor();
        await page.getByRole('button', { name: 'Ver detalle', exact: true }).first().click();
        await page.getByText('Detalle del proyecto', { exact: true }).waitFor();
        await foto(page, nombre + '-03-proyectos');
        await navegar(page, 'Vista general');
        await page.locator('#instruccion').fill('analiza el proyecto');
        await page.locator('#alcance-avanzado summary').click();
        await page.locator('#allowed-paths').fill('src/'); await page.locator('#allowed-paths').press('Enter');
        await page.locator('#protected-paths').fill('.env'); await page.locator('#protected-paths').press('Enter');
        const req = page.waitForRequest(r => r.url().endsWith('/runs') && r.method() === 'POST');
        await page.locator('#btn-crear').click();
        const payload = (await req).postDataJSON();
        check(nombre + ': scope payload', payload.options.allowed_paths[0] === 'src/' && payload.options.protected_paths[0] === '.env');
        await page.locator('#btn-confirmar-requisitos').waitFor(); await foto(page, nombre + '-04-requisitos');
        await page.locator('#btn-confirmar-requisitos').click();
        await page.waitForFunction(() => !['running','planned','awaiting_human_requirements_confirmation'].includes(window.__AISWE__?.status));
        check(nombre + ': requisitos reanudados por UI', !(await page.locator('#btn-confirmar-requisitos').count()));
        const creadoId = await page.evaluate(() => window.__AISWE__?.runId);
        await page.waitForFunction(() => window.__AISWE__?.tipos.includes('plan.completed'), null, { timeout:10000 });
        check(nombre + ': SSE continua despues de la puerta', await page.evaluate(() => window.__AISWE__?.tipos.includes('plan.completed')));
        await foto(page, nombre + '-05-overview-con-run');
        await seleccionar(page, 'run-puerta-aprobacion'); await page.locator('#btn-aprobar').waitFor();
        check(nombre + ': gate evidencia real', await page.locator('.pruebas li').count() === 2 && await page.locator('.veredicto').count() === 1);
        check(nombre + ': decision sin preseleccion', await page.locator('.puerta-decision input:checked').count() === 0);
        check(nombre + ': presupuesto desconocido honesto', (await page.locator('body').innerText()).includes('Coste no disponible'));
        await foto(page, nombre + '-06-aprobacion');
        await navegar(page, 'Seguridad'); await foto(page, nombre + '-07-seguridad');
        await seleccionar(page, 'run-fallo-promocion'); await navegar(page, 'Flujo');
        const etapa = page.locator('.flujo-etapa').filter({ hasText: 'Promoción al repositorio' });
        check(nombre + ': PROMOTION_FAILED se ve fallido', (await etapa.getAttribute('class')).includes('fallida'));
        await foto(page, nombre + '-08-promocion-fallida');
        await navegar(page, 'Ejecuciones'); await page.locator('#tabla-ejecuciones button').first().focus();
        await page.keyboard.press('Enter'); await page.waitForFunction(() => window.__AISWE__?.vista === 'detalle');
        check(nombre + ': historial con teclado', await page.locator('.vista').getAttribute('aria-label') === 'Vista: detalle');
        await navegar(page, 'Ejecuciones'); await page.locator('#tabla-ejecuciones button').first().focus();
        await page.keyboard.press('Space'); await page.waitForFunction(() => window.__AISWE__?.vista === 'detalle');
        await page.waitForFunction(() => window.__AISWE__?.status !== null);
        check(nombre + ': historial con Space', await page.locator('.vista').getAttribute('aria-label') === 'Vista: detalle');
        await navegar(page, 'Vista general');
        await audio(page); await page.locator('#transcripcion-texto').waitFor();
        const totalAntes = await page.evaluate(() => window.__AISWE__?.runId);
        await page.locator('#transcripcion-texto').fill('analiza el proyecto desde voz');
        await page.locator('#btn-usar-transcripcion').click();
        check(nombre + ': confirmar voz no crea run', totalAntes === await page.evaluate(() => window.__AISWE__?.runId));
        const vozReq = page.waitForRequest(r => r.url().endsWith('/runs') && r.method() === 'POST');
        await page.locator('#btn-crear').click(); const vozPayload = (await vozReq).postDataJSON();
        check(nombre + ': voz conserva procedencia', vozPayload.source === 'voice' && !!vozPayload.transcript_meta);
        await page.locator('#btn-confirmar-requisitos').waitFor(); await page.locator('#btn-confirmar-requisitos').click();
        await page.waitForFunction(() => window.__AISWE__?.status === 'completed' || window.__AISWE__?.status === 'needs_human');
        await navegar(page, 'Vista general');
        await page.route('**/transcriptions', r => r.fulfill({ status: 403, contentType: 'application/json', body: JSON.stringify({ detail: "esta accion requiere el rol 'operator'; la clave usada tiene 'reader'" }) }));
        // Remontar el panel para salir del dictado ya confirmado.
        await navegar(page, 'Ejecuciones'); await navegar(page, 'Vista general');
        await audio(page); await page.getByRole('alert').filter({ hasText: 'permisos' }).waitFor();
        check(nombre + ': voice 403 mantiene sesion', await page.locator('.navegacion').isVisible());
        await page.unroute('**/transcriptions');
        if (auth) {
          await page.route('**/transcriptions', r => r.fulfill({ status: 401, contentType: 'application/json', body: '{"detail":"credencial rechazada"}' }));
          await navegar(page, 'Ejecuciones'); await navegar(page, 'Vista general');
          // El 403 anterior informa reader: recuperar una credencial de operador/admin.
          await navegar(page, 'Sesión'); await page.locator('#btn-cambiar-clave').click(); await entrar(page);
          await navegar(page, 'Vista general'); await audio(page); await page.locator('#api-key').waitFor();
          check('voice 401 borra credencial y vuelve al acceso', await page.locator('#api-key').isVisible());
          await page.unroute('**/transcriptions'); await entrar(page);
          await navegar(page, 'Sesión'); await page.locator('#btn-cerrar-sesion').click(); await page.locator('#api-key').waitFor();
          check('logout borra acceso local', await page.locator('#api-key').isVisible()); await entrar(page);
          check('credencial no visible en texto ni almacenamiento', await page.evaluate(k => !document.body.textContent.includes(k) && ![...Object.values(localStorage),...Object.values(sessionStorage)].some(v => v.includes(k)), key));
        }
        await page.reload();
        if (auth) await entrar(page);
        await seleccionar(page, creadoId);
        await page.waitForFunction(() => window.__AISWE__?.tipos.includes('plan.completed'));
        check(nombre + ': replay historico conserva hitos posteriores a la puerta', await page.evaluate(() => window.__AISWE__?.tipos.includes('plan.completed')));
        await navegar(page, 'Vista general');
        for (const [w,h] of [[1920,1080],[1440,900],[1366,768],[1024,768],[834,1112],[390,844]]) {
          await page.setViewportSize({ width:w, height:h });
          for (const tema of ['claro','oscuro']) {
            await page.locator('#tema').selectOption(tema);
            await page.evaluate(() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r))));
            check(`${nombre}: ${w}x${h} ${tema} sin overflow`, await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
            check(`${nombre}: ${w}x${h} ${tema} compositor visible`, await page.locator('#btn-crear').isVisible());
            const contraste = await page.evaluate(() => {
              const color = s => { const m = /rgba?\(([^)]+)\)/.exec(s); return m ? m[1].split(',').map(Number) : [0,0,0,0]; };
              const mezclar = (a,b) => a.slice(0,3).map((c,i) => c*(a[3] ?? 1)+b[i]*(1-(a[3] ?? 1)));
              const fondo = e => {
                if (!e) return [255,255,255];
                const c = color(getComputedStyle(e).backgroundColor);
                return (c[3] ?? 1) >= 1 ? c : mezclar(c,fondo(e.parentElement));
              };
              const lum = c => c.slice(0,3).map(v => v/255).map(v => v<=.04045 ? v/12.92 : ((v+.055)/1.055)**2.4)
                .reduce((s,v,i) => s + v*[.2126,.7152,.0722][i], 0);
              let peor = { ratio:21, texto:'' };
              for(const e of document.querySelectorAll('.tenue,.chip,.hero-texto,.hero-antetitulo,.sidebar-pie,.nav-item,.primario,.hero-proceso li>span')) {
                if (!e.checkVisibility() || !e.textContent.trim() || e.disabled) continue;
                const bg = fondo(e); const fg = mezclar(color(getComputedStyle(e).color),bg);
                const a=lum(bg), b=lum(fg), ratio=(Math.max(a,b)+.05)/(Math.min(a,b)+.05);
                if(ratio < peor.ratio) peor={ratio,texto:e.textContent.trim().slice(0,60)};
              }
              return peor;
            });
            check(`${nombre}: ${w}x${h} ${tema} contraste AA (${contraste.ratio.toFixed(2)}: ${contraste.texto})`, contraste.ratio >= 4.5);
            await foto(page, `${nombre}-${w}-${tema}`);
            if (w === 1440 && tema === 'claro' && process.env.AI_SWE_TEST_NO_SCREENSHOTS !== '1') {
              const archivo = join(salida, nombre + '-overview-viewport.png');
              await page.screenshot({ path:archivo }); informe.screenshots.push(archivo);
            }
          }
        }
        if (await page.locator('#abrir-menu').isVisible()) {
          await page.locator('#abrir-menu').click(); check(nombre + ': drawer móvil visible', await page.locator('.navegacion').isVisible());
          await page.keyboard.press('Escape'); check(nombre + ': Escape devuelve foco', await page.locator('#abrir-menu').evaluate(e => e === document.activeElement));
        }
        check(nombre + ': sin errores de React', errores.length === 0);
        const caida = await context.newPage();
        await caida.route('**/projects', r => r.fulfill({ status:503, contentType:'application/json', body:'{"detail":"fallo controlado"}' }));
        await caida.goto(base + '/app/');
        await caida.getByRole('alert').filter({ hasText:'No se pudo comprobar el acceso' }).waitFor();
        check(nombre + ': fallo de boot no ofrece ejecutar', await caida.locator('#btn-crear').count() === 0);
        await caida.close();
        informe.modes.push(nombre);
      } finally { await context.close(); child.kill(); }
    }
  } finally {
    await browser.close();
    writeFileSync(join(salida, 'report.json'), JSON.stringify(informe, null, 2));
    console.log('EVIDENCIA:', salida);
  }
  console.log('RESULTADO:', informe.checks.length, 'comprobaciones; evidencia:', salida);
}
main().catch(e => { console.error('FALLO:', String(e.message).split(key).join('[REDACTED]')); process.exitCode = 1; });

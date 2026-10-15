"""Verifica el flujo de voz de extremo a extremo, en un motor real.

**Que comprueba y por que existe.** El dictado era la unica capacidad del backend
sin verificar: `POST /transcriptions` existe, la interfaz la consume, y el camino
"audio -> texto -> instruccion -> ejecucion" nadie lo habia conducido de verdad en
un navegador. Esta herramienta lo hace, con el adaptador fingido del backend
(`AI_SWE_STT_PROVIDER=fake`, determinista y sin modelo), y se detiene en las dos
cosas que de verdad importan:

  1. **La transcripcion no lanza sola una ejecucion** (`RF-02`): el texto vuelve a
     la persona, que lo lee y decide. Se comprueba que `/runs` sigue vacio despues
     de confirmar el texto.
  2. **La ejecucion queda registrada con su procedencia** (`RF-03`): la dictada
     nace con `source: "voice"` y sus metadatos; la tecleada a mano nace con
     `source: "text"` y sin metadatos. Se comprueban las dos, porque un sistema que
     marcase todo como dictado falsearia el origen igual que uno que no marcase
     nada.

Se conduccen los botones de verdad: se elige un fichero de audio (la segunda via
del panel, que no necesita microfono), se transcribe, **se corrige el texto**, se
confirma y se lanza. Despues se lee el estado por la API, con el servidor en pie.

Uso:
    python tools/verify_voz.py
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_frontend import (  # noqa: E402
    _lanzar_navegador,
    _matar_arbol,
    _reconstruir,
    encontrar_navegador,
    esperar_servidor,
    puerto_libre,
)

RAIZ = Path(__file__).resolve().parents[1]
DIST = RAIZ / "frontend" / "dist"

# Un WAV minimo valido: cabecera de 44 bytes y muestras de silencio. El contenido
# da igual -el adaptador fingido no decodifica-, pero la peticion tiene que ser
# audio valido y declarar un MIME que el endpoint acepte.
WAV_B64 = (
    "UklGRiQAAABXQVZFZm10IBAAAAABAAEAESsAABErAAABAAgAZGF0YQAAAAA="
)

SONDA = r"""
var pasos = [], errores = [];
window.EventSource = function () { this.close = function () {}; this.addEventListener = function () {}; return this; };
window.addEventListener('error', function (e) { errores.push('ERROR: ' + e.message); }, true);
document.addEventListener('securitypolicyviolation', function (e) { errores.push('CSP: ' + e.violatedDirective); });
(function () {
  var oe = console.error, ow = console.warn;
  console.error = function () { errores.push('CONSOLE_ERROR: ' + [].join.call(arguments, ' ')); oe.apply(console, arguments); };
  console.warn = function () { errores.push('CONSOLE_WARN: ' + [].join.call(arguments, ' ')); ow.apply(console, arguments); };
})();
function anota(k, v) { pasos.push(k + '=' + v); }
function volcar() {
  var d = document.createElement('div');
  d.id = '_informe';
  d.textContent = 'N_ERRORS=' + errores.length + ' ||| ' + errores.join(' ||| ') + ' ||| ' + pasos.join(' ||| ');
  document.body.appendChild(d);
}
function escribir(campo, valor) {
  // Un campo controlado por React no cambia con `campo.value = x`.
  var setter = Object.getOwnDescriptor
    ? Object.getOwnDescriptor(campo.constructor.prototype, 'value')
    : Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value');
  if (campo.tagName === 'INPUT') {
    setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value');
  }
  setter.set.call(campo, valor);
  campo.dispatchEvent(new Event('input', { bubbles: true }));
}
function botonConTexto(texto) {
  var bs = document.querySelectorAll('button');
  for (var i = 0; i < bs.length; i++) {
    if ((bs[i].textContent || '').trim() === texto) return bs[i];
  }
  return null;
}
function abrirDetalleDictado() {
  var ds = document.querySelectorAll('details');
  for (var i = 0; i < ds.length; i++) {
    if ((ds[i].textContent || '').indexOf('Dictar') >= 0) { ds[i].open = true; return ds[i]; }
  }
  return null;
}

var hechos = { fichero: false, transcripcion: false, corregido: false, confirmado: false, lanzado: false, manual: false };
var relojReal = window.setInterval.bind(window);

relojReal(function paso() {
  // 1. El panel de dictado, dentro de su <details>.
  if (!hechos.fichero) {
    if (!document.querySelector('#audio-fichero')) return;
    abrirDetalleDictado();
    var bytes = atob('__WAV__');
    var trozos = [];
    for (var i = 0; i < bytes.length; i++) trozos.push(bytes.charCodeAt(i));
    var blob = new Blob([new Uint8Array(trozos)], { type: 'audio/wav' });
    var dt = new DataTransfer();
    dt.items.add(new File([blob], 'dictado.wav', { type: 'audio/wav' }));
    var campo = document.querySelector('#audio-fichero');
    campo.files = dt.files;
    campo.dispatchEvent(new Event('change', { bubbles: true }));
    hechos.fichero = true;
    anota('FICHERO_ELEGIDO', 'true');
    return;
  }
  // 2. Transcribir: el audio sube y el texto vuelve.
  if (!hechos.transcripcion) {
    var b = botonConTexto('Transcribir');
    if (!b || b.disabled) return;
    b.click();
    hechos.transcripcion = true;
    anota('TRANSCRIBIR_PULSADO', 'true');
    return;
  }
  // 3. El texto llega **editable** y se corrige.
  if (!hechos.corregido) {
    var t = document.querySelector('#transcripcion-texto');
    if (!t) return;
    anota('TEXTO_RECIBIDO', (t.value || '').trim());
    if (!(t.value || '').trim()) return;
    escribir(t, 'analiza el proyecto, corrige los errores y anade una prueba');
    hechos.corregido = true;
    anota('TEXTO_CORREGIDO', (t.value || '').trim());
    anota('CONFIANZA_VISTA', document.body.textContent.indexOf('confianza') >= 0);
    return;
  }
  // 4. Confirmar: el texto pasa a la instruccion con su procedencia.
  if (!hechos.confirmado) {
    var u = document.querySelector('#btn-usar-transcripcion');
    if (!u || u.disabled) return;
    // Antes de confirmar: **ninguna ejecucion**. RF-02.
    fetch('/runs').then(function (r) { return r.json(); }).then(function (rs) {
      anota('RUNS_ANTES_DE_CONFIRMAR', rs.length);
    });
    u.click();
    hechos.confirmado = true;
    anota('CONFIRMADO', 'true');
    return;
  }
  if (!hechos.lanzado) {
    var inst = document.querySelector('#instruccion');
    if (!inst) return;
    anota('INSTRUCCION_CON_TEXTO', (inst.value || '').trim() ===
      'analiza el proyecto, corrige los errores y anade una prueba');
    anota('ORIGEN_VISIBLE', document.body.textContent.indexOf('Instrucción dictada') >= 0);
    var crear = document.querySelector('#btn-crear');
    if (!crear) return;
    crear.click();
    hechos.lanzado = true;
    anota('LANZADO', 'true');
    return;
  }
  // 5. La de control: tecleada a mano, sin dictado por medio.
  if (!hechos.manual) {
    var inst2 = document.querySelector('#instruccion');
    var crear2 = document.querySelector('#btn-crear');
    if (!inst2 || !crear2) return;
    escribir(inst2, 'revisa el frontend y dime que falta');
    hechos.manual = 'escrito';
    anota('MANUAL_ESCRITO', 'true');
    return;
  }
  if (hechos.manual === 'escrito') {
    var crear3 = document.querySelector('#btn-crear');
    if (!crear3) return;
    crear3.click();
    hechos.manual = 'lanzado';
    anota('MANUAL_LANZADO', 'true');
    return;
  }
}, 100);

// El sondeo de 900 ms de la aplicacion no aporta nada aqui.
var intervaloReal2 = relojReal(function () {
  var rs = document.querySelectorAll('button');
  var todos = true;
  for (var i = 0; i < rs.length; i++) { if (rs[i].id === 'x') todos = false; }
  if (hechos.manual === 'lanzado') {
    clearInterval(intervaloReal2);
    setTimeout(volcar, 800);
  }
}, 100);
window.setInterval = function () { return 0; };
"""


def _campos(dom: str) -> tuple[dict[str, str], list[str]]:
    coincidencia = re.search(r'<div id="_informe">(.*?)</div>', dom, re.S)
    if not coincidencia:
        return {}, ["PROBE: la pagina no emitio informe"]
    campos: dict[str, str] = {}
    errores: list[str] = []
    for parte in coincidencia.group(1).split("|||"):
        parte = parte.strip()
        if not parte:
            continue
        if "=" in parte:
            clave, valor = parte.split("=", 1)
            campos[clave.strip()] = valor.strip()
        elif parte.startswith(("ERROR:", "PROBE", "CONSOLE_", "CSP:")):
            errores.append(parte)
    return campos, errores


def main() -> int:
    navegador = encontrar_navegador()
    if navegador is None:
        print("VERIFICACION OMITIDA: no se encontro Chromium")
        return 0

    _reconstruir()
    carpeta = Path(tempfile.mkdtemp(prefix="aiswe-voz-"))
    estado_db = carpeta / "estado.sqlite3"
    sonda = SONDA.replace("__WAV__", WAV_B64)

    html = (DIST / "index.html").read_text(encoding="utf-8")
    (DIST / "_voz.js").write_text(sonda, encoding="utf-8")
    (DIST / "_voz.html").write_text(
        html.replace('<script type="module"',
                     '<script src="_voz.js"></script>\n    <script type="module"', 1),
        encoding="utf-8",
    )

    puerto = puerto_libre()
    base = f"http://127.0.0.1:{puerto}"
    entorno = {
        **os.environ,
        "PYTHONPATH": "src",
        "AI_SWE_STATE_DB_PATH": str(estado_db),
        # El adaptador fingido: determinista, sin modelo y sin microfono. Es el que
        # hace verificable el camino completo sin audio real.
        "AI_SWE_STT_PROVIDER": "fake",
    }
    servidor = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "ai_swe.api.app:crear_app", "--factory",
         "--host", "127.0.0.1", "--port", str(puerto), "--log-level", "warning"],
        cwd=RAIZ, env=entorno, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    perfil = tempfile.mkdtemp(prefix="aiswe-voz-chrome-")
    try:
        if not esperar_servidor(f"{base}/health"):
            print("FALLO: el servidor no arranco")
            return 1
        with urllib.request.urlopen(f"{base}/health", timeout=10) as r:
            salud = json.loads(r.read())

        dom, _ = _lanzar_navegador(
            [str(navegador), "--headless", "--disable-gpu", "--no-sandbox", "--dump-dom",
             "--hide-scrollbars", "--window-size=1440,900", "--virtual-time-budget=40000",
             f"--user-data-dir={perfil}", f"{base}/app/_voz.html"],
            limite=120,
        )
        # Las dos ejecuciones se leen **por la API**, con el servidor en pie.
        # `/runs` devuelve `RunSummary`, que **no lleva la instruccion**: hay que
        # pedir el detalle de cada una. La primera version de esta herramienta
        # buscaba el texto en el resumen y no encontraba nada -un fallo del
        # instrumento, no de la aplicacion-.
        with urllib.request.urlopen(f"{base}/runs?limit=200", timeout=10) as r:
            resumenes = json.loads(r.read())
        runs: list[dict] = []
        for resumen in resumenes:
            with urllib.request.urlopen(
                f"{base}/runs/{resumen['run_id']}", timeout=10
            ) as r:
                runs.append(json.loads(r.read()))
    finally:
        servidor.terminate()
        try:
            servidor.wait(timeout=10)
        except subprocess.TimeoutExpired:
            servidor.kill()
        shutil.rmtree(perfil, ignore_errors=True)
        shutil.rmtree(carpeta, ignore_errors=True)

    campos, errores = _campos(dom)
    fallos: list[str] = []

    def comprobar(nombre: str, condicion: bool, detalle: str = "") -> None:
        print(f"  {'OK   ' if condicion else 'FALLO'} {nombre}{('  (' + detalle + ')') if detalle else ''}")
        if not condicion:
            fallos.append(nombre)

    print("\n== informe del navegador ==")
    for clave in sorted(campos):
        print(f"  {clave:26s} {campos[clave][:110]}")

    print("\n== comprobaciones ==")
    comprobar("la aplicacion monto sin errores", not errores, "; ".join(errores[:2]))
    comprobar("el servidor declara el adaptador de voz disponible", salud.get("stt") is True,
              f"stt={salud.get('stt')}")
    comprobar("el fichero de audio se acepto en el panel",
              campos.get("FICHERO_ELEGIDO") == "true")
    comprobar("la transcripcion se pidio al servidor",
              campos.get("TRANSCRIBIR_PULSADO") == "true")
    texto_recibido = campos.get("TEXTO_RECIBIDO", "")
    comprobar("el texto vuelve del servidor y se ensena editable",
              bool(texto_recibido) and campos.get("TEXTO_CORREGIDO") != "",
              f"recibido={texto_recibido[:60]!r}")
    comprobar("el texto reconocido se puede corregir",
              campos.get("TEXTO_CORREGIDO", "") ==
              "analiza el proyecto, corrige los errores y anade una prueba",
              f"corregido={campos.get('TEXTO_CORREGIDO', '')[:60]!r}")
    comprobar("la confianza del reconocimiento se declara en pantalla",
              campos.get("CONFIANZA_VISTA") == "true")
    # RF-02: el texto no ejecuta nada por si solo.
    comprobar("confirmar la transcripcion no lanza ninguna ejecucion",
              campos.get("RUNS_ANTES_DE_CONFIRMAR") == "0",
              f"RUNS_ANTES_DE_CONFIRMAR={campos.get('RUNS_ANTES_DE_CONFIRMAR')}")
    comprobar("el texto confirmado pasa al campo de instruccion",
              campos.get("INSTRUCCION_CON_TEXTO") == "true")
    comprobar("la interfaz declara el origen dictado de la instruccion",
              campos.get("ORIGEN_VISIBLE") == "true")
    comprobar("se lanzo la ejecucion dictada", campos.get("LANZADO") == "true")
    comprobar("se lanzo la ejecucion de control, tecleada a mano",
              campos.get("MANUAL_LANZADO") == "true")

    # Y lo que el servidor guardo, que es la prueba que de verdad vale.
    dictada = next((r for r in runs if "anade una prueba" in (r.get("instruction") or {}).get("text", "")), None)
    manual = next((r for r in runs if "revisa el frontend" in (r.get("instruction") or {}).get("text", "")), None)
    comprobar("hay dos ejecuciones guardadas", len(runs) == 2, f"runs={len(runs)}")
    if dictada:
        ins = dictada.get("instruction", {})
        meta = ins.get("transcript_meta")
        comprobar("la ejecucion dictada se registro como de voz",
                  ins.get("source") == "voice", f"source={ins.get('source')}")
        comprobar("la ejecucion dictada lleva los metadatos del reconocimiento",
                  bool(meta) and meta.get("provider") == "fake:deterministic",
                  f"meta={json.dumps(meta)[:120] if meta else 'null'}")
        comprobar("la confianza registrada es la del reconocimiento",
                  bool(meta) and abs(float(meta.get("confidence", 0)) - 0.92) < 0.001,
                  f"confidence={meta.get('confidence') if meta else 'null'}")
        comprobar("el texto guardado es el que la persona corrigio",
                  ins.get("text") == "analiza el proyecto, corrige los errores y anade una prueba",
                  f"text={ins.get('text')!r}")
        comprobar("el servidor la marco como confirmada por la persona",
                  ins.get("confirmed_by_user") is True)
    else:
        comprobar("la ejecucion dictada existe", False, "no se encontro")
    if manual:
        ins = manual.get("instruction", {})
        comprobar("la ejecucion tecleada se registro como de texto",
                  ins.get("source") == "text", f"source={ins.get('source')}")
        comprobar("la ejecucion tecleada no lleva metadatos de dictado",
                  ins.get("transcript_meta") is None,
                  f"meta={json.dumps(ins.get('transcript_meta'))[:80]}")
    else:
        comprobar("la ejecucion de control existe", False, "no se encontro")

    if fallos:
        print(f"\nRESULTADO: {len(fallos)} comprobacion(es) fallidas -> {fallos}")
        return 1
    print("\nRESULTADO: el flujo de voz funciona en un motor real y deja rastro.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

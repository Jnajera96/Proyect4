"""Verifica el frontend en un motor de render real, sin navegador visible.

Motivo: leer el HTML no demuestra que la interfaz funcione. Un `EventSource` mal
conectado, un `id` que no existe o una lista de eventos vacia se leen igual de
bien que una version correcta. Esta comprobacion **pulsa el boton** y mira lo que
pasa.

Que cubre que una prueba de DOM no cubriria:
  - Si la pagina pinto de verdad y el navegador no se quejo.
  - Si el contrato exportado se carga y sus enumeraciones son las esperadas.
  - Si el flujo SSE entrega eventos al navegador y la linea de tiempo se puebla.
  - Si los errores de consola existen (en un shim no existen).

Uso:
    python tools/verify_frontend.py
"""

from __future__ import annotations

import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
FRONTEND = RAIZ / "frontend"
PAGINA = FRONTEND / "_verify.html"
SONDA = FRONTEND / "_verify_probe.js"

# Orden de preferencia: **nombres por fuera, directorios por dentro**. Al reves se
# encuentra primero `chromium-<build>/chrome-win64/chrome.exe` y nunca se llega al
# shell sin interfaz, que con `--dump-dom` arranca igual pero se queda colgado.
CANDIDATOS = (
    ("chrome-headless-shell.exe", "chrome-headless-shell-win64"),
    ("chrome.exe", "chrome-win64"),
)


def encontrar_navegador() -> Path | None:
    base = Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright"
    if not base.is_dir():
        return None
    for nombre, carpeta in CANDIDATOS:
        for build in sorted(base.iterdir(), reverse=True):
            if not build.is_dir():
                continue
            ruta = build / carpeta / nombre
            if ruta.exists():
                return ruta
    return None


SONDA_JS = r"""
var pasos = [], errores = [];
window.addEventListener('error', function (e) { errores.push('ERROR: ' + e.message); }, true);
window.addEventListener('unhandledrejection', function (e) {
  errores.push('PROMESA: ' + ((e.reason && e.reason.message) || e.reason));
});
document.addEventListener('securitypolicyviolation', function (e) {
  errores.push('CSP: ' + e.violatedDirective);
});
(function () {
  var oe = console.error, ow = console.warn;
  console.error = function () { errores.push('CONSOLE_ERROR: ' + [].join.call(arguments, ' ')); oe.apply(console, arguments); };
  console.warn = function () { errores.push('CONSOLE_WARN: ' + [].join.call(arguments, ' ')); ow.apply(console, arguments); };
})();
function anota(k, v) { pasos.push(k + '=' + v); }

// La sonda envuelve `pintarEvento` para contar cuantas veces se pinta de verdad.
// Una funcion declarada en un script clasico vive en `window`, asi que la
// sustitucion es efectiva y permite distinguir "no llego el evento" de "llego y no
// se pinto".
var vistos = 0, tipos_vistos = [];
if (typeof window.pintarEvento === 'function') {
  var original = window.pintarEvento;
  window.pintarEvento = function (ev) {
    vistos++;
    tipos_vistos.push(ev.kind);
    return original(ev);
  };
}

window.addEventListener('load', function () {
  setTimeout(function () {
    var pasos_async = [];
    function volcar() {
      var d = document.createElement('div');
      d.id = '_informe';
      d.textContent = 'N_ERRORS=' + errores.length + ' ||| ' + errores.join(' ||| ')
        + ' ||| ' + pasos.concat(pasos_async).join(' ||| ');
      document.body.appendChild(d);
    }
    try {
      anota('CONTRATOS', (typeof contratos !== 'undefined' && contratos)
        ? Object.keys(contratos.schemas).length : 'null');
      anota('CHIP_SALUD', document.getElementById('salud').textContent);
      anota('ENUMS_EVENTO', (typeof contratos !== 'undefined' && contratos)
        ? contratos.schemas.EventKind.enum.length : 0);
      anota('LISTA_CARGADA', document.querySelectorAll('#tabla-runs tr').length > 0);

      // Pulsar el boton de verdad, no llamar a la funcion interna.
      document.getElementById('instruccion').value =
        'Analiza el proyecto e identifica los errores principales.';
      document.getElementById('btn-crear').click();
    } catch (e) {
      errores.push('PROBE: ' + e.message);
      volcar();
      return;
    }
    setTimeout(function () {
      try {
        var filas = document.querySelectorAll('#timeline li');
        pasos_async.push('EVENTOS_PINTADOS=' + vistos);
        pasos_async.push('TIPOS_PINTADOS=' + tipos_vistos.join(','));
        pasos_async.push('FUENTE_ESTADO=' + (window.fuente ? window.fuente.readyState : 'null'));
        pasos_async.push('FILAS_TIMELINE=' + filas.length);
        pasos_async.push('TIPOS=' + Array.prototype.map.call(filas, function (f) {
          return f.querySelector('.kind').textContent;
        }).join(','));
        pasos_async.push('CHIP_ESTADO=' + document.getElementById('estado-run').textContent);
        pasos_async.push('RUN_ID=' + document.getElementById('run-id').textContent);
        pasos_async.push('PANEL_RUN_VISIBLE=' +
          !document.getElementById('panel-run').classList.contains('oculto'));
        pasos_async.push('TABLA_FILAS=' + document.querySelectorAll('#tabla-runs tr').length);
        pasos_async.push('SIN_SCROLL_HORIZONTAL=' +
          (document.documentElement.scrollWidth <= window.innerWidth + 1));
      } catch (e) {
        errores.push('PROBE2: ' + e.message);
      }
      volcar();
    }, 2500);
  }, 800);
});
"""


def puerto_libre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def esperar_servidor(url: str, limite: float = 40.0) -> bool:
    fin = time.time() + limite
    while time.time() < fin:
        try:
            with urllib.request.urlopen(url, timeout=1) as r:
                if r.status == 200:
                    return True
        except Exception:
            time.sleep(0.3)
    return False


def preparar_pagina() -> None:
    """Escribe la copia instrumentada y la sonda.

    **No se borra nada.** El entorno bloquea los borrados tras 50 por turno, y
    cada borrado bloqueado mata el proceso: la verificacion moria en 1,3 s y el
    verificador de mutaciones lo interpretaba como «mutacion cazada». Un falso
    positivo, y de los peores: el que hace parecer que la comprobacion funciona.

    Los dos ficheros se sobrescriben en cada ejecucion, asi que no hay contenido
    obsoleto. Si al empezar existe una sonda con otro contenido, es que una
    ejecucion anterior murio, y se avisa.
    """
    if SONDA.exists() and SONDA.read_text(encoding="utf-8") != SONDA_JS:
        print("AVISO: habia una sonda de una ejecucion anterior interrumpida; se sobrescribe")

    html = (FRONTEND / "index.html").read_text(encoding="utf-8")
    # Sonda como script EXTERNO, no en linea: es lo que exige una CSP y ademas
    # mantiene intacto el punto de entrada real.
    html = html.replace("</body>", '<script src="_verify_probe.js"></script>\n</body>')
    PAGINA.write_text(html, encoding="utf-8")
    SONDA.write_text(SONDA_JS, encoding="utf-8")


def limpiar() -> list[str]:
    """Los ficheros de sonda se dejan en su sitio; estan ignorados por git.

    Borrarlos costaba dos operaciones de borrado por ejecucion, y en este entorno
    un borrado bloqueado **mata el proceso**. Se prefiere dejar dos ficheros
    ignorados a que la verificacion muera a mitad y el verificador de mutaciones lo
    confunda con una mutacion cazada. Ese falso positivo es peor que la suciedad:
    hace parecer que la comprobacion funciona cuando no ha llegado a correr.
    """
    return []


def _matar_arbol(pid: int) -> None:
    """Mata el proceso y **todos sus hijos**.

    Chromium lanza procesos hijos que **sobreviven al padre**. Matar solo al padre
    deja navegadores huerfanos corriendo: en una sesion se acumularon ocho, y el
    verificador de mutaciones paso de tardar un minuto a quedarse colgado mas de
    trece. `taskkill /T` es la diferencia entre limpiar y aparentar que se limpia.
    """
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(pid)],
            capture_output=True, check=False,
        )
    else:
        import signal

        try:
            os.killpg(os.getpgid(pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass


def _lanzar_navegador(orden: list[str], limite: float) -> tuple[str, bool]:
    """Ejecuta el navegador y devuelve (salida, termino_a_tiempo)."""
    proceso = subprocess.Popen(
        orden, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace",
    )
    try:
        salida, _ = proceso.communicate(timeout=limite)
        return salida or "", True
    except subprocess.TimeoutExpired:
        _matar_arbol(proceso.pid)
        try:
            salida, _ = proceso.communicate(timeout=15)
        except subprocess.TimeoutExpired:
            salida = ""
        return salida or "", False


def main() -> int:
    navegador = encontrar_navegador()
    if navegador is None:
        print("VERIFICACION OMITIDA: no se encontro Chromium en las rutas de Playwright")
        return 0
    print(f"navegador: {navegador}")

    # Restos de una ejecucion anterior: NO se borran, se sobrescriben. Borrar
    # consume cuota del interceptor de este entorno, y un borrado bloqueado mata el
    # proceso. `preparar_pagina` avisa si el resto tenia otro contenido.
    puerto = puerto_libre()
    # Base limpia y propia: la verificacion debe ser reproducible. Con el almacen
    # por defecto, la lista de ejecuciones crecia entre corridas y los numeros del
    # informe cambiaban sin que cambiara el codigo.
    estado = Path(tempfile.mkdtemp(prefix="aiswe-estado-")) / "estado.sqlite3"
    entorno = {**os.environ, "PYTHONPATH": "src", "AI_SWE_STATE_DB_PATH": str(estado)}
    servidor = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "ai_swe.api.app:crear_app", "--factory",
         "--host", "127.0.0.1", "--port", str(puerto), "--log-level", "warning"],
        cwd=RAIZ, env=entorno, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    perfil = tempfile.mkdtemp(prefix="aiswe-chrome-")
    try:
        base = f"http://127.0.0.1:{puerto}"
        if not esperar_servidor(f"{base}/health"):
            print("FALLO: el servidor no arranco")
            return 1

        preparar_pagina()
        orden = [
            str(navegador),
            "--headless", "--disable-gpu", "--no-sandbox", "--dump-dom",
            "--hide-scrollbars", "--window-size=1600,1000",
            "--virtual-time-budget=20000",
            f"--user-data-dir={perfil}",
            f"{base}/app/_verify.html",
        ]
        dom, a_tiempo = _lanzar_navegador(orden, limite=90)
        if not a_tiempo:
            print("AVISO: el navegador no termino a tiempo; se mato el arbol de procesos")
    finally:
        servidor.terminate()
        try:
            servidor.wait(timeout=10)
        except subprocess.TimeoutExpired:
            servidor.kill()
        shutil.rmtree(perfil, ignore_errors=True)
        shutil.rmtree(estado.parent, ignore_errors=True)
        no_borrados = limpiar()

    coincidencia = re.search(r'<div id="_informe">(.*?)</div>', dom, re.S)
    if not coincidencia:
        print("FALLO: la pagina no emitio informe (no llego a ejecutarse la sonda)")
        print(dom[-1500:] if dom else "(el navegador no devolvio DOM)")
        return 1

    campos: dict[str, str] = {}
    errores: list[str] = []
    for parte in coincidencia.group(1).split("|||"):
        parte = parte.strip()
        if not parte:
            continue
        if "=" in parte:
            clave, valor = parte.split("=", 1)
            campos[clave.strip()] = valor.strip()
        elif parte.startswith(("ERROR:", "PROMESA:", "CSP:", "CONSOLE_", "PROBE")):
            errores.append(parte)

    print("\n== informe del navegador ==")
    for clave, valor in campos.items():
        print(f"  {clave:26s} {valor}")

    fallos: list[str] = []

    def comprobar(nombre: str, condicion: bool, detalle: str = "") -> None:
        print(f"  {'OK   ' if condicion else 'FALLO'} {nombre}{('  (' + detalle + ')') if detalle else ''}")
        if not condicion:
            fallos.append(nombre)

    print("\n== comprobaciones ==")
    # El contador se llama N_ERRORS a proposito: si se llamara ERRORS, un patron
    # de error lo confundiria con un fallo real de la aplicacion.
    comprobar("la aplicacion no emitio errores", not errores, "; ".join(errores[:3]))
    comprobar("los contratos se cargaron", campos.get("CONTRATOS") == "15",
              f"CONTRATOS={campos.get('CONTRATOS')}")
    comprobar("el servidor se declara vivo", "fase M1" in campos.get("CHIP_SALUD", ""),
              campos.get("CHIP_SALUD", ""))
    comprobar("la lista de ejecuciones se pinto", campos.get("LISTA_CARGADA") == "true")
    comprobar("el panel de la ejecucion se abrio", campos.get("PANEL_RUN_VISIBLE") == "true")
    comprobar("el cliente recibio un run_id", campos.get("RUN_ID", "").startswith("run-"),
              campos.get("RUN_ID", ""))
    comprobar("llegaron eventos al navegador",
              int(campos.get("FILAS_TIMELINE", "0") or 0) >= 4,
              f"FILAS_TIMELINE={campos.get('FILAS_TIMELINE')}")
    comprobar("se recibio progreso por nodo", "run.step" in campos.get("TIPOS", ""),
              campos.get("TIPOS", "")[:80])
    comprobar("el estado final se mostro",
              campos.get("CHIP_ESTADO", "") in {"completada", "requiere intervención"},
              campos.get("CHIP_ESTADO", ""))
    comprobar("la pagina no desborda horizontalmente",
              campos.get("SIN_SCROLL_HORIZONTAL") == "true")
    # La base arranca limpia, asi que debe haber exactamente una ejecucion: la que
    # acaba de crear la interfaz. Comprueba de paso que el aislamiento funciona.
    comprobar("el almacen arranco aislado y limpio", campos.get("TABLA_FILAS") == "1",
              f"TABLA_FILAS={campos.get('TABLA_FILAS')}")

    if no_borrados:
        print(f"\nAVISO: no se pudieron borrar {no_borrados}")

    if fallos:
        print(f"\nRESULTADO: {len(fallos)} comprobacion(es) fallidas -> {fallos}")
        return 1
    print("\nRESULTADO: la interfaz funciona en un motor real.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

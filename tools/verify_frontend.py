"""Verifica el frontend React en un motor de render real, sin navegador visible.

Motivo: leer el HTML no demuestra que la interfaz funcione. Un `EventSource` mal
conectado, una etiqueta que no existe o una lista de eventos vacia se leen igual de
bien que una version correcta. Esta comprobacion **pulsa los botones** y mira lo
que pasa.

**Desde F11 se verifica la aplicacion construida, no el fuente.** La interfaz es
React y se compila con Vite; lo que se sirve es `frontend/dist`. La verificacion
inyecta una sonda en ese `index.html` construido, arranca el backend real y abre la
pagina. La sonda pulsa "Ejecutar", espera a que lleguen los eventos y lee el estado
**real** que la aplicacion expone en `window.__AISWE__`, en lugar de reimplementar
la logica del cliente y comprobarse a si misma.

Que cubre que una prueba de DOM no cubriria:
  - Si la aplicacion **monto** de verdad (React sin errores de consola).
  - Si el flujo SSE entrega eventos al navegador y la linea de tiempo se puebla.
  - Si los eventos que llegan son los **canonicos de F10** y no los heredados
    (AUD-11): la lista de tipos recibidos se compara con la esperada.
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
DIST = FRONTEND / "dist"
PAGINA = DIST / "_verify.html"
SONDA = DIST / "_verify_probe.js"

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


# La sonda se ejecuta en la pagina construida. Espera a que React monte el boton
# "Ejecutar" (`#btn-crear`), lo pulsa, y despues de unos segundos lee el estado real
# de la aplicacion desde `window.__AISWE__` y del DOM.
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
function texto(id) { var e = document.getElementById(id); return e ? e.textContent : '(no existe)'; }

// La sonda se instala cuando React ya ha montado: espera a que `#btn-crear`
// aparezca. Un `setInterval` acotado evita colgarse si el montaje falla.
var intentos = 0;
var esperar = setInterval(function () {
  intentos++;
  var boton = document.querySelector('#btn-crear');
  if (!boton) {
    if (intentos > 100) {   // 10 s
      clearInterval(esperar);
      errores.push('PROBE: la aplicacion no monto (#btn-crear no aparecio)');
      volcar();
    }
    return;
  }
  clearInterval(esperar);
  arrancar(boton);
}, 100);

var pasos_async = [];
function volcar() {
  var d = document.createElement('div');
  d.id = '_informe';
  d.textContent = 'N_ERRORS=' + errores.length + ' ||| ' + errores.join(' ||| ')
    + ' ||| ' + pasos.concat(pasos_async).join(' ||| ');
  document.body.appendChild(d);
}

function arrancar(boton) {
  try {
    anota('MONTO', 'true');
    anota('CHIP_SALUD', document.querySelector('header .chip') ? document.querySelector('header .chip').textContent : '(sin chip)');
    anota('TABLA_INICIAL', document.querySelectorAll('tbody tr').length);

    // Pulsar el boton de verdad, no llamar a una funcion interna.
    boton.click();
  } catch (e) {
    errores.push('PROBE: ' + e.message);
    volcar();
    return;
  }

  recorrer(0);
}

// Recorre el ciclo **pulsando los botones de verdad**: responde a la puerta de
// requisitos cuando aparece, y despues a la de aprobacion, hasta que la ejecucion
// llega a un terminal (o se agota el margen). La sonda no simula el flujo: lo
// conduce, y anota en que estados paso para que el verificador lo compruebe.
var estadosVistos = [];
var puertasVistas = [];
var pulsadoConfirmar = false;
var pulsadoAprobar = false;
var salioDeRequisitos = false;
function anotarEstado(s) {
  if (s && estadosVistos.indexOf(s) < 0) estadosVistos.push(s);
}
function recorrer(vueltas) {
  var st = window.__AISWE__ || {};
  var status = st.status;
  anotarEstado(status);

  if (status === 'awaiting_human_requirements_confirmation') {
    if (puertasVistas.indexOf('requisitos') < 0) puertasVistas.push('requisitos');
    if (!pulsadoConfirmar) {
      var b = document.querySelector('#btn-confirmar-requisitos');
      if (b && !b.disabled) { b.click(); pulsadoConfirmar = true; }
    }
  } else if (status === 'awaiting_approval') {
    // Haber llegado aqui significa que la confirmacion de requisitos funcionó.
    salioDeRequisitos = true;
    if (puertasVistas.indexOf('aprobacion') < 0) puertasVistas.push('aprobacion');
    if (!pulsadoAprobar) {
      var a = document.querySelector('#btn-aprobar');
      if (a && !a.disabled) { a.click(); pulsadoAprobar = true; }
    }
  } else if (pulsadoConfirmar && status && status !== 'awaiting_human_requirements_confirmation') {
    // Dejo atras la puerta de requisitos hacia cualquier otro estado (running,
    // needs_human, completed…). Eso es lo que se queria observar.
    salioDeRequisitos = true;
  }

  var terminal = status === 'completed' || status === 'failed' ||
                 status === 'needs_human' || status === 'cancelled';
  // Se para cuando la ejecucion es terminal **y** ya se observo que salio de la
  // puerta de requisitos, o cuando se agota un margen generoso. El margen tiene en
  // cuenta que la reanudacion vuelve del trabajador y que el estado se relee.
  if ((terminal && salioDeRequisitos) || vueltas > 120) { setTimeout(medir, 1200); return; }
  setTimeout(function () { recorrer(vueltas + 1); }, 250);
}

function medir() {
  try {
    var st = window.__AISWE__ || {};
    pasos_async.push('RUN_ID=' + (st.runId || '(ninguno)'));
    pasos_async.push('ESTADO_APP=' + (st.status || '(ninguno)'));
    pasos_async.push('CONEXION=' + (st.conexion || '(ninguno)'));
    pasos_async.push('EVENTOS=' + (st.eventos || 0));
    pasos_async.push('TIPOS=' + ((st.tipos || []).join(',')));
    pasos_async.push('HITOS=' + ((st.hitos || []).join(',')));
    pasos_async.push('ESTADOS_VISTOS=' + estadosVistos.join('>'));
    pasos_async.push('PUERTAS_VISTAS=' + puertasVistas.join(','));
    pasos_async.push('PULSO_CONFIRMAR=' + (pulsadoConfirmar ? 'true' : 'false'));
    pasos_async.push('PULSO_APROBAR=' + (pulsadoAprobar ? 'true' : 'false'));
    pasos_async.push('SALIO_DE_REQUISITOS=' + (salioDeRequisitos ? 'true' : 'false'));
    pasos_async.push('FILAS_TIMELINE=' + document.querySelectorAll('.timeline li').length);
    pasos_async.push('FILAS_TABLA=' + document.querySelectorAll('tbody tr').length);
    var chip = document.querySelector('header .chip');
    pasos_async.push('CHIP_SALUD=' + (chip ? chip.textContent : '(sin chip)'));
    pasos_async.push('SIN_SCROLL_HORIZONTAL=' +
      (document.documentElement.scrollWidth <= window.innerWidth + 1));
    // La etiqueta de fase debe venir de /health, no de un literal (AUD-13).
    var cuerpo = document.body.textContent || '';
    pasos_async.push('MENCIONA_M1=' + (cuerpo.indexOf('fase M1') >= 0));
  } catch (e) {
    errores.push('PROBE2: ' + e.message);
  }
  volcar();
}
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
    """Escribe la copia instrumentada de la pagina construida y la sonda.

    **No se borra nada.** El entorno bloquea los borrados tras 50 por turno, y
    cada borrado bloqueado mata el proceso: la verificacion moria en 1,3 s y el
    verificador de mutaciones lo interpretaba como «mutacion cazada». Un falso
    positivo, y de los peores: el que hace parecer que la comprobacion funciona.

    Los dos ficheros se sobrescriben en cada ejecucion, asi que no hay contenido
    obsoleto. Se escriben en `dist/`, que esta ignorado por git.
    """
    if not DIST.is_dir():
        raise SystemExit(
            "FALLO: no existe la construccion del frontend en frontend/dist.\n"
            "       Ejecuta:  cd frontend && npm install && npm run build"
        )
    if SONDA.exists() and SONDA.read_text(encoding="utf-8") != SONDA_JS:
        print("AVISO: habia una sonda de una ejecucion anterior interrumpida; se sobrescribe")

    html = (DIST / "index.html").read_text(encoding="utf-8")
    # La sonda va como script EXTERNO y **antes** del modulo de la aplicacion, para
    # que sus manejadores de error esten instalados cuando React monte. Aun asi,
    # espera a que el boton exista antes de tocar nada.
    html = html.replace(
        '<script type="module"',
        '<script src="_verify_probe.js"></script>\n    <script type="module"',
        1,
    )
    PAGINA.write_text(html, encoding="utf-8")
    SONDA.write_text(SONDA_JS, encoding="utf-8")


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

    if not DIST.is_dir():
        print(
            "FALLO: no existe frontend/dist. Ejecuta: cd frontend && npm install && npm run build"
        )
        return 1

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
            "--virtual-time-budget=40000",
            f"--user-data-dir={perfil}",
            f"{base}/app/_verify.html",
        ]
        dom, a_tiempo = _lanzar_navegador(orden, limite=120)
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

    coincidencia = re.search(r'<div id="_informe">(.*?)</div>', dom, re.S)
    if not coincidencia:
        print("FALLO: la pagina no emitio informe (no llego a ejecutarse la sonda)")
        print(dom[-2000:] if dom else "(el navegador no devolvio DOM)")
        return 1

    campos: dict[str, str] = {}
    errores: list[str] = []
    for parte in coincidencia.group(1).split("|||"):
        parte = parte.strip()
        if not parte:
            continue
        if "=" in parte:
            clave, valor = parte.split("=", 1)
            # El informe viaja dentro del DOM volcado con `--dump-dom`, asi que un
            # `>` del propio valor (`a>b`) vuelve escapado como `&gt;`. Se
            # desescapa antes de comparar: sin esto, una comparacion contra el
            # valor real fallaba por un detalle de serializacion, no por la
            # aplicacion.
            valor = (
                valor.strip()
                .replace("&gt;", ">")
                .replace("&lt;", "<")
                .replace("&amp;", "&")
            )
            campos[clave.strip()] = valor
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
    comprobar("la aplicacion monto sin errores", not errores, "; ".join(errores[:3]))
    comprobar("React monto el punto de entrada", campos.get("MONTO") == "true")
    chip_salud = campos.get("CHIP_SALUD", "")
    comprobar(
        "el servidor se declara vivo y la fase sale de /health",
        "servidor ok" in chip_salud and "fase " in chip_salud,
        chip_salud,
    )
    # AUD-13: la etiqueta de fase no debe estar escrita a mano. Si hay un literal
    # "fase M1" en el cuerpo, el defecto ha vuelto.
    comprobar(
        "no queda ninguna etiqueta de fase obsoleta (AUD-13)",
        campos.get("MENCIONA_M1") == "false",
        f"MENCIONA_M1={campos.get('MENCIONA_M1')}",
    )
    comprobar("el cliente recibio un run_id", (campos.get("RUN_ID") or "").startswith("run-"),
              campos.get("RUN_ID", ""))
    comprobar("los eventos llegaron por SSE",
              int(campos.get("EVENTOS", "0") or 0) >= 2,
              f"EVENTOS={campos.get('EVENTOS')}")
    # El nucleo de F11: se consumen los hitos canonicos de F10, no los heredados.
    tipos = campos.get("TIPOS", "")
    comprobar(
        "llego el hito canonico de requisitos (F10)",
        "requirements.completed" in tipos,
        tipos[:140],
    )
    comprobar(
        "llego la senal de puerta humana",
        "run.awaiting_human" in tipos,
        tipos[:140],
    )
    comprobar(
        "NO se consumen los eventos heredados (AUD-11)",
        not any(v in tipos for v in ("run.step", "run.status", "run.awaiting_approval", "run.report")),
        tipos[:140],
    )
    # La puerta de requisitos se alcanza **y se responde** desde la interfaz: es la
    # parte central de F11 (el HITL) y prueba que el boton esta cableado de verdad.
    comprobar(
        "la puerta de requisitos aparecio en la interfaz",
        "requisitos" in campos.get("PUERTAS_VISTAS", ""),
        f"PUERTAS_VISTAS={campos.get('PUERTAS_VISTAS')}",
    )
    comprobar(
        "la interfaz respondio a la puerta de requisitos",
        campos.get("PULSO_CONFIRMAR") == "true",
        f"PULSO_CONFIRMAR={campos.get('PULSO_CONFIRMAR')}",
    )
    # Y la ejecucion **avanzo**: dejo atras la puerta de requisitos y llego a otro
    # estado. Eso demuestra que la respuesta de la interfaz llego al servidor y lo
    # reanudo. Sin modelo ni repositorio reales, el grafo termina de forma
    # determinista en `needs_human` con `CODER_PRODUCED_NO_CHANGES`: es una
    # transicion real y observable, no un fallo de la interfaz, y por eso lo que se
    # comprueba es que **salio de la puerta**, no a que estado llego.
    estados = [e for e in campos.get("ESTADOS_VISTOS", "").split(">") if e]
    comprobar(
        "la ejecucion avanzo tras confirmar los requisitos",
        campos.get("SALIO_DE_REQUISITOS") == "true" and len(estados) >= 2,
        f"SALIO_DE_REQUISITOS={campos.get('SALIO_DE_REQUISITOS')} ESTADOS_VISTOS={campos.get('ESTADOS_VISTOS')}",
    )
    comprobar("la linea de tiempo se pinto",
              int(campos.get("FILAS_TIMELINE", "0") or 0) >= 1,
              f"FILAS_TIMELINE={campos.get('FILAS_TIMELINE')}")
    comprobar("la pagina no desborda horizontalmente",
              campos.get("SIN_SCROLL_HORIZONTAL") == "true")
    # La base arranca limpia, asi que debe haber exactamente una ejecucion: la que
    # acaba de crear la interfaz. Comprueba de paso que el aislamiento funciona.
    comprobar("el almacen arranco aislado y limpio", campos.get("FILAS_TABLA") == "1",
              f"FILAS_TABLA={campos.get('FILAS_TABLA')}")

    if fallos:
        print(f"\nRESULTADO: {len(fallos)} comprobacion(es) fallidas -> {fallos}")
        return 1
    print("\nRESULTADO: la interfaz funciona en un motor real.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

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

**Y desde Fase 4, `dist` se reconstruye antes de servir.** servia `dist` tal como
estuviera en el disco, asi que verificaba lo ultimo que alguien compilo: un cambio
en `src/` sin compilar pasaba desapercibido y la herramienta daba verde sobre un
arbol que ya no era el que se sirve -medir con la construccion anterior al cambio-.
Lo hace ademas indispensable el verificador de mutaciones: sus mutaciones del
frontend atacan `src/`, y sin reconstruccion el navegador seguiria viendo el bundle
viejo, asi que todas saldrian "NO CAZADA" sin que nada hubiera fallado. Un punto
ciego fabricado por el instrumento, no por el codigo.

Que cubre que una prueba de DOM no cubriria:
  - Si la aplicacion **monto** de verdad (React sin errores de consola).
  - Si el flujo SSE entrega eventos al navegador y la linea de tiempo se puebla.
  - Si los eventos que llegan son los **canonicos de F10** y no los heredados
    (AUD-11): la lista de tipos recibidos se compara con la esperada.
  - Si los errores de consola existen (en un shim no existen).

Uso:
    python tools/verify_frontend.py            # servidor sin autenticacion
    python tools/verify_frontend.py --auth     # servidor con AI_SWE_API_KEYS

El modo `--auth` arranca el backend **con** claves declaradas y deja que la sonda
recorra el flujo completo autenticado. La credencial **no se inyecta en ningun
almacen del navegador**: la sonda rellena la pantalla de acceso de la aplicacion
-la teclea y pulsa Continuar, como lo haria una persona- porque la credencial vive
en memoria y comprobar que no se persiste es parte de lo que hay que verificar.
Ahi se comprueba ademas que el servidor exige la credencial de verdad -una peticion
sin ella es 401 y con ella 200-, que la credencial no acaba ni en el almacen del
navegador ni en el DOM ni en la consola, y que el flujo SSE viaja autenticado. Es
la unica forma de probar la ruta del `?api_key=` del flujo SSE, que ningun `fetch`
del cliente puede ejercitar.
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
var pasos = [], errores = [], consola = [];

// Modo de la verificacion. El modo `--auth` inyecta un preambulo que pone estos
// dos valores antes de que arranque el sondeo; sin el, el servidor no exige
// credencial y no hay nada que teclear.
var MODO_AUTH = false;
var CLAVE_PRUEBA = '';

// Nada de lo que la sonda escriba en su informe puede contener la credencial. Se
// redacta al vuelo: si la aplicacion la imprimiera en la consola -que es uno de
// los fallos que se vigilan-, el informe no la repetiria.
function redactar(t) {
  var texto = String(t);
  return CLAVE_PRUEBA ? texto.split(CLAVE_PRUEBA).join('[REDACTED]') : texto;
}
function contieneClave(t) {
  return CLAVE_PRUEBA ? String(t).indexOf(CLAVE_PRUEBA) >= 0 : false;
}

window.addEventListener('error', function (e) { errores.push(redactar('ERROR: ' + e.message)); }, true);
window.addEventListener('unhandledrejection', function (e) {
  errores.push(redactar('PROMESA: ' + ((e.reason && e.reason.message) || e.reason)));
});
document.addEventListener('securitypolicyviolation', function (e) {
  errores.push(redactar('CSP: ' + e.violatedDirective));
});
(function () {
  var oe = console.error, ow = console.warn, ol = console.log;
  console.error = function () { var t = [].join.call(arguments, ' '); consola.push(t); errores.push('CONSOLE_ERROR: ' + redactar(t)); oe.apply(console, arguments); };
  console.warn = function () { var t = [].join.call(arguments, ' '); consola.push(t); errores.push('CONSOLE_WARN: ' + redactar(t)); ow.apply(console, arguments); };
  console.log = function () { consola.push([].join.call(arguments, ' ')); ol.apply(console, arguments); };
})();
function anota(k, v) { pasos.push(k + '=' + v); }
function texto(id) { var e = document.getElementById(id); return e ? e.textContent : '(no existe)'; }

// ------------------------------------------- pantalla de acceso (modo --auth)
// La credencial llega al frontend **por la pantalla de acceso**: se teclea y se
// envia como lo haria una persona. No se inyecta en ningun almacen del navegador
// -la credencial vive en memoria-, que es justo lo que hay que verificar.
var pantallaAccesoVista = false;
var claveEscrita = false;
var claveEnviada = false;

function escribirCredencial(campo) {
  // Un campo controlado por React no cambia con `campo.value = x`: hay que usar
  // el setter nativo y disparar `input`, que es lo que React escucha. Teclear de
  // verdad, en una palabra.
  var setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
  setter.call(campo, CLAVE_PRUEBA);
  campo.dispatchEvent(new Event('input', { bubbles: true }));
}

function autenticarse() {
  var campo = document.querySelector('#api-key');
  if (campo) pantallaAccesoVista = true;
  if (!MODO_AUTH || !campo || claveEnviada) return;
  if (!claveEscrita) {
    // Se escribe en un tic y se envia en el siguiente: el boton se habilita al
    // repintar React, y pulsarlo antes seria pulsar un boton deshabilitado.
    escribirCredencial(campo);
    claveEscrita = true;
    return;
  }
  var boton = document.querySelector('#btn-continuar');
  if (boton && !boton.disabled) {
    boton.click();
    claveEnviada = true;
  }
}

function hayCredencialEnAlmacen() {
  try {
    // El nombre concreto que usaba la version anterior: si vuelve a aparecer, la
    // credencial se esta persistiendo otra vez.
    if (window.localStorage.getItem('ai_swe.api_key') !== null) return true;
    if (window.sessionStorage.getItem('ai_swe.api_key') !== null) return true;
    var almacenes = [window.localStorage, window.sessionStorage];
    for (var i = 0; i < almacenes.length; i++) {
      var a = almacenes[i];
      for (var j = 0; j < a.length; j++) {
        if (contieneClave(a.getItem(a.key(j)))) return true;
      }
    }
  } catch (e) {
    return false;
  }
  return false;
}

// La sonda se instala cuando React ya ha montado: espera a que `#btn-crear`
// aparezca. Un `setInterval` acotado evita colgarse si el montaje falla.
var intentos = 0;
var esperar = setInterval(function () {
  intentos++;
  var boton = document.querySelector('#btn-crear');
  if (boton) {
    clearInterval(esperar);
    arrancar(boton);
    return;
  }
  // Sin credencial no hay aplicacion que pulsar: primero la pantalla de acceso.
  autenticarse();
  if (intentos > 150) {   // 15 s: el viaje de ida y vuelta de la credencial suma
    clearInterval(esperar);
    errores.push('PROBE: la aplicacion no monto (#btn-crear no aparecio)');
    volcar();
  }
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
    // Estado de acceso. `AUTH_PANTALLA` dice si la aplicacion pidio credencial
    // -tiene que pedirla con el servidor autenticado y no pedirla sin el- y las
    // tres siguientes son las que vigilan que la credencial no se persista, no se
    // pinte y no se registre.
    pasos_async.push('SESION=' + (st.sesion || '(ninguno)'));
    pasos_async.push('AUTH_PANTALLA=' + (pantallaAccesoVista ? 'true' : 'false'));
    pasos_async.push('CLAVE_ENVIADA=' + (claveEnviada ? 'true' : 'false'));
    pasos_async.push('ALMACEN_CLAVE=' + (hayCredencialEnAlmacen() ? 'true' : 'false'));
    pasos_async.push('CLAVE_EN_DOM=' +
      (contieneClave(document.documentElement.outerHTML) ? 'true' : 'false'));
    pasos_async.push('CLAVE_EN_CONSOLA=' + (contieneClave(consola.join(' ')) ? 'true' : 'false'));
    pasos_async.push('ESTADOS_VISTOS=' + estadosVistos.join('>'));
    pasos_async.push('PUERTAS_VISTAS=' + puertasVistas.join(','));
    pasos_async.push('PULSO_CONFIRMAR=' + (pulsadoConfirmar ? 'true' : 'false'));
    pasos_async.push('PULSO_APROBAR=' + (pulsadoAprobar ? 'true' : 'false'));
    pasos_async.push('SALIO_DE_REQUISITOS=' + (salioDeRequisitos ? 'true' : 'false'));
    pasos_async.push('FILAS_TIMELINE=' + document.querySelectorAll('.timeline li').length);
    // Las filas pendientes se pintan **siempre** (la linea de tiempo muestra los
    // cuatro hitos canonicos, alcanzados o no), asi que contar filas no prueba
    // nada del progreso. Lo que prueba que los eventos llegaron y se pintaron
    // es contar los hitos **alcanzados**: los alcanzados llevan la marca
    // `#{seq} - hora`, los pendientes llevan la clase `tenue`. Contar solo
    // `<li>` habria dado verde con la linea de tiempo inventada.
    pasos_async.push('HITOS_ALCANZADOS=' +
      document.querySelectorAll('.timeline li .cuando:not(.tenue)').length);
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


# Preambulo del modo `--auth`. Se inyecta en la sonda justo despues del helper
# `anota` (para poder usarlo) y antes de que el modulo de la aplicacion se
# ejecute.
#
# **No inyecta la credencial en ningun sitio.** Pone la sonda en modo autenticado
# y le da la clave de fantasia; la credencial llega a la aplicacion porque la
# sonda rellena su pantalla de acceso y pulsa Continuar. Con la credencial en
# memoria -que es como funciona-, inyectarla en un almacen no probaria el camino
# real y ademas taparia el fallo que hay que vigilar: que alguien la persista.
#
# Las dos peticiones propias de la sonda son la prueba de que el servidor la
# exige: sin cabecera 401, con la cabecera 200.
PREAMBULO_AUTH = r"""
MODO_AUTH = true;
CLAVE_PRUEBA = '__CLAVE__';
fetch('/runs')
  .then(function (r) { anota('SIN_CLAVE', r.status); })
  .catch(function (e) { errores.push(redactar('AUTH_PROBE: ' + e.message)); });
fetch('/runs', { headers: { 'X-API-Key': '__CLAVE__' } })
  .then(function (r) { anota('CON_CLAVE', r.status); })
  .catch(function (e) { errores.push(redactar('AUTH_PROBE: ' + e.message)); });
"""

#: Marca de insercion del preambulo: el final del helper `anota`/`texto`.
_MARCA_PREAMBULO = "function texto(id) { var e = document.getElementById(id); return e ? e.textContent : '(no existe)'; }\n"

#: Clave de fantasia del modo `--auth`. Larga a proposito: por debajo de seis
#: caracteres el redactor del backend no la registraria.
CLAVE_VERIFICACION = "clave-verificacion-operator-0001"


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


def preparar_pagina(preambulo: str = "") -> None:
    """Escribe la copia instrumentada de la pagina construida y la sonda.

    **No se borra nada.** El entorno bloquea los borrados tras 50 por turno, y
    cada borrado bloqueado mata el proceso: la verificacion moria en 1,3 s y el
    verificador de mutaciones lo interpretaba como «mutacion cazada». Un falso
    positivo, y de los peores: el que hace parecer que la comprobacion funciona.

    Los dos ficheros se sobrescriben en cada ejecucion, asi que no hay contenido
    obsoleto. Se escriben en `dist/`, que esta ignorado por git.

    `preambulo` se inyecta al principio de la sonda, antes de que el modulo de
    la aplicacion se ejecute. En el modo `--auth` guarda la clave en el
    `localStorage`; en el modo normal va vacio.
    """
    if not DIST.is_dir():
        raise SystemExit(
            "FALLO: no existe la construccion del frontend en frontend/dist.\n"
            "       Ejecuta:  cd frontend && npm install && npm run build"
        )
    sonda = SONDA_JS.replace(_MARCA_PREAMBULO, _MARCA_PREAMBULO + preambulo, 1)
    if preambulo and sonda == SONDA_JS:
        raise SystemExit("FALLO: no se pudo inyectar el preambulo en la sonda")
    if SONDA.exists() and SONDA.read_text(encoding="utf-8") != sonda:
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
    SONDA.write_text(sonda, encoding="utf-8")


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


def _reconstruir() -> None:
    """Reconstruye `frontend/dist` desde el fuente antes de verificar.

    **Por que.** Ver la cabecera del modulo: sin esto la herramienta mide la
    construccion anterior al cambio. La reconstruccion es lo unico que hace
    que "verde" signifique "el arbol actual funciona".

    Un fallo de compilacion es un fallo de la verificacion, no una excusa: con
    una mutacion aplicada -typecheck roto- el `npm run build` sale con codigo
    distinto de cero y hay que pararse y decirlo, no seguir con el `dist`
    anterior como si nada.
    """
    npm = shutil.which("npm") or "npm"
    orden = (
        ["cmd", "/c", npm, "run", "build"]
        if sys.platform == "win32"
        else [npm, "run", "build"]
    )
    try:
        resultado = subprocess.run(
            orden, cwd=FRONTEND, capture_output=True, text=True, timeout=300
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise SystemExit(f"FALLO: no se pudo reconstruir el frontend: {exc}") from exc
    if resultado.returncode != 0:
        # El typecheck roto **es** la mutacion cazada: con la mutacion aplicada
        # el codigo no compila y la propiedad no puede sostenerse. Se emite el
        # marcador de veredicto para que el arnes lo cuente como cazada -un
        # fallo de compilacion es un veredicto, no una caida del verificador-.
        # Un `npm` ausente o un corte de tiempo NO llevan marcador: ahi si que
        # no se ha comprobado nada, y eso debe seguir siendo NO CONCLUYENTE.
        raise SystemExit(
            "RESULTADO: FALLO DE CONSTRUCCION - el frontend no compila (con una "
            "mutacion del verificador aplicada, el typecheck la caza):\n"
            + (resultado.stdout + resultado.stderr)[-2000:]
        )

def main() -> int:
    modo_auth = "--auth" in sys.argv
    navegador = encontrar_navegador()
    if navegador is None:
        print("VERIFICACION OMITIDA: no se encontro Chromium en las rutas de Playwright")
        return 0
    print(f"navegador: {navegador}")

    # La reconstruccion es la puerta: si `src/` no compila, la verificacion no
    # puede continuar -y con una mutacion del verificador aplicada, que no
    # compile ES el resultado-. Sustituye a la vieja comprobacion de que
    # `dist/` existiera, que media restos de compilaciones ajenas.
    _reconstruir()
    if not DIST.is_dir():
        print("FALLO: la reconstruccion no dejo frontend/dist")
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
    if modo_auth:
        # Una sola clave, de `operator`: el flujo de la interfaz crea ejecuciones
        # y responde las dos puertas, que es lo que `operator` puede hacer.
        entorno["AI_SWE_API_KEYS"] = json.dumps({CLAVE_VERIFICACION: "operator"})
        print("modo: autenticacion ACTIVADA (una clave de operator)")
    else:
        print("modo: autenticacion desactivada")
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

        preparar_pagina(PREAMBULO_AUTH.replace("__CLAVE__", CLAVE_VERIFICACION) if modo_auth else "")
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
    # Y los hitos llegaron **marcados como alcanzados**, no solo como filas
    # pendientes: la linea de tiempo pinta los cuatro hitos canonicos siempre,
    # asi que sin esta comprobacion una interfaz que nunca recibiera un evento
    # habria pasado la anterior.
    comprobar(
        "los hitos recibidos se pintan como alcanzados",
        int(campos.get("HITOS_ALCANZADOS", "0") or 0) >= 1,
        f"HITOS_ALCANZADOS={campos.get('HITOS_ALCANZADOS')}",
    )
    comprobar("la pagina no desborda horizontalmente",
              campos.get("SIN_SCROLL_HORIZONTAL") == "true")
    # La base arranca limpia, asi que debe haber exactamente una ejecucion: la que
    # acaba de crear la interfaz. Comprueba de paso que el aislamiento funciona.
    comprobar("el almacen arranco aislado y limpio", campos.get("FILAS_TABLA") == "1",
              f"FILAS_TABLA={campos.get('FILAS_TABLA')}")

    if modo_auth:
        # La credencial llega al frontend **por su pantalla de acceso**: la sonda
        # la teclea y pulsa Continuar, como una persona. Que los eventos lleguen
        # por SSE prueba ademas la ruta de `?api_key=` del `EventSource`, que
        # ningun `fetch` del cliente puede ejercitar.
        comprobar(
            "la pantalla de acceso aparecio",
            campos.get("AUTH_PANTALLA") == "true",
            f"AUTH_PANTALLA={campos.get('AUTH_PANTALLA')}",
        )
        comprobar(
            "la credencial tecleada se envio desde la interfaz",
            campos.get("CLAVE_ENVIADA") == "true",
            f"CLAVE_ENVIADA={campos.get('CLAVE_ENVIADA')}",
        )
        comprobar(
            "la sesion quedo autenticada",
            campos.get("SESION") == "autenticado",
            f"SESION={campos.get('SESION')}",
        )
        comprobar("el servidor rechaza la peticion sin credencial (401)",
                  campos.get("SIN_CLAVE") == "401",
                  f"SIN_CLAVE={campos.get('SIN_CLAVE')}")
        comprobar("la credencial valida autentica (200)",
                  campos.get("CON_CLAVE") == "200",
                  f"CON_CLAVE={campos.get('CON_CLAVE')}")
        # Las tres que vigilan el manejo de la credencial. La primera es la
        # decision de esta entrega -vive en memoria-, y las otras dos son las
        # reglas de siempre: no se pinta y no se registra.
        comprobar(
            "la credencial no se guarda en el navegador",
            campos.get("ALMACEN_CLAVE") == "false",
            f"ALMACEN_CLAVE={campos.get('ALMACEN_CLAVE')}",
        )
        comprobar(
            "la credencial no aparece en el DOM",
            campos.get("CLAVE_EN_DOM") == "false",
            f"CLAVE_EN_DOM={campos.get('CLAVE_EN_DOM')}",
        )
        comprobar(
            "la credencial no se escribe en la consola",
            campos.get("CLAVE_EN_CONSOLA") == "false",
            f"CLAVE_EN_CONSOLA={campos.get('CLAVE_EN_CONSOLA')}",
        )
    else:
        # Con el servidor sin autenticacion no hay nada que pedir: la interfaz no
        # puede bloquearse pidiendo una credencial que nadie va a comprobar.
        comprobar(
            "la interfaz no pide credencial si el servidor no la exige",
            campos.get("AUTH_PANTALLA") == "false",
            f"AUTH_PANTALLA={campos.get('AUTH_PANTALLA')}",
        )

    if fallos:
        print(f"\nRESULTADO: {len(fallos)} comprobacion(es) fallidas -> {fallos}")
        return 1
    etiqueta = " (modo autenticado)" if modo_auth else ""
    print(f"\nRESULTADO: la interfaz funciona en un motor real{etiqueta}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

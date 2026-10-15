"""Captura de pantalla de la interfaz, para revisar el resultado visual.

No es parte de la verificacion -eso lo hacen `tools/verify_frontend.py`,
`tools/verify_puerta_aprobacion.py` y `tools/verify_pantallas.py`, que ademas
comprueban-: esto sirve para **mirar** las pantallas en un navegador real y
ensenarlas. Se apoya en las mismas piezas de los verificadores (servidor real,
`dist` reconstruido, sembrador de una ejecucion con evidencia, Chromium de
Playwright).

Cada captura es una corrida del navegador con un **guion** de navegacion: se
rellena la credencial si hace falta, se pulsa la seccion en la barra y, cuando la
vista necesita una ejecucion abierta, se pulsa su fila. Nada de eso simula la
aplicacion: son los mismos clics que daria una persona.

Uso: python tools/capturar_interfaz.py <carpeta-de-salida>
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_frontend import (  # noqa: E402
    CLAVE_VERIFICACION,
    DIST,
    RAIZ,
    _matar_arbol,
    _reconstruir,
    encontrar_navegador,
    esperar_servidor,
    puerto_libre,
)
from verify_puerta_aprobacion import sembrar  # noqa: E402

# El guion se inyecta como datos: una lista de pasos, cada uno o el nombre de una
# seccion de la barra o `fila` (pulsar la primera ejecucion del historial).
#
# **No hay paso de scroll, a proposado.** La primera version tenia `ir:<selector>`
# para llevar una seccion a la vista (`scrollIntoView`), y con el Chrome headless
# de este entorno **dejaba el fotograma en blanco**: un PNG de 5,8 KB, la pagina
# entera pintada de nada. Con ventana alta salia un recorte de 28 KB -el trozo de
# abajo-, nunca lo que se pedia. Lo que funciona es lo contrario: no hacer scroll y
# dar una ventana lo bastante alta para que la pagina quepa entera
# (`06-detalle-completo`). Medido, no supuesto: 5.853 bytes con scroll, 174.829 sin.
GUION_JS = """
(function () {
  var GUION = __GUION__;
  var CLAVE = '__CLAVE__';
  var paso = 0, intentos = 0, tecleada = false;

  // **El flujo en vivo se sustituye por uno de mentira.** Abrir una ejecucion
  // levanta un `EventSource` de verdad, y `--virtual-time-budget` **espera a que
  // no queden peticiones pendientes** antes de disparar la captura: una corriente
  // SSE no termina nunca, asi que el navegador no cerraba jamas y las capturas que
  // abren una ejecucion se quedaban sin fichero. Se descubrio porque fallaban
  // justo las que pulsan una fila.
  window.EventSource = function () {
    this.close = function () {};
    this.addEventListener = function () {};
    return this;
  };

  function escribirCredencial(campo) {
    var setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
    setter.call(campo, CLAVE);
    campo.dispatchEvent(new Event('input', { bubbles: true }));
  }

  function accion() {
    if (paso >= GUION.length) return 'fin';
    var orden = GUION[paso];
    if (orden === 'fila') {
      var fila = document.querySelector('#tabla-ejecuciones tbody tr');
      if (fila) { fila.click(); paso++; return 'sigo'; }
      return 'espero';
    }
    var nav = document.querySelector('.navegacion');
    if (!nav) return 'espero';
    var botones = nav.querySelectorAll('.nav-item');
    for (var i = 0; i < botones.length; i++) {
      if (botones[i].textContent.indexOf(orden) >= 0) {
        botones[i].click();
        paso++;
        return 'sigo';
      }
    }
    return 'espero';
  }

  var t = setInterval(function () {
    intentos++;
    var campo = document.querySelector('#api-key');
    if (campo) {
      if (!tecleada) { escribirCredencial(campo); tecleada = true; return; }
      var boton = document.querySelector('#btn-continuar');
      if (boton && !boton.disabled) boton.click();
      return;
    }
    if (accion() === 'fin' || intentos > 200) clearInterval(t);
  }, 100);
})();
"""


def preparar_pagina(guion: list[str] | None) -> None:
    """Escribe la copia instrumentada. El script va **externo**, no incrustado.

    `guion=None` deja la pagina **sin tocar**: es lo que se quiere para capturar
    la pantalla de acceso, que es justo lo que sale cuando nadie teclea la
    credencial. Una lista -aunque este vacia- si instrumenta: rellena la
    credencial y, si hay pasos, navega. La primera version solo instrumentaba
    cuando el guion tenia pasos, asi que la captura de la vista general salio
    siendo otra vez la pantalla de acceso.

    El script va externo porque la CSP del backend declara `script-src 'self'`:
    un `<script>` en linea no se ejecuta, y lo que parecia un problema de tiempos
    era la politica de seguridad haciendo su trabajo.
    """
    html = (DIST / "index.html").read_text(encoding="utf-8")
    if guion is not None:
        (DIST / "_captura.js").write_text(
            GUION_JS.replace("__GUION__", json.dumps(guion)).replace(
                "__CLAVE__", CLAVE_VERIFICACION
            ),
            encoding="utf-8",
        )
        html = html.replace(
            '<script type="module"',
            '<script src="_captura.js"></script>\n    <script type="module"',
            1,
        )
    (DIST / "_captura.html").write_text(html, encoding="utf-8")


def capturar(navegador: Path, url: str, destino: Path, espera_ms: int, tamano: str) -> None:
    perfil = tempfile.mkdtemp(prefix="aiswe-shot-")
    orden = [
        str(navegador),
        "--headless", "--disable-gpu", "--no-sandbox", "--hide-scrollbars",
        f"--window-size={tamano}",
        f"--virtual-time-budget={espera_ms}",
        f"--user-data-dir={perfil}",
        f"--screenshot={destino}",
        url,
    ]
    proceso = subprocess.Popen(
        orden, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace",
    )
    try:
        proceso.communicate(timeout=120)
    except subprocess.TimeoutExpired:
        _matar_arbol(proceso.pid)


# nombre del fichero, con credencial, guion de navegacion (`None` = sin
# instrumentar: la pagina tal cual, que es como se ve la pantalla de acceso),
# tamano
CAPTURAS: list[tuple[str, bool, list[str] | None, str]] = [
    ("01-acceso.png", True, None, "1440,900"),
    ("02-vista-general.png", True, [], "1440,900"),
    ("03-proyectos.png", True, ["Proyectos"], "1440,900"),
    ("04-ejecuciones.png", True, ["Ejecuciones"], "1440,900"),
    ("05-puerta-aprobacion.png", True, ["Ejecuciones", "fila"], "1440,900"),
    # El detalle completo, de arriba abajo, en una ventana alta: es la unica forma
    # de verlo entero en una imagen (ver la nota sobre el scroll en GUION_JS).
    ("06-detalle-completo.png", True, ["Ejecuciones", "fila"], "1440,2600"),
    ("07-flujo.png", True, ["Ejecuciones", "fila", "Flujo"], "1440,900"),
    ("08-seguridad.png", True, ["Seguridad"], "1440,900"),
    ("09-sesion.png", True, ["Sesión"], "1440,900"),
    ("10-general-1920.png", True, [], "1920,1080"),
    ("11-general-1366.png", True, [], "1366,768"),
    ("12-general-tablet.png", True, [], "834,1112"),
]


def main() -> int:
    salida = Path(sys.argv[1]).resolve()
    salida.mkdir(parents=True, exist_ok=True)
    navegador = encontrar_navegador()
    if navegador is None:
        print("FALLO: no se encontro Chromium")
        return 1

    # **Reconstruir antes de capturar, o se fotografia el codigo equivocado.** El
    # verificador de mutaciones deja `dist` compilado desde la **ultima mutacion**
    # que probo: la primera version de este capturador servia ese `dist` y la
    # captura del panel autenticado salio con la credencial entera a la vista,
    # porque la ultima mutacion era justo la que rompe la mascara. El fichero del
    # producto estaba bien; lo que estaba mal era lo que se estaba sirviendo.
    _reconstruir()

    puerto = puerto_libre()
    carpeta = Path(tempfile.mkdtemp(prefix="aiswe-estado-"))
    estado = carpeta / "estado.sqlite3"
    # Una ejecucion detenida en la puerta de aprobacion, con evidencia real: es lo
    # que hace que el detalle, el flujo y el presupuesto tengan algo que ensenar.
    sembrar(estado)
    base = f"http://127.0.0.1:{puerto}"

    for nombre, con_auth, guion, tamano in CAPTURAS:
        entorno = {**os.environ, "PYTHONPATH": "src", "AI_SWE_STATE_DB_PATH": str(estado)}
        if con_auth:
            entorno["AI_SWE_API_KEYS"] = json.dumps({CLAVE_VERIFICACION: "operator"})
        servidor = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "ai_swe.api.app:crear_app", "--factory",
             "--host", "127.0.0.1", "--port", str(puerto), "--log-level", "warning"],
            cwd=RAIZ, env=entorno, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        try:
            if not esperar_servidor(f"{base}/health"):
                print("FALLO: el servidor no arranco")
                return 1
            preparar_pagina(guion)
            capturar(navegador, f"{base}/app/_captura.html", salida / nombre, 15000, tamano)
            print(f"  {nombre}: {'ok' if (salida / nombre).exists() else 'FALLO'}")
        finally:
            servidor.terminate()
            try:
                servidor.wait(timeout=10)
            except subprocess.TimeoutExpired:
                servidor.kill()
            time.sleep(0.4)
    print(f"capturas en {salida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

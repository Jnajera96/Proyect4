"""Captura de pantalla de la interfaz, para revisar el resultado visual.

No es parte de la verificacion -eso lo hace `tools/verify_frontend.py`, que
ademas comprueba-: esto solo sirve para mirar la pantalla de acceso y el estado
autenticado en un navegador real. Se apoya en las mismas piezas del verificador
(servidor real, `dist` reconstruido, Chromium de Playwright).

Uso: python tools/capturar_interfaz.py <carpeta-de-salida>
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
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

# Rellena la pantalla de acceso y pulsa Continuar, como la sonda del verificador.
ESCRIBIR_CLAVE = """
(function () {
  var intentos = 0;
  var t = setInterval(function () {
    intentos++;
    var campo = document.querySelector('#api-key');
    if (campo) {
      var setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
      setter.call(campo, '%s');
      campo.dispatchEvent(new Event('input', { bubbles: true }));
      var boton = document.querySelector('#btn-continuar');
      if (boton && !boton.disabled) { boton.click(); clearInterval(t); }
    }
    if (intentos > 100) clearInterval(t);
  }, 100);
})();
""" % CLAVE_VERIFICACION


def preparar_pagina(instrumentar: bool) -> None:
    """Escribe la copia instrumentada. El script va **externo**, no incrustado.

    La CSP del backend declara `script-src 'self'`, asi que un `<script>` en linea
    no se ejecuta. La primera version de este capturador lo incrustaba y la
    captura del estado autenticado salia identica a la de la pantalla de acceso:
    el script no habia corrido y la credencial nunca se tecleo. Lo que parecia un
    problema de tiempos era la politica de seguridad haciendo su trabajo.
    """
    html = (DIST / "index.html").read_text(encoding="utf-8")
    if instrumentar:
        (DIST / "_captura.js").write_text(ESCRIBIR_CLAVE, encoding="utf-8")
        html = html.replace(
            '<script type="module"',
            '<script src="_captura.js"></script>\n    <script type="module"',
            1,
        )
    (DIST / "_captura.html").write_text(html, encoding="utf-8")


def capturar(navegador: Path, url: str, destino: Path, espera_ms: int) -> None:
    perfil = tempfile.mkdtemp(prefix="aiswe-shot-")
    orden = [
        str(navegador),
        "--headless", "--disable-gpu", "--no-sandbox", "--hide-scrollbars",
        "--window-size=1500,1000",
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
    estado = Path(tempfile.mkdtemp(prefix="aiswe-estado-")) / "estado.sqlite3"
    base = f"http://127.0.0.1:{puerto}"

    for nombre, con_auth, instrumentar in (
        ("acceso.png", True, False),
        ("panel-autenticado.png", True, True),
        ("sin-autenticacion.png", False, False),
    ):
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
            preparar_pagina(instrumentar)
            capturar(navegador, f"{base}/app/_captura.html", salida / nombre, 12000)
            print(f"  {nombre}: {'ok' if (salida / nombre).exists() else 'FALLO'}")
        finally:
            servidor.terminate()
            try:
                servidor.wait(timeout=10)
            except subprocess.TimeoutExpired:
                servidor.kill()
            time.sleep(0.5)
    print(f"capturas en {salida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

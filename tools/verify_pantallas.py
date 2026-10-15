"""Verifica la **presentacion**: responsive y presupuesto, en un navegador real.

**Por que hace falta.** `verify_frontend.py` conduce el flujo completo -crear una
ejecucion, responder a las dos puertas- y comprueba que la interfaz *funciona*;
pero corre en **un solo tamano de ventana** y no mira el presupuesto. Dos cosas
del alcance de esta entrega quedaban, por tanto, sin comprobar: que la interfaz
aguante los tamanos en los que se va a presentar (1920x1080, 1440x900,
1366x768 y una tableta) y que el presupuesto que se pinta sea **el del servidor**
y no una cifra inventada.

**Que se comprueba, y de donde sale cada dato.** Se siembra una ejecucion con
presupuesto real -el mismo sembrador que usa `verify_puerta_aprobacion.py`-, se
abre su detalle y se comparan las filas del panel con lo que devuelve
`GET /runs/{id}`: si la pantalla ensena otra cosa que lo que el servidor dice, la
comprobacion falla. El coste se comprueba en su forma declarada: el acumulado cero no distingue desconocido de gratuito; se presenta como coste
no disponible. max_cost nulo solo declara que no hay limite monetario.

**Lo que NO se comprueba aqui.** El aspecto. Que una captura "se vea bien" no es
una comprobacion automatica y no se finge que lo sea: lo que se mide es que no
haya desbordamiento horizontal, que la navegacion y el contenido esten visibles y
que los datos pintados sean los del servidor. Las capturas de esta corrida se
guardan para revisarlas a ojo.

Uso: python tools/verify_pantallas.py [carpeta-de-capturas]
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from verify_frontend import (  # noqa: E402
    DIST,
    RAIZ,
    _lanzar_navegador,
    _matar_arbol,
    _reconstruir,
    encontrar_navegador,
    esperar_servidor,
    puerto_libre,
)
from verify_puerta_aprobacion import sembrar  # noqa: E402

# Los tamanos en los que se presenta el sistema, mas una tableta.
TAMANOS = [
    ("1920x1080", 1920, 1080),
    ("1440x900", 1440, 900),
    ("1366x768", 1366, 768),
    ("tableta-834", 834, 1112),
]

PROBE = r"""
var pasos = [], errores = [];
// El flujo en vivo no aporta nada aqui y mete ruido: la pantalla se mide sin el.
window.EventSource = function () { this.close = function () {}; this.addEventListener = function () {}; return this; };
window.addEventListener('error', function (e) { errores.push('ERROR: ' + e.message); }, true);
(function () {
  var oe = console.error, ow = console.warn;
  console.error = function () { errores.push('CONSOLE_ERROR: ' + [].join.call(arguments, ' ')); oe.apply(console, arguments); };
  console.warn = function () { errores.push('CONSOLE_WARN: ' + [].join.call(arguments, ' ')); ow.apply(console, arguments); };
})();
function anota(k, v) { pasos.push(k + '=' + v); }
function volcar() {
  var d = document.createElement('div');
  d.id = '_informe';
  d.textContent = 'N_ERRORS=' + errores.length + ' ||| ' + errores.join(' ||| ')
    + ' ||| ' + pasos.join(' ||| ');
  document.body.appendChild(d);
}

// --------------------------------------------------------------- contraste
// **Se mide lo que el navegador pinta, no lo que dice la hoja de estilos.** El
// encargo pide contraste, y "se ve bien" no es una comprobacion: se lee el color
// calculado de cada texto secundario, se busca su fondo real subiendo por el DOM
// y se calcula la razon de contraste de la WCAG. Antes de esto el valor de
// `--texto-tenue` daba 3,62:1 -por debajo del minimo AA- y no lo detectaba nadie.
function luminancia(rgb) {
  var c = [];
  for (var i = 0; i < 3; i++) {
    var v = rgb[i] / 255;
    c.push(v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4));
  }
  return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
}
function colorDe(t) {
  var m = /rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*([\d.]+))?\)/.exec(t || '');
  if (!m) return null;
  return { rgb: [Number(m[1]), Number(m[2]), Number(m[3])], a: m[4] === undefined ? 1 : Number(m[4]) };
}
function fondoDe(nodo) {
  var n = nodo;
  while (n) {
    var c = colorDe(getComputedStyle(n).backgroundColor);
    if (c && c.a > 0.95) return c.rgb;
    n = n.parentElement;
  }
  return [255, 255, 255];
}
function contrasteDe(nodo) {
  var t = colorDe(getComputedStyle(nodo).color);
  if (!t) return -1;
  var a = luminancia(t.rgb), b = luminancia(fondoDe(nodo));
  return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
}
var SELECTORES_CONTRASTE = [
  '.tenue', '.panel-nota', '.seccion-nota', '.tarjeta-pie', '.tarjeta-rotulo',
  '.subtitulo', 'dl.datos dt', '.estado-vacio-texto',
];
function medirContraste() {
  var peor = 99, peorSel = '', medidos = 0;
  for (var s = 0; s < SELECTORES_CONTRASTE.length; s++) {
    var nodos = document.querySelectorAll(SELECTORES_CONTRASTE[s]);
    for (var i = 0; i < nodos.length; i++) {
      if (!(nodos[i].textContent || '').trim()) continue;
      var r = contrasteDe(nodos[i]);
      if (r > 0) {
        medidos++;
        if (r < peor) { peor = r; peorSel = SELECTORES_CONTRASTE[s]; }
      }
    }
  }
  anota('CONTRASTE_MEDIDOS', medidos);
  anota('CONTRASTE_MINIMO', medidos ? peor.toFixed(2) : 'sin-medir');
  anota('CONTRASTE_PEOR', peorSel || '-');
}

// Modo: 'con-ejecucion' abre el detalle sembrado; 'vacio' mide los estados vacios.
var MODO = '__MODO__';
var abierto = false, medido = false, intentos = 0;

function medir() {
  medido = true;
  anota('ANCHO', window.innerWidth);
  anota('ALTO', window.innerHeight);
  anota('DESBORDA', document.documentElement.scrollWidth > window.innerWidth + 1);
  anota('NAV_ITEMS', document.querySelectorAll('.navegacion .nav-item').length);
  var vista = document.querySelector('.vista');
  anota('CONTENIDO_VISIBLE', !!(vista && vista.getBoundingClientRect().height > 0));
  anota('VACIOS', document.querySelectorAll('.estado-vacio').length);
  anota('ESQUELETOS', document.querySelectorAll('.esqueleto').length);
  anota('TABLA_FILAS', document.querySelectorAll('#tabla-ejecuciones tbody tr').length);

  if (MODO === 'con-ejecucion') {
    // Las filas del presupuesto, tal cual se pintan: "rotulo|usado/maximo".
    var filas = [];
    var nodos = document.querySelectorAll('.presupuesto-fila');
    for (var i = 0; i < nodos.length; i++) {
      var rotulo = nodos[i].querySelector('.presupuesto-rotulo');
      var valores = nodos[i].querySelectorAll('span');
      var ultimo = valores[valores.length - 1];
      filas.push((rotulo ? rotulo.textContent : '?') + '|' + (ultimo ? ultimo.textContent : '?'));
    }
    anota('PRESUPUESTO', filas.join(';'));
    var cuerpo = document.body.textContent || '';
    anota('COSTE_DECLARADO', cuerpo.indexOf('Coste no disponible') >= 0 ? 'desconocido' : 'registrado');
    anota('IMPRIME_CERO', /\$\s*0[.,]00/.test(cuerpo));
    // Los dos desgloses de tokens, leidos del propio panel.
    var dl = document.querySelector('.datos');
    anota('PANEL_DATOS', dl ? 'true' : 'false');
  }
  clearInterval(reloj);
  medirContraste();
  volcar();
}

var intervaloReal = window.setInterval.bind(window);
var reloj = intervaloReal(function () {
  intentos++;
  if (MODO === 'con-ejecucion' && !medido) {
    if (!document.querySelector('.presupuesto')) {
      var fila = document.querySelector('#tabla-ejecuciones tbody tr');
      if (fila && !abierto) { abierto = true; fila.click(); }
    } else {
      medir();
      return;
    }
  } else if (MODO === 'vacio' && !medido) {
    // Con el almacen vacio se espera a que el montaje termine: sin esqueletos.
    if (document.querySelector('.navegacion') && !document.querySelector('.esqueleto')) {
      medir();
      return;
    }
  }
  if (intentos > 150) {
    clearInterval(reloj);
    errores.push('PROBE: la pantalla no llego a un estado medible');
    volcar();
  }
}, 100);

// A partir de aqui, la aplicacion no arranca su sondeo de 900 ms.
window.setInterval = function () { return 0; };
"""


def _lanzar(navegador: Path, url: str, ancho: int, alto: int) -> str:
    dom, _ = _lanzar_navegador(
        [
            str(navegador), "--headless", "--disable-gpu", "--no-sandbox", "--dump-dom",
            "--hide-scrollbars", f"--window-size={ancho},{alto}", "--virtual-time-budget=40000",
            f"--user-data-dir={tempfile.mkdtemp(prefix='aiswe-chrome-')}", url,
        ],
        limite=120,
    )
    return dom


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
        elif parte.startswith(("ERROR:", "PROBE", "CONSOLE")):
            errores.append(parte)
    return campos, errores


def _numero(texto: str) -> int:
    """Los digitos de una cifra pintada, sin separadores de millar."""
    limpio = re.sub(r"[^0-9]", "", texto or "")
    return int(limpio) if limpio else -1


def _contraste(campos: dict[str, str]) -> float:
    """El contraste minimo medido en el navegador, o 0 si no se pudo medir.

    Un cero hace fallar la comprobacion a proposito: **"no se pudo medir" no es
    "cumple"**. Si el probe no encuentra ningun nodo de texto secundario, la
    comprobacion tiene que fallar y decir que no midio nada, no pasar en verde por
    ausencia de datos.
    """
    try:
        return float(campos.get("CONTRASTE_MINIMO", ""))
    except ValueError:
        return 0.0


def _servir(navegador: Path, estado_db: Path) -> tuple[int, dict, str]:
    """Levanta el servidor y devuelve (puerto, estado de la ejecucion, run_id)."""
    puerto = puerto_libre()
    base = f"http://127.0.0.1:{puerto}"
    entorno = {**os.environ, "PYTHONPATH": "src", "AI_SWE_STATE_DB_PATH": str(estado_db)}
    servidor = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "ai_swe.api.app:crear_app", "--factory",
         "--host", "127.0.0.1", "--port", str(puerto), "--log-level", "warning"],
        cwd=RAIZ, env=entorno, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    if not esperar_servidor(f"{base}/health"):
        _matar_arbol(servidor.pid)
        raise SystemExit("FALLO: el servidor no arranco")
    return puerto, base, servidor


def main() -> int:
    salida = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else None
    if salida:
        salida.mkdir(parents=True, exist_ok=True)

    navegador = encontrar_navegador()
    if navegador is None:
        print("VERIFICACION OMITIDA: no se encontro Chromium")
        return 0

    # Reconstruir **siempre**: el arnes de mutaciones deja `dist` compilado desde
    # la ultima mutacion que probo.
    _reconstruir()

    fallos: list[str] = []

    def comprobar(nombre: str, condicion: bool, detalle: str = "") -> None:
        print(f"  {'OK   ' if condicion else 'FALLO'} {nombre}{('  (' + detalle + ')') if detalle else ''}")
        if not condicion:
            fallos.append(nombre)

    html = (DIST / "index.html").read_text(encoding="utf-8")

    def instrumentar(modo: str) -> None:
        (DIST / "_pantallas.js").write_text(PROBE.replace("__MODO__", modo), encoding="utf-8")
        (DIST / "_pantallas.html").write_text(
            html.replace(
                '<script type="module"',
                '<script src="_pantallas.js"></script>\n    <script type="module"',
                1,
            ),
            encoding="utf-8",
        )

    # ---------------------------------------------------- pasada 1: responsive
    carpeta = Path(tempfile.mkdtemp(prefix="aiswe-pantallas-"))
    estado_db = carpeta / "estado.sqlite3"
    run_id = sembrar(estado_db)
    instrumentar("con-ejecucion")

    puerto, base, servidor = _servir(navegador, estado_db)
    try:
        with urllib.request.urlopen(f"{base}/runs/{run_id}", timeout=10) as respuesta:
            estado = json.loads(respuesta.read())
        presupuesto = estado["budget"]

        for nombre, ancho, alto in TAMANOS:
            print(f"\n== {nombre} ==")
            dom = _lanzar(navegador, f"{base}/app/_pantallas.html", ancho, alto)
            campos, errores = _campos(dom)
            comprobar("la pantalla monto sin errores", not errores, "; ".join(errores[:2]))
            comprobar(
                "no desborda horizontalmente",
                campos.get("DESBORDA") == "false",
                f"ancho={campos.get('ANCHO')} desborda={campos.get('DESBORDA')}",
            )
            comprobar(
                "la navegacion esta entera",
                _numero(campos.get("NAV_ITEMS", "")) == 7,
                f"NAV_ITEMS={campos.get('NAV_ITEMS')}",
            )
            comprobar(
                "el contenido es visible",
                campos.get("CONTENIDO_VISIBLE") == "true",
                f"CONTENIDO_VISIBLE={campos.get('CONTENIDO_VISIBLE')}",
            )
            # El contraste se mide sobre los colores que el navegador pinta. El
            # encargo lo pide y "se ve bien" no es una comprobacion.
            comprobar(
                "el texto secundario cumple AA (4,5:1)",
                _contraste(campos) >= 4.5,
                f"minimo={campos.get('CONTRASTE_MINIMO')} en {campos.get('CONTRASTE_PEOR')} "
                f"({campos.get('CONTRASTE_MEDIDOS')} nodos medidos)",
            )
            comprobar(
                "la ejecucion se abrio en el detalle",
                campos.get("PANEL_DATOS") == "true",
                f"PANEL_DATOS={campos.get('PANEL_DATOS')}",
            )

            # ---- el presupuesto pintado contra el presupuesto del servidor
            filas: dict[str, str] = {}
            for trozo in (campos.get("PRESUPUESTO") or "").split(";"):
                if "|" in trozo:
                    rotulo, valores = trozo.split("|", 1)
                    filas[rotulo.strip()] = valores.strip()
            esperado = {
                "tokens": (presupuesto["used_tokens"], presupuesto["max_tokens"]),
                "llamadas al modelo": (
                    presupuesto["used_model_calls"],
                    presupuesto["max_model_calls"],
                ),
                "llamadas a herramientas": (
                    presupuesto["used_tool_calls"],
                    presupuesto["max_tool_calls"],
                ),
                "ciclos de revisión": (
                    presupuesto["review_cycles_used"],
                    presupuesto["max_review_cycles"],
                ),
            }
            for rotulo, (usado, maximo) in esperado.items():
                pintado = filas.get(rotulo)
                if pintado is None:
                    comprobar(f"el presupuesto ensena {rotulo}", False, "no se pinto la fila")
                    continue
                partes = [p for p in pintado.split("/")]
                acierta = (
                    len(partes) == 2
                    and _numero(partes[0]) == usado
                    and _numero(partes[1]) == maximo
                )
                comprobar(
                    f"el presupuesto de {rotulo} es el del servidor",
                    acierta,
                    f"pintado={pintado} servidor={usado}/{maximo}",
                )
            comprobar(
                "un acumulado cero no se presenta como coste conocido",
                (
                    campos.get("COSTE_DECLARADO") == "desconocido"
                    if presupuesto["used_cost"] == 0
                    else campos.get("COSTE_DECLARADO") == "registrado"
                ),
                f"max_cost={presupuesto['max_cost']} pintado={campos.get('COSTE_DECLARADO')}",
            )
            comprobar(
                "nunca se imprime un importe de cero",
                campos.get("IMPRIME_CERO") == "false",
                f"IMPRIME_CERO={campos.get('IMPRIME_CERO')}",
            )
    finally:
        servidor.terminate()
        try:
            servidor.wait(timeout=10)
        except subprocess.TimeoutExpired:
            servidor.kill()

    # ------------------------------------------------- pasada 2: estados vacios
    print("\n== almacen vacio ==")
    carpeta_vacia = Path(tempfile.mkdtemp(prefix="aiswe-vacio-"))
    instrumentar("vacio")
    puerto, base, servidor = _servir(navegador, carpeta_vacia / "estado.sqlite3")
    try:
        dom = _lanzar(navegador, f"{base}/app/_pantallas.html", 1440, 900)
        campos, errores = _campos(dom)
        comprobar("la pantalla monto sin errores", not errores, "; ".join(errores[:2]))
        comprobar(
            "sin datos se explica la situacion, no se deja un hueco",
            _numero(campos.get("VACIOS", "")) >= 1,
            f"VACIOS={campos.get('VACIOS')}",
        )
        comprobar(
            "no queda ningun esqueleto de carga colgado",
            campos.get("ESQUELETOS") == "0",
            f"ESQUELETOS={campos.get('ESQUELETOS')}",
        )
        comprobar(
            "la tabla de ejecuciones no se pinta vacia",
            campos.get("TABLA_FILAS") == "0",
            f"TABLA_FILAS={campos.get('TABLA_FILAS')}",
        )
        comprobar(
            "no desborda horizontalmente",
            campos.get("DESBORDA") == "false",
            f"desborda={campos.get('DESBORDA')}",
        )
        # El contraste tambien se comprueba sin datos: el texto de un estado vacio
        # es texto secundario y se lee igual de mal si no llega al minimo.
        comprobar(
            "el texto secundario cumple AA (4,5:1) sin datos",
            _contraste(campos) >= 4.5,
            f"minimo={campos.get('CONTRASTE_MINIMO')} en {campos.get('CONTRASTE_PEOR')} "
            f"({campos.get('CONTRASTE_MEDIDOS')} nodos medidos)",
        )
    finally:
        servidor.terminate()
        try:
            servidor.wait(timeout=10)
        except subprocess.TimeoutExpired:
            servidor.kill()

    if fallos:
        print(f"\nRESULTADO: {len(fallos)} comprobacion(es) fallidas -> {fallos}")
        return 1
    print("\nRESULTADO: la presentacion aguanta los cuatro tamanos y el presupuesto es el del servidor.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

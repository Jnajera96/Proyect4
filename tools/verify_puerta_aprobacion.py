"""Verifica la **pantalla de la puerta de aprobacion** en un navegador real.

**Por que hace falta un verificador aparte.** El flujo automatizado no llega a
esta puerta: sin repositorio ni modelo reales el Coder no produce cambios, el
grafo termina en `escalate_no_changes` y la ejecucion pasa de la puerta de
requisitos a `completed` sin pedir aprobacion. Es decir, la pantalla mas
consecuente del sistema -la unica que promueve cambios al repositorio del
usuario- no la ejercitaba nadie.

**Que se verifica aqui, y que no.** Aqui se siembra una ejecucion detenida en
`awaiting_approval` con evidencia real (un diff, dos ejecuciones de pruebas -una
correcta y una fallida-, un veredicto del revisor con hallazgos y un presupuesto
consumido) y se comprueba **lo que la pantalla ensena**: el diff, la evidencia,
el veredicto, el aviso de consecuencia, los tres botones y que la pantalla **no
decide nada por su cuenta**.

**Lo que NO se puede verificar aqui, y por que.** Pulsar Aprobar reanuda el grafo
desde el checkpoint de LangGraph, y una fila sembrada a mano no tiene checkpoint:
el servidor responde **409 `NOTHING_TO_RESUME`** -y hace bien, porque aprobar sin
nada que reanudar seria una promocion sin cambio-. La reanudacion y la promocion
las cubre la suite de pytest (F12: `tests/test_f12_promocion.py`), que si puede
construir el estado interrumpido. Fingir aqui un clic que no puede funcionar
seria verificar el camino de error y llamarlo exito.

Uso: python tools/verify_puerta_aprobacion.py
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

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

from ai_swe.contracts.outputs import (  # noqa: E402
    CodeChange,
    FileChange,
    Finding,
    ReviewVerdict,
    TestRun,
)
from ai_swe.contracts.state import (  # noqa: E402
    Artifacts,
    Budget,
    Evidence,
    Instruction,
    InstructionSource,
    Outputs,
    RunOptions,
    RunState,
    RunStatus,
)
from ai_swe.contracts.tasks import RunPlan, Subtask, SubtaskStatus, TaskInterpretation  # noqa: E402
from ai_swe.state.store import RunStore  # noqa: E402

DIFF = """diff --git a/src/app.py b/src/app.py
--- a/src/app.py
+++ b/src/app.py
@@ -1,4 +1,6 @@
 def f():
-    return 1
+    valor = 1
+    return valor
+
+
"""

PROBE = r"""
var pasos = [], errores = [];
window.addEventListener('error', function (e) { errores.push('ERROR: ' + e.message); }, true);
function anota(k, v) { pasos.push(k + '=' + v); }

// **Se apagan el flujo SSE y el sondeo de la aplicacion, y se dice por que.**
// El reloj virtual de Chrome no avanza mientras hay una peticion pendiente, y el
// flujo de eventos de una ejecucion detenida es una peticion abierta para
// siempre: la pagina no terminaba nunca y el volcado del DOM salia vacio. El
// sondeo de 900 ms hace lo mismo por otra via. Las dos cosas -el flujo y el
// sondeo- las verifica la verificacion principal, donde la ejecucion termina y se
// observa que la vista avanza; aqui lo que se mira es la pantalla de la puerta,
// que es estatica. La sonda crea su propio intervalo **antes** de apagarlos.
window.EventSource = function () {
  this.close = function () {};
  this.addEventListener = function () {};
  return this;
};
var intervaloReal = window.setInterval.bind(window);
var reloj = intervaloReal(function () {
  intentos++;
  var fila = document.querySelector('#tabla-ejecuciones tbody tr');
  if (fila && !document.querySelector('#btn-aprobar')) {
    fila.click();
    return;
  }
  if (document.querySelector('#btn-aprobar') && !medido) {
    medido = true;
    anota('PUERTA_APARECIO', 'true');
    anota('TIENE_DIFF', (document.querySelector('.visor-diff') ? 'true' : 'false'));
    anota('TIENE_FICHERO', (document.querySelector('.fichero-cabecera') ? 'true' : 'false'));
    anota('PRUEBAS', (document.querySelectorAll('.pruebas li').length));
    anota('PASS', (document.querySelectorAll('.pruebas li.ok').length));
    anota('FAIL', (document.querySelectorAll('.pruebas li.error').length));
    anota('TIENE_VEREDICTO', (document.querySelector('.veredicto') ? 'true' : 'false'));
    anota('TIENE_HALLAZGOS', (document.querySelectorAll('.hallazgos li').length));
    anota('TIENE_AVISO', (document.body.textContent.indexOf('se promover') >= 0 ? 'true' : 'false'));
    anota('BOTONES', (document.querySelectorAll('.puerta-decision button').length));
    anota('APROBAR_HABILITADO', (document.querySelector('#btn-aprobar').disabled ? 'false' : 'true'));
    anota('PRESELECCION', (document.querySelectorAll('.puerta-decision input:checked').length));
    anota('DIFERENCIAS', (document.querySelectorAll('.diff .add').length + '/' + document.querySelectorAll('.diff .del').length));
    clearInterval(reloj);
    volcar();
    return;
  }
  if (intentos > 150) {
    clearInterval(reloj);
    errores.push('PROBE: la puerta de aprobacion no aparecio');
    volcar();
  }
}, 100);

// A partir de aqui, la aplicacion no arranca su sondeo.
window.setInterval = function () { return 0; };

var intentos = 0;
var medido = false;

function volcar() {
  var d = document.createElement('div');
  d.id = '_informe';
  d.textContent = 'N_ERRORS=' + errores.length + ' ||| ' + errores.join(' ||| ')
    + ' ||| ' + pasos.join(' ||| ');
  document.body.appendChild(d);
}
"""


def sembrar(estado_db: Path) -> str:
    """Deja una ejecucion detenida en la puerta de aprobacion, con evidencia."""
    ahora = datetime.now(timezone.utc)
    run_id = "run-puerta-aprobacion"
    estado = RunState(
        run_id=run_id,
        trace_id="trace-puerta-aprobacion",
        created_at=ahora,
        updated_at=ahora,
        status=RunStatus.AWAITING_APPROVAL,
        instruction=Instruction(
            text="Corrige el retorno de f() y anade una prueba",
            source=InstructionSource.TEXT,
            confirmed_by_user=True,
        ),
        options=RunOptions(repo_path=str(RAIZ)),
        interpretation=TaskInterpretation(
            intent="modify",
            scope={
                "repo_path": str(RAIZ),
                "allowed_paths": ["src/"],
                "protected_paths": ["migrations/"],
                "max_files_changed": 5,
                "max_lines_changed": 200,
            },
            confidence=0.88,
            rationale="La peticion pide cambiar una funcion y anadir cobertura.",
            constraints=["no toques las migraciones"],
        ),
        plan=RunPlan(
            subtasks=[
                Subtask(
                    id="s1",
                    description="Localizar la funcion",
                    agent="researcher",
                    allowed_tools=["read_file"],
                    status=SubtaskStatus.COMPLETED,
                    done_criteria="la funcion esta localizada",
                ),
                Subtask(
                    id="s2",
                    description="Aplicar el cambio",
                    agent="coder",
                    allowed_tools=["read_file", "apply_patch"],
                    status=SubtaskStatus.COMPLETED,
                    done_criteria="el diff aplica limpio",
                ),
            ],
            rationale="Primero se localiza y despues se cambia.",
        ),
        artifacts=Artifacts(
            diff=DIFF,
            changed_files=[
                FileChange(
                    path="src/app.py",
                    added=3,
                    removed=1,
                    sha256="a" * 64,
                )
            ],
            base_commit="b" * 40,
            worktree_path=str(RAIZ / "data" / "workspaces" / run_id),
        ),
        outputs=Outputs(
            coder_output=CodeChange(
                rationale="Se asigna el valor a una variable antes de devolverlo.",
                diff=DIFF,
                diff_sha256="c" * 64,
                files_changed=[FileChange(path="src/app.py", added=3, removed=1, sha256="a" * 64)],
            ),
            reviewer_output=ReviewVerdict(
                decision="request_changes",
                summary="El cambio es correcto pero falta cubrir el caso vacio.",
                findings=[
                    Finding(
                        severity="medium",
                        path="src/app.py",
                        line=2,
                        explanation="No hay prueba para el caso vacio.",
                        evidence="tests/test_app.py no menciona el caso vacio",
                    )
                ],
                required_fixes=["anade una prueba del caso vacio"],
            ),
        ),
        evidence=Evidence(
            test_runs=[
                TestRun(
                    target="unit",
                    exit_code=0,
                    stdout="1 passed",
                    stderr="",
                    duration_s=1.25,
                    argv=["python", "-m", "pytest", "-q"],
                ),
                TestRun(
                    target="lint",
                    exit_code=1,
                    stdout="",
                    stderr="E501 line too long",
                    duration_s=0.4,
                    argv=["ruff", "check", "."],
                ),
            ],
            findings=[],
        ),
        budget=Budget(
            used_tokens=1200,
            used_input_tokens=800,
            used_output_tokens=400,
            used_model_calls=3,
            used_tool_calls=2,
            elapsed_seconds=12.5,
        ),
    )
    with RunStore(estado_db) as almacen:
        almacen.create(estado)
    return run_id


def main() -> int:
    navegador = encontrar_navegador()
    if navegador is None:
        print("VERIFICACION OMITIDA: no se encontro Chromium")
        return 0

    _reconstruir()
    carpeta = Path(tempfile.mkdtemp(prefix="aiswe-puerta-"))
    estado_db = carpeta / "estado.sqlite3"
    run_id = sembrar(estado_db)

    html = (DIST / "index.html").read_text(encoding="utf-8")
    (DIST / "_puerta.js").write_text(PROBE, encoding="utf-8")
    (DIST / "_puerta.html").write_text(
        html.replace(
            '<script type="module"',
            '<script src="_puerta.js"></script>\n    <script type="module"',
            1,
        ),
        encoding="utf-8",
    )

    puerto = puerto_libre()
    base = f"http://127.0.0.1:{puerto}"
    entorno = {**os.environ, "PYTHONPATH": "src", "AI_SWE_STATE_DB_PATH": str(estado_db)}
    servidor = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "ai_swe.api.app:crear_app", "--factory",
         "--host", "127.0.0.1", "--port", str(puerto), "--log-level", "warning"],
        cwd=RAIZ, env=entorno, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        if not esperar_servidor(f"{base}/health"):
            print("FALLO: el servidor no arranco")
            return 1
        dom, _ = _lanzar_navegador(
            [str(navegador), "--headless", "--disable-gpu", "--no-sandbox", "--dump-dom",
             "--hide-scrollbars", "--window-size=1600,1000", "--virtual-time-budget=40000",
             f"--user-data-dir={tempfile.mkdtemp(prefix='aiswe-chrome-')}",
             f"{base}/app/_puerta.html"],
            limite=120,
        )
        # Se lee **por la API**, con el servidor todavia en pie: abrir el SQLite en
        # paralelo da un bloqueo de fichero, y ademas esto comprueba el camino real.
        with urllib.request.urlopen(f"{base}/runs/{run_id}", timeout=10) as respuesta:
            estado = json.loads(respuesta.read())
    finally:
        servidor.terminate()
        try:
            servidor.wait(timeout=10)
        except subprocess.TimeoutExpired:
            servidor.kill()

    coincidencia = re.search(r'<div id="_informe">(.*?)</div>', dom, re.S)
    if not coincidencia:
        print("FALLO: la pagina no emitio informe")
        print(dom[-1500:] if dom else "(sin DOM)")
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
        elif parte.startswith(("ERROR:", "PROBE")):
            errores.append(parte)

    # Y lo que de verdad importa: que mirar la pantalla no haya decidido nada.
    fallos: list[str] = []

    def comprobar(nombre: str, condicion: bool, detalle: str = "") -> None:
        print(f"  {'OK   ' if condicion else 'FALLO'} {nombre}{('  (' + detalle + ')') if detalle else ''}")
        if not condicion:
            fallos.append(nombre)

    print("\n== informe del navegador ==")
    for clave, valor in campos.items():
        print(f"  {clave:22s} {valor}")

    print("\n== comprobaciones ==")
    comprobar("la aplicacion monto sin errores", not errores, "; ".join(errores[:2]))
    comprobar("la puerta de aprobacion aparecio", campos.get("PUERTA_APARECIO") == "true")
    comprobar("la puerta ensena el diff", campos.get("TIENE_DIFF") == "true")
    comprobar("el diff viene con la cabecera del fichero", campos.get("TIENE_FICHERO") == "true")
    comprobar(
        "el diff se pinta con sus lineas anadidas y borradas",
        campos.get("DIFERENCIAS") not in (None, "0/0"),
        f"anadidas/borradas={campos.get('DIFERENCIAS')}",
    )
    comprobar(
        "la puerta ensena las dos ejecuciones de pruebas",
        campos.get("PRUEBAS") == "2",
        f"PRUEBAS={campos.get('PRUEBAS')}",
    )
    comprobar(
        "el veredicto de las pruebas se deriva del exit_code (una pasa, una falla)",
        campos.get("PASS") == "1" and campos.get("FAIL") == "1",
        f"PASS={campos.get('PASS')} FAIL={campos.get('FAIL')}",
    )
    comprobar("la puerta ensena el veredicto del revisor", campos.get("TIENE_VEREDICTO") == "true")
    comprobar(
        "la puerta ensena los hallazgos",
        int(campos.get("TIENE_HALLAZGOS", "0") or 0) >= 1,
        f"TIENE_HALLAZGOS={campos.get('TIENE_HALLAZGOS')}",
    )
    comprobar("el aviso de consecuencia esta en pantalla", campos.get("TIENE_AVISO") == "true")
    comprobar(
        "estan las tres decisiones",
        campos.get("BOTONES") == "3",
        f"BOTONES={campos.get('BOTONES')}",
    )
    comprobar("el boton de aprobar estaba habilitado", campos.get("APROBAR_HABILITADO") == "true")
    comprobar(
        "ninguna decision viene preseleccionada",
        campos.get("PRESELECCION") == "0",
        f"PRESELECCION={campos.get('PRESELECCION')}",
    )
    # Lo mas importante de esta verificacion: mirar la pantalla no decide nada.
    comprobar(
        "la pantalla no registro ninguna decision por si sola",
        len(estado.get("approvals", [])) == 0 and estado.get("status") == "awaiting_approval",
        f"aprobaciones={len(estado.get('approvals', []))} estado={estado.get('status')}",
    )

    if fallos:
        print(f"\nRESULTADO: {len(fallos)} comprobacion(es) fallidas -> {fallos}")
        return 1
    print("\nRESULTADO: la puerta de aprobacion funciona en un motor real.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

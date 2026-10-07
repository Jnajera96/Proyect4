"""Verifica las suposiciones de las que depende la fase M1.

Toda la arquitectura descansa en cuatro supuestos:

  A1. Un grafo con estado tipado se puede compilar y ejecutar.
  A2. El grafo se **pausa** en un punto y persiste su estado en disco.
  A3. Ese estado se puede **reanudar desde otro proceso**, sin repetir el trabajo
      ya confirmado. Es el supuesto critico: sostiene DEC-01, RF-11, RF-12,
      RNF-D1 y RNF-E1 a la vez.
  A4. Una ejecucion alcanza un estado terminal explicito (RNF-D4, MET-13 = 0).

Por que esto y no escribir directamente la fase M1: si A3 no se cumple, el
diseno cambia a nivel de DEC-01, no de codigo. Es mas barato descubrirlo con un
guion que despues de construir los agentes encima.

El guion se ejecuta a si mismo en **dos procesos separados** que comparten el
mismo fichero SQLite. Que sean procesos distintos es el punto: una reanudacion
dentro del mismo proceso no demuestra nada sobre RNF-D1.

Y el guion se verifica a si mismo: `--self-check` introduce cada forma conocida de
romper la persistencia y comprueba que la verificacion lo detecta.

Uso:
    python tools/verify_m1_assumptions.py
    python tools/verify_m1_assumptions.py --self-check
"""

from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import TypedDict

HILO = "verificacion-m1"

# Mutaciones: cada una rompe la persistencia de una forma distinta y concreta.
MUTACIONES: dict[str, str] = {
    "checkpointer en memoria": "memory_saver",
    "sin checkpointer": "no_checkpointer",
    "hilo distinto al reanudar": "wrong_thread",
}


# --------------------------------------------------------------- utilidades


def _registrar(ruta: Path, entrada: str) -> None:
    """Registra la ejecucion de un nodo en un fichero aparte del estado.

    Se usa un fichero lateral a proposito: el estado del grafo se reemplaza,
    pero el registro de ejecuciones se acumula. Asi se puede contar cuantas
    veces corrio realmente cada nodo, que es lo que prueba A3.
    """
    with ruta.open("a", encoding="utf-8") as fh:
        fh.write(entrada + "\n")


def _leer_registro(ruta: Path) -> list[str]:
    if not ruta.exists():
        return []
    return [linea for linea in ruta.read_text(encoding="utf-8").splitlines() if linea]


# ------------------------------------------------------------------- grafo


class EstadoDemo(TypedDict):
    historial: list[str]
    decision: str | None


def _compilar(db: Path, mutacion: str | None):
    """Compila el grafo y devuelve tambien la conexion, para poder cerrarla.

    Cerrar importa: en Windows un fichero SQLite con el descriptor abierto no se
    puede borrar, y `TemporaryDirectory` falla al limpiar con WinError 32.
    """
    from langgraph.graph import END, START, StateGraph
    from langgraph.types import interrupt

    registro = db.with_suffix(".log")

    def nodo_uno(state: EstadoDemo) -> dict:
        # Efecto lateral observable: si este nodo se reejecutara al reanudar,
        # apareceria dos veces en el registro.
        _registrar(registro, "nodo_uno")
        # `state.get` y no `state[...]`: al reanudar sobre un hilo SIN punto de
        # control, LangGraph entrega un estado vacio y el acceso directo lanza
        # KeyError dentro del nodo. Hallazgo de esta verificacion: la fase M1
        # debe comprobar que existe punto de control antes de reanudar, y
        # devolver un error tipado en lugar de fallar dentro de un nodo.
        return {"historial": list(state.get("historial", [])) + ["nodo_uno"]}

    def nodo_dos(state: EstadoDemo) -> dict:
        respuesta = interrupt({"pregunta": "¿promover los cambios al repositorio?"})
        _registrar(registro, f"nodo_dos:{respuesta}")
        return {
            "historial": list(state.get("historial", [])) + [f"nodo_dos:{respuesta}"],
            "decision": str(respuesta),
        }

    grafo = StateGraph(EstadoDemo)
    grafo.add_node("nodo_uno", nodo_uno)
    grafo.add_node("nodo_dos", nodo_dos)
    grafo.add_edge(START, "nodo_uno")
    grafo.add_edge("nodo_uno", "nodo_dos")
    grafo.add_edge("nodo_dos", END)

    mut = mutacion or ""
    if mut == "no_checkpointer":
        return grafo.compile(), None

    if mut == "memory_saver":
        try:
            from langgraph.checkpoint.memory import InMemorySaver as EnMemoria
        except ImportError:  # nombre anterior
            from langgraph.checkpoint.memory import MemorySaver as EnMemoria
        return grafo.compile(checkpointer=EnMemoria()), None

    from langgraph.checkpoint.sqlite import SqliteSaver

    conexion = sqlite3.connect(str(db), check_same_thread=False)
    return grafo.compile(checkpointer=SqliteSaver(conexion)), conexion


def _config(mutacion: str | None, fase: str = "a") -> dict:
    """Configuracion del hilo.

    La mutacion `wrong_thread` es **asimetrica** a proposito: la fase A escribe en
    el hilo correcto y la fase B reanuda en otro. Si se aplicara el mismo hilo
    cambiado a las dos fases, seguirian siendo coherentes entre si y la mutacion
    no romperia nada — que es exactamente el error que cometio la primera version
    de esta prueba.
    """
    hilo = HILO
    if mutacion == "wrong_thread" and fase == "b":
        hilo = "otro-hilo"
    return {"configurable": {"thread_id": hilo}}


def fase_a(db: Path, mutacion: str | None = None) -> dict:
    """Primer proceso: ejecuta hasta la pausa y termina el proceso."""
    app, conexion = _compilar(db, mutacion)
    try:
        resultado = app.invoke({"historial": [], "decision": None}, _config(mutacion, "a"))
    finally:
        if conexion is not None:
            conexion.close()
    interrupciones = resultado.get("__interrupt__") or []
    return {
        "historial": list(resultado.get("historial", [])),
        "pausado": bool(interrupciones),
        "pregunta": interrupciones[0].value.get("pregunta") if interrupciones else None,
    }


def fase_b(db: Path, mutacion: str | None = None) -> dict:
    """Segundo proceso, independiente: reanuda desde el punto de pausa."""
    from langgraph.types import Command

    app, conexion = _compilar(db, mutacion)
    try:
        resultado = app.invoke(Command(resume="aprobado"), _config(mutacion, "b"))
    finally:
        if conexion is not None:
            conexion.close()
    return {
        "historial": list(resultado.get("historial", [])),
        "decision": resultado.get("decision"),
        "sigue_pausado": bool(resultado.get("__interrupt__")),
    }


# ---------------------------------------------------------------- evaluacion


def _ejecutar_fase(fase: str, db: Path, mutacion: str | None) -> dict:
    orden = [sys.executable, __file__, "--fase", fase, "--db", str(db)]
    if mutacion:
        orden += ["--mutacion", mutacion]
    proceso = subprocess.run(orden, capture_output=True, text=True)
    if proceso.returncode != 0:
        detalle = (proceso.stderr.strip() or proceso.stdout.strip())[-600:]
        raise RuntimeError(f"la fase {fase} fallo: {detalle}")
    lineas = [l for l in proceso.stdout.splitlines() if l.startswith("{")]
    if not lineas:
        raise RuntimeError(f"la fase {fase} no devolvio resultado")
    return json.loads(lineas[-1])


def evaluar(mutacion: str | None = None) -> dict:
    """Ejecuta las dos fases y devuelve el veredicto de cada supuesto."""
    with tempfile.TemporaryDirectory(prefix="aiswe-m1-") as tmp:
        db = Path(tmp) / "estado.sqlite3"
        a = _ejecutar_fase("a", db, mutacion)
        b = _ejecutar_fase("b", db, mutacion)
        ejecuciones = _leer_registro(db.with_suffix(".log"))

    supuestos = {
        "A1 grafo con estado tipado": a["historial"] == ["nodo_uno"],
        "A2 pausa con estado persistido": bool(a["pausado"]) and a["pregunta"] is not None,
        "A3 reanudacion desde otro proceso": b["historial"] == ["nodo_uno", "nodo_dos:aprobado"],
        "A3 el trabajo confirmado no se repite": ejecuciones.count("nodo_uno") == 1,
        "A4 estado terminal explicito": not b["sigue_pausado"],
    }
    return {"supuestos": supuestos, "ok": all(supuestos.values()), "a": a, "b": b,
            "ejecuciones": ejecuciones}


# ------------------------------------------------------------------- salida


def _linea_base() -> int:
    print("== linea base ==")
    try:
        r = evaluar()
    except RuntimeError as exc:
        print(f"ABORTADO: {exc}")
        return 1

    print(f"  historial tras la pausa : {r['a']['historial']}")
    print(f"  pregunta de la pausa    : {r['a']['pregunta']!r}")
    print(f"  historial tras reanudar : {r['b']['historial']}")
    print(f"  registro de ejecuciones : {r['ejecuciones']}")
    print()
    for nombre, cumple in r["supuestos"].items():
        print(f"  {'OK ' if cumple else 'FALLO'}  {nombre}")

    if not r["ok"]:
        print("\nRESULTADO: la linea base falla. M1 NO es viable tal como esta disenada.")
        print("Hay que revisar DEC-01 antes de escribir la fase M1.")
        return 1

    print("\nRESULTADO: los 5 supuestos se cumplen. M1 es viable.")
    print("El diseno puede apoyarse en pausa y reanudacion reales entre procesos.")
    return 0


def _auto_verificacion() -> int:
    print("\n== auto-verificacion: cada forma de romper la persistencia debe ser cazada ==")
    cazadas = 0
    for descripcion, mutacion in MUTACIONES.items():
        try:
            r = evaluar(mutacion)
            cazada = not r["ok"]
            detalle = "alguna comprobacion fallo" if cazada else "paso como si nada"
        except RuntimeError as exc:
            cazada = True
            detalle = str(exc)[:90]
        cazadas += int(cazada)
        marca = "cazada" if cazada else "NO CAZADA <<< PUNTO CIEGO"
        print(f"  {descripcion:30s} -> {marca}  ({detalle})")

    print(f"\n{cazadas}/{len(MUTACIONES)} mutaciones cazadas")
    return 0 if cazadas == len(MUTACIONES) else 1


def main() -> int:
    import importlib.metadata as md

    print("== entorno ==")
    for paquete in ("langgraph", "langgraph-checkpoint-sqlite"):
        try:
            print(f"  {paquete:30s} {md.version(paquete)}")
        except Exception:
            print(f"  {paquete:30s} NO INSTALADO")
            return 1
    print()

    codigo = _linea_base()
    if codigo != 0:
        return codigo

    codigo_mutaciones = _auto_verificacion()
    if codigo_mutaciones != 0:
        print("\nLa verificacion NO es fiable: no detecta todas las formas de romper la persistencia.")
        return codigo_mutaciones

    print("\nLa verificacion es fiable: detecta todas las formas de romper la persistencia.")
    return 0


if __name__ == "__main__":
    if "--fase" in sys.argv:
        fase = sys.argv[sys.argv.index("--fase") + 1]
        ruta_db = Path(sys.argv[sys.argv.index("--db") + 1])
        mut = sys.argv[sys.argv.index("--mutacion") + 1] if "--mutacion" in sys.argv else None
        salida = fase_a(ruta_db, mut) if fase == "a" else fase_b(ruta_db, mut)
        print(json.dumps(salida, ensure_ascii=False))
        raise SystemExit(0)

    if "--self-check" in sys.argv:
        raise SystemExit(_auto_verificacion())
    raise SystemExit(main())

"""Verifica que la suite de redaccion realmente protege el redactor.

Metodo: por cada mutacion se introduce el fallo en el codigo de produccion, se
ejecuta la suite, se restaura el fichero y se informa si **alguna** prueba fallo.
Una mutacion que no hace fallar nada senala una prueba ausente o inutil.

Regla de oro, aprendida a golpes: si la linea base no esta verde, el resultado de
las mutaciones no significa nada. Este guion aborta si la suite ya falla antes de
empezar, en lugar de informar de "mutaciones cazadas" sobre un arbol roto.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
OBJETIVO = RAIZ / "src" / "ai_swe" / "security" / "redaction.py"
COPIA = RAIZ / ".redaction_mutation_backup.py"
PYTHON = sys.executable

MUTACIONES: list[tuple[str, str, str]] = [
    # (nombre, texto_original, texto_mutado)
    (
        "el registro de secretos deja de aplicarse",
        "    for secreto in conocidos:\n        if secreto in salida:\n            salida = salida.replace(secreto, REDACTADO)",
        "    for secreto in conocidos:\n        pass",
    ),
    (
        "los patrones con prefijo no se aplican",
        "    for patron in _PATRONES_PREFIJO:\n        salida = patron.sub(REDACTADO, salida)",
        "    pass",
    ),
    (
        "la cabecera de autorizacion no se redacta",
        '    salida = _PATRON_AUTORIZACION.sub(\n        lambda m: f"{m.group(1)}{m.group(2)}{m.group(3) or \'\'}{REDACTADO}", salida\n    )',
        "    pass",
    ),
    (
        "los pares clave=valor no se redactan",
        "            or _nombre_delegado(m.group(1))\n            or m.group(3).strip(\"\\\"'\") == REDACTADO\n            or m.group(3).strip(\"\\\"'\").lower() in _ESQUEMAS_AUTORIZACION\n            else f\"{m.group(1)}{m.group(2)}{REDACTADO}\"",
        "            else m.group(0)",
    ),
    (
        "las claves de dict dejan de redactarse",
        "            if isinstance(clave, str) and _clave_sensible(clave):\n                salida[clave] = REDACTADO\n            else:\n                salida[clave] = redact_deep(valor, _profundidad=_profundidad + 1)",
        "            salida[clave] = redact_deep(valor, _profundidad=_profundidad + 1)",
    ),
    (
        "_nombre_es_sensible siempre dice que no",
        "    normalizado = (\n        nombre.strip().strip(\"\\\"'\").lower().replace(\"-\", \"_\").replace(\".\", \"_\")\n    )",
        "    return False\n    normalizado = (\n        nombre.strip().strip(\"\\\"'\").lower().replace(\"-\", \"_\").replace(\".\", \"_\")\n    )",
    ),
    (
        "URL con credenciales no se redacta",
        '    salida = _PATRON_URL_CON_CREDENCIALES.sub(lambda m: f"{m.group(1)}{REDACTADO}@", salida)',
        "    pass",
    ),
    (
        "redact_deep deja de bajar a las listas",
        "        redactados = [redact_deep(v, _profundidad=_profundidad + 1) for v in objeto]",
        "        redactados = list(objeto)",
    ),
]


def _ejecutar_suite() -> bool:
    """Devuelve True si la suite pasa."""
    resultado = subprocess.run(
        [PYTHON, "-m", "pytest", "tests/test_redaction.py", "-q", "--no-header", "-p", "no:cacheprovider"],
        cwd=RAIZ,
        capture_output=True,
        text=True,
        env={**__import__("os").environ, "PYTHONPATH": "src"},
    )
    return resultado.returncode == 0


def main() -> int:
    if not OBJETIVO.exists():
        print(f"no existe el objetivo: {OBJETIVO}")
        return 2

    # Si quedo una copia de una ejecucion interrumpida, se restaura: una mutacion
    # que sobreviva a la muerte del proceso mediria un arbol corrupto.
    if COPIA.exists():
        shutil.copy2(COPIA, OBJETIVO)
        COPIA.unlink()
        print("restaurada una copia huerfana de una ejecucion anterior")

    original = OBJETIVO.read_text(encoding="utf-8")
    shutil.copy2(OBJETIVO, COPIA)

    print("=== verificando linea base ===")
    if not _ejecutar_suite():
        print("LINEA BASE EN ROJO: las mutaciones no significarian nada. Se aborta.")
        OBJETIVO.write_text(original, encoding="utf-8")
        COPIA.unlink(missing_ok=True)
        return 1
    print("linea base verde\n")

    cazadas = 0
    for nombre, viejo, nuevo in MUTACIONES:
        if viejo not in original:
            print(f"[?] NO APLICABLE: {nombre} (el texto original no coincide)")
            continue
        # Se restaura desde `original` (memoria) y no desde el disco: asi una
        # mutacion no puede encadenarse con la siguiente.
        OBJETIVO.write_text(original.replace(viejo, nuevo, 1), encoding="utf-8")
        cayo = not _ejecutar_suite()
        OBJETIVO.write_text(original, encoding="utf-8")
        if cayo:
            cazadas += 1
            print(f"[OK] cazada: {nombre}")
        else:
            print(f"[!!] NO CAZADA: {nombre}")

    OBJETIVO.write_text(original, encoding="utf-8")
    COPIA.unlink(missing_ok=True)
    print(f"\n{cazadas}/{len(MUTACIONES)} mutaciones cazadas")
    return 0 if cazadas == len(MUTACIONES) else 1


if __name__ == "__main__":
    raise SystemExit(main())

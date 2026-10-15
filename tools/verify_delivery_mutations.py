"""Solo mutaciones semanticas de entrega; no ejecuta la suite integral.

Cada mutacion debe compilar y fallar en el verificador indicado. Un fallo de
build o timeout es NO CONCLUYENTE. Restaura bytes y reconstruye dist al terminar.
Uso: .venv/Scripts/python.exe tools/verify_delivery_mutations.py
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
FRONTEND = RAIZ / "frontend"
SALIDA = RAIZ / "_tmp" / f"delivery-mutations-{int(time.time())}"
JOURNAL = SALIDA / "journal.json"

MUTACIONES = [
    ("scope omitido", "frontend/src/lib/api.ts",
     'allowed_paths: [...new Set(alcance.allowed_paths.map(p => p.trim()).filter(Boolean))],',
     'allowed_paths: [],', "browser"),
    ("error de promocion ignorado", "frontend/src/components/DiagramaFlujo.tsx",
     'const falloPromocion = estado.errors.some((e) => e.error_class.startsWith("PROMOTION_"));',
     'const falloPromocion = false;', "browser"),
    ("voz evita tratamiento central", "frontend/src/components/PanelVoz.tsx",
     'const detalle = alFallo(causa);',
     'const detalle = causa instanceof Error ? causa.message : alFallo(causa);', "browser"),
    ("SSE sin credencial valida", "frontend/src/hooks/useEventosRun.ts",
     'if (clave) parametros.set("api_key", clave);',
     'if (clave) parametros.set("api_key", "incorrecta-sintetica");', "browser"),
    ("primera decision historica", "frontend/src/components/DiagramaFlujo.tsx",
     '[...aprobaciones].reverse().find((a) => a.action === "promote_changes")',
     'aprobaciones.find((a) => a.action === "promote_changes")', "component"),
    ("subtarea activa durante espera", "frontend/src/components/evidencia.tsx",
     'status === "running" && i === indice',
     'status !== "planned" && i === indice', "component"),
]
if len(sys.argv) > 1:
    MUTACIONES = [m for m in MUTACIONES if sys.argv[1] in m[0]]
    if not MUTACIONES:
        raise SystemExit("Ninguna mutacion coincide con el filtro")


def ejecutar(orden, cwd=RAIZ, timeout=180):
    try:
        r = subprocess.run(orden, cwd=cwd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout,
                           env={**os.environ, "AI_SWE_TEST_NO_SCREENSHOTS": "1"})
        return r.returncode, r.stdout + r.stderr
    except subprocess.TimeoutExpired:
        return None, "TIMEOUT: no cuenta como mutacion cazada"


def build():
    orden = ["cmd", "/c", "npm", "run", "build"] if os.name == "nt" else ["npm", "run", "build"]
    return ejecutar(orden, FRONTEND)


def verificar(tipo):
    if tipo == "browser":
        return ejecutar(["node", "tools/verify_delivery.cjs", str(SALIDA / "browser")])
    return ejecutar(["node", "--test", "tests/estados.test.mjs"], FRONTEND)


def main():
    SALIDA.mkdir(parents=True)
    resultados = []
    originales = {RAIZ / ruta: (RAIZ / ruta).read_bytes() for _, ruta, *_ in MUTACIONES}
    try:
        codigo, salida = build()
        if codigo != 0:
            raise RuntimeError("La linea base no compila: " + salida[-1000:])
        for tipo in ("component", "browser"):
            codigo, salida = verificar(tipo)
            if codigo != 0:
                raise RuntimeError(f"Linea base {tipo} no verde: " + salida[-1000:])
        print("Linea base: build + componentes + navegador verdes", flush=True)
        for nombre, relativa, antes, despues, tipo in MUTACIONES:
            ruta = RAIZ / relativa
            original = originales[ruta]
            texto = original.decode("utf-8")
            if texto.count(antes) != 1:
                raise RuntimeError(f"Patron ambiguo o ausente: {nombre}")
            mutado = texto.replace(antes, despues).encode("utf-8")
            JOURNAL.write_text(json.dumps({"file": relativa,
                "original_base64": base64.b64encode(original).decode("ascii")}), encoding="utf-8")
            ruta.write_bytes(mutado)
            try:
                codigo, salida = build()
                if codigo != 0:
                    raise RuntimeError(f"NO CONCLUYENTE: {nombre} no compila: " + salida[-800:])
                codigo, salida = verificar(tipo)
                marcador = "FALLO:" in salida if tipo == "browser" else "AssertionError" in salida
                cazada = codigo is not None and codigo != 0 and marcador
                resultados.append({"name": nombre, "type": tipo, "caught": cazada})
                (SALIDA / f"mutation-{len(resultados)}.log").write_text(salida, encoding="utf-8")
                print(f"{'CAZADA' if cazada else 'NO CAZADA/NO CONCLUYENTE'}: {nombre}", flush=True)
            finally:
                if ruta.read_bytes() not in (mutado, original):
                    raise RuntimeError(
                        f"Cambio externo en {relativa}: se conserva; backup en {JOURNAL}"
                    )
                ruta.write_bytes(original)
                JOURNAL.write_text("{}", encoding="utf-8")
    finally:
        restaurado = all(p.read_bytes() == b for p, b in originales.items())
        codigo, salida = build()
        informe = {"mutations": resultados, "source_restored": restaurado,
                   "final_build": codigo == 0,
                   "sha256": {str(p.relative_to(RAIZ)): hashlib.sha256(b).hexdigest()
                              for p, b in originales.items()}}
        (SALIDA / "report.json").write_text(json.dumps(informe, indent=2), encoding="utf-8")
        print(f"Restauracion byte a byte: {restaurado}; build final: {codigo == 0}", flush=True)
    codigo, salida = verificar("component")
    if codigo != 0:
        raise RuntimeError("Componentes no verdes tras restaurar: " + salida[-1000:])
    print(f"RESULTADO: {sum(r['caught'] for r in resultados)}/{len(MUTACIONES)}; {SALIDA}")
    completo = len(resultados) == len(MUTACIONES) and all(r["caught"] for r in resultados)
    return 0 if restaurado and informe["final_build"] and completo else 1


if __name__ == "__main__":
    raise SystemExit(main())

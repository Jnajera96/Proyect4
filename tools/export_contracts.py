"""Exporta los contratos a JSON Schema para el frontend.

Problema que resuelve: el frontend no comparte el sistema de tipos del backend.
Sin un artefacto comun, los dos lados se desincronizan y los fallos aparecen en
tiempo de ejecucion, en el navegador, con un `undefined` en algun sitio.

Aqui hay **una sola fuente de verdad**: los modelos Pydantic. El frontend consume
`frontend/contracts.json`, y una prueba comprueba que el fichero esta al dia, de
modo que no puede quedarse obsoleto en silencio.

Uso:
    python tools/export_contracts.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
SALIDA = RAIZ / "frontend" / "contracts.json"

# Contratos que el navegador necesita conocer. Se listan a mano a proposito: son
# la **superficie publica** del backend, no todos los tipos internos. Exportar
# todo invitaria al frontend a depender de detalles que no son suyos.
CONTRATOS_PUBLICOS = (
    "Project",
    "ProjectRequest",
    "RunEvent",
    "RunSummary",
    "RunState",
    "RunStatus",
    "EventKind",
    "RunOptions",
    "InstructionSource",
    "TranscriptMeta",
    "ApprovalDecision",
    "FinalReport",
    "RunError",
    "Intent",
)

NOTA = (
    "GENERADO AUTOMATICAMENTE por tools/export_contracts.py. No editar a mano. "
    "Para regenerar: python tools/export_contracts.py"
)


def construir() -> dict:
    from enum import Enum

    import ai_swe.contracts as contratos
    from ai_swe.api import ApproveRequest, RunRequest
    from ai_swe.stt import Transcript

    esquemas: dict[str, dict] = {}

    def exportar(nombre: str, modelo) -> None:
        """Los modelos dan JSON Schema; las enumeraciones, su lista de valores.

        Las enumeraciones son `StrEnum`, no modelos Pydantic, y no tienen
        `model_json_schema`. Exportarlas como `{"enum": [...]}` es justo lo que el
        frontend necesita: el conjunto cerrado de valores validos.
        """
        if isinstance(modelo, type) and issubclass(modelo, Enum):
            esquemas[nombre] = {
                "title": nombre,
                "type": "string",
                "enum": [miembro.value for miembro in modelo],
            }
        else:
            esquemas[nombre] = modelo.model_json_schema()

    for nombre in CONTRATOS_PUBLICOS:
        exportar(nombre, getattr(contratos, nombre))

    # Los modelos de peticion viven en la capa HTTP, pero el frontend tambien los
    # necesita para construir el cuerpo de la peticion.
    for modelo in (RunRequest, ApproveRequest, Transcript):
        exportar(modelo.__name__, modelo)

    return {
        "nota": NOTA,
        "esquema_estado": contratos.RunState.model_fields["schema_version"].default,
        "endpoints": {
            "DELETE /projects/{project_id}": {
                "codigo": 204,
                "nota": (
                    "Solo quita el registro del perfil; conserva archivos e historial. "
                    "Requiere administrador."
                ),
            },
            "POST /projects": {
                "cuerpo": "ProjectRequest", "respuesta": "Project", "codigo": 201,
                "nota": "create_if_missing autoriza crear un nuevo repositorio local vacío.",
            },
            "GET /health": {
                "codigo": 200,
                "respuesta": "Health",
                "nota": (
                    "Incluye provider_configuration sin secretos: presencia no acredita "
                    "credencial ni inferencia."
                ),
            },
            "POST /runs": {
                "cuerpo": "RunRequest",
                "respuesta": "RunState",
                "codigo": 202,
                "nota": (
                    "Responde antes de ejecutar. El run_id llega de inmediato. Devuelve 503 "
                    "sin crear run si los roles remotos estan habilitados y falta configuracion."
                ),
            },
            "GET /runs/{run_id}": {"respuesta": "RunState", "codigo": 200},
            "GET /runs": {"respuesta": "RunSummary[]", "codigo": 200},
            "GET /runs/{run_id}/events": {
                "respuesta": "text/event-stream",
                "nota": (
                    "Cada evento lleva id, event y data. data es un RunEvent. "
                    "Reanudable con la cabecera Last-Event-ID."
                ),
            },
            "POST /runs/{run_id}/approve": {
                "cuerpo": "ApproveRequest",
                "respuesta": "RunState",
                "codigo": 200,
            },
            "POST /transcriptions": {
                "respuesta": "Transcript",
                "nota": "multipart/form-data con el campo 'audio'. NO crea ejecucion.",
            },
        },
        "schemas": esquemas,
    }


def main() -> int:
    datos = construir()
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA.write_text(
        json.dumps(datos, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    total = sum(1 for _ in datos["schemas"])
    print(f"exportados {total} contratos a {SALIDA.relative_to(RAIZ)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

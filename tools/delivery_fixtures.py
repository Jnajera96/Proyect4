"""Escenarios aislados para verificar presentacion; nunca usa var/state.sqlite3.

Las filas sembradas no tienen checkpoint de LangGraph. Sirven para inspeccionar
evidencia y estados, no para afirmar que un clic sobre ellas promueve cambios.
"""
import sys
from datetime import UTC, datetime
from pathlib import Path

from verify_puerta_aprobacion import sembrar

from ai_swe.contracts import Approval, RunError, RunState, RunStatus
from ai_swe.state import RunStore


def preparar(ruta: Path):
    run_id = sembrar(ruta)
    with RunStore(ruta) as store:
        base = store.initial_state(run_id)
        aprobado = Approval(
            action="promote_changes", actor="verificacion", decided_at=datetime.now(UTC),
            content_sha256="a" * 64, decision="approved", reason="escenario sintetico"
        )
        datos = base.model_dump()
        datos.update(
            run_id="run-fallo-promocion", status=RunStatus.NEEDS_HUMAN, next_step=None,
            approvals=[aprobado], errors=[RunError(
                error_class="PROMOTION_FAILED", agent="supervisor",
                message="Fallo controlado de verificacion; no se aplico el cambio.",
                recoverable=False, occurred_at=datetime.now(UTC)
            )]
        )
        store.create(RunState.model_validate(datos))


if __name__ == "__main__":
    preparar(Path(sys.argv[1]))

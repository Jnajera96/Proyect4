"""Pruebas de F6: el Coder real (CodeProposal -> CodeChange derivado).

**Que protege este fichero.** Que el modelo proponga archivos y contenido, y que
el **sistema** derive de forma determinista el diff, el conteo de lineas y los
`sha256` -el modelo no puede inventar un hash de un fichero que aun no escribio-.
Que el Coder consuma presupuesto, respete los limites del `Scope`, y que **sin
modelo siga devolviendo un cambio vacio controlado** en vez de uno inventado.

Ninguna prueba toca la red ni exige credenciales. El modelo se sustituye por
`FakeModelAdapter`.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

import pytest

from ai_swe.contracts import (
    Budget,
    CodeProposal,
    FileOperation,
    FileProposal,
    Instruction,
    InstructionSource,
    Intent,
    RunError,
    RunOptions,
    RunPlan,
    RunState,
    Scope,
    Subtask,
    TaskInterpretation,
)
from ai_swe.graph import nodes
from ai_swe.models import FakeModelAdapter, ModelGateway

# --------------------------------------------------------------- utilidades

CONTENIDO = "def f():\n    return 1\n"


def _propuesta(**cambios) -> dict:
    """El `CodeProposal` que un modelo bien portado devolveria."""
    base = {
        "files": [
            {
                "path": "src/parser.py",
                "operation": "modify",
                "new_content": CONTENIDO,
                "rationale": "corrige el parseo",
            }
        ],
        "rationale": "corrijo el parser segun la evidencia",
    }
    base.update(cambios)
    return base


def _estado(
    *,
    scope: Scope | None = None,
    con_plan: bool = True,
    repositorio: str = "/repo/autorizado",
) -> RunState:
    ahora = datetime.now(UTC)
    alcance = scope or Scope(repo_path=repositorio)
    plan = None
    if con_plan:
        plan = RunPlan(
            subtasks=[
                Subtask(
                    id="aplicar",
                    description="Aplicar el parche al parser.",
                    agent=nodes.AgentRole.CODER,
                    depends_on=[],
                    allowed_tools=["read_file", "write_file"],
                    done_criteria="El diff aplica y es revisable.",
                )
            ],
            max_review_cycles=2,
            rationale="plan de prueba",
        )
    return RunState(
        run_id="run-f6",
        trace_id="trace-f6",
        created_at=ahora,
        updated_at=ahora,
        instruction=Instruction(
            text="arregla el parser", source=InstructionSource.TEXT, confirmed_by_user=True
        ),
        options=RunOptions(repo_path=repositorio),
        interpretation=TaskInterpretation(
            intent=Intent.MODIFY,
            scope=alcance,
            constraints=["no tocar produccion"],
            confidence=0.9,
            rationale="pide un cambio",
        ),
        plan=plan,
        budget=Budget(),
    )


@pytest.fixture(autouse=True)
def _restaurar_gateway():
    previo = nodes._GATEWAY
    yield
    nodes.usar_gateway(previo)


# --------------------------------------------- 1. contrato CodeProposal

def test_delete_no_lleva_contenido() -> None:
    """Un borrado no tiene contenido nuevo: el contrato lo rechaza."""
    import pydantic

    with pytest.raises(pydantic.ValidationError, match="delete"):
        FileProposal(
            path="a.py",
            operation=FileOperation.DELETE,
            new_content="algo",
            rationale="r",
        )


def test_modify_exige_contenido() -> None:
    """Modificar sin contenido no dice nada: el contrato lo rechaza."""
    import pydantic

    with pytest.raises(pydantic.ValidationError, match="new_content"):
        FileProposal(path="a.py", operation=FileOperation.MODIFY, rationale="r")


def test_create_sin_contenido_no_vale() -> None:
    import pydantic

    with pytest.raises(pydantic.ValidationError):
        FileProposal(path="a.py", operation=FileOperation.CREATE, rationale="r")


def test_las_tres_operaciones_son_distinguibles() -> None:
    """Crear, modificar y borrar son valores distintos y se conservan."""
    for op in FileOperation:
        f = FileProposal(
            path="a.py",
            operation=op,
            new_content=None if op is FileOperation.DELETE else "x",
            rationale="r",
        )
        assert f.operation is op


# --------------------------------------------- 2. derivacion determinista

def test_el_sha256_lo_calcula_el_sistema_no_el_modelo() -> None:
    """**La proteccion central.** El hash corresponde al contenido, no a lo que diga el modelo.

    El modelo no puede saber el hash de un fichero que aun no ha escrito; aqui se
    comprueba que el `sha256` del `FileChange` es exactamente el del contenido que
    el modelo propuso.
    """
    propuesta = CodeProposal.model_validate(_propuesta())
    cambio = nodes._cambio_desde_propuesta(propuesta)

    esperado = hashlib.sha256(CONTENIDO.encode("utf-8")).hexdigest()
    assert cambio.files_changed[0].sha256 == esperado


def test_el_diff_sha256_es_el_del_diff() -> None:
    """El hash del diff corresponde al diff generado."""
    propuesta = CodeProposal.model_validate(_propuesta())
    cambio = nodes._cambio_desde_propuesta(propuesta)

    assert cambio.diff_sha256 == hashlib.sha256(cambio.diff.encode("utf-8")).hexdigest()


def test_el_diff_se_deriva_del_contenido() -> None:
    """El diff contiene el contenido propuesto, marcado como anadido."""
    propuesta = CodeProposal.model_validate(_propuesta())
    cambio = nodes._cambio_desde_propuesta(propuesta)

    assert "+def f():" in cambio.diff
    assert "+++ b/src/parser.py" in cambio.diff


def test_create_marca_dev_null() -> None:
    """Un archivo nuevo se marca con /dev/null como origen."""
    propuesta = CodeProposal.model_validate(
        _propuesta(
            files=[
                {
                    "path": "src/nuevo.py",
                    "operation": "create",
                    "new_content": "x = 1\n",
                    "rationale": "nuevo",
                }
            ]
        )
    )
    cambio = nodes._cambio_desde_propuesta(propuesta)
    assert "--- /dev/null" in cambio.diff
    assert cambio.files_changed[0].added == 1


def test_delete_marca_dev_null_como_destino() -> None:
    """Un archivo eliminado se marca con /dev/null como destino."""
    propuesta = CodeProposal.model_validate(
        _propuesta(
            files=[
                {"path": "src/viejo.py", "operation": "delete", "rationale": "ya no se usa"}
            ]
        )
    )
    cambio = nodes._cambio_desde_propuesta(propuesta)
    assert "+++ /dev/null" in cambio.diff
    assert cambio.files_changed[0].added == 0
    assert cambio.files_changed[0].removed == 0


def test_la_derivacion_es_determinista() -> None:
    """La misma propuesta da siempre el mismo diff y los mismos hashes."""
    propuesta = CodeProposal.model_validate(_propuesta())
    a = nodes._cambio_desde_propuesta(propuesta)
    b = nodes._cambio_desde_propuesta(propuesta)
    assert a.model_dump() == b.model_dump()


def test_el_conteo_de_lineas_ignora_la_final_vacia() -> None:
    """Un texto que termina en salto no cuenta una linea extra."""
    assert nodes._contar_lineas("a\nb\n") == 2
    assert nodes._contar_lineas("a\nb") == 2
    assert nodes._contar_lineas("") == 0


# --------------------------------------------- 3. limites del Scope

def test_la_propuesta_se_recorta_al_maximo_de_archivos() -> None:
    """Mas archivos de los permitidos: se conservan los primeros y se declara."""
    alcance = Scope(repo_path="/repo", max_files_changed=2)
    propuesta = CodeProposal(
        files=[
            FileProposal(
                path=f"src/f{i}.py",
                operation=FileOperation.CREATE,
                new_content="x\n",
                rationale="r",
            )
            for i in range(5)
        ],
        rationale="muchos",
    )
    recortada, motivo = nodes._respetar_limites(propuesta, alcance)

    assert len(recortada.files) == 2
    assert [f.path for f in recortada.files] == ["src/f0.py", "src/f1.py"]
    assert motivo is not None and "archivos" in motivo


def test_la_propuesta_se_recorta_al_maximo_de_lineas() -> None:
    """Mas lineas de las permitidas: se descartan archivos por el final."""
    alcance = Scope(repo_path="/repo", max_lines_changed=3)
    propuesta = CodeProposal(
        files=[
            FileProposal(
                path="src/a.py",
                operation=FileOperation.CREATE,
                new_content="1\n2\n3\n4\n5\n6\n",
                rationale="r",
            )
        ],
        rationale="muchas lineas",
    )
    recortada, motivo = nodes._respetar_limites(propuesta, alcance)

    assert len(recortada.files) == 0
    assert motivo is not None and "lineas" in motivo


def test_una_propuesta_dentro_del_alcance_no_se_toca() -> None:
    alcance = Scope(repo_path="/repo", max_files_changed=10, max_lines_changed=400)
    propuesta = CodeProposal.model_validate(_propuesta())
    recortada, motivo = nodes._respetar_limites(propuesta, alcance)

    assert recortada.model_dump() == propuesta.model_dump()
    assert motivo is None


def test_el_recorte_no_es_silencioso() -> None:
    """Un recorte por alcance deja un error registrado, nunca se aplica callado."""
    alcance = Scope(repo_path="/repo/autorizado", max_files_changed=1)
    fake = FakeModelAdapter(
        structured=_propuesta(
            files=[
                {
                    "path": "src/a.py",
                    "operation": "create",
                    "new_content": "x\n",
                    "rationale": "r",
                },
                {
                    "path": "src/b.py",
                    "operation": "create",
                    "new_content": "y\n",
                    "rationale": "r",
                },
            ]
        )
    )
    nodes.usar_gateway(ModelGateway([fake]))
    delta = nodes.coder(_estado(scope=alcance))

    clases = [e.error_class for e in delta["errors"]]
    assert "SCOPE_TRIMMED" in clases
    assert len(delta["outputs"].coder_output.files_changed) == 1


# --------------------------------------------- 4. el modelo propone

def test_con_modelo_el_cambio_es_el_derivado() -> None:
    fake = FakeModelAdapter(structured=_propuesta())
    nodes.usar_gateway(ModelGateway([fake]))
    delta = nodes.coder(_estado())

    cambio = delta["outputs"].coder_output
    assert [f.path for f in cambio.files_changed] == ["src/parser.py"]
    assert cambio.files_changed[0].sha256 == hashlib.sha256(CONTENIDO.encode()).hexdigest()


def test_el_prompt_lleva_la_subtarea_y_la_evidencia() -> None:
    """El Coder planifica sobre la subtarea y la evidencia acumulada (F5)."""
    fake = FakeModelAdapter(structured=_propuesta())
    nodes.usar_gateway(ModelGateway([fake]))
    nodes.coder(_estado())

    enviado = "\n".join(m.content for m in fake.calls[0].messages)
    assert "Aplicar el parche al parser" in enviado  # descripcion de la subtarea
    assert "El diff aplica y es revisable" in enviado  # criterio de termino
    assert "arregla el parser" in enviado  # peticion original


def test_el_esquema_enviado_es_el_de_codeproposal() -> None:
    """El contrato pedido es `CodeProposal`, no `CodeChange`."""
    from ai_swe.contracts import CodeProposal as CP

    fake = FakeModelAdapter(structured=_propuesta())
    nodes.usar_gateway(ModelGateway([fake]))
    nodes.coder(_estado())

    enviado = fake.calls[0].json_schema
    assert set(enviado["properties"]) == set(CP.model_json_schema()["properties"])
    assert "files" in enviado["properties"]


def test_una_propuesta_fuera_de_contrato_cae_al_fallback() -> None:
    """Un `delete` con contenido no cruza el contrato: se cae al cambio vacio."""
    fake = FakeModelAdapter(
        structured=_propuesta(
            files=[
                {
                    "path": "a.py",
                    "operation": "delete",
                    "new_content": "no deberia estar",
                    "rationale": "r",
                }
            ]
        )
    )
    nodes.usar_gateway(ModelGateway([fake]))
    delta = nodes.coder(_estado())

    assert delta["errors"][0].error_class == "MODEL_FALLBACK"
    assert delta["outputs"].coder_output.files_changed == []


# --------------------------------------------- 5. presupuesto

def test_una_codificacion_se_contabiliza() -> None:
    """`RNF-C1`: codificar es una llamada al modelo y cuenta."""
    fake = FakeModelAdapter(structured=_propuesta())
    nodes.usar_gateway(ModelGateway([fake]))
    delta = nodes.coder(_estado())

    assert delta["budget"].used_model_calls == 1
    assert delta["budget"].used_tokens > 0


def test_el_presupuesto_devuelto_es_uno_nuevo() -> None:
    fake = FakeModelAdapter(structured=_propuesta())
    nodes.usar_gateway(ModelGateway([fake]))
    original = _estado()
    delta = nodes.coder(original)

    assert original.budget.used_model_calls == 0
    assert delta["budget"].used_model_calls == 1


# --------------------------------------------- 6. fallback

def test_sin_modelo_devuelve_un_cambio_vacio_controlado() -> None:
    """**La regla inquebrantable.** Sin modelo: cambio vacio, nunca inventado."""
    nodes.usar_gateway(nodes.SIN_GATEWAY)
    delta = nodes.coder(_estado())

    cambio = delta["outputs"].coder_output
    assert cambio.files_changed == []
    assert cambio.diff == ""
    assert cambio.diff_sha256 == hashlib.sha256(b"").hexdigest()
    assert "no hay modelo conectado" in cambio.rationale


def test_sin_modelo_no_hay_error_porque_nada_fallo() -> None:
    """No tener modelo no es un fallo: no se registra error."""
    nodes.usar_gateway(nodes.SIN_GATEWAY)
    delta = nodes.coder(_estado())
    assert "errors" not in delta


@pytest.mark.parametrize(
    "fallo", ["timeout", "rate_limit", "unavailable", "auth_error", "invalid_response"]
)
def test_cualquier_fallo_del_proveedor_deja_un_cambio_valido(fallo: str) -> None:
    nodes.usar_gateway(ModelGateway([FakeModelAdapter(fault=fallo)], max_retries=0))
    delta = nodes.coder(_estado())

    assert delta["outputs"].coder_output is not None
    assert delta["errors"][0].error_class == "MODEL_FALLBACK"
    assert delta["errors"][0].recoverable is True


def test_un_error_de_programacion_no_se_traga() -> None:
    class GatewayRoto:
        requested_provider = "roto"

        def generate_structured(self, request, *, response_model, budget=None):
            raise TypeError("defecto propio, no del modelo")

        def consume(self, budget, response):  # pragma: no cover
            return budget

    nodes.usar_gateway(GatewayRoto())
    with pytest.raises(TypeError):
        nodes.coder(_estado())


def test_el_fallo_escribe_el_motivo() -> None:
    nodes.usar_gateway(ModelGateway([FakeModelAdapter(fault="auth_error")], max_retries=0))
    delta = nodes.coder(_estado())

    assert "cambio determinista de respaldo" in delta["errors"][0].message
    assert "ModelAuthenticationError" in delta["errors"][0].message


def test_el_fallo_no_pisa_los_errores_previos() -> None:
    """**Punto ciego que encontro la mutacion.** Un fallo del Coder debe *anadir*
    su error a los que ya hubiera, no sustituir la lista entera.

    En una ejecucion real el estado puede llegar con errores: por ejemplo, si el
    plan cayo a su fallback determinista en F4. La version mutada hacia
    `list(state.errors) or _error(...)`: con la lista **no vacia**, el `or` la daba
    por buena y el `MODEL_FALLBACK` del Coder **se perdia**. Ninguna prueba lo veia
    porque todas partian de un estado sin errores -un resultado vacio hace que la
    comprobacion parezca verde-.
    """
    previo = RunError(
        error_class="MODEL_FALLBACK",
        agent="supervisor",
        message="el plan uso el fallback determinista",
        recoverable=True,
        occurred_at=datetime.now(UTC),
    )
    estado = _estado().model_copy(update={"errors": [previo]})

    nodes.usar_gateway(ModelGateway([FakeModelAdapter(fault="auth_error")], max_retries=0))
    delta = nodes.coder(estado)

    clases = [e.error_class for e in delta["errors"]]
    assert len(clases) == 2, f"el error previo debe sobrevivir y el nuevo anadirse: {clases}"
    assert clases[0] == "MODEL_FALLBACK" and delta["errors"][0].agent == "supervisor"
    assert clases[1] == "MODEL_FALLBACK" and delta["errors"][1].agent == "coder"


# --------------------------------------------- 7. el coder no escribe

def test_el_coder_no_toca_el_disco(tmp_path) -> None:
    """F6 solo propone: el parche queda en el estado, no en el sistema de archivos."""
    fake = FakeModelAdapter(structured=_propuesta())
    nodes.usar_gateway(ModelGateway([fake]))

    estado = _estado(repositorio=str(tmp_path))
    delta = nodes.coder(estado)

    # El parche esta en el estado...
    assert delta["outputs"].coder_output.files_changed
    # ...pero no se creo ningun archivo en disco.
    assert list(tmp_path.rglob("*.py")) == []


# --------------------------------------------- 8. integracion F5

def test_el_coder_avanza_el_indice() -> None:
    """F5 sigue vigente: cada ejecutor declara completada su subtarea."""
    fake = FakeModelAdapter(structured=_propuesta())
    nodes.usar_gateway(ModelGateway([fake]))
    delta = nodes.coder(_estado())

    assert delta["plan_index"] == 1

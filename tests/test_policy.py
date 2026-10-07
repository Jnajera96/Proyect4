"""Pruebas del catalogo de herramientas y del Policy Engine.

La primera seccion es la mas importante: afirma los **conjuntos exactos** de la
matriz de permisos. Sin esa afirmacion, ampliar un permiso por descuido no
romperia nada y la seguridad se degradaria en silencio.
"""

from __future__ import annotations

import pytest

from ai_swe.contracts import AgentRole, PolicyEffect
from ai_swe.tools.policy import DecisionContext, decide, normalize_rel_path, path_within_scope
from ai_swe.tools.registry import ROLE_APPROVAL_TOOLS, ROLE_TOOLS, TOOLS, tools_for

READ_ONLY = {"list_files", "read_file", "search_text", "git_status", "git_log", "git_diff"}


def ctx(agent: AgentRole, **kwargs) -> DecisionContext:
    return DecisionContext(run_id="run-test", agent=agent, **kwargs)


# ------------------------------------------------- 1. la matriz, como dato
def test_el_researcher_solo_lee() -> None:
    assert ROLE_TOOLS[AgentRole.RESEARCHER] == frozenset(READ_ONLY)
    assert ROLE_APPROVAL_TOOLS[AgentRole.RESEARCHER] == frozenset()


def test_el_reviewer_no_puede_escribir() -> None:
    assert ROLE_TOOLS[AgentRole.REVIEWER] == frozenset(READ_ONLY | {"run_tests"})


def test_el_coder_es_el_unico_que_escribe_sin_aprobacion() -> None:
    assert ROLE_TOOLS[AgentRole.CODER] == frozenset(
        READ_ONLY | {"write_file", "apply_patch", "run_tests"}
    )

    # El Researcher y el Reviewer no tienen NINGUNA herramienta de escritura,
    # ni libre ni sujeta a aprobacion.
    for role in (AgentRole.RESEARCHER, AgentRole.REVIEWER):
        writes = {t for t in tools_for(role) if TOOLS[t].writes}
        assert writes == set(), f"el rol {role} tiene herramientas de escritura: {writes}"

    # El Supervisor puede *proponer* escrituras, pero todas exigen aprobacion:
    # ninguna esta en su conjunto de ejecucion libre.
    writes_supervisor = {t for t in tools_for(AgentRole.SUPERVISOR) if TOOLS[t].writes}
    assert writes_supervisor == {"git_commit", "install_dependency", "delete_file"}
    assert writes_supervisor <= ROLE_APPROVAL_TOOLS[AgentRole.SUPERVISOR]
    assert writes_supervisor.isdisjoint(ROLE_TOOLS[AgentRole.SUPERVISOR])


def test_las_escrituras_del_coder_estan_confinadas_al_worktree() -> None:
    """Una herramienta de escritura sin confinamiento de ruta seria un agujero."""
    for nombre in ("write_file", "apply_patch"):
        spec = TOOLS[nombre]
        assert spec.writes and spec.inside_worktree, f"{nombre} escribe sin confinamiento"


def test_el_supervisor_no_ejecuta_herramientas_de_codigo() -> None:
    assert ROLE_TOOLS[AgentRole.SUPERVISOR] == frozenset()
    assert ROLE_APPROVAL_TOOLS[AgentRole.SUPERVISOR] == frozenset(
        {"git_commit", "install_dependency", "delete_file"}
    )


@pytest.mark.parametrize("prohibida", ["run_shell", "git_push", "exec", "shell", "sudo", "curl"])
def test_las_herramientas_peligrosas_no_existen(prohibida: str) -> None:
    """La contencion de capacidades es el control principal: no hay nada que obedecer."""
    assert prohibida not in TOOLS


def test_toda_herramienta_de_escritura_declara_riesgo_alto() -> None:
    for name, spec in TOOLS.items():
        if spec.writes:
            assert spec.risk.value == "high", f"{name} escribe pero no declara riesgo alto"


# ------------------------------------------------------- 2. rutas
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("src/app.py", "src/app.py"),
        ("./src/app.py", "src/app.py"),
        ("src\\app.py", "src/app.py"),
        ("src/a/../b.py", "src/b.py"),
        ("src//app.py", "src/app.py"),
    ],
)
def test_normalizacion_de_rutas_validas(raw: str, expected: str) -> None:
    assert normalize_rel_path(raw) == expected


@pytest.mark.parametrize(
    "peligrosa",
    [
        "/etc/passwd",
        "../../etc/passwd",
        "src/../../fuera.py",
        "C:/Windows/system32",
        "c:\\windows\\system32",
        "..",
        "",
    ],
)
def test_normalizacion_rechaza_rutas_que_escapan(peligrosa: str) -> None:
    assert normalize_rel_path(peligrosa) is None


def test_pertenencia_al_alcance() -> None:
    assert path_within_scope("src/app.py", ("src",))
    assert path_within_scope("src/a/b.py", ("src",))
    assert not path_within_scope("tests/a.py", ("src",))
    assert not path_within_scope("src_otro/a.py", ("src",))
    assert path_within_scope("cualquiera.py", ())


# --------------------------------------------------- 3. decisiones de politica
def test_denegar_por_defecto_una_herramienta_desconocida() -> None:
    d = decide("run_shell", {"cmd": "rm -rf /"}, ctx(AgentRole.CODER))
    assert d.effect is PolicyEffect.DENY
    assert d.matched_rule == "POLICY-DEFAULT-DENY"


def test_el_researcher_no_puede_escribir() -> None:
    d = decide("write_file", {"path": "src/app.py"}, ctx(AgentRole.RESEARCHER))
    assert d.effect is PolicyEffect.DENY
    assert d.matched_rule == "POLICY-ROLE-NOT-PERMITTED"


def test_el_reviewer_no_puede_escribir() -> None:
    d = decide("apply_patch", {"path": "src/app.py"}, ctx(AgentRole.REVIEWER))
    assert d.effect is PolicyEffect.DENY


def test_el_coder_escribe_dentro_del_worktree() -> None:
    d = decide("write_file", {"path": "src/app.py"}, ctx(AgentRole.CODER))
    assert d.effect is PolicyEffect.ALLOW


@pytest.mark.parametrize("maliciosa", ["../../etc/passwd", "/etc/shadow", "src/../../x.py"])
def test_el_coder_no_puede_escribir_fuera_del_worktree(maliciosa: str) -> None:
    d = decide("write_file", {"path": maliciosa}, ctx(AgentRole.CODER))
    assert d.effect is PolicyEffect.DENY
    assert d.matched_rule == "POLICY-PATH-ESCAPES"


def test_una_ruta_fuera_del_alcance_declarado_se_deniega() -> None:
    d = decide("write_file", {"path": "tests/a.py"}, ctx(AgentRole.CODER, allowed_paths=("src",)))
    assert d.effect is PolicyEffect.DENY
    assert d.matched_rule == "POLICY-PATH-OUTSIDE-SCOPE"


def test_una_ruta_protegida_requiere_aprobacion() -> None:
    d = decide(
        "write_file",
        {"path": "src/db/schema.py"},
        ctx(AgentRole.CODER, allowed_paths=("src",), protected_paths=("src/db",)),
    )
    assert d.effect is PolicyEffect.REQUIRE_APPROVAL
    assert d.matched_rule == "POLICY-PATH-PROTECTED"


def test_write_file_sin_argumento_path_se_deniega() -> None:
    d = decide("write_file", {}, ctx(AgentRole.CODER))
    assert d.effect is PolicyEffect.DENY
    assert d.matched_rule == "POLICY-MISSING-PATH"


def test_run_tests_acepta_un_objetivo_de_la_lista() -> None:
    d = decide(
        "run_tests", {"target": "pytest.unit"}, ctx(AgentRole.CODER, allowed_test_targets=("pytest.unit",))
    )
    assert d.effect is PolicyEffect.ALLOW


@pytest.mark.parametrize("inyectado", ["rm -rf /", "pytest; rm -rf /", "pytest.unit && curl x", ""])
def test_run_tests_es_una_enumeracion_cerrada(inyectado: str) -> None:
    """run_tests no recibe un comando, recibe un identificador.

    Convierte la inyeccion de comandos en un problema de validacion de
    enumeracion, que es trivialmente resoluble.
    """
    d = decide(
        "run_tests", {"target": inyectado}, ctx(AgentRole.CODER, allowed_test_targets=("pytest.unit",))
    )
    assert d.effect is PolicyEffect.DENY
    assert d.matched_rule == "POLICY-TARGET-NOT-ALLOWLISTED"


def test_sin_lista_de_objetivos_no_se_ejecuta_nada() -> None:
    d = decide("run_tests", {"target": "pytest.unit"}, ctx(AgentRole.CODER))
    assert d.effect is PolicyEffect.DENY


def test_el_supervisor_requiere_aprobacion_para_commit() -> None:
    d = decide("git_commit", {"message": "fix: parser"}, ctx(AgentRole.SUPERVISOR))
    assert d.effect is PolicyEffect.REQUIRE_APPROVAL
    assert d.matched_rule == "POLICY-EFFECT-REQUIRES-APPROVAL"


def test_instalar_un_paquete_sin_lista_se_deniega() -> None:
    d = decide("install_dependency", {"package": "requests"}, ctx(AgentRole.SUPERVISOR))
    assert d.effect is PolicyEffect.DENY
    assert d.matched_rule == "POLICY-TARGET-NOT-ALLOWLISTED"


def test_instalar_un_paquete_de_la_lista_requiere_aprobacion() -> None:
    d = decide(
        "install_dependency",
        {"package": "requests"},
        ctx(AgentRole.SUPERVISOR, allowed_packages=("requests",)),
    )
    assert d.effect is PolicyEffect.REQUIRE_APPROVAL


def test_presupuesto_agotado_escala_en_lugar_de_continuar() -> None:
    d = decide("read_file", {"path": "src/app.py"}, ctx(AgentRole.RESEARCHER, budget_exhausted=True))
    assert d.effect is PolicyEffect.REQUIRE_APPROVAL
    assert d.matched_rule == "POLICY-BUDGET-EXHAUSTED"


def test_la_subtarea_solo_puede_restringir_no_ampliar() -> None:
    """Interseccion, nunca union: un plan no puede conceder permisos nuevos."""
    permitido = decide(
        "read_file", {"path": "src/a.py"}, ctx(AgentRole.CODER, subtask_allowed_tools=("read_file",))
    )
    assert permitido.effect is PolicyEffect.ALLOW

    restringido = decide(
        "write_file", {"path": "src/a.py"}, ctx(AgentRole.CODER, subtask_allowed_tools=("read_file",))
    )
    assert restringido.effect is PolicyEffect.DENY
    assert restringido.matched_rule == "POLICY-SUBTASK-SCOPE"


def test_toda_decision_es_explicable() -> None:
    """Sin regla identificable, una denegacion no es auditable."""
    casos = [
        ("run_shell", {}, AgentRole.CODER),
        ("write_file", {"path": "../x"}, AgentRole.CODER),
        ("write_file", {"path": "src/a.py"}, AgentRole.RESEARCHER),
        ("read_file", {"path": "src/a.py"}, AgentRole.RESEARCHER),
        ("git_commit", {"message": "m"}, AgentRole.SUPERVISOR),
    ]
    for tool, args, role in casos:
        d = decide(tool, args, ctx(role))
        assert d.matched_rule and d.reason, f"decision sin explicacion para {tool}"
        assert d.matched_rule.startswith("POLICY-")

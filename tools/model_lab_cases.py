"""Small reproducible role cases; imported by CLI and notebook, never by runtime."""

from __future__ import annotations

import ast
from dataclasses import dataclass

from pydantic import BaseModel

from ai_swe.contracts import CodeProposal, ReviewVerdict, RunPlan, TaskInterpretation


@dataclass(frozen=True)
class LabCase:
    case_id: str
    role: str
    prompt: str
    schema: type[BaseModel]
    expected: str


CASES = (
    LabCase(
        "requirements-modify",
        "requirements_analyst",
        "Repo autorizado '.'. Crea GET /hello y tests. Nunca modifiques .env. "
        "Interpreta requisitos; no confirmes en nombre del usuario.",
        TaskInterpretation,
        "modify",
    ),
    LabCase(
        "requirements-inspect",
        "requirements_analyst",
        "Repo autorizado '.'. Inspecciona src/app.py e informa problemas. "
        "Solo lectura, no modifiques archivos. Interpreta requisitos sin confirmarlos.",
        TaskInterpretation,
        "inspect",
    ),
    LabCase(
        "plan-modify",
        "supervisor",
        "Requisitos confirmados: modificar src/app.py, anadir tests, .env protegido. "
        "Planifica investigacion seguida de coder con dependencias y herramientas "
        "permitidas list_files/read_file/write_file/run_tests segun rol.",
        RunPlan,
        "modify",
    ),
    LabCase(
        "plan-inspect",
        "supervisor",
        "Requisitos confirmados: inspeccion de solo lectura. Plan con researcher, "
        "herramientas list_files/read_file. No asignes coder ni escrituras.",
        RunPlan,
        "inspect",
    ),
    LabCase(
        "code-return",
        "coder",
        "src/app.py contiene def f(): return 1. Propone modificar solo src/app.py "
        "para que def f() devuelva 42. Devuelve CodeProposal (files/new_content), "
        "no inventes diff ni hashes. No ejecutes herramientas.",
        CodeProposal,
        "return42",
    ),
    LabCase(
        "code-sum",
        "coder",
        "Crea solo src/suma.py con def sumar(a, b): return a + b. "
        "Devuelve CodeProposal con operation=create y contenido completo.",
        CodeProposal,
        "sum",
    ),
    LabCase(
        "review-good",
        "reviewer",
        "Revisa cambio src/app.py: def f(): return 1 -> def f(): return 42. "
        "Requisito: devolver 42. Tests en sandbox: test_f exige f()==42, exit_code=0. "
        "Sin otros cambios, errores ni hallazgos. Emite ReviewVerdict.",
        ReviewVerdict,
        "accept",
    ),
    LabCase(
        "review-bad",
        "reviewer",
        "Requisito: f() devuelve 42. Diff propuesto deja def f(): return 1. "
        "Test test_f exige f()==42 y falla con exit_code=1, actual 1. "
        "Emite ReviewVerdict con correcciones concretas obligatorias.",
        ReviewVerdict,
        "request_changes",
    ),
)


def task_success(case: LabCase, parsed: BaseModel) -> bool:
    """Check semantics without executing generated code or trusting model assertions."""
    if isinstance(parsed, TaskInterpretation):
        return (
            parsed.intent.value == case.expected
            and parsed.scope.repo_path == "."
            and not parsed.confirmed_by_user
            and (case.expected != "modify" or ".env" in parsed.scope.protected_paths)
        )
    if isinstance(parsed, RunPlan):
        tasks = parsed.subtasks
        if case.expected == "inspect":
            return all(
                t.agent.value == "researcher"
                and set(t.allowed_tools) <= {"list_files", "read_file"}
                for t in tasks
            )
        researchers = {t.id for t in tasks if t.agent.value == "researcher"}
        return bool(researchers) and any(
            t.agent.value == "coder"
            and "write_file" in t.allowed_tools
            and "run_tests" in t.allowed_tools
            and bool(researchers & set(t.depends_on))
            for t in tasks
        )
    if isinstance(parsed, ReviewVerdict):
        return parsed.decision.value == case.expected and (
            case.expected != "request_changes" or bool(parsed.required_fixes)
        )
    if not isinstance(parsed, CodeProposal) or len(parsed.files) != 1:
        return False
    file = parsed.files[0]
    expected_path = "src/app.py" if case.expected == "return42" else "src/suma.py"
    expected_operation = "modify" if case.expected == "return42" else "create"
    if file.path != expected_path or file.operation.value != expected_operation:
        return False
    try:
        tree = ast.parse(file.new_content or "")
    except (SyntaxError, ValueError, RecursionError):
        return False
    if len(tree.body) != 1 or not isinstance(tree.body[0], ast.FunctionDef):
        return False
    fn = tree.body[0]
    if fn.decorator_list or len(fn.body) != 1 or not isinstance(fn.body[0], ast.Return):
        return False
    value = fn.body[0].value
    if case.expected == "return42":
        return (
            fn.name == "f"
            and not fn.args.args
            and isinstance(value, ast.Constant)
            and type(value.value) is int
            and value.value == 42
        )
    return (
        fn.name == "sumar"
        and [a.arg for a in fn.args.args] == ["a", "b"]
        and isinstance(value, ast.BinOp)
        and isinstance(value.op, ast.Add)
        and isinstance(value.left, ast.Name)
        and value.left.id == "a"
        and isinstance(value.right, ast.Name)
        and value.right.id == "b"
    )

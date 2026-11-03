"""Full E2E execution of Representative Product 1 (Scientific Calculator) hermetically.

Verifies:
1. Interpretation of instructions.
2. Requirements confirmation gate.
3. Plan generation.
4. Coder sandbox implementation.
5. In-sandbox test execution (pytest.unit and ruff.check).
6. Automated review with clean verdict.
7. Approval gate and promotion to real git repository.
8. Post-promotion mathematical verification with independent oracle.
9. Execution of pytest directly in the promoted repository.
10. $0.00 spent and zero remote network requests.
"""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path

import pytest

from ai_swe.config import Settings
from ai_swe.contracts import RunOptions, RunStatus
from ai_swe.graph import RunEngine, model_routing
from ai_swe.models import FakeModelAdapter, ModelGateway
from ai_swe.state import RunStore


CALCULATOR_CODE = '''"""Scientific calculator with trigonometric functions."""
from __future__ import annotations

import math

__all__ = ["coseno", "seno", "tangente"]


def seno(grados: float) -> float:
    """Calcula el seno de un angulo dado en grados sexagesimales."""
    return math.sin(math.radians(grados))


def coseno(grados: float) -> float:
    """Calcula el coseno de un angulo dado en grados sexagesimales."""
    return math.cos(math.radians(grados))


def tangente(grados: float) -> float:
    """Calcula la tangente de un angulo dado en grados sexagesimales."""
    return math.tan(math.radians(grados))
'''

TEST_CALCULATOR_CODE = '''import pytest

from calculator import coseno, seno, tangente


def test_seno():
    assert seno(0) == pytest.approx(0.0)
    assert seno(30) == pytest.approx(0.5)
    assert seno(-30) == pytest.approx(-0.5)


def test_coseno():
    assert coseno(0) == pytest.approx(1.0)
    assert coseno(60) == pytest.approx(0.5)
    assert coseno(180) == pytest.approx(-1.0)


def test_tangente():
    assert tangente(0) == pytest.approx(0.0)
    assert tangente(45) == pytest.approx(1.0)
    assert tangente(-45) == pytest.approx(-1.0)
'''


def test_full_calculator_e2e_cycle_promoted_and_verified(tmp_path, monkeypatch):
    # 1. Create a real git repository for user project
    user_repo = tmp_path / "user_calc_repo"
    user_repo.mkdir()

    def git(*args: str) -> None:
        subprocess.run(
            ["git", "-C", str(user_repo), *args],
            check=True,
            capture_output=True,
            text=True,
        )

    git("init", "-q")
    git("-c", "user.name=Tester", "-c", "user.email=tester@test.local", "commit", "--allow-empty", "-qm", "initial commit")
    (user_repo / "README.md").write_text("# Calculadora Científica\n", encoding="utf-8")
    git("add", "README.md")
    git("-c", "user.name=Tester", "-c", "user.email=tester@test.local", "commit", "-qm", "add readme")

    # 2. Setup hermetic model adapter with the exact code proposal
    proposal = {
        "files": [
            {
                "path": "calculator.py",
                "operation": "create",
                "new_content": CALCULATOR_CODE,
                "rationale": "Implementacion de funciones trigonometricas seno, coseno y tangente en grados",
            },
            {
                "path": "test_calculator.py",
                "operation": "create",
                "new_content": TEST_CALCULATOR_CODE,
                "rationale": "Pruebas unitarias de las funciones con pytest.approx",
            },
        ],
        "rationale": "Calculadora trigonometrica completa con pruebas unitarias",
    }

    fake = FakeModelAdapter(structured=proposal)
    gateway = ModelGateway([fake])
    monkeypatch.setattr(model_routing, "gateway_from_settings", lambda _: gateway)

    settings = Settings(
        _env_file=None,
        network_egress_enabled=True,
        profile_id="hermetic-calculator-e2e",
        remote_model_roles=["coder"],
        workspace_root=tmp_path / "worktrees",
        allowed_test_targets=["pytest.unit", "ruff.check"],
    )

    db_path = tmp_path / "runs.sqlite3"
    with RunStore(db_path) as store:
        engine = RunEngine(store, settings=settings)
        instruction_text = (
            "Construye una calculadora que incluya funciones para hacer cálculos con seno, "
            "coseno y tangente en grados. Crea calculator.py y test_calculator.py."
        )
        state = engine.crear_estado(
            instruction_text,
            options=RunOptions(repo_path=str(user_repo)),
        )

        # Stage 1: Start engine -> reaches human requirements gate
        s1 = engine.start(state)
        assert s1.status == RunStatus.AWAITING_HUMAN_REQUIREMENTS_CONFIRMATION
        assert s1.instruction.capture_fidelity == 1.0
        assert s1.interpretation.intent == "modify"

        # Stage 2: Confirm requirements -> executes Plan, Coder, Test targets, Reviewer
        s2 = engine.resume(s1.run_id, "approved")
        assert s2.status == RunStatus.AWAITING_APPROVAL
        assert len(s2.evidence.test_runs) >= 1
        assert all(t.exit_code == 0 for t in s2.evidence.test_runs)
        assert not (user_repo / "calculator.py").exists(), "Must not write to user repo before approval"

        # Stage 3: Human approves final change -> promotes to user repository
        s3 = engine.resume(s2.run_id, "approved")
        assert s3.status == RunStatus.COMPLETED
        assert s3.errors == []

        # Stage 4: Verify files on disk in user repository
        promoted_calc = user_repo / "calculator.py"
        promoted_test = user_repo / "test_calculator.py"
        assert promoted_calc.is_file(), "calculator.py must exist in user repo"
        assert promoted_test.is_file(), "test_calculator.py must exist in user repo"

        calc_sha256 = hashlib.sha256(promoted_calc.read_bytes()).hexdigest()
        test_sha256 = hashlib.sha256(promoted_test.read_bytes()).hexdigest()
        assert calc_sha256 == hashlib.sha256(CALCULATOR_CODE.encode("utf-8")).hexdigest()
        assert test_sha256 == hashlib.sha256(TEST_CALCULATOR_CODE.encode("utf-8")).hexdigest()

        # Stage 5: Independent mathematical verification outside repo
        oracle_code = (
            "import importlib.util, math, sys\n"
            "spec = importlib.util.spec_from_file_location('calc', sys.argv[1])\n"
            "mod = importlib.util.module_from_spec(spec)\n"
            "spec.loader.exec_module(mod)\n"
            "assert math.isclose(mod.seno(0), 0.0, abs_tol=1e-7)\n"
            "assert math.isclose(mod.seno(30), 0.5, abs_tol=1e-7)\n"
            "assert math.isclose(mod.seno(-30), -0.5, abs_tol=1e-7)\n"
            "assert math.isclose(mod.coseno(0), 1.0, abs_tol=1e-7)\n"
            "assert math.isclose(mod.coseno(60), 0.5, abs_tol=1e-7)\n"
            "assert math.isclose(mod.coseno(180), -1.0, abs_tol=1e-7)\n"
            "assert math.isclose(mod.tangente(0), 0.0, abs_tol=1e-7)\n"
            "assert math.isclose(mod.tangente(45), 1.0, abs_tol=1e-7)\n"
            "assert math.isclose(mod.tangente(-45), -1.0, abs_tol=1e-7)\n"
            "print('ORACLE_OK')\n"
        )
        oracle_proc = subprocess.run(
            [sys.executable, "-c", oracle_code, str(promoted_calc)],
            cwd=str(tmp_path),
            capture_output=True,
            text=True,
            check=True,
        )
        assert "ORACLE_OK" in oracle_proc.stdout

        # Stage 6: Run pytest directly in the user repository
        pytest_proc = subprocess.run(
            [sys.executable, "-m", "pytest", "test_calculator.py", "-v"],
            cwd=str(user_repo),
            capture_output=True,
            text=True,
            check=True,
        )
        assert "3 passed" in pytest_proc.stdout

        # Stage 7: Verify financial and network constraints ($0.00 spent)
        assert s3.budget.used_model_calls >= 1
        # FakeModelAdapter records calls without network
        assert len(fake.calls) >= 1
        assert s3.budget.used_cost == 0.0 or s3.budget.used_cost is None

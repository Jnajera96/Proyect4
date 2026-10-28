"""Opt-in calculator E2E; default is offline and performs no inference.

Run using the project interpreter, or the portable interpreter with --bundle.
The existing shared spending grant is never created, reset, or refunded.
"""

from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import os
import subprocess
import sys
import uuid
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODEL = "Qwen/Qwen2.5-Coder-32B-Instruct:nscale"
TARGETS = ["pytest.unit", "ruff.check"]
FILES = ["calculator.py", "test_calculator.py"]
PROMPT = (
    "Construye una calculadora que incluya funciones para hacer cálculos con seno, "
    "coseno y tangente. Crea calculator.py con funciones coseno(grados), seno(grados) y "
    "tangente(grados): todas reciben grados y usan math.radians con math.cos, math.sin y "
    "math.tan. Crea test_calculator.py en la raíz con tres funciones de prueba pytest "
    "(test_seno, test_coseno y test_tangente) usando pytest.approx: "
    "en test_seno() comprueba seno(0) == pytest.approx(0.0), seno(30) == pytest.approx(0.5) "
    "y seno(-30) == pytest.approx(-0.5); "
    "en test_coseno() comprueba coseno(0) == pytest.approx(1.0), coseno(60) == pytest.approx(0.5) "
    "y coseno(180) == pytest.approx(-1.0); "
    "en test_tangente() comprueba tangente(0) == pytest.approx(0.0), "
    "tangente(45) == pytest.approx(1.0) "
    "y tangente(-45) == pytest.approx(-1.0). "
    "En test_calculator.py escribe el bloque de imports junto al inicio ('import pytest' "
    "y en la línea siguiente 'from calculator import coseno, seno, tangente'). "
    "No hay carpeta tests: descubre las pruebas de la raíz. Ejecuta pytest.unit y "
    "ruff.check. Solo puedes crear calculator.py y test_calculator.py; conserva README.md. "
    "Sin dependencias externas nuevas. Máximo 10 archivos y 400 líneas."
)


@contextmanager
def exclusive_lock(path: Path):
    handle = path.open("x", encoding="utf-8")
    try:
        yield
    finally:
        handle.close()
        path.unlink()


def reserve_batch(
    ledger: Path,
    observations: Path,
    candidate,
    report: Path,
    *,
    maximum_attempts: int = 18,
    logical_calls: int = 6,
    max_output_tokens: int = 4096,
    max_input_tokens: int | None = None,
) -> Decimal:
    """Deduplicate observed UI reservations and reserve all configured attempts.

    Unknown usage is charged at the entire reservation. Observed reservations are
    retained at max(reserved, consumed), so this never frees existing headroom.
    An exclusive lock prevents concurrent invocations of this harness racing.
    """
    from tools.model_lab import SpendGuard

    lock = ledger.with_suffix(".calculator.lock")
    with exclusive_lock(lock):
        try:
            state = json.loads(ledger.read_text(encoding="utf-8"))
            authorized = Decimal(str(state["authorized_usd"]))
            used = Decimal(str(state["reserved_usd"]))
            if not authorized.is_finite() or not 0 < authorized <= 3:
                raise ValueError("Existing grant must be positive and no greater than USD 3")
            if not used.is_finite() or used < 0:
                raise ValueError("Invalid existing reservation total")
            known = {
                item["observation_id"] for item in state["batches"] if "observation_id" in item
            }
            for owner in json.loads(observations.read_text(encoding="utf-8")):
                for row in owner["reservations"]:
                    identity = row["id"]
                    if identity in known:
                        continue
                    amount = max(
                        Decimal(str(row["reserved"])), Decimal(str(row.get("consumed") or 0))
                    )
                    if not amount.is_finite() or amount < 0:
                        raise ValueError("Invalid observed reservation")
                    used += amount
                    known.add(identity)
                    state["batches"].append(
                        {
                            "observation_id": identity,
                            "run_id": row["run_id"],
                            "reserved_usd": str(amount),
                            "source": str(observations),
                        }
                    )
            # Preserve observed spend even when there is insufficient room for E2E.
            state["reserved_usd"] = str(used)
            ledger.write_text(json.dumps(state, indent=2), encoding="utf-8")
            guard = SpendGuard(authorized - used)
            effective_candidate = (
                candidate.model_copy(
                    update={"context_length": min(candidate.context_length, max_input_tokens)}
                )
                if max_input_tokens is not None and candidate.context_length is not None
                else candidate
            )
            for _ in range(maximum_attempts):
                guard.reserve(effective_candidate, max_output_tokens)
            state["reserved_usd"] = str(used + guard.reserved_usd)
            state["batches"].append(
                {
                    "output": str(report),
                    "reserved_usd": str(guard.reserved_usd),
                    "maximum_attempts": maximum_attempts,
                    "logical_calls": logical_calls,
                    "max_output_tokens": max_output_tokens,
                    "model": MODEL,
                }
            )
            ledger.write_text(json.dumps(state, indent=2), encoding="utf-8")
            return guard.reserved_usd
        finally:
            pass


def snapshot(repo: Path) -> dict[str, str]:
    return {
        path: hashlib.sha256((repo / path).read_bytes()).hexdigest()
        for path in ["README.md", *FILES]
        if (repo / path).is_file()
    }


def command(argv: list[str], cwd: Path) -> dict:
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    # Generated code and its tests do not need provider credentials.
    for key in list(env):
        if any(word in key.upper() for word in ("TOKEN", "SECRET", "API_KEY")):
            env.pop(key, None)
    completed = subprocess.run(
        argv,
        cwd=cwd,
        env=env,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    return {
        "argv": argv,
        "exit_code": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def oracle(repo: Path, outside: Path) -> dict:
    """Independent math acceptance, executed outside the generated repository."""
    code = (
        "import importlib.util,math,sys; "
        "s=importlib.util.spec_from_file_location('calculator',sys.argv[1]); "
        "m=importlib.util.module_from_spec(s); s.loader.exec_module(m); "
        "cases=[('seno',30,.5),('coseno',60,.5),('tangente',45,1),"
        "('seno',0,0),('coseno',0,1),('tangente',0,0),"
        "('seno',-30,-.5),('coseno',180,-1),('tangente',-45,-1)]; "
        "results=[(n,x,getattr(m,n)(x),v) for n,x,v in cases]; "
        "print(results); assert all(math.isclose(a,b,rel_tol=1e-9,abs_tol=1e-9) "
        "for _,_,a,b in results)"
    )
    return command([sys.executable, "-B", "-c", code, str(repo / "calculator.py")], outside)


def verify_activity(events: list[dict]) -> None:
    """Require remote generation, both real test targets, then remote review."""
    responses = [e["seq"] for e in events if e["kind"] == "model_response_received"]
    starts = [e["seq"] for e in events if e["kind"] == "test_target_started"]
    completed = [e for e in events if e["kind"] == "test_target_completed"]
    assert len(responses) >= 2 and starts and completed, "Missing model/test activity evidence"
    assert min(responses) < min(starts) < max(e["seq"] for e in completed) < max(responses)
    assert set(TARGETS) <= {e["data"].get("target") for e in completed}


def run_real(args, root: Path, report: dict) -> None:
    # Set before importing Settings/runtime modules. Never prepend source in a
    # portable run: the package's own ai_swe imports must remain packaged.
    if args.bundle:
        sys._ai_swe_bundle = str(args.bundle.resolve())
    sys.path.append(str(ROOT))
    from dotenv import dotenv_values
    from pydantic import SecretStr

    from ai_swe.config import Settings
    from ai_swe.contracts import RunOptions, RunStatus
    from ai_swe.graph.engine import RunEngine
    from ai_swe.security import redact_deep, register_secret
    from ai_swe.state import RunStore
    from ai_swe.state.budget_ledger import BudgetLedger
    from ai_swe.tools.runner import comando_de
    from tools.model_lab import discover

    engine_module = Path(inspect.getfile(RunEngine)).resolve()
    report["engine_module_path"] = str(engine_module)
    if args.bundle:
        assert engine_module.is_relative_to((args.bundle / "app").resolve()), (
            "Portable E2E must import RunEngine from the selected bundle/app"
        )

    dotenv = dotenv_values(ROOT / ".env")
    token = (
        os.getenv("HF_TOKEN")
        or os.getenv("AI_SWE_HF_TOKEN")
        or dotenv.get("HF_TOKEN")
        or dotenv.get("AI_SWE_HF_TOKEN")
        or ""
    )
    register_secret(token)
    if not token.strip():
        raise ValueError("HF_TOKEN/AI_SWE_HF_TOKEN is not configured")
    candidates = discover()  # Public GET without authorization headers.
    candidate = next((c for c in candidates if c.routing_id == MODEL), None)
    if candidate is None or candidate.status != "live":
        raise ValueError("Requested model/provider is not live in the public catalog")
    report["catalog"] = candidate.model_dump()
    reserved = reserve_batch(
        args.ledger,
        args.observations,
        candidate,
        root / "report.json",
        maximum_attempts=2,
        logical_calls=2,
        max_output_tokens=992,
        max_input_tokens=11200,
    )
    report["reserved_usd"] = str(reserved)
    repo = root / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("# Disposable calculator E2E\n", encoding="utf-8")
    for argv in (
        ["git", "init", "-q"],
        ["git", "config", "user.name", "Calculator E2E"],
        ["git", "config", "user.email", "calculator-e2e@localhost"],
        ["git", "add", "README.md"],
        ["git", "commit", "-qm", "README only"],
    ):
        result = command(argv, repo)
        if result["exit_code"]:
            raise RuntimeError("Disposable Git fixture could not be initialized")
    original = snapshot(repo)
    report["repo"] = str(repo)
    pricing = json.dumps(
        [
            {
                "model": name,
                "input_per_1k": candidate.input_usd_per_million / 1000,
                "output_per_1k": candidate.output_usd_per_million / 1000,
                "currency": "USD",
            }
            for name in (candidate.routing_id, candidate.model_id)
        ]
    )
    settings = Settings(
        _env_file=None,
        runtime_mode="installed" if args.bundle else "development",
        profile_mode=True,
        profile_id=str(uuid.uuid4()),
        profiles_root=root / "profiles",
        state_db_path=root / "state.sqlite3",
        workspace_root=root / "workspaces",
        log_dir=root / "logs",
        cache_dir=root / "cache",
        stt_download_root=root / "speech",
        remote_model_roles=["coder", "reviewer"],
        model_provider="openai_compatible",
        model_name=MODEL,
        reviewer_model=MODEL,
        model_api_key=SecretStr(token),
        hf_token=SecretStr(token),
        model_base_url="https://router.huggingface.co/v1",
        model_pricing=pricing,
        max_model_calls_per_run=2,
        max_review_cycles=1,
        max_seconds_per_run=300,
        max_cost_per_run=float(reserved),
        authorized_repos=[repo],
        allowed_test_targets=TARGETS,
        allowed_packages=[],
        langfuse_enabled=False,
    )
    settings.registrar_secretos()
    ledger = BudgetLedger(settings.state_db_path)
    ledger.set_limit(float(reserved))  # A sublimit of the already-reserved grant.
    report["profile_id"] = settings.profile_id
    with RunStore(settings.state_db_path) as store:
        engine = RunEngine(store, settings=settings)
        state = None
        try:
            state = engine.start(
                engine.crear_estado(
                    PROMPT,
                    source="text",
                    options=RunOptions(
                        repo_path=str(repo),
                        allowed_paths=FILES,
                        protected_paths=["README.md"],
                    ),
                )
            )
            report["statuses"].append(state.status.value)
            assert state.status == RunStatus.AWAITING_HUMAN_REQUIREMENTS_CONFIRMATION
            assert state.interpretation.intent.value == "modify"
            assert state.instruction.source.value == "text"
            assert state.instruction.capture_fidelity == 1.0
            assert state.interpretation.scope.repo_path == str(repo)
            assert snapshot(repo) == original and len(original) == 1
            state = engine.resume(state.run_id, "approved")
            report["statuses"].append(state.status.value)
            # Existing internal reviewer loop is bounded at two cycles. Human
            # feedback is only used at a real approval gate, never patching files.
            for _ in range(2):
                if state.status != RunStatus.AWAITING_APPROVAL:
                    break
                runs = {r.target: r for r in state.evidence.test_runs}
                reviewer = state.outputs.reviewer_output
                if all(t in runs and runs[t].exit_code == 0 for t in TARGETS) and (
                    reviewer and reviewer.decision.value == "accept"
                ):
                    break
                state = engine.resume(
                    state.run_id,
                    {
                        "decision": "modified",
                        "comments": (
                            "Corrige calculator.py y test_calculator.py según la evidencia real. "
                            "Ejecuta pytest.unit y ruff.check con éxito y obtén revisión accept."
                        ),
                    },
                )
                report["statuses"].append(state.status.value)
            assert state.status == RunStatus.AWAITING_APPROVAL, "Final approval gate not reached"
            assert snapshot(repo) == original, "Original changed before approval"
            report["original_unchanged_before_approval"] = True
            scope = state.interpretation.scope
            assert scope.max_files_changed <= 10 and scope.max_lines_changed <= 400
            report["approved_scope"] = scope.model_dump(mode="json")
            worktree = Path(state.artifacts.worktree_path)
            approved = snapshot(worktree)
            assert set(approved) == {"README.md", *FILES}
            report["approved_files"] = approved
            report["approved_diff"] = state.artifacts.diff
            runs = {r.target: r for r in state.evidence.test_runs}
            assert all(t in runs and runs[t].exit_code == 0 for t in TARGETS)
            # pytest exit 5 rejects no-tests runs. A successful -qq run may only
            # print dots, so summary wording is not an execution signal.
            assert runs["pytest.unit"].argv
            assert tuple(runs["pytest.unit"].argv) == comando_de("pytest.unit")
            assert (worktree / "test_calculator.py").is_file()
            report["pytest_evidence_scope"] = {
                "worktree": str(worktree.resolve()),
                "test_file": str((worktree / "test_calculator.py").resolve()),
                "argv_matches_closed_target": True,
            }
            assert state.outputs.reviewer_output.decision.value == "accept"
            report["prepromotion_oracle"] = oracle(worktree, root)
            assert report["prepromotion_oracle"]["exit_code"] == 0
            activity = [e.model_dump(mode="json") for e in store.events(state.run_id)]
            verify_activity(activity)
            report["model_test_event_order_verified"] = True
            # Explicit user authorization covers promotion into this disposable
            # fixture only; no other repository can be targeted by this harness.
            state = engine.resume(state.run_id, "approved")
            report["statuses"].append(state.status.value)
            assert state.status == RunStatus.COMPLETED
            assert snapshot(repo) == approved, "Promotion differs from approved file contents"
            report["promotion_matches_approved"] = True
            report["oracle"] = oracle(repo, root)
            assert report["oracle"]["exit_code"] == 0
            report["output_files"] = {
                name: (repo / name).read_text(encoding="utf-8") for name in FILES
            }
            report["passed"] = True
        finally:
            if state is not None:
                current = engine.get(state.run_id)
                report["state"] = current.model_dump(mode="json")
                report["final_status"] = current.status.value
                report["tests"] = [r.model_dump(mode="json") for r in current.evidence.test_runs]
                report["events"] = [e.model_dump(mode="json") for e in store.events(state.run_id)]
                report["model_cost_and_calls"] = current.budget.model_dump(mode="json")
            report["profile_budget"] = ledger.summary()
            report.update(redact_deep(report))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-real", action="store_true")
    parser.add_argument("--bundle", type=Path)
    parser.add_argument(
        "--ledger", type=Path, default=ROOT / "_tmp/hybrid-validation/spend-ledger.json"
    )
    parser.add_argument(
        "--observations",
        type=Path,
        default=ROOT / "_tmp/calculator-profile-budget-observation.json",
    )
    args = parser.parse_args(argv)
    if not args.run_real:
        print("DRY RUN: no inference, no network, no spend reservation. Use --run-real to opt in.")
        return 0
    root = (ROOT / "_tmp/calculator-e2e" / uuid.uuid4().hex[:12]).resolve()
    root.mkdir(parents=True)
    report = {"passed": False, "statuses": [], "model": MODEL, "bundle": str(args.bundle or "")}
    try:
        run_real(args, root, report)
    except Exception as exc:
        from ai_swe.security import redact_deep

        report["blocked_reason"] = redact_deep(f"{type(exc).__name__}: {exc}")
    finally:
        # Central redaction applies to evidence, exceptions and generated content.
        from ai_swe.security import redact_deep

        report = redact_deep(report)
        (root / "report.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(
            json.dumps(
                {
                    "passed": report["passed"],
                    "report": str(root / "report.json"),
                    "blocked_reason": report.get("blocked_reason"),
                },
                ensure_ascii=False,
            )
        )
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

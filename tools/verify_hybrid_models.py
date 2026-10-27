"""Opt-in real hybrid graph verification on disposable Git repositories.

Requires an existing spending ledger with the user's total grant. Never creates
or renews that grant. Reserves 18 maximum HTTP attempts before inference.
"""


def main():
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-real", action="store_true")
    parser.add_argument("--scenario", choices=["approve", "reject", "changes"], default="approve")
    parser.add_argument("--catalog", default="_tmp/hybrid-catalog.json")
    parser.add_argument("--ledger", default="_tmp/hybrid-validation/spend-ledger.json")
    args = parser.parse_args()
    if not args.run_real:
        print("No inference performed; use --run-real with an existing authorized ledger.")
        return 0
    scenario = args.scenario

    import json
    import os
    import subprocess
    import uuid
    from decimal import Decimal
    from pathlib import Path

    from dotenv import dotenv_values
    from pydantic import SecretStr

    from ai_swe.config import Settings
    from ai_swe.contracts import RunOptions, RunStatus
    from ai_swe.graph import nodes
    from ai_swe.graph.engine import RunEngine
    from ai_swe.state import RunStore
    from tools.model_lab import Candidate, SpendGuard

    root = Path("_tmp/hybrid-e2e") / uuid.uuid4().hex[:8]
    root.mkdir(parents=True)
    repo = root / "repo"
    repo.mkdir()
    (repo / "src").mkdir()
    (repo / "tests").mkdir()
    (repo / "src/app.py").write_text("def f():\n    return 1\n")
    (repo / "tests/test_app.py").write_text(
        'from pathlib import Path\nimport runpy\ndef test_return():\n'
        '    path = Path(__file__).parents[1]/"src"/"app.py"\n'
        '    assert runpy.run_path(str(path))["f"]() == 42\n'
    )

    def git(*args):
        r = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True)
        return r.stdout.strip()

    git("init", "-q")
    git("config", "user.email", "hybrid-test@localhost")
    git("config", "user.name", "Hybrid Test")
    git("add", ".")
    git("commit", "-qm", "synthetic fixture")
    model = "Qwen/Qwen2.5-Coder-32B-Instruct"
    provider = "nscale"
    c = Candidate(
        **next(
            m
            for m in json.loads(Path(args.catalog).read_text())["candidates"]
            if m["model_id"] == model and m["provider"] == provider
        )
    )
    ledger = Path(args.ledger)
    state = json.loads(ledger.read_text())
    guard = SpendGuard(Decimal(state["authorized_usd"]) - Decimal(state["reserved_usd"]))
    for _ in range(18):
        guard.reserve(c, 4096)
    state["reserved_usd"] = str(Decimal(state["reserved_usd"]) + guard.reserved_usd)
    state["batches"].append(
        {
            "output": str(root / "report.json"),
            "reserved_usd": str(guard.reserved_usd),
            "maximum_attempts": 18,
        }
    )
    ledger.write_text(json.dumps(state, indent=2))
    print("E2E reserve USD:", guard.reserved_usd, "; total:", state["reserved_usd"], flush=True)
    token = os.environ.get("HF_TOKEN") or dotenv_values(".env").get("HF_TOKEN") or ""
    settings = Settings(
        _env_file=None,
        remote_model_roles=["coder", "reviewer"],
        model_provider="openai_compatible",
        model_name=c.routing_id,
        model_base_url="https://router.huggingface.co/v1",
        model_api_key=SecretStr(token),
        reviewer_model=c.routing_id,
        max_model_calls_per_run=6,
        max_review_cycles=1,
        max_seconds_per_run=180,
        model_pricing=json.dumps(
            [
                {
                    "model": c.routing_id,
                    "input_per_1k": c.input_usd_per_million / 1000,
                    "output_per_1k": c.output_usd_per_million / 1000,
                    "currency": "USD",
                }
            ]
        ),
    )
    settings.model_pricing = json.dumps(
        [
            {
                "model": name,
                "input_per_1k": c.input_usd_per_million / 1000,
                "output_per_1k": c.output_usd_per_million / 1000,
                "currency": "USD",
            }
            for name in [c.routing_id, c.model_id]
        ]
    )
    nodes.usar_workspace_root(root / "workspaces")
    nodes.usar_gateway(nodes.SIN_GATEWAY)
    nodes.usar_targets_permitidos(["pytest.unit"])
    report = {
        "scenario": scenario,
        "repo": str(repo),
        "model": c.routing_id,
        "statuses": [],
        "reserved_usd": str(guard.reserved_usd),
    }
    try:
        with RunStore(root / "state.sqlite3") as store:
            engine = RunEngine(store, settings=settings)
            initial = engine.crear_estado(
                "Modifica solo src/app.py para que f devuelva 42. La prueba existente "
                "tests/test_app.py ya exige que f() == 42; conserva ese archivo sin "
                "modificar y ejecuta las pruebas. No agregues ni cambies pruebas porque "
                "ya expresan el comportamiento solicitado.",
                options=RunOptions(
                    repo_path=str(repo.resolve()),
                    allowed_paths=["src/app.py"],
                    protected_paths=["tests"],
                ),
            )
            s = engine.start(initial)
            report["statuses"].append(s.status.value)
            assert s.status == RunStatus.AWAITING_HUMAN_REQUIREMENTS_CONFIRMATION
            assert (repo / "src/app.py").read_text() == "def f():\n    return 1\n"
            s = engine.resume(s.run_id, "approved")
            report["statuses"].append(s.status.value)
            report["errors"] = [e.error_class for e in s.errors]
            report["original_unchanged_before_approval"] = (
                repo / "src/app.py"
            ).read_text() == "def f():\n    return 1\n"
            report["model_calls"] = (
                s.budget.used_model_calls
                if hasattr(s.budget, "used_model_calls")
                else s.budget.model_dump()
            )
            print("Before approval:", s.status.value, "errors:", report["errors"], flush=True)
            if s.status == RunStatus.AWAITING_APPROVAL:
                if scenario == "reject":
                    s = engine.resume(s.run_id, "rejected")
                    report["statuses"].append(s.status.value)
                elif scenario == "changes":
                    s = engine.resume(
                        s.run_id,
                        {
                            "decision": "modified",
                                "comments": "Manten f() devolviendo 42 y anade a f el docstring: "
                                "Devuelve el valor acordado. No cambies pruebas.",
                        },
                    )
                    report["statuses"].append(s.status.value)
                    report["unchanged_after_change_request"] = (
                        repo / "src/app.py"
                    ).read_text() == "def f():\n    return 1\n"
                    if s.status == RunStatus.AWAITING_APPROVAL:
                        s = engine.resume(s.run_id, "approved")
                        report["statuses"].append(s.status.value)
                else:
                    s = engine.resume(s.run_id, "approved")
                    report["statuses"].append(s.status.value)
            report["final_status"] = s.status.value
            report["promoted_return_42"] = "return 42" in (repo / "src/app.py").read_text()
            report["git_status"] = git("status", "--porcelain")
            report["model_calls_budget"] = s.budget.model_dump()
            report["interpretation_rationale"] = s.interpretation.rationale
            report["plan_rationale"] = s.plan.rationale if s.plan else None
            report["passed"] = report["original_unchanged_before_approval"] and (
                s.status == RunStatus.CANCELLED
                and not report["promoted_return_42"]
                and not report["git_status"]
                if scenario == "reject"
                else s.status == RunStatus.COMPLETED
                and report["promoted_return_42"]
                and (
                    scenario != "changes"
                    or (
                        report.get("unchanged_after_change_request")
                        and "Devuelve el valor acordado" in (repo / "src/app.py").read_text()
                    )
                )
            )
    finally:
        nodes.usar_workspace_root(None)
        nodes.usar_targets_permitidos(None)
        (root / "report.json").write_text(json.dumps(report, indent=2, default=str))
        print("Report:", root / "report.json", flush=True)
    print("E2E passed:", report["passed"], flush=True)

    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

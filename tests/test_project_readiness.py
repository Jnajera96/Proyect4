import subprocess

from fastapi.testclient import TestClient

from ai_swe.api import crear_app
from ai_swe.config import Settings
from ai_swe.readiness import check_readiness
from ai_swe.state.budget_ledger import BudgetLedger


def git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True).stdout


def test_readiness_and_empty_initial_commit_preserve_user_index(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    (repo / "private.txt").write_text("not approved for commit")
    git(repo, "add", "private.txt")
    settings = Settings(
        _env_file=None,
        profile_mode=False,
        profile_id="readiness-fixture",
        state_db_path=tmp_path / "state.sqlite3",
        authorized_repos=[repo],
        model_provider="fake",
        model_name="fixture",
        max_cost_per_run=1,
        remote_model_roles=["coder", "reviewer"],
        model_pricing='[{"model":"fixture","input_per_1k":0.001,"output_per_1k":0.001}]',
        api_keys={"admin-fixture": "admin", "reader-fixture": "reader"},
    )
    app = crear_app(settings=settings)
    BudgetLedger(settings.state_db_path).set_limit(5)
    with TestClient(app) as client:
        headers = {"X-API-Key": "admin-fixture"}
        project = client.post(
            "/projects", headers=headers, json={"name": "Fixture", "repo_path": str(repo)}
        ).json()
        url = "/projects/" + project["project_id"]
        before = client.get(url + "/readiness", headers=headers)
        assert before.status_code == 200, before.text
        assert not before.json()["ready"]
        assert (
            next(c for c in before.json()["checks"] if c["code"] == "HEAD")["action"]
            == "initialize_head"
        )
        assert (
            client.post(
                url + "/initialize-head", headers={"X-API-Key": "reader-fixture"}
            ).status_code
            == 403
        )
        result = client.post(url + "/initialize-head", headers=headers)
        assert result.status_code == 200, result.text
        assert result.json()["ready"]
        assert not result.json()["remote_billing_verified"]
        assert git(repo, "ls-tree", "-r", "--name-only", "HEAD") == b""
        assert git(repo, "diff", "--cached", "--name-only").strip() == b"private.txt"
        assert client.post(url + "/initialize-head", headers=headers).status_code == 200
        assert git(repo, "rev-list", "--count", "HEAD").strip() == b"1"


def test_readiness_no_network_no_database_creation_and_mode_scope(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    git(
        repo,
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@localhost",
        "commit",
        "--allow-empty",
        "-qm",
        "base",
    )
    settings = Settings(_env_file=None, state_db_path=tmp_path / "missing.sqlite3")
    report = check_readiness(settings, str(repo))
    assert not report.ready
    assert {c.code for c in report.checks if not c.ready} >= {"PROVIDER", "BUDGET"}
    assert not settings.state_db_path.exists()
    assert check_readiness(settings, str(repo), "PLAN_ONLY").ready


def test_ledger_read_status_is_pure_and_counts_unknown_reservations(tmp_path):
    path = tmp_path / "budget.sqlite3"
    ledger = BudgetLedger(path)
    ledger.set_limit(2)
    ledger.reserve_call("unknown", run_limit=1.5, estimate=0.1)
    before = path.read_bytes()
    assert BudgetLedger.read_status(path) == {"available": 0.5, "hourly_used": 1.5}
    assert path.read_bytes() == before

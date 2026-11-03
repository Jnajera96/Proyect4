"""Regressions reproduced during release verification; real Git and pytest."""

import subprocess
from pathlib import Path

import pytest

from ai_swe.sandbox import crear, destruir, git
from ai_swe.tools.promoter import promover
from ai_swe.tools.runner import ejecutar


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    git("init", "-q", cwd=root)
    git("config", "user.name", "Release verification", cwd=root)
    git("config", "user.email", "verification@localhost", cwd=root)
    return root


def test_test_runner_does_not_add_bytecode_to_reviewed_diff(repo, tmp_path, monkeypatch):
    monkeypatch.delenv("PYTHONDONTWRITEBYTECODE", raising=False)
    (repo / "tests").mkdir()
    (repo / "tests/test_ok.py").write_bytes(b"def test_ok():\n    assert 1 == 1\n")
    git("add", ".", cwd=repo)
    git("commit", "-qm", "initial", cwd=repo)
    sandbox = crear(repo, "run-no-bytecode", workspace_root=tmp_path / "ws")
    try:
        before = sandbox.diff()
        result = ejecutar(sandbox, "pytest.unit", permitidos=("pytest.unit",),
            network_egress_enabled=True)
        assert result.exit_code == 0, result.stdout + result.stderr
        assert sandbox.diff() == before
        assert not list(sandbox.raiz.rglob("*.pyc"))
    finally:
        destruir(sandbox)


@pytest.mark.parametrize("autocrlf", ["true", "false"])
def test_promotion_preserves_patch_bytes_with_lf_source(repo, tmp_path, autocrlf):
    git("config", "core.autocrlf", autocrlf, cwd=repo)
    (repo / "app.py").write_bytes(b"def f():\n    return 1\n")
    git("add", ".", cwd=repo)
    git("commit", "-qm", "initial", cwd=repo)
    sandbox = crear(repo, "run-newlines", workspace_root=tmp_path / "ws")
    try:
        content = b"def f():\n    return 42\n"
        if autocrlf == "true":
            content = content.replace(b"\n", b"\r\n")
        (sandbox.raiz / "app.py").write_bytes(content)
        reviewed = sandbox.diff()
        result = promover(sandbox, repo_autorizado=repo, expected_diff=reviewed)
        assert result.applied
        assert (repo / "app.py").read_bytes() == (sandbox.raiz / "app.py").read_bytes()
        assert git("diff", "--cached", "--name-only", cwd=repo).stdout.strip() == ""
    finally:
        destruir(sandbox)


def test_git_diff_preserves_literal_crlf_content(repo):
    (repo / ".gitattributes").write_bytes(b"* -text\n")
    (repo / "app.py").write_bytes(b"old\r\n")
    git("add", ".", cwd=repo)
    git("commit", "-qm", "initial", cwd=repo)
    (repo / "app.py").write_bytes(b"new\r\n")
    raw = subprocess.run(
        ["git", "diff", "HEAD"], cwd=repo, capture_output=True, check=True
    ).stdout
    assert git("diff", "HEAD", cwd=repo).stdout.encode("utf-8") == raw

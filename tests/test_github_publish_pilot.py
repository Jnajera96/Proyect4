"""Automated tests for the GitHub Publish Pilot (Day 4).

Validates:
1. Vault storage & retrieval of GitHub PAT credentials with AES-256-GCM encryption.
2. End-to-end publish flow onto a disposable test repository (test-ai-swe-disposable).
3. Push credentials isolated to ephemeral environment variables without leaking to .git/config.
4. Streaming progress events and redaction of credentials in error logs.
5. Strict protection against overwriting existing remotes or publishing dirty trees.
"""

from __future__ import annotations

import base64
import json
import os
import subprocess
from pathlib import Path

import pytest
from test_launch_guide import promoted

from ai_swe.github_publish import (
    GitHubPublishRequest,
    git,
    git_environment,
    publication_steps,
    publish,
    push,
)
from ai_swe.security import redact, register_secret
from ai_swe.security.vault import create_vault, unlock_vault


def test_pat_vault_lifecycle_encryption_and_retrieval(tmp_path):
    """Verifies storing and retrieving GitHub PAT using the AES-256-GCM vault."""
    owner = "pilot-user"
    passphrase = "correct-horse-battery-staple-vault-key"
    pat = "ghp_SyntheticDisposableTokenForTesting0123456789"
    register_secret(pat)

    # 1. Create sealed vault with the PAT
    initial_data = {"github_pat": pat, "github_user": "pilot-user"}
    envelope, key = create_vault(owner, passphrase, initial_data)
    vault_file = tmp_path / "pilot.aiswe-vault"
    vault_file.write_text(json.dumps(envelope), encoding="utf-8")

    # 2. Plaintext file does not contain the token
    raw_content = vault_file.read_text(encoding="utf-8")
    assert pat not in raw_content
    assert "ghp_" not in raw_content

    # 3. Unauthorized access without passphrase fails
    with pytest.raises(Exception):
        unlock_vault(owner, "wrong-password-fails", envelope)

    # 4. Authorized access unseals PAT cleanly
    unsealed_key, data = unlock_vault(owner, passphrase, envelope)
    assert data["github_pat"] == pat
    assert data["github_user"] == "pilot-user"

    # 5. Redaction masks the secret in logs and string representations
    log_output = f"Attempting connection with token {pat} for user {owner}"
    assert pat not in redact(log_output)
    assert "[REDACTED]" in redact(log_output)


def test_disposable_repo_publish_and_push_isolation(tmp_path, monkeypatch):
    """Simulates publishing a disposable project onto GitHub with isolated ephemeral push."""
    import ai_swe.github_publish as pub_mod

    # Create promoted state with application files in disposable project directory
    state = promoted(tmp_path, filename="app.py", text="def run():\n    return 'OK'\n")
    user_project = Path(state.options.repo_path)

    def run_git(*args):
        subprocess.run(["git", "-C", str(user_project), *args], check=True, capture_output=True)

    run_git("init", "-q")
    (user_project / "README.md").write_text("# Disposable App\nCreated for pilot testing.\n", encoding="utf-8")
    run_git("add", "README.md")
    run_git("-c", "user.name=PilotUser", "-c", "user.email=pilot@test.invalid", "commit", "-qm", "initial commit")

    test_pat = "ghp_MockDisposableTokenForPushTesting987654321"
    register_secret(test_pat)

    # Capture push invocations and verify credentials are strictly ephemeral
    push_calls = []

    def tracking_push(root: Path, url: str, token: str):
        push_calls.append({"root": root, "url": url, "token": token})
        # Simulate push by validating what git_environment() produces
        env = git_environment()
        encoded = base64.b64encode(("x-access-token:" + token).encode()).decode()
        index = int(env["GIT_CONFIG_COUNT"])
        env["GIT_CONFIG_COUNT"] = str(index + 1)
        env[f"GIT_CONFIG_KEY_{index}"] = "http.https://github.com/.extraHeader"
        env[f"GIT_CONFIG_VALUE_{index}"] = "Authorization: Basic " + encoded
        assert env["GIT_TERMINAL_PROMPT"] == "0"
        assert env["GIT_ALLOW_PROTOCOL"] == "https"
        assert env["GIT_CONFIG_NOSYSTEM"] == "1"
        assert f"Authorization: Basic {encoded}" in env.values()

    monkeypatch.setattr(
        "ai_swe.models.providers.github_repository.validate_token",
        lambda tok: "pilot-user",
    )
    monkeypatch.setattr(
        pub_mod,
        "create_repository",
        lambda req: "https://github.com/pilot-user/test-ai-swe-disposable.git",
    )
    monkeypatch.setattr(pub_mod, "push", tracking_push)

    req = GitHubPublishRequest(
        repo_name="test-ai-swe-disposable",
        pat_token=test_pat,
        private=True,
    )

    events = list(publication_steps(state, req))
    stages = [e.get("stage") for e in events if "stage" in e]
    assert stages == ["validating", "creating", "uploading"]

    final_result = events[-1]
    assert final_result["published"] is True
    assert final_result["url"] == "https://github.com/pilot-user/test-ai-swe-disposable"
    assert "app.py" in final_result["files"]
    assert "README.md" in final_result["files"]

    # Verify push call details
    assert len(push_calls) == 1
    assert push_calls[0]["root"] == user_project
    assert push_calls[0]["url"] == "https://github.com/pilot-user/test-ai-swe-disposable.git"
    assert push_calls[0]["token"] == test_pat

    # Verify the local repository's new commit
    head_msg = subprocess.run(
        ["git", "-C", str(user_project), "log", "-n", "1", "--format=%B"],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout.strip()
    assert "Mi aplicación inicial construida con AI-SWE" in head_msg

    # Verify the files included in HEAD
    tree_files = subprocess.run(
        ["git", "-C", str(user_project), "ls-tree", "-r", "--name-only", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    assert sorted(tree_files) == ["README.md", "app.py"]

    # Verify remote was added to user project
    remote_url = subprocess.run(
        ["git", "-C", str(user_project), "remote", "get-url", "origin"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert remote_url == "https://github.com/pilot-user/test-ai-swe-disposable.git"

    # Verify no PAT persisted in user's .git/config
    user_git_config = (user_project / ".git" / "config").read_text(encoding="utf-8")
    assert test_pat not in user_git_config
    assert "ghp_" not in user_git_config


def test_publish_aborts_on_preexisting_remote(tmp_path):
    """Ensures repository with existing remote is never overwritten or re-linked."""
    state = promoted(tmp_path, filename="app.py", text="def run(): return 42\n")
    user_project = Path(state.options.repo_path)

    def run_git(*args):
        subprocess.run(["git", "-C", str(user_project), *args], check=True, capture_output=True)

    run_git("init", "-q")
    (user_project / "README.md").write_text("# Project with remote\n", encoding="utf-8")
    run_git("add", "README.md")
    run_git("-c", "user.name=PilotUser", "-c", "user.email=pilot@test.invalid", "commit", "-qm", "initial")
    run_git("remote", "add", "origin", "https://github.com/existing/remote.git")

    req = GitHubPublishRequest(repo_name="new-repo", pat_token="ghp_SafeToken1234567890", private=True)
    with pytest.raises(ValueError, match="ya tiene una conexión remota"):
        publish(state, req)


def test_publish_refuses_files_with_embedded_credentials(tmp_path):
    """Ensures source files containing accidental credentials abort publication before network calls."""
    leaking_pat = "ghp_AccidentalLeakInsideSourceFile9999"
    # Case 1: File modified post-approval is rejected by approved_repository
    state = promoted(tmp_path, filename="app.py", text="def run(): return 42\n")
    user_project = Path(state.options.repo_path)

    def run_git(*args):
        subprocess.run(["git", "-C", str(user_project), *args], check=True, capture_output=True)

    run_git("init", "-q")
    (user_project / "README.md").write_text("# Leaking App\n", encoding="utf-8")
    run_git("add", "README.md")
    run_git("-c", "user.name=PilotUser", "-c", "user.email=pilot@test.invalid", "commit", "-qm", "initial")

    (user_project / "app.py").write_text(f"API_KEY = '{leaking_pat}'\n", encoding="utf-8")
    req = GitHubPublishRequest(repo_name="leaking-repo", pat_token="ghp_SafePublishToken0000", private=True)
    with pytest.raises(ValueError, match="cambiaron después de la revisión"):
        publish(state, req)

    # Case 2: File promoted with credential is caught by publication_steps security scan
    second_dir = tmp_path / "second"
    second_dir.mkdir()
    state_with_leak = promoted(second_dir, filename="app.py", text=f"API_KEY = '{leaking_pat}'\n")
    user_project2 = Path(state_with_leak.options.repo_path)
    subprocess.run(["git", "-C", str(user_project2), "init", "-q"], check=True)
    (user_project2 / "README.md").write_text("# Leaking App 2\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(user_project2), "add", "README.md"], check=True)
    subprocess.run(["git", "-C", str(user_project2), "-c", "user.name=PilotUser", "-c", "user.email=pilot@test.invalid", "commit", "-qm", "initial"], check=True)

    with pytest.raises(ValueError, match="contener una credencial"):
        publish(state_with_leak, req)

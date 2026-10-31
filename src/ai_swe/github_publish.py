"""Explicit first publication: reviewed files only, private by default, ephemeral PAT."""

from __future__ import annotations

import base64
import hashlib
import os
import re
import subprocess
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, SecretStr

from ai_swe.launch_guide import approved_repository
from ai_swe.security import register_secret

SECRET_PATTERN = re.compile(
    rb"hf_[A-Za-z0-9]{12,}|ghp_[A-Za-z0-9]+|github_pat_[A-Za-z0-9_]+|"
    rb"-----BEGIN .*PRIVATE KEY-----"
)


class GitHubPublishRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    repo_name: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,99}$")
    pat_token: SecretStr = Field(min_length=10, max_length=512)
    private: bool = True
    organization: str = Field(default="", pattern=r"^(?:[A-Za-z0-9][A-Za-z0-9-]{0,38})?$")


def git_environment():
    needed = {
        "PATH",
        "SYSTEMROOT",
        "WINDIR",
        "COMSPEC",
        "TEMP",
        "TMP",
        "USERPROFILE",
        "HOME",
        "LOCALAPPDATA",
        "APPDATA",
        "PATHEXT",
        "PROGRAMFILES",
        "PROGRAMFILES(X86)",
    }
    env = {k: v for k, v in os.environ.items() if k.upper() in needed}
    # Ignore global/system Git configuration, signing, credential helpers and hooks.
    env.update(
        GIT_CONFIG_NOSYSTEM="1",
        GIT_CONFIG_GLOBAL=os.devnull,
        GIT_TERMINAL_PROMPT="0",
        GIT_ALLOW_PROTOCOL="https",
    )
    settings = {
        "core.hooksPath": os.devnull,
        "core.fsmonitor": "false",
        "commit.gpgSign": "false",
        "credential.helper": "",
        "http.sslVerify": "true",
        "http.followRedirects": "false",
    }
    env["GIT_CONFIG_COUNT"] = str(len(settings))
    for i, (key, value) in enumerate(settings.items()):
        env[f"GIT_CONFIG_KEY_{i}"] = key
        env[f"GIT_CONFIG_VALUE_{i}"] = value
    return env


def git(root: Path, *args: str, input: bytes | None = None, env=None) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *args],
            input=input,
            capture_output=True,
            timeout=60,
            shell=False,
            env=env or git_environment(),
        )
    except (OSError, subprocess.TimeoutExpired):
        raise ValueError(
            "Git no pudo completar la publicación. Revisa la conexión y Git."
        ) from None
    if result.returncode:
        raise ValueError("Git no pudo completar la publicación. No se hizo push forzado.")
    return result.stdout.decode("utf-8", errors="replace").strip()


def create_repository(request: GitHubPublishRequest) -> str:
    from ai_swe.models.providers.github_repository import create_repository as create

    return create(
        request.repo_name,
        request.pat_token.get_secret_value(),
        request.private,
        request.organization,
    )


def push(root: Path, url: str, token: str):
    environment = git_environment()
    encoded = base64.b64encode(("x-access-token:" + token).encode()).decode()
    register_secret(encoded)
    index = int(environment["GIT_CONFIG_COUNT"])
    environment["GIT_CONFIG_COUNT"] = str(index + 1)
    environment[f"GIT_CONFIG_KEY_{index}"] = "http.https://github.com/.extraHeader"
    environment[f"GIT_CONFIG_VALUE_{index}"] = "Authorization: Basic " + encoded
    branch = git(root, "symbolic-ref", "--short", "HEAD")
    git(root, "push", "--no-verify", "-u", "origin", branch, env=environment)


def publish(state, request: GitHubPublishRequest) -> dict:
    return list(publication_steps(state, request))[-1]


def publication_steps(state, request: GitHubPublishRequest):
    """Progress is emitted only at real phase boundaries; the PAT is never an event."""
    from ai_swe.models.providers.github_repository import validate_token

    register_secret(request.pat_token.get_secret_value())
    root = approved_repository(state)
    local_keys = git(root, "config", "--no-includes", "--local", "--name-only", "--list")
    if any(
        key.lower().startswith(("url.", "include.", "includeif.", "http.", "core.gitproxy"))
        for key in local_keys.splitlines()
    ):
        raise ValueError("La configuración local de Git necesita revisión antes de publicar.")
    if git(root, "remote"):
        raise ValueError("Este proyecto ya tiene una conexión remota. No se reemplazará.")
    if git(root, "diff", "--cached", "--name-only"):
        raise ValueError("Hay cambios preparados por otra operación. Termínala antes de publicar.")
    allowed = {f.path for f in state.artifacts.changed_files} | {"README.md"}
    tracked = set(git(root, "ls-tree", "-r", "--name-only", "HEAD").splitlines())
    if not tracked.issubset(allowed) or git(root, "rev-list", "--count", "HEAD") != "1":
        raise ValueError("La publicación sencilla requiere un proyecto nuevo sin historial ajeno.")
    git(root, "symbolic-ref", "--short", "HEAD")
    for relative in tracked:
        if SECRET_PATTERN.search(git(root, "show", f"HEAD:{relative}").encode()):
            raise ValueError("El historial contiene una posible credencial. No se publicará.")
    files = {}
    for relative in sorted(allowed):
        path = root / relative
        if (
            not path.resolve().is_relative_to(root)
            or path.is_symlink()
            or any(part.startswith(".env") or part == ".git" for part in Path(relative).parts)
            or path.suffix in {".sqlite3", ".aiswe-vault", ".log", ".pem", ".key"}
        ):
            raise ValueError("Se detectó un archivo privado o una ruta no autorizada.")
        if not path.is_file():
            continue
        data = path.read_bytes()
        if SECRET_PATTERN.search(data) or request.pat_token.get_secret_value().encode() in data:
            raise ValueError(
                "Un archivo parece contener una credencial. Revísalo antes de publicar."
            )
        change = next((f for f in state.artifacts.changed_files if f.path == relative), None)
        if (
            change
            and hashlib.sha256(data.decode("utf-8").replace("\r\n", "\n").encode()).hexdigest()
            != change.sha256
        ):
            raise ValueError("Hay archivos modificados después de la aprobación.")
        files[relative] = data
    # No network until all local preconditions have passed.
    yield {"stage": "validating"}
    validate_token(request.pat_token.get_secret_value())
    yield {"stage": "creating"}
    url = create_repository(request)
    yield {"stage": "uploading"}
    try:
        for relative, data in files.items():
            blob = git(root, "hash-object", "-w", "--no-filters", "--stdin", input=data)
            git(root, "update-index", "--add", "--cacheinfo", "100644", blob, relative)
        git(
            root,
            "-c",
            "user.name=AI SWE",
            "-c",
            "user.email=local@ai-swe.invalid",
            "commit",
            "-m",
            "Mi aplicación inicial construida con AI-SWE",
        )
        git(root, "remote", "add", "origin", url)
        push(root, url, request.pat_token.get_secret_value())
    except (ValueError, OSError, subprocess.TimeoutExpired):
        raise ValueError(
            "El repositorio fue creado en "
            + url.removesuffix(".git")
            + ", pero la publicación no terminó. Los archivos locales se conservaron."
        ) from None
    yield {
        "published": True,
        "url": url.removesuffix(".git"),
        "private": request.private,
        "files": sorted(files),
    }

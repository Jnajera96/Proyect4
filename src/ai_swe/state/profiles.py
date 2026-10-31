"""Public UUID identities and unlocked profile configuration. No environment fallback."""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import shutil
import threading
import unicodedata
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import SecretStr

from ai_swe.config import Settings
from ai_swe.security.vault import (
    VaultError,
    create_vault,
    save_vault,
    unlock_vault,
    unwrap_key,
    wrap_key,
)


def atomic_json(path: Path, data: dict):
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with temporary.open("x", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def normalize_name(name: str) -> str:
    name = unicodedata.normalize("NFKC", name).strip().casefold()
    if not re.fullmatch(r"[\w -]{1,64}", name, re.UNICODE):
        raise ValueError("Nombre invalido: usa letras, numeros, espacios o guiones")
    return name


@dataclass(frozen=True)
class UserPaths:
    root: Path

    @classmethod
    def for_user(cls, users: Path, user_id: str):
        if str(uuid.UUID(user_id)) != user_id:
            raise ValueError("Identificador invalido")
        root = users.resolve() / user_id
        if root.is_symlink() or root.resolve().parent != users.resolve():
            raise ValueError("Ruta de perfil invalida")
        return cls(root)

    @property
    def database(self):
        return self.root / "state.sqlite3"

    @property
    def logs(self):
        return self.root / "logs"

    @property
    def worktrees(self):
        return self.root / "worktrees"

    @property
    def cache(self):
        return self.root / "cache"

    @property
    def vault(self):
        return self.root / "vault.json"

    @property
    def identity(self):
        return self.root / "identity.json"

    def prepare(self):
        for path in (self.root, self.logs, self.worktrees, self.cache):
            if path.is_symlink() or not path.resolve().is_relative_to(self.root.resolve()):
                raise ValueError("Ruta de perfil invalida")
            path.mkdir(parents=True, exist_ok=True)
        for path in (self.database, self.vault, self.identity):
            if path.is_symlink():
                raise ValueError("Ruta de perfil invalida")


class ProfileSettings(Settings):
    @classmethod
    def settings_customise_sources(cls, settings_cls, init_settings, **kwargs):
        return (init_settings,)


@dataclass
class UnlockedProfile:
    user_id: str
    name: str
    paths: UserPaths
    key: bytes = field(repr=False)
    header: dict = field(repr=False)
    data: dict = field(repr=False)

    def save(self, data: dict):
        existing = json.loads(self.paths.vault.read_text(encoding="utf-8"))
        if existing.get("header") != self.header:
            raise VaultError("Las credenciales cambiaron. Vuelve a iniciar sesión.")
        envelope = save_vault(self.user_id, self.key, self.header, data)
        if "recovery" in existing:
            envelope["recovery"] = existing["recovery"]
        atomic_json(self.paths.vault, envelope)
        self.data = data

    def settings(self, base: Settings) -> Settings:
        values = base.model_dump()
        values.update(
            profiles_root=self.paths.root.parent,
            profile_mode=False,
            profile_id=self.user_id,
            api_keys={},
            state_db_path=self.paths.database,
            log_dir=self.paths.logs,
            workspace_root=self.paths.worktrees,
            cache_dir=self.paths.cache,
            stt_download_root=self.paths.cache / "speech",
            authorized_repos=[],
            model_api_key=SecretStr(self.data.get("hf_token", "")),
            hf_token=SecretStr(""),
            langfuse_public_key=SecretStr(""),
            langfuse_secret_key=SecretStr(""),
            langfuse_enabled=False,
            model_provider=self.data.get("model_provider", "openai_compatible"),
            model_base_url=self.data.get("model_base_url", "https://router.huggingface.co/v1"),
            model_name=self.data.get("model_name", ""),
            reviewer_model=self.data.get("reviewer_model", ""),
            remote_model_roles=self.data.get("remote_model_roles", []),
            model_pricing=self.data.get("model_pricing", ""),
            max_cost_per_run=self.data.get("max_cost_per_run"),
            max_cost_per_hour=self.data.get("max_cost_per_hour"),
        )
        result = ProfileSettings(**values)
        result.registrar_secretos()
        return result


class ProfileStore:
    def __init__(self, users: Path):
        self.users = users.resolve()
        self.users.mkdir(parents=True, exist_ok=True)
        self.names = self.users / ".names"
        if self.names.is_symlink() or self.names.resolve().parent != self.users:
            raise ValueError("Ruta de identidades invalida")
        self.names.mkdir(exist_ok=True)
        self._lock = threading.RLock()

    def _find(self, name):
        for directory in self.users.iterdir():
            if not directory.is_dir() or directory.is_symlink():
                continue
            try:
                paths = UserPaths.for_user(self.users, directory.name)
                if paths.identity.is_symlink():
                    continue
                identity = json.loads(paths.identity.read_text(encoding="utf-8"))
                if identity["name"] == name and identity["user_id"] == directory.name:
                    return paths, identity
            except (ValueError, OSError, KeyError):
                continue
        return None

    def create(self, name: str, password: str) -> UnlockedProfile:
        name = normalize_name(name)
        if not 12 <= len(password) <= 1024:
            raise ValueError("La contraseña debe tener entre 12 y 1024 caracteres")
        with self._lock:
            if self._find(name):
                raise ValueError("Nombre ya registrado")
            user_id = str(uuid.uuid4())
            paths = UserPaths.for_user(self.users, user_id)
            envelope, key = create_vault(user_id, password, {})
            # An exclusive public-name claim also serializes separate server processes.
            # Names never become paths; only a fixed SHA-256 basename is used.
            claim = self.names / hashlib.sha256(name.encode()).hexdigest()
            try:
                with claim.open("x", encoding="utf-8") as stream:
                    stream.write(user_id)
            except FileExistsError:
                raise ValueError("Nombre ya registrado") from None
            try:
                paths.prepare()
                atomic_json(paths.vault, envelope)
                atomic_json(paths.identity, {"user_id": user_id, "name": name})
            except BaseException:
                claim.unlink(missing_ok=True)
                raise
            return UnlockedProfile(user_id, name, paths, key, envelope["header"], {})

    def rollback_creation(self, profile: UnlockedProfile) -> None:
        """Release only the new identity owned by an unsuccessful import."""
        with self._lock:
            paths = UserPaths.for_user(self.users, profile.user_id)
            claim = self.names / hashlib.sha256(profile.name.encode()).hexdigest()
            if paths.root != profile.paths.root or claim.is_symlink():
                raise ValueError("No se puede revertir una identidad ajena")
            if claim.read_text(encoding="utf-8") != profile.user_id:
                raise ValueError("La reserva del nombre pertenece a otra identidad")
            shutil.rmtree(paths.root)
            claim.unlink()

    def unlock(self, name: str, password: str) -> UnlockedProfile:
        with self._lock:
            found = self._find(normalize_name(name))
            if not found:
                # Equal-cost KDF for unknown names; no enumeration via fast failures.
                create_vault(str(uuid.uuid4()), password, {})
                raise VaultError("Credenciales incorrectas")
            paths, identity = found
            paths.prepare()
            if paths.vault.stat().st_size > 2 * 1024 * 1024:
                raise VaultError("Boveda invalida")
            envelope = json.loads(paths.vault.read_text(encoding="utf-8"))
            key, data = unlock_vault(identity["user_id"], password, envelope)
            return UnlockedProfile(
                identity["user_id"], identity["name"], paths, key, envelope["header"], data
            )

    def generate_recovery(self, name: str, password: str) -> str:
        """Reauthenticate and wrap the DEK with a new high-entropy rescue code."""
        with self._lock:
            profile = self.unlock(name, password)
            envelope = json.loads(profile.paths.vault.read_text(encoding="utf-8"))
            code = secrets.token_urlsafe(32)
            envelope["recovery"] = wrap_key(profile.user_id, code, profile.key)
            atomic_json(profile.paths.vault, envelope)
            return code

    def recover(self, name: str, code: str, new_password: str) -> UnlockedProfile:
        """One-use rescue code rewraps the same DEK; never resets user data."""
        with self._lock:
            found = self._find(normalize_name(name))
            if not found:
                create_vault(str(uuid.uuid4()), code, {})
                raise VaultError("No se pudo recuperar el perfil")
            paths, identity = found
            paths.prepare()
            if paths.vault.stat().st_size > 2 * 1024 * 1024:
                raise VaultError("No se pudo recuperar el perfil")
            try:
                envelope = json.loads(paths.vault.read_text(encoding="utf-8"))
                key = unwrap_key(identity["user_id"], code, envelope["recovery"])
                header = wrap_key(identity["user_id"], new_password, key)
                # Authenticate the existing data before replacing any credential.
                probe = {"header": header, "data": envelope["data"]}
                _, data = unlock_vault(identity["user_id"], new_password, probe)
            except (KeyError, TypeError, ValueError):
                raise VaultError("No se pudo recuperar el perfil") from None
            atomic_json(paths.vault, probe)  # recovery code consumed atomically
            return UnlockedProfile(identity["user_id"], identity["name"], paths, key, header, data)

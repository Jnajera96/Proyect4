"""Opt-in local Docker Desktop execution, with owned snapshots and verified cleanup."""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import stat
import subprocess
import tempfile
import time
import uuid
from contextlib import suppress
from pathlib import Path
from types import SimpleNamespace

from pydantic import BaseModel, ConfigDict, Field

from ai_swe.cancellation import current_cancellation
from ai_swe.state.operation_lock import operation_lock
from ai_swe.tools.execution_snapshot import SnapshotError, create_snapshot


class DockerSettings(BaseModel):
    model_config = ConfigDict(
        frozen=True, extra="forbid", strict=True, revalidate_instances="always",
    )
    image: str = Field(default="", pattern=r"^(?:sha256:[0-9a-f]{64})?$")
    memory_mb: int = Field(default=512, ge=64, le=4096)
    cpus: float = Field(default=1.0, gt=0, le=4, allow_inf_nan=False)
    cpu_seconds: int = Field(default=600, ge=1, le=3600)
    pids_limit: int = Field(default=32, ge=4, le=128)


class DockerError(RuntimeError):
    pass


def session_directory():
    return Path(tempfile.gettempdir()) / "AISWESystem-docker"


def _local_directory(path):
    return (path.resolve() == path.absolute() and path.is_dir()
            and not getattr(path.lstat(), "st_file_attributes", 0) & 0x400)


def docker_executable():
    if os.name != "nt":
        raise DockerError("El ejecutor Docker requiere Windows y Docker Desktop Linux local")
    paths = [Path.home() / "AppData/Local/Programs/DockerDesktop/resources/bin/docker.exe",
             Path("C:/Program Files/Docker/Docker/resources/bin/docker.exe")]
    for path in paths:
        if path.is_file():
            return str(path)
    raise DockerError("No se encontró Docker Desktop; configura el ejecutor antes de construir")


class DockerSession:
    def __init__(self):
        executable = docker_executable()
        base = session_directory()
        base.mkdir(parents=True, exist_ok=True)
        if not _local_directory(base):
            raise DockerError("La carpeta de sesiones Docker no es local y regular")
        self.root = Path(tempfile.mkdtemp(prefix="aiswe-docker-", dir=base)).resolve()
        self.temp_parent = self.root.parent
        config = self.root / "config"
        config.mkdir()
        (config / "config.json").write_text(json.dumps({"auths": {}}))
        self.prefix = [executable, "--host", "npipe:////./pipe/dockerDesktopLinuxEngine",
                       "--config", str(config)]
        self.owner = uuid.uuid4().hex
        self.label = "io.aiswe.execution=" + self.owner
        self.create_started = False
        self.create_uncertain = False
        self.cid = None
        self.image = ""
        self.control = current_cancellation()
        self._lease = operation_lock(self.root.with_suffix(".lock"))
        self._lease.__enter__()
        try:
            self.record("prepared")
        except BaseException:
            self.release()
            raise

    def record(self, phase):
        path = self.root / "execution.json"
        temporary = path.with_suffix(".tmp")
        with temporary.open("w", encoding="utf-8") as stream:
            json.dump({"version": 1, "owner": self.owner, "phase": phase,
                       "container_id": self.cid, "image": self.image}, stream)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)

    def release(self):
        if self._lease is not None:
            self._lease.__exit__(None, None, None)
            self._lease = None
            with suppress(OSError):
                self.root.with_suffix(".lock").unlink()

    def run(self, arguments, *, timeout=15, cancellable=False):
        from ai_swe.tools.runner import _capturar

        result = _capturar(
            [*self.prefix, *arguments], SimpleNamespace(raiz=self.root), timeout,
            control=self.control if cancellable else None,
        )
        if result.returncode:
            raise DockerError("Falló una operación Docker: " + result.stderr[-1000:])
        return result.stdout.strip()

    def ready(self, policy):
        if not policy.image:
            raise DockerError("Falta configurar una imagen local inmutable del ejecutor Docker")
        text = self.run(["image", "inspect", policy.image])
        image = json.loads(text)[0]
        if (image["Os"] != "linux" or image["Architecture"] != "amd64"
                or (image["Config"].get("Labels") or {}).get("io.aiswe.runner-protocol") != "2"):
            raise DockerError("Reconstruye la imagen: falta el protocolo 2 de dependencias offline")
        try:
            entries = image["Config"]["Labels"]["io.aiswe.python-modules"].split(",")
            return dict(entry.split("=", 1) for entry in entries)
        except (KeyError, ValueError, AttributeError) as exc:
            raise DockerError("La imagen no declara su inventario de módulos") from exc

    def close(self):
        try:
            if self.create_started:
                ids = self.run(["container", "ls", "-aq", "--no-trunc", "--filter",
                                "label=" + self.label]).splitlines()
                for cid in ids:
                    if not re.fullmatch(r"[0-9a-f]{64}", cid):
                        raise DockerError("No se pudo verificar un ID de limpieza Docker")
                    image = json.loads(self.run(["container", "inspect", cid]))[0]
                    labels = image["Config"].get("Labels") or {}
                    if labels.get("io.aiswe.execution") != self.owner:
                        raise DockerError("No se confirmó la propiedad del contenedor")
                    self.run(["container", "rm", "--force", "--volumes", cid])
                if self.run(["container", "ls", "-aq", "--filter", "label=" + self.label]):
                    raise DockerError("El contenedor sigue presente después de la limpieza")
                if self.cid and self.run(["container", "ls", "-aq", "--filter", "id=" + self.cid]):
                    raise DockerError("El contenedor conocido no quedó eliminado")
                if self.create_uncertain:
                    raise DockerError("No se confirmó la finalización de la solicitud de creación")
            if (self.root.parent != self.temp_parent or self.root.resolve() != self.root
                    or not self.root.name.startswith("aiswe-docker-")
                    or self.root.lstat().st_file_attributes & 0x400):
                raise DockerError("No se verificó la carpeta temporal propia")
            shutil.rmtree(self.root)
        except Exception as exc:
            message = "Cierre Docker sin verificar; conserva el diario " + str(self.root)
            if self.control:
                self.control.block_cleanup(message)
            with suppress(OSError):
                (self.root / "recovery.json").write_text(json.dumps({
                    "owner_label": self.label, "container_id": self.cid,
                    "create_uncertain": self.create_uncertain,
                }))
            raise DockerError(message) from exc
        finally:
            self.release()


def recover_stopped_sessions():
    """Bounded startup sweep; never touch active, running or uncertain executions."""
    report = dict(removed=0, active=0, running=0, uncertain=0, unresolved=0)
    base = session_directory()
    if not base.exists():
        return report
    deadline = time.monotonic() + 5
    try:
        if not _local_directory(base):
            raise DockerError("Carpeta de sesiones no verificable")
        with os.scandir(base) as entries:
            for index, entry in enumerate(entries):
                if index >= 100 or time.monotonic() >= deadline:
                    report["unresolved"] += 1
                    break
                if not re.fullmatch(r"aiswe-docker-[a-z0-9_]{8}", entry.name):
                    continue
                root = Path(entry.path)
                try:
                    if not _local_directory(root):
                        raise DockerError("Sesión no verificable")
                    if not (root / "execution.json").is_file():
                        continue
                    lock_path = root.with_suffix(".lock")
                    if lock_path.exists():
                        info = lock_path.lstat()
                        if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                                or getattr(info, "st_file_attributes", 0) & 0x400):
                            raise DockerError("Archivo de bloqueo no verificable")
                    lease = operation_lock(lock_path)
                    try:
                        lease.__enter__()
                    except OSError:
                        report["active"] += 1
                        continue
                    try:
                        _recover_session(root, deadline, report)
                    finally:
                        lease.__exit__(None, None, None)
                        if not root.exists():
                            with suppress(OSError):
                                root.with_suffix(".lock").unlink()
                except Exception as exc:  # Preserve resources on any startup verification error.
                    report["unresolved"] += 1
                    logging.getLogger(__name__).warning("Recuperación Docker pendiente: %s", exc)
    except (DockerError, OSError) as exc:
        report["unresolved"] += 1
        logging.getLogger(__name__).warning("Recuperación Docker pendiente: %s", exc)
    if any(report[key] for key in ("removed", "running", "uncertain", "unresolved")):
        logging.getLogger(__name__).info("Recuperación Docker: %s", report)
    return report


def _recover_session(root, deadline, report):
    from ai_swe.tools.execution_snapshot import _open_entry

    path = root / "execution.json"
    with _open_entry(path):
        if path.stat().st_size > 4096:
            raise DockerError("Diario demasiado extenso")
        data = json.loads(path.read_text(encoding="utf-8"))
    if (not isinstance(data, dict) or data.get("version") != 1
            or not re.fullmatch(r"[0-9a-f]{32}", data.get("owner", ""))
            or data.get("phase") not in {"prepared", "creating", "created"}):
        raise DockerError("Identidad del diario no válida")
    if data["phase"] == "creating":
        report["uncertain"] += 1
        return
    cid, image = data.get("container_id"), data.get("image")
    if data["phase"] == "created":
        if (not isinstance(cid, str) or not re.fullmatch(r"[0-9a-f]{64}", cid)
                or not isinstance(image, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", image)):
            raise DockerError("Contenedor del diario no válido")
    elif cid is not None or image != "":
        raise DockerError("Diario preparado inconsistente")
    session = DockerSession.__new__(DockerSession)
    session.root, session.temp_parent = root, root.parent
    session._lease, session.control = None, None
    session.owner, session.cid = data["owner"], cid
    session.label = "io.aiswe.execution=" + session.owner
    session.create_started, session.create_uncertain = True, False
    session.prefix = [docker_executable(), "--host", "npipe:////./pipe/dockerDesktopLinuxEngine",
                      "--config", str(root / "config")]
    original = session.run

    def bounded(arguments, *, timeout=15):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise DockerError("Plazo de recuperación agotado")
        return original(arguments, timeout=min(timeout, remaining))

    session.run = bounded
    ids = session.run(["container", "ls", "-aq", "--no-trunc", "--filter",
                       "label=" + session.label]).splitlines()
    if ids and ids != [cid]:
        raise DockerError("El inventario no coincide con el diario")
    for identity in ids:
        container = json.loads(session.run(["container", "inspect", identity]))[0]
        if (container["Config"].get("Labels", {}).get("io.aiswe.execution") != session.owner
                or container["Config"].get("Labels", {}).get("io.aiswe.session") != root.name
                or container["Config"]["Image"] != image):
            raise DockerError("La identidad del contenedor no coincide")
        if container["State"]["Running"]:
            report["running"] += 1
            return
    session.close()
    report["removed"] += 1


def check_ready(policy):
    from ai_swe.tools.runner import RunnerError

    session = DockerSession()
    try:
        return session.ready(policy)
    except (RunnerError, OSError, ValueError, subprocess.TimeoutExpired) as exc:
        raise DockerError("No se pudo verificar Docker y la imagen local") from exc
    finally:
        session.close()


def execute(sandbox, target, policy, timeout):
    from ai_swe.tools.runner import _capturar

    policy = DockerSettings.model_validate(policy)
    if target not in {"pytest.unit", "pytest.integration", "ruff.check"}:
        raise DockerError("Objetivo Docker no permitido")
    deadline = time.monotonic() + min(timeout, 3600)
    session = DockerSession()
    try:
        available = session.ready(policy)
        if session.control:
            session.control.check()
        snapshot = session.root / "snapshot"
        digest = create_snapshot(sandbox.raiz, snapshot)
        from ai_swe.tools.dependency_detector import (
            DependencyError,
            detect_python_dependencies,
            repository_files,
        )

        manifest = detect_python_dependencies(repository_files(snapshot))
        missing = sorted(set(manifest.third_party_modules) - set(available))
        if missing:
            raise DependencyError("DEPENDENCY_UNAVAILABLE: módulos ausentes en la imagen: "
                                  + ", ".join(missing))
        if "," in str(snapshot):
            raise DockerError("Ruta temporal no compatible con montajes Docker")
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise subprocess.TimeoutExpired(["docker", target], timeout)
        arguments = ["container", "create", "--pull=never", "--label", session.label,
                     "--label", "io.aiswe.session=" + session.root.name,
                     "--label", "io.aiswe.snapshot=" + digest, "--network=none", "--read-only",
                     "--user=0:0", "--cap-drop=ALL", "--cap-add=SETUID", "--cap-add=SETGID",
                     "--security-opt=no-new-privileges=true", "--cgroupns=private",
                     f"--memory={policy.memory_mb}m", f"--memory-swap={policy.memory_mb}m",
                     f"--cpus={policy.cpus}", f"--pids-limit={policy.pids_limit}",
                     "--log-driver=none", "--workdir=/workspace", "--tmpfs",
                     "/tmp:rw,nosuid,nodev,size=64m,mode=1777", "--tmpfs",
                     "/workspace:rw,nosuid,nodev,size=256m,mode=1777", "--mount",
                     f"type=bind,source={snapshot},target=/input,readonly", "--entrypoint",
                     "/usr/local/bin/python", policy.image, "-I", "/opt/aiswe/run_target.py",
                     target, digest, str(remaining), str(policy.cpu_seconds)]
        session.create_started = True
        session.create_uncertain = True
        session.image = policy.image
        session.record("creating")
        cid = session.run(arguments, timeout=min(30, remaining))
        if not re.fullmatch(r"[0-9a-f]{64}", cid):
            raise DockerError("No se recibió un ID válido del contenedor creado")
        session.cid, session.create_uncertain = cid, False
        session.record("created")
        if session.control:
            session.control.check()
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise subprocess.TimeoutExpired(arguments, timeout)
        # The image watchdog remains active if this Windows process disappears.
        result = _capturar(
            [*session.prefix, "container", "start", "--attach", cid],
            SimpleNamespace(raiz=session.root), remaining, control=session.control,
        )
        state = json.loads(session.run(["container", "inspect", cid]))[0]["State"]
        if state["Running"]:
            raise DockerError("El contenedor sigue activo después de la ejecución")
        if result.returncode and state["ExitCode"] == 0:
            raise DockerError("El cliente Docker falló sin confirmar la salida")
        error = result.stderr
        if state["ExitCode"] == 127 and "DEPENDENCY_UNAVAILABLE:" in error:
            raise DependencyError(error[-2000:])
        if state.get("OOMKilled"):
            error += "\nEl contenedor agotó su cuota de memoria"
        return subprocess.CompletedProcess(
            [*session.prefix, *arguments], state["ExitCode"], result.stdout, error,
        )
    except SnapshotError as exc:
        raise DockerError("Snapshot de ejecución rechazado: " + str(exc)) from exc
    finally:
        session.close()

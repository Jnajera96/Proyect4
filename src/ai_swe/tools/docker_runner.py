"""Opt-in local Docker Desktop execution, with owned snapshots and verified cleanup."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import uuid
from contextlib import suppress
from pathlib import Path
from types import SimpleNamespace

from pydantic import BaseModel, ConfigDict, Field

from ai_swe.cancellation import current_cancellation
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
        self.root = Path(tempfile.mkdtemp(prefix="aiswe-docker-")).resolve()
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
        self.control = current_cancellation()

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
                or (image["Config"].get("Labels") or {}).get("io.aiswe.runner-protocol") != "1"):
            raise DockerError("La imagen no implementa el protocolo aprobado del ejecutor Linux")

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


def check_ready(policy):
    from ai_swe.tools.runner import RunnerError

    session = DockerSession()
    try:
        session.ready(policy)
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
        session.ready(policy)
        if session.control:
            session.control.check()
        snapshot = session.root / "snapshot"
        digest = create_snapshot(sandbox.raiz, snapshot)
        if "," in str(snapshot):
            raise DockerError("Ruta temporal no compatible con montajes Docker")
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise subprocess.TimeoutExpired(["docker", target], timeout)
        arguments = ["container", "create", "--pull=never", "--label", session.label,
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
        cid = session.run(arguments, timeout=min(30, remaining))
        if not re.fullmatch(r"[0-9a-f]{64}", cid):
            raise DockerError("No se recibió un ID válido del contenedor creado")
        session.cid, session.create_uncertain = cid, False
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
        if state.get("OOMKilled"):
            error += "\nEl contenedor agotó su cuota de memoria"
        return subprocess.CompletedProcess(
            [*session.prefix, *arguments], state["ExitCode"], result.stdout, error,
        )
    except SnapshotError as exc:
        raise DockerError("Snapshot de ejecución rechazado: " + str(exc)) from exc
    finally:
        session.close()

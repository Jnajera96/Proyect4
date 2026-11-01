"""Bounded Windows snapshots: locked handles, no links, no original repository mount."""

from __future__ import annotations

import ctypes
import hashlib
import json
import os
from contextlib import contextmanager
from ctypes import wintypes as w
from functools import lru_cache
from pathlib import Path

MANIFEST = ".aiswe-snapshot.json"
_IGNORED = {".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache",
            ".ruff_cache", "dist", "build", ".aws", ".ssh", ".gnupg", ".codex", ".serena"}


class SnapshotError(RuntimeError):
    pass


class _FileInfo(ctypes.Structure):
    _fields_ = [("attributes", w.DWORD), ("created", w.FILETIME), ("accessed", w.FILETIME),
               ("written", w.FILETIME), ("volume", w.DWORD), ("size_hi", w.DWORD),
               ("size_lo", w.DWORD), ("links", w.DWORD), ("index_hi", w.DWORD),
               ("index_lo", w.DWORD)]


@lru_cache(maxsize=1)
def _api():
    api = ctypes.WinDLL("kernel32", use_last_error=True)
    signatures = {
        "CreateFileW": (w.HANDLE, [w.LPCWSTR, w.DWORD, w.DWORD, ctypes.c_void_p,
                                   w.DWORD, w.DWORD, w.HANDLE]),
        "GetFileInformationByHandle": (w.BOOL, [w.HANDLE, ctypes.POINTER(_FileInfo)]),
        "GetFinalPathNameByHandleW": (w.DWORD, [w.HANDLE, w.LPWSTR, w.DWORD, w.DWORD]),
        "GetFileType": (w.DWORD, [w.HANDLE]),
        "ReadFile": (w.BOOL, [w.HANDLE, ctypes.c_void_p, w.DWORD, ctypes.POINTER(w.DWORD),
                              ctypes.c_void_p]),
        "CloseHandle": (w.BOOL, [w.HANDLE]),
    }
    for name, (result, arguments) in signatures.items():
        function = getattr(api, name)
        function.restype, function.argtypes = result, arguments
    return api


def _final_path(handle):
    buffer = ctypes.create_unicode_buffer(32768)
    size = _api().GetFinalPathNameByHandleW(handle, buffer, len(buffer), 0)
    if not size or size >= len(buffer) or buffer.value.startswith("\\\\?\\UNC\\"):
        raise SnapshotError("No se pudo verificar una ruta local del snapshot")
    return Path(buffer.value.removeprefix("\\\\?\\"))


@contextmanager
def _open_entry(path):
    api = _api()
    # Do not follow the leaf reparse point; deny concurrent writes/deletion while copying.
    handle = api.CreateFileW(str(path), 0x80000000, 1, None, 3, 0x02200000, None)
    if not handle or handle == ctypes.c_void_p(-1).value:
        raise SnapshotError(f"No se pudo bloquear una entrada: Windows {ctypes.get_last_error()}")
    try:
        info = _FileInfo()
        if not api.GetFileInformationByHandle(handle, ctypes.byref(info)):
            raise SnapshotError("No se pudo verificar el tipo de una entrada")
        if info.attributes & 0x400 or api.GetFileType(handle) != 1:
            raise SnapshotError("No se permiten enlaces, reparse points ni dispositivos")
        if not info.attributes & 0x10 and info.links != 1:
            raise SnapshotError("No se permiten archivos con enlaces duros")
        yield handle, info, _final_path(handle)
    finally:
        if not api.CloseHandle(handle):
            raise SnapshotError("No se pudo cerrar un handle del snapshot")


def create_snapshot(source: Path, destination: Path, *, max_bytes: int = 64 * 1024 * 1024) -> str:
    """Copy authorized regular files, returning the canonical manifest digest.

    A failed snapshot is never executable; the caller owns and cleans its fresh destination.
    """
    source, destination = Path(source).absolute(), Path(destination).absolute()
    if (os.name != "nt" or source.drive.startswith("\\\\") or destination.exists()
            or destination.resolve().is_relative_to(source.resolve())):
        raise SnapshotError("Se requiere Windows y un destino nuevo fuera del repositorio")
    if type(max_bytes) is not int or not 1 <= max_bytes <= 64 * 1024 * 1024:
        raise SnapshotError("Límite de snapshot no válido")
    files, total, entries = {}, 0, 0
    with _open_entry(source) as (root_handle, root_info, root):
        if not root_info.attributes & 0x10:
            raise SnapshotError("La raíz del snapshot no es una carpeta")
        destination.mkdir()

        def copy(directory, relative=Path(), depth=0):
            nonlocal total, entries
            if depth > 32:
                raise SnapshotError("El snapshot supera la profundidad permitida")
            with os.scandir(directory) as iterator:
                for entry in iterator:
                    entries += 1
                    from ai_swe.cancellation import current_cancellation

                    control = current_cancellation()
                    if control:
                        control.check()
                    if entries > 4000:
                        raise SnapshotError("El snapshot tiene demasiadas entradas")
                    name = entry.name
                    if name in {".", ".."} or any(c in name for c in "/\\:\x00"):
                        raise SnapshotError("Nombre de entrada no permitido")
                    lowered = name.casefold()
                    private = {"credentials.json", "secrets.json", "id_rsa", "id_ed25519"}
                    if (lowered in _IGNORED or lowered.startswith(".env")
                            or lowered.endswith(".aiswe-vault") or lowered in private):
                        continue
                    if lowered == MANIFEST:
                        raise SnapshotError("El repositorio contiene un manifiesto reservado")
                    rel = relative / name
                    with _open_entry(directory / name) as (handle, info, actual):
                        if _final_path(root_handle) != root or not actual.is_relative_to(root):
                            raise SnapshotError("Una entrada escapó de la raíz del snapshot")
                        target = destination / rel
                        if info.attributes & 0x10:
                            target.mkdir()
                            copy(actual, rel, depth + 1)
                            continue
                        size = (info.size_hi << 32) | info.size_lo
                        if len(files) >= 2000 or total + size > max_bytes:
                            raise SnapshotError("El snapshot supera el límite de archivos o bytes")
                        digest, copied = hashlib.sha256(), 0
                        with target.open("xb") as output:
                            buffer, count = ctypes.create_string_buffer(65536), w.DWORD()
                            while True:
                                read = _api().ReadFile(
                                    handle, buffer, len(buffer), ctypes.byref(count), None,
                                )
                                if not read:
                                    raise SnapshotError("No se pudo leer una entrada bloqueada")
                                if not count.value:
                                    break
                                copied += count.value
                                if copied > size:
                                    raise SnapshotError("Una entrada cambió durante la copia")
                                data = buffer.raw[:count.value]
                                digest.update(data)
                                output.write(data)
                        if copied != size:
                            raise SnapshotError("Una entrada cambió durante la copia")
                        files[rel.as_posix()] = digest.hexdigest()
                        total += copied

        copy(root)
    manifest = json.dumps(files, sort_keys=True, separators=(",", ":"))
    (destination / MANIFEST).write_text(manifest, encoding="utf-8")
    return hashlib.sha256(manifest.encode("utf-8")).hexdigest()

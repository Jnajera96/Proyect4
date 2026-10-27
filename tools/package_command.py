"""Resolve a package entry without a shell or a generated executable wrapper."""

from pathlib import Path


def package_command(path: Path) -> list[str]:
    if path.is_dir():
        python, entry = path / "runtime/python.exe", path / "start.py"
        if not python.is_file() or not entry.is_file():
            raise ValueError("Incomplete signed Python bundle")
        return [str(python), "-B", str(entry)]
    return [str(path)]

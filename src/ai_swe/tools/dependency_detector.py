"""Bounded static import inventory. Never import application code or install packages."""

from __future__ import annotations

import ast
import importlib.machinery
import importlib.metadata
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING

from packaging.requirements import InvalidRequirement, Requirement
from packaging.utils import canonicalize_name

if TYPE_CHECKING:
    from ai_swe.contracts.outputs import FileChange, FileProposal

IMPORT_PACKAGES = {"yaml": "pyyaml", "dotenv": "python-dotenv", "PIL": "pillow",
                   "bs4": "beautifulsoup4", "sklearn": "scikit-learn"}
TOOL_MODULES = frozenset({"pytest", "ruff", "iniconfig", "packaging", "pluggy", "pygments"})


@dataclass
class SourceFile:
    path: str
    new_content: str
    operation: str = "create"


@dataclass
class DependencyManifest:
    stdlib_modules: list[str] = field(default_factory=list)
    local_modules: list[str] = field(default_factory=list)
    third_party_modules: list[str] = field(default_factory=list)
    unmet_modules: list[str] = field(default_factory=list)
    has_manifest: bool = False
    packages: list[str] = field(default_factory=list)
    declared_packages: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    requirements: list[str] = field(default_factory=list)

    @property
    def canonical_requirements(self):
        # Versions cannot be inferred from imports; this is a proposal, never a lockfile.
        return "".join(package + "\n" for package in self.packages)

    @property
    def needs_manifest(self):
        return bool(self.unmet_modules)


def package_for(module):
    return canonicalize_name(IMPORT_PACKAGES.get(module, module))


class DependencyError(RuntimeError):
    pass


def installed_modules(modules):
    """Distribution metadata only: do not import a module from the project."""
    result = {}
    for module in modules:
        try:
            distribution = importlib.metadata.distribution(package_for(module))
            # Search only the installed distribution location, never the application directory.
            spec = importlib.machinery.PathFinder.find_spec(
                module, [str(distribution.locate_file(""))],
            )
            if spec is not None:
                result[module] = distribution.version
        except importlib.metadata.PackageNotFoundError:
            continue
    return result


def detect_python_dependencies(
    files: list[FileProposal | FileChange | SourceFile],
) -> DependencyManifest:
    manifest = DependencyManifest()
    content = {}
    for file in files:
        if getattr(file, "operation", "") == "delete":
            continue
        path = PurePosixPath(file.path.replace("\\", "/"))
        if path.is_absolute() or ".." in path.parts or ":" in str(path):
            manifest.errors.append("Ruta no relativa: " + str(path))
            continue
        if path.suffix != ".py" and path.as_posix() != "requirements.txt":
            continue
        text = getattr(file, "new_content", None)
        if not isinstance(text, str):
            manifest.errors.append("Contenido no disponible: " + str(path))
            continue
        if len(text.encode("utf-8")) > 512 * 1024:
            manifest.errors.append("Archivo demasiado extenso: " + str(path))
            continue
        content[path.as_posix()] = text
    local = set()
    for name in content:
        path = PurePosixPath(name)
        if path.suffix == ".py":
            parts = path.with_suffix("").parts
            local.add(parts[0])
            if parts[0] == "src" and len(parts) > 1:
                parts = parts[1:]
            local.add(parts[0])
    manifest.has_manifest = "requirements.txt" in content
    declared = set()
    for line in content.get("requirements.txt", "").splitlines():
        line = line.split(" #", 1)[0].strip()
        if not line or line.startswith("#"):
            continue
        try:
            requirement = Requirement(line)
            if requirement.url:
                raise InvalidRequirement("Remote sources are not authorized")
            declared.add(canonicalize_name(requirement.name))
            manifest.requirements.append(str(requirement))
        except InvalidRequirement:
            manifest.errors.append("requirements.txt contiene una fuente o instrucción no admitida")
    standard, internal, external = set(), set(), set()
    for name, text in content.items():
        if not name.endswith(".py"):
            continue
        try:
            tree = ast.parse(text, filename=name)
        except (SyntaxError, ValueError, RecursionError):
            manifest.errors.append("No se pudo analizar Python: " + name)
            continue
        for node in ast.walk(tree):
            modules = []
            if isinstance(node, ast.Import):
                modules = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    internal.add((node.module or PurePosixPath(name).parent.name).split(".")[0])
                    continue
                if node.module:
                    modules = [node.module.split(".")[0]]
            for module in modules:
                if module in local:
                    internal.add(module)
                elif module in sys.stdlib_module_names or module in sys.builtin_module_names:
                    standard.add(module)
                else:
                    external.add(module)
    manifest.stdlib_modules, manifest.local_modules = sorted(standard), sorted(internal)
    manifest.third_party_modules = sorted(external)
    manifest.packages = sorted({package_for(module) for module in external})
    manifest.declared_packages = sorted(declared)
    manifest.unmet_modules = sorted(m for m in external if package_for(m) not in declared)
    return manifest


def repository_files(root: Path, proposals=()):
    """Read only Python/requirements, excluding links and private/generated trees."""
    root = root.resolve()
    files, total = {}, 0
    ignored = {".git", ".venv", "venv", "node_modules", "__pycache__", "dist", "build",
               ".pytest_cache", ".ruff_cache", ".codex", ".serena"}
    for parent, directories, names in os.walk(root, followlinks=False):
        directories[:] = [d for d in directories if d not in ignored
                          and not (Path(parent) / d).is_symlink()
                          and not getattr((Path(parent) / d).lstat(),
                                          "st_file_attributes", 0) & 0x400]
        for name in names:
            path = Path(parent) / name
            relative = path.relative_to(root).as_posix()
            if path.suffix != ".py" and relative != "requirements.txt":
                continue
            info = path.lstat()
            if (path.is_symlink() or info.st_nlink != 1
                    or getattr(info, "st_file_attributes", 0) & 0x400
                    or not path.resolve().is_relative_to(root)):
                raise ValueError("Archivo de dependencias no regular")
            if (len(files) >= 2000 or info.st_size > 512 * 1024
                    or total + info.st_size > 64 * 1024**2):
                raise ValueError("Inventario de dependencias demasiado extenso")
            with path.open("rb") as stream:
                data = stream.read(512 * 1024 + 1)
            if len(data) > 512 * 1024 or total + len(data) > 64 * 1024**2:
                raise ValueError("Inventario de dependencias demasiado extenso")
            text = data.decode("utf-8-sig")
            total += len(data)
            files[relative] = SourceFile(relative, text)
    for proposal in proposals:
        name = PurePosixPath(proposal.path.replace("\\", "/")).as_posix()
        if proposal.operation == "delete":
            files.pop(name, None)
        else:
            files[name] = SourceFile(name, proposal.new_content, proposal.operation)
    return list(files.values())

"""Bounded static import inventory. Never import application code or install packages."""

from __future__ import annotations

import ast
import importlib.machinery
import importlib.metadata
import json
import os
import re
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

NODE_EXTENSIONS = frozenset({".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx"})
NODE_BUILTINS = frozenset({
    "assert", "async_hooks", "buffer", "child_process", "cluster", "console",
    "constants", "crypto", "dgram", "diagnostics_channel", "dns", "domain",
    "events", "fs", "http", "http2", "https", "inspector", "module", "net",
    "os", "path", "perf_hooks", "process", "punycode", "querystring",
    "readline", "repl", "stream", "string_decoder", "test", "timers", "tls",
    "trace_events", "tty", "url", "util", "v8", "vm", "wasi", "worker_threads",
    "zlib",
})

def repository_node_files(root: Path, proposals=()):
    """Read only Node/JS files and package.json, excluding links and private trees."""
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
            if path.suffix not in NODE_EXTENSIONS and relative != "package.json":
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
            text_content = data.decode("utf-8-sig", errors="replace")
            total += len(data)
            files[relative] = SourceFile(relative, text_content)
    for proposal in proposals:
        name = PurePosixPath(proposal.path.replace("\\", "/")).as_posix()
        ext = PurePosixPath(name).suffix
        if ext in NODE_EXTENSIONS or name == "package.json":
            if getattr(proposal, "operation", "") == "delete":
                files.pop(name, None)
            else:
                files[name] = SourceFile(name, getattr(proposal, "new_content", ""), getattr(proposal, "operation", "create"))
    return list(files.values())




@dataclass
class NodeDependencyManifest:
    required_versions: dict[str, str] = field(default_factory=dict)
    builtin_modules: list[str] = field(default_factory=list)
    local_modules: list[str] = field(default_factory=list)
    third_party_modules: list[str] = field(default_factory=list)
    unmet_modules: list[str] = field(default_factory=list)
    has_manifest: bool = False
    packages: list[str] = field(default_factory=list)
    declared_packages: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def needs_manifest(self) -> bool:
        return bool(self.unmet_modules)

    def preflight(self) -> dict:
        """Static requirements are not evidence of an installed runtime."""
        return {
            "scope": "static_only", "runtime_available": False,
            "required_versions": self.required_versions,
            "version_source": "package.json engines; no se consulta PATH",
            "offline_packages": [],
            "missing_packages": sorted(set(self.third_party_modules) | set(self.declared_packages)),
        }


def npm_package_name(specifier: str) -> str:
    specifier = specifier.strip()
    if specifier.startswith("@"):
        parts = specifier.split("/")
        return f"{parts[0]}/{parts[1]}" if len(parts) >= 2 else specifier
    return specifier.split("/")[0]


def _strip_js_comments(text: str) -> str:
    # Strip block comments
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    # Strip line comments
    text = re.sub(r"//.*", "", text)
    return text


def detect_node_dependencies(
    files: list[FileProposal | FileChange | SourceFile],
) -> NodeDependencyManifest:
    manifest = NodeDependencyManifest()
    content: dict[str, str] = {}
    for file in files:
        if getattr(file, "operation", "") == "delete":
            continue
        path = PurePosixPath(file.path.replace("\\", "/"))
        if path.is_absolute() or ".." in path.parts or ":" in str(path):
            manifest.errors.append("Ruta no relativa: " + str(path))
            continue
        if path.suffix not in NODE_EXTENSIONS and path.as_posix() != "package.json":
            continue
        text = getattr(file, "new_content", None)
        if not isinstance(text, str):
            manifest.errors.append("Contenido no disponible: " + str(path))
            continue
        if len(text.encode("utf-8")) > 512 * 1024:
            manifest.errors.append("Archivo demasiado extenso: " + str(path))
            continue
        content[path.as_posix()] = text

    manifest.has_manifest = "package.json" in content
    declared: set[str] = set()
    if manifest.has_manifest:
        try:
            pkg_data = json.loads(content["package.json"])
            if isinstance(pkg_data, dict):
                engines = pkg_data.get("engines", {})
                if isinstance(engines, dict):
                    manifest.required_versions = {
                        name: value for name in ("node", "npm")
                        if isinstance(value := engines.get(name), str) and len(value) <= 128
                    }
                for key in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
                    val = pkg_data.get(key)
                    if isinstance(val, dict):
                        declared.update(val.keys())
        except Exception:
            manifest.errors.append("package.json no es un JSON válido")

    local_names: set[str] = set()
    for name in content:
        p = PurePosixPath(name)
        if p.suffix in NODE_EXTENSIONS:
            local_names.add(p.stem)
            local_names.add(p.as_posix())

    builtins: set[str] = set()
    local: set[str] = set()
    external: set[str] = set()

    # Regexes for import / export / require
    import_re = re.compile(
        r"""(?:import\s+(?:(?:[\w*\s{},]+from\s+)|)?['"]([^'"]+)['"]|"""
        r"""require\(\s*['"]([^'"]+)['"]\s*\)|"""
        r"""import\(\s*['"]([^'"]+)['"]\s*\)|"""
        r"""export\s+.*\s+from\s+['"]([^'"]+)['"])"""
    )

    for name, text in content.items():
        if not any(name.endswith(ext) for ext in NODE_EXTENSIONS):
            continue
        clean_text = _strip_js_comments(text)
        for match in import_re.finditer(clean_text):
            specifier = next(s for s in match.groups() if s is not None).strip()
            if not specifier:
                continue
            if specifier.startswith(("./", "../", "/", "#")):
                local.add(specifier)
            elif specifier.startswith("node:"):
                clean_builtin = specifier.removeprefix("node:").split("/")[0]
                builtins.add(clean_builtin)
            elif specifier.split("/")[0] in NODE_BUILTINS:
                builtins.add(specifier.split("/")[0])
            elif specifier in local_names:
                local.add(specifier)
            else:
                pkg = npm_package_name(specifier)
                external.add(pkg)

    manifest.builtin_modules = sorted(builtins)
    manifest.local_modules = sorted(local)
    manifest.third_party_modules = sorted(external)
    manifest.packages = sorted(external)
    manifest.declared_packages = sorted(declared)
    manifest.unmet_modules = sorted(p for p in external if p not in declared)
    return manifest


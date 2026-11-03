"""Extracted local structure; never label co-occurrence or guesses as semantic facts."""

import ast
from pathlib import PurePosixPath

from ai_swe.mcp.files import read_source


def build_graph(repository, paths, allowed_paths=()):
    selected = sorted(set(paths))[:100]
    nodes, edges, errors = [], [], []
    modules = {
        p.removesuffix(".py").replace("/", ".").removeprefix("src."): p
        for p in selected
        if p.endswith(".py")
    }
    file_ids = set(selected)
    for path in selected:
        try:
            source = read_source(repository, path, allowed_paths)
        except (OSError, ValueError, RuntimeError):
            errors.append({"path": path, "reason": "Lectura no disponible o no autorizada"})
            continue
        file_id = "file:" + path
        nodes.append({"id": file_id, "label": path, "kind": "file", "path": path})
        if not path.endswith(".py"):
            continue
        if source["truncated"]:
            errors.append({"path": path, "reason": "Archivo truncado; no se infieren relaciones"})
            continue
        try:
            tree = ast.parse(source["text"])
        except (SyntaxError, RecursionError):
            errors.append({"path": path, "reason": "Python no analizable"})
            continue
        for item in list(ast.walk(tree))[:1000]:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                symbol = f"{path}:{item.lineno}:{item.name}"
                nodes.append(
                    {
                        "id": symbol,
                        "label": item.name,
                        "kind": "symbol",
                        "path": path,
                        "line": item.lineno,
                    }
                )
                edges.append({"source": file_id, "target": symbol, "kind": "defines"})
            imports = []
            if isinstance(item, ast.Import):
                imports = [alias.name for alias in item.names]
            elif isinstance(item, ast.ImportFrom):
                prefix = list(PurePosixPath(path).parent.parts)
                if item.level:
                    prefix = prefix[: len(prefix) - item.level + 1]
                    imports = [
                        ".".join(filter(None, [*prefix, item.module or "", alias.name]))
                        for alias in item.names
                    ]
                    imports.append(".".join(filter(None, [*prefix, item.module or ""])))
                else:
                    imports = [item.module or ""]
            for module in imports:
                target = modules.get(module.removeprefix("src."))
                if target and target in file_ids:
                    edge = {"source": file_id, "target": "file:" + target, "kind": "imports"}
                    if edge not in edges:
                        edges.append(edge)
            if len(nodes) >= 2000 or len(edges) >= 3000:
                break
        if len(nodes) >= 2000 or len(edges) >= 3000:
            break
    existing = {n["id"] for n in nodes}
    return {
        "provenance": "EXTRACTED",
        "engine": "python_ast_local",
        "nodes": nodes,
        "edges": [e for e in edges if e["target"] in existing],
        "errors": errors,
        "truncated": len(paths) > len(selected) or len(nodes) >= 2000,
        "graphify_integrated": False,
    }

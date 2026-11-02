import pytest

from ai_swe.tools.dependency_detector import (
    SourceFile,
    detect_node_dependencies,
    npm_package_name,
)


def test_npm_package_name_resolution():
    assert npm_package_name("express") == "express"
    assert npm_package_name("lodash/debounce") == "lodash"
    assert npm_package_name("@types/node") == "@types/node"
    assert npm_package_name("@angular/core/testing") == "@angular/core"
    assert npm_package_name("   react   ") == "react"


def test_node_builtins_never_executes_code(tmp_path):
    marker = tmp_path / "must-not-run.txt"
    code = f"""
    const fs = require('fs');
    const path = require('node:path');
    import {{ createServer }} from 'node:http';
    import crypto from 'crypto';
    // Malicious statement that should never be executed
    fs.writeFileSync('{str(marker).replace('\\\\', '/')}', 'executed');
    """
    result = detect_node_dependencies([SourceFile("server.js", code)])
    assert not marker.exists(), "El detector estático no debe ejecutar código"
    assert "fs" in result.builtin_modules
    assert "path" in result.builtin_modules
    assert "http" in result.builtin_modules
    assert "crypto" in result.builtin_modules
    assert not result.third_party_modules
    assert not result.errors


def test_node_local_relative_and_subpath_imports():
    files = [
        SourceFile("src/index.ts", "import { helper } from './utils';\nimport config from '../config.json';\nimport '#internal';\n"),
        SourceFile("src/utils.ts", "export const helper = 42;\n"),
        SourceFile("config.json", "{}\n"),
    ]
    result = detect_node_dependencies(files)
    assert not result.third_party_modules
    assert "./utils" in result.local_modules
    assert "../config.json" in result.local_modules
    assert "#internal" in result.local_modules


def test_node_third_party_and_package_json():
    files = [
        SourceFile("index.js", """
            const express = require('express');
            import debounce from 'lodash/debounce';
            import React from 'react';
            import { z } from 'zod';
            import type { Request } from '@types/node';
            import('@tanstack/react-query');
        """),
        SourceFile("package.json", """{
            "dependencies": {
                "express": "^4.18.2",
                "lodash": "^4.17.21",
                "react": "^18.2.0"
            },
            "devDependencies": {
                "@types/node": "^20.0.0"
            }
        }"""),
    ]
    result = detect_node_dependencies(files)
    assert result.has_manifest is True
    assert "express" in result.packages
    assert "lodash" in result.packages
    assert "react" in result.packages
    assert "zod" in result.packages
    assert "@types/node" in result.packages
    assert "@tanstack/react-query" in result.packages

    # Express, lodash, react, and @types/node are declared in package.json.
    # zod and @tanstack/react-query are unmet.
    assert sorted(result.unmet_modules) == ["@tanstack/react-query", "zod"]
    assert result.needs_manifest is True


def test_comments_do_not_produce_false_positives():
    code = """
    // import axios from 'axios';
    /* const moment = require('moment'); */
    import { readFile } from 'fs/promises';
    """
    result = detect_node_dependencies([SourceFile("test.mjs", code)])
    assert "axios" not in result.third_party_modules
    assert "moment" not in result.third_party_modules
    assert not result.third_party_modules
    assert "fs" in result.builtin_modules


def test_security_and_size_limits():
    result = detect_node_dependencies([
        SourceFile("../escape.js", "import x from 'malicious';"),
        SourceFile("normal.js", "const a = 1;"),
    ])
    assert any("Ruta no relativa" in err for err in result.errors)

    oversized = SourceFile("huge.js", "x" * (600 * 1024))
    result2 = detect_node_dependencies([oversized])
    assert any("Archivo demasiado extenso" in err for err in result2.errors)


def test_node_policy_integration():
    from ai_swe.tools.policy import node_dependency_issues

    files = [
        SourceFile("index.js", "import express from 'express'; import axios from 'axios';"),
        SourceFile("package.json", '{"dependencies": {"express": "^4.18.2"}}'),
    ]
    manifest = detect_node_dependencies(files)
    issues = node_dependency_issues(
        manifest,
        allowed_packages=["express"],
        available_modules=["express"],
    )
    # axios is not allowed, and unmet
    assert any("axios' no está en allowed_packages" in i for i in issues)
    assert any("Declara 'axios' en package.json" in i for i in issues)


def test_empty_allowlist_denies_declared_npm_packages():
    from ai_swe.tools.policy import node_dependency_issues

    manifest = detect_node_dependencies([
        SourceFile("package.json", '{"dependencies":{"express":"4.18.2"}}'),
    ])
    assert any("allowed_packages" in issue for issue in node_dependency_issues(manifest, []))


@pytest.mark.parametrize("stage", ["coder", "test_runner"])
@pytest.mark.parametrize("allowed,declared", [([], True), (["other"], True), (["express"], False)])
def test_node_dependency_gate_stops_before_tools(tmp_path, monkeypatch, stage, allowed, declared):
    from test_f8_test_runner import _estado

    from ai_swe.config import Settings
    from ai_swe.contracts import CodeProposal, FileProposal
    from ai_swe.graph import nodes

    state = _estado(tmp_path)
    files = [FileProposal(path="index.js", operation="create", rationale="fixture",
                          new_content="import express from 'express';\n")]
    if declared:
        files.append(FileProposal(path="package.json", operation="create", rationale="fixture",
                                  new_content='{"dependencies":{"express":"4.18.2"}}'))
    proposal = CodeProposal(files=files, rationale="fixture")
    settings = Settings(_env_file=None, allowed_packages=allowed)
    monkeypatch.setattr(nodes, "_entorno_dependencias", lambda *_: (settings, {}))
    monkeypatch.setattr(
        nodes, "ejecutar_target", lambda *a, **k: pytest.fail("No ejecutar herramientas")
    )
    calls = []

    def propose(_):
        calls.append(1)
        return nodes._cambio_desde_propuesta(proposal), state.budget, [], proposal

    monkeypatch.setattr(nodes, "_coder_del_modelo", propose)
    if stage == "coder":
        result = nodes.coder(state)
        assert calls == [1]
        assert result["outputs"].code_proposal == proposal
    else:
        for file in files:
            (tmp_path / file.path).write_text(file.new_content, encoding="utf-8")
        state = state.model_copy(update={"artifacts": state.artifacts.model_copy(
            update={"worktree_path": str(tmp_path)})})
        result = nodes.run_tests(state)
        assert calls == []
    assert result["status"] == "needs_human"
    assert result["next_step"] is None
    assert result["errors"][-1].error_class == "DEPENDENCY_UNAVAILABLE"
    assert not result["errors"][-1].recoverable
    assert state.budget.used_tool_calls == 0

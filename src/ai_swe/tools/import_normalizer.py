"""Normalize I001 in proposal text only; never write files or execute proposed code."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

from ai_swe.contracts import CodeProposal
from ai_swe.tools.policy import normalize_rel_path


def normalize_imports(proposal: CodeProposal) -> tuple[CodeProposal, list[dict]]:
    bundle = getattr(sys, "_ai_swe_bundle", None) or getattr(sys, "_MEIPASS", None)
    command = ([str(Path(bundle) / "tools/ruff.exe")] if bundle
               else [sys.executable, "-m", "ruff"])
    modules = set()
    for file in proposal.files:
        relative = normalize_rel_path(file.path)
        if relative and relative.endswith(".py"):
            parts = Path(relative).with_suffix("").parts
            name = parts[1] if parts[0] == "src" and len(parts) > 1 else parts[0]
            if name.isidentifier():
                modules.add(name)
    files, changes = [], []
    for file in proposal.files:
        before = file.new_content
        relative = normalize_rel_path(file.path)
        if relative and relative.endswith(".py") and before:
            try:
                result = subprocess.run(
                    [*command, "check", "--isolated", "--select", "I001", "--fix",
                     "--config", "lint.isort.known-first-party=" + json.dumps(sorted(modules)),
                     "--stdin-filename", relative, "-"],
                    input=before, capture_output=True, text=True, encoding="utf-8",
                    timeout=10, shell=False,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                if result.returncode == 0 and result.stdout and result.stdout != before:
                    after = result.stdout
                    changes.append({"path": relative, "rule": "I001",
                                    "before_sha256": hashlib.sha256(before.encode()).hexdigest(),
                                    "after_sha256": hashlib.sha256(after.encode()).hexdigest()})
                    file = file.model_copy(update={"new_content": after})
            except (OSError, subprocess.TimeoutExpired):
                # No invented success: unchanged source still faces the real Ruff target.
                pass
        files.append(file)
    return proposal.model_copy(update={"files": files}), changes

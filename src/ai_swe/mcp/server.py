"""Fixed read-only MCP stdio server. stdout contains JSON-RPC messages only."""

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ai_swe.mcp.files import read_source
from ai_swe.tools.policy import DecisionContext, decide

VERSION = "2025-06-18"
TOOLS = [
    {
        "name": "read_file",
        "description": "Lee texto autorizado, máximo 32 KiB.",
        "inputSchema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
            "additionalProperties": False,
        },
    },
    {
        "name": "git_status",
        "description": (
            "Consulta solo HEAD local; no inspecciona archivos ni activa filtros del worktree."
        ),
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
]


def call_tool(root, scope, name, arguments):
    if name == "read_file" and set(arguments) == {"path"} and isinstance(arguments["path"], str):
        return read_source(root, arguments["path"], scope)
    if name == "git_status" and not arguments:
        if (
            decide(name, {}, DecisionContext(run_id="mcp-git", agent="researcher")).effect
            != "allow"
        ):
            raise ValueError("Operación no autorizada.")
        from ai_swe.github_publish import git_environment

        git = shutil.which("git")
        if not git:
            raise ValueError("Git no está disponible.")
        environment = git_environment()
        environment["GIT_NO_LAZY_FETCH"] = "1"
        if "SYSTEMDRIVE" in os.environ:
            environment["SYSTEMDRIVE"] = os.environ["SYSTEMDRIVE"]
        # rev-parse reads references, never working-tree content or clean/smudge filters.
        try:
            result = subprocess.run(
                [git, "--no-pager", "-C", str(root), "rev-parse", "--verify", "HEAD"],
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=3,
                shell=False,
                env=environment,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        except subprocess.TimeoutExpired:
            raise ValueError("La consulta de HEAD superó el plazo.") from None
        head = result.stdout.strip()
        if result.returncode or not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", head):
            raise ValueError("No se pudo consultar HEAD local.")
        return {"head": head, "working_tree_inspected": False, "scope": "head_only"}
    raise ValueError("Herramienta o argumentos no permitidos.")


def serve(root, scope):
    initialized, ready = False, False
    for _ in range(32):
        raw = sys.stdin.buffer.readline(65537)
        if not raw:
            return 0
        if len(raw) > 65536:
            return 2
        identifier = None
        try:
            message = json.loads(raw)
            if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
                raise ValueError("Mensaje JSON-RPC no válido.")
            identifier = message.get("id")
            method = message.get("method")
            params = message.get("params", {})
            if not isinstance(params, dict):
                raise ValueError("Parámetros no válidos.")
            if method == "initialize" and not initialized:
                if not isinstance(params.get("protocolVersion"), str):
                    raise ValueError("Falta la versión MCP solicitada.")
                initialized = True
                result = {
                    "protocolVersion": VERSION,
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "ai-swe-readonly", "version": "0.2.0"},
                }
            elif method == "notifications/initialized" and initialized:
                ready = True
                continue
            elif method == "ping" and initialized:
                result = {}
            elif method == "tools/list" and ready:
                result = {"tools": TOOLS}
            elif method == "tools/call" and ready:
                try:
                    data = call_tool(root, scope, params.get("name"), params.get("arguments", {}))
                    result = {
                        "content": [{"type": "text", "text": json.dumps(data, ensure_ascii=False)}],
                        "isError": False,
                    }
                except (ValueError, OSError, RuntimeError):
                    result = {
                        "content": [
                            {"type": "text", "text": "Lectura no autorizada o no disponible."}
                        ],
                        "isError": True,
                    }
            else:
                raise ValueError("Método no disponible o sesión no inicializada.")
            reply = {"jsonrpc": "2.0", "id": identifier, "result": result}
        except (ValueError, TypeError, AttributeError):
            reply = {
                "jsonrpc": "2.0",
                "id": identifier,
                "error": {"code": -32600, "message": "Solicitud MCP no válida o no permitida."},
            }
        if identifier is not None:
            sys.stdout.buffer.write((json.dumps(reply, ensure_ascii=False) + "\n").encode("utf-8"))
            sys.stdout.buffer.flush()
    return 0


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    try:
        if len(args) != 2:
            return 2
        root = Path(args[0])
        scope = json.loads(args[1])
        if (
            not root.is_absolute()
            or not root.is_dir()
            or str(root).startswith("\\\\")
            or not isinstance(scope, list)
            or len(scope) > 100
            or not all(isinstance(p, str) and len(p) <= 512 for p in scope)
        ):
            return 2
    except (ValueError, OSError, TypeError):
        return 2
    return serve(root, scope)


if __name__ == "__main__":
    sys.dont_write_bytecode = True
    raise SystemExit(main())

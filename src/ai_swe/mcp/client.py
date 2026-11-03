"""Bounded client for the bundled server only; no server command is supplied by a model."""

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

from ai_swe.mcp.server import VERSION
from ai_swe.security import redact


class MCPReadError(ValueError):
    def __init__(self, tool_calls=0):
        super().__init__("MCP local no está disponible; no se amplió el alcance de lectura.")
        self.tool_calls = tool_calls


async def _read_context(root, paths, scope):
    bundle = getattr(sys, "_ai_swe_bundle", None)
    args = [str(Path(root).resolve()), json.dumps(list(scope))]
    if bundle:
        command = [sys.executable, "-B", str(Path(bundle) / "start.py"), "--mcp-server", *args]
    elif getattr(sys, "frozen", False):
        command = [sys.executable, "--mcp-server", *args]
    else:
        command = [sys.executable, "-I", "-B", str(Path(__file__).with_name("server.py")), *args]
    env = {
        k: v
        for k, v in os.environ.items()
        if k.upper() in {"SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "PATH", "TEMP", "TMP"}
    }
    process = await asyncio.create_subprocess_exec(
        *command,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
        env=env,
        cwd=tempfile.gettempdir(),
        limit=262144,
    )

    async def request(identifier, method, params):
        message = {"jsonrpc": "2.0", "method": method, "params": params}
        if identifier is not None:
            message["id"] = identifier
        process.stdin.write((json.dumps(message) + "\n").encode())
        await process.stdin.drain()
        if identifier is None:
            return None
        data = json.loads(await process.stdout.readline())
        if data.get("id") != identifier or "error" in data or data.get("jsonrpc") != "2.0":
            raise ValueError("El servidor MCP no confirmó la operación.")
        return data["result"]

    tool_calls = 0
    try:
        async with asyncio.timeout(10):
            result = await request(
                1,
                "initialize",
                {
                    "protocolVersion": VERSION,
                    "capabilities": {},
                    "clientInfo": {"name": "ai-swe", "version": "0.2.0"},
                },
            )
            if result.get("protocolVersion") != VERSION:
                raise ValueError("Versión MCP incompatible.")
            await request(None, "notifications/initialized", {})
            listed = await request(2, "tools/list", {})
            if {t["name"] for t in listed["tools"]} != {"read_file", "git_status"}:
                raise ValueError("Catálogo MCP inesperado.")
            output = {}
            for identifier, path in enumerate(paths[:5], 3):
                from ai_swe.cancellation import current_cancellation

                control = current_cancellation()
                if control:
                    control.check()
                tool_calls += 1
                result = await request(
                    identifier, "tools/call", {"name": "read_file", "arguments": {"path": path}}
                )
                if result.get("isError"):
                    raise ValueError("MCP rechazó una lectura del contexto.")
                content = json.loads(result["content"][0]["text"])
                if content.get("path") != path or not isinstance(content.get("text"), str):
                    raise ValueError("Respuesta MCP no válida.")
                # The child never receives the parent's registry of literal secrets.
                output[path] = redact(content["text"][:32768])
            process.stdin.close()
            await asyncio.wait_for(process.wait(), 2)
            if process.returncode:
                raise ValueError("El servidor MCP no terminó correctamente.")
            return output
    except (OSError, ValueError, KeyError, TypeError, TimeoutError):
        raise MCPReadError(tool_calls) from None
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()


def read_context(root, paths, scope=()):
    try:
        return asyncio.run(_read_context(root, paths, scope))
    except MCPReadError:
        raise
    except (OSError, ValueError, KeyError, TypeError, TimeoutError, asyncio.LimitOverrunError):
        raise MCPReadError() from None

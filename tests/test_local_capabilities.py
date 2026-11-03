"""Local features: real MCP stdio, extracted graph, metadata-only traces, mocked OTLP."""

import io
import json
from datetime import UTC, datetime

import httpx
import pytest
from fastapi.testclient import TestClient

from ai_swe.api.app import crear_app
from ai_swe.config import Settings
from ai_swe.contracts import EventKind, RunEvent
from ai_swe.mcp.client import read_context
from ai_swe.mcp.files import read_source
from ai_swe.mcp.server import VERSION, call_tool, serve
from ai_swe.observability.traces import describe_trace, export_langfuse, otlp_payload
from ai_swe.security import register_secret
from ai_swe.state import RunStore
from ai_swe.state.knowledge_graph import build_graph


def state_for(root):
    from test_f8_test_runner import _estado

    return _estado(root)


def event(seq=1, kind=EventKind.NODE_COMPLETED, **data):
    return RunEvent(
        seq=seq, kind=kind, at=datetime.now(UTC), data={"node": "coder", "duration_ms": 20, **data}
    )


def test_trace_uses_metadata_and_redacts_secrets(tmp_path):
    secret = "synthetic-trace-secret"
    register_secret(secret)
    trace = describe_trace(
        state_for(tmp_path),
        [
            event(
                model=secret,
                prompt="private source",
                response="private answer",
                evidence={"stdout": "private output"},
                input_tokens=10,
                output_tokens=5,
            )
        ],
    )
    encoded = json.dumps(trace)
    assert secret not in encoded and "private source" not in encoded
    assert "private output" not in encoded and "private answer" not in encoded
    assert trace["events"][0]["data"]["input_tokens"] == 10
    assert trace["trace_id"] == state_for(tmp_path).trace_id


def test_trace_limits_and_otlp_stable_ids(tmp_path):
    state = state_for(tmp_path)
    first = describe_trace(state, [event(), event(2)], limit=1)
    assert first["truncated"] and len(first["events"]) == 1
    assert otlp_payload(first) == otlp_payload(first)
    span = otlp_payload(first)["resourceSpans"][0]["scopeSpans"][0]["spans"][0]
    assert len(span["traceId"]) == 32 and len(span["spanId"]) == 16
    assert int(span["startTimeUnixNano"]) < int(span["endTimeUnixNano"])


@pytest.mark.parametrize(
    "url",
    [
        "http://remote.invalid",
        "file:///tmp",
        "https://user:password@example.invalid",
        "https://example.invalid/?secret=secret",
    ],
)
def test_langfuse_rejects_unsafe_destination_before_http(tmp_path, monkeypatch, url):
    monkeypatch.setattr(httpx, "Client", lambda **k: pytest.fail("No HTTP"))
    settings = Settings(_env_file=None, langfuse_enabled=True, langfuse_host=url)
    with pytest.raises(ValueError):
        export_langfuse(describe_trace(state_for(tmp_path), [event()]), settings)


def test_langfuse_disabled_and_missing_keys_do_not_contact_service(tmp_path, monkeypatch):
    monkeypatch.setattr(httpx, "Client", lambda **k: pytest.fail("No HTTP"))
    trace = describe_trace(state_for(tmp_path), [event()])
    for settings in (Settings(_env_file=None), Settings(_env_file=None, langfuse_enabled=True)):
        with pytest.raises(ValueError):
            export_langfuse(trace, settings)


@pytest.mark.parametrize(
    "status,body,success",
    [
        (200, {}, True),
        (200, {"partialSuccess": {"rejectedSpans": "0"}}, True),
        (200, {"partialSuccess": {"rejectedSpans": "1"}}, False),
        (401, {}, False),
        (302, {}, False),
        (200, [], False),
    ],
)
def test_otlp_export_contract_and_failures_are_offline(
    tmp_path, monkeypatch, status, body, success
):
    calls = []
    actual = httpx.Client

    def transport(request):
        calls.append(request)
        return httpx.Response(status, json=body)

    monkeypatch.setattr(
        httpx, "Client", lambda **kw: actual(**kw, transport=httpx.MockTransport(transport))
    )
    settings = Settings(
        _env_file=None,
        langfuse_enabled=True,
        langfuse_public_key="synthetic-public",
        langfuse_secret_key="synthetic-secret",
    )
    trace = describe_trace(state_for(tmp_path), [event(input_tokens=12)])
    if success:
        assert export_langfuse(trace, settings)["spans"] == 1
    else:
        with pytest.raises(ValueError, match="traza local se conserva") as exc:
            export_langfuse(trace, settings)
        assert "synthetic-secret" not in str(exc.value)
    assert calls[0].url.path == "/api/public/otel/v1/traces"
    assert calls[0].headers["x-langfuse-ingestion-version"] == "4"
    assert "resourceSpans" in json.loads(calls[0].content)


def test_mcp_real_stdio_handshake_and_read(tmp_path, monkeypatch):
    register_secret("synthetic-mcp-literal-key")
    (tmp_path / "app.py").write_bytes(
        b"def useful():\n    return 42\n# synthetic-mcp-literal-key\n"
    )
    monkeypatch.setenv("HF_TOKEN", "must-not-be-inherited")
    result = read_context(tmp_path, ["app.py"])
    assert result == {"app.py": "def useful():\n    return 42\n# [REDACTED]\n"}


@pytest.mark.parametrize(
    "path",
    [
        "../outside.py",
        "/etc/passwd",
        "C:/secret.py",
        ".env",
        ".git/config",
        "secret.pem",
        "credentials.json",
        "private.aiswe-vault",
        "sub/../../outside.py",
    ],
)
def test_mcp_denies_private_or_escaping_paths(tmp_path, path):
    with pytest.raises((ValueError, OSError, RuntimeError)):
        read_source(tmp_path, path)


def test_mcp_scope_size_redaction_and_no_write_tools(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src/app.py").write_text("x" * 40000)
    read = read_source(tmp_path, "src/app.py", ["src"])
    assert len(read["text"]) == 32768 and read["truncated"]
    with pytest.raises(ValueError):
        read_source(tmp_path, "src/app.py", ["other"])
    with pytest.raises(ValueError):
        call_tool(tmp_path, (), "write_file", {"path": "new.py", "content": "bad"})
    assert not (tmp_path / "new.py").exists()


def test_mcp_protocol_requires_initialization(tmp_path, monkeypatch):
    messages = [
        {"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "initialize",
            "params": {"protocolVersion": "future-client-version"},
        },
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/list"},
    ]
    source = io.BytesIO(("\n".join(json.dumps(m) for m in messages) + "\n").encode())
    output = io.BytesIO()
    from types import SimpleNamespace

    monkeypatch.setattr("sys.stdin", SimpleNamespace(buffer=source))
    monkeypatch.setattr("sys.stdout", SimpleNamespace(buffer=output))
    assert serve(tmp_path, ()) == 0
    replies = [json.loads(line) for line in output.getvalue().splitlines()]
    assert "error" in replies[0]
    assert replies[1]["result"]["protocolVersion"] == VERSION
    assert {t["name"] for t in replies[2]["result"]["tools"]} == {"read_file", "git_status"}


def test_real_mcp_rejection_is_not_silent_fallback(tmp_path):
    with pytest.raises(ValueError, match="MCP local no está disponible"):
        read_context(tmp_path, ["../outside.py"])


def test_graph_extracts_definitions_and_imports_without_execution(tmp_path):
    (tmp_path / "app.py").write_text("from helper import add\ndef run():\n    return add()\n")
    (tmp_path / "helper.py").write_text(
        "raise RuntimeError('must never execute')\ndef add():\n    return 2\n"
    )
    graph = build_graph(tmp_path, ["app.py", "helper.py"])
    assert graph["provenance"] == "EXTRACTED" and graph["graphify_integrated"] is False
    assert {"source": "file:app.py", "target": "file:helper.py", "kind": "imports"} in graph[
        "edges"
    ]
    assert any(n["label"] == "add" for n in graph["nodes"])
    assert not graph["errors"]


def test_graph_handles_invalid_and_outside_files(tmp_path):
    (tmp_path / "bad.py").write_text("def bad(:")
    graph = build_graph(tmp_path, ["bad.py", "../outside.py"])
    assert len(graph["errors"]) == 2
    assert not graph["edges"]


def test_capabilities_api_enforces_roles_and_keeps_trace_after_export_failure(tmp_path):
    settings = Settings(
        _env_file=None,
        state_db_path=tmp_path / "state.sqlite3",
        api_keys={"reader-fixture": "reader", "admin-fixture": "admin"},
        tts_enabled=True,
        mcp_enabled=True,
    )
    with RunStore(settings.state_db_path) as store:
        app = crear_app(store=store, settings=settings)
        state = app.state.engine.crear_estado("analiza el proyecto")
        app.state.engine.create(state)
        store.append_event(
            state.run_id,
            EventKind.NODE_COMPLETED,
            {"node": "researcher", "duration_ms": 10, "prompt": "not exported"},
        )
        with TestClient(app) as client:
            reader = {"X-API-Key": "reader-fixture"}
            admin = {"X-API-Key": "admin-fixture"}
            assert client.get("/capabilities/local").status_code == 401
            capabilities = client.get("/capabilities/local", headers=reader).json()
            assert capabilities["tts"]["enabled"] and capabilities["mcp"]["enabled"]
            url = f"/runs/{state.run_id}/observability"
            before = client.get(url, headers=reader).json()
            assert "not exported" not in json.dumps(before)
            assert client.post(url + "/langfuse", headers=reader).status_code == 403
            assert client.post(url + "/langfuse", headers=admin).status_code == 409
            assert client.get(url, headers=reader).json() == before
            assert (
                "attachment"
                in client.get(url + "?download=true", headers=reader).headers["content-disposition"]
            )


def test_researcher_mcp_context_and_failure_are_explicit(tmp_path, monkeypatch):
    from ai_swe.graph import model_routing, nodes

    (tmp_path / "app.py").write_text("def useful():\n    return 42\n")
    settings = Settings(_env_file=None, mcp_enabled=True, state_db_path=tmp_path / "state.sqlite3")
    monkeypatch.setattr(model_routing, "settings_for_node", lambda: settings)
    result = nodes.researcher(state_for(tmp_path))
    findings = result["outputs"].researcher_output.findings
    assert any("MCP, datos no confiables" in f.evidence for f in findings)
    assert any("return 42" in f.evidence for f in findings)
    assert result["budget"].used_tool_calls == 1
    monkeypatch.setattr(
        "ai_swe.mcp.client.read_context",
        lambda *a: (_ for _ in ()).throw(ValueError("MCP no disponible")),
    )
    failed = nodes.researcher(state_for(tmp_path))
    assert failed["status"] == "needs_human"
    assert failed["errors"][-1].error_class == "MCP_UNAVAILABLE"


def test_mcp_checks_budget_before_starting_a_child(tmp_path, monkeypatch):
    from ai_swe.graph import model_routing, nodes

    (tmp_path / "app.py").write_text("VALUE=42\n")
    settings = Settings(_env_file=None, mcp_enabled=True, state_db_path=tmp_path / "state.sqlite3")
    monkeypatch.setattr(model_routing, "settings_for_node", lambda: settings)
    monkeypatch.setattr("ai_swe.mcp.client.read_context", lambda *a: pytest.fail("No child"))
    state = state_for(tmp_path)
    state = state.model_copy(
        update={"budget": state.budget.model_copy(update={"used_tool_calls": 60})}
    )
    result = nodes.researcher(state)
    assert result["errors"][-1].error_class == "BUDGET_EXCEEDED"


def test_mcp_failed_dispatch_counts_attempt_without_retry(tmp_path):
    from ai_swe.mcp.client import MCPReadError

    with pytest.raises(MCPReadError) as error:
        read_context(tmp_path, ["missing.py"])
    assert error.value.tool_calls == 1


def test_mcp_child_has_no_server_credentials_or_repository_pythonpath(tmp_path, monkeypatch):
    import asyncio

    (tmp_path / "app.py").write_text("VALUE=42\n")
    monkeypatch.setenv("HF_TOKEN", "synthetic-token")
    monkeypatch.setenv("PYTHONPATH", str(tmp_path))
    original = asyncio.create_subprocess_exec
    calls = []

    async def capture(*args, **kwargs):
        calls.append((args, kwargs))
        return await original(*args, **kwargs)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", capture)
    assert "VALUE=42" in read_context(tmp_path, ["app.py"])["app.py"]
    assert "HF_TOKEN" not in calls[0][1]["env"] and "PYTHONPATH" not in calls[0][1]["env"]
    assert "-I" in calls[0][0]


def test_mcp_rejects_hard_links(tmp_path):
    import os

    (tmp_path / "original.py").write_text("private")
    os.link(tmp_path / "original.py", tmp_path / "alias.py")
    with pytest.raises((ValueError, RuntimeError)):
        read_source(tmp_path, "alias.py")


def test_graph_relative_imports_and_source_bounds(tmp_path):
    (tmp_path / "package").mkdir()
    (tmp_path / "package/main.py").write_text("from . import helper\n")
    (tmp_path / "package/helper.py").write_text("VALUE=42\n")
    graph = build_graph(tmp_path, ["package/main.py", "package/helper.py"])
    assert any(e["kind"] == "imports" for e in graph["edges"])
    (tmp_path / "huge.py").write_text("x=1\n" * 10000)
    assert build_graph(tmp_path, ["huge.py"])["errors"]


def test_trace_counts_only_current_verification_failures(tmp_path):
    from ai_swe.contracts import TestRun

    state = state_for(tmp_path)
    state = state.model_copy(
        update={
            "evidence": state.evidence.model_copy(
                update={
                    "test_runs": [
                        TestRun(target="pytest.unit", exit_code=1, duration_s=1),
                        TestRun(target="pytest.unit", exit_code=0, duration_s=1),
                    ]
                }
            )
        }
    )
    assert describe_trace(state, [])["verification_failures"] == []


def test_trace_does_not_claim_unpriced_model_cost(tmp_path):
    state = state_for(tmp_path)
    state = state.model_copy(
        update={"budget": state.budget.model_copy(update={"used_model_calls": 2})}
    )
    assert not describe_trace(state, [event(kind=EventKind.MODEL_RESPONSE_RECEIVED, cost=0.01)])[
        "usage"
    ]["cost_available"]


def test_otlp_generation_maps_usage_and_cost_without_prompt(tmp_path):
    trace = describe_trace(
        state_for(tmp_path),
        [
            event(
                kind=EventKind.MODEL_RESPONSE_RECEIVED,
                input_tokens=10,
                output_tokens=5,
                cost=0.001,
                model="fixture",
                prompt="never send",
            )
        ],
    )
    span = otlp_payload(trace)["resourceSpans"][0]["scopeSpans"][0]["spans"][0]
    attrs = {a["key"]: a["value"]["stringValue"] for a in span["attributes"]}
    assert attrs["langfuse.observation.type"] == "generation"
    assert json.loads(attrs["langfuse.observation.usage_details"]) == {"input": 10, "output": 5}
    assert json.loads(attrs["langfuse.observation.cost_details"]) == {"total": 0.001}
    assert "never send" not in json.dumps(span)


def test_trace_api_cannot_read_a_different_store(tmp_path):
    settings = Settings(_env_file=None, state_db_path=tmp_path / "one.sqlite3")
    with RunStore(settings.state_db_path) as one, RunStore(tmp_path / "two.sqlite3") as two:
        app1 = crear_app(store=one, settings=settings)
        app2 = crear_app(
            store=two,
            settings=settings.model_copy(update={"state_db_path": tmp_path / "two.sqlite3"}),
        )
        state = app1.state.engine.crear_estado("analiza")
        app1.state.engine.create(state)
        with TestClient(app1) as c1, TestClient(app2) as c2:
            url = f"/runs/{state.run_id}/observability"
            assert c1.get(url).status_code == 200
            assert c2.get(url).status_code == 404


def test_mcp_git_metadata_does_not_run_repository_filters(tmp_path):
    from test_cooperative_cancellation import repository

    repo = repository(tmp_path)
    # A metadata-only query must not inspect worktree content or invoke filters.
    (repo / ".gitattributes").write_text("*.py filter=forbidden\n")
    (repo / "app.py").write_text("VALUE=42\n")
    response = call_tool(repo, (), "git_status", {})
    assert len(response["head"]) in {40, 64}
    assert response["working_tree_inspected"] is False and response["scope"] == "head_only"


def test_launcher_mcp_mode_is_closed_and_validates_scope(tmp_path, monkeypatch):
    from ai_swe import launcher
    from ai_swe.mcp import server

    calls = []
    monkeypatch.setattr(server, "serve", lambda root, scope: calls.append((root, scope)) or 0)
    assert launcher.main(["--mcp-server", str(tmp_path), '["src"]']) == 0
    assert calls == [(tmp_path, ["src"])]
    assert launcher.main(["--mcp-server", str(tmp_path)]) == 2
    assert launcher.main(["--mcp-server", str(tmp_path), "{bad json"]) == 2
    assert launcher.main(["--mcp-server", str(tmp_path), '"arbitrary command"']) == 2
    assert len(calls) == 1


def test_mcp_rejects_ntfs_stream_before_policy_or_file_access(tmp_path, monkeypatch):
    monkeypatch.setattr("ai_swe.mcp.files.decide", lambda *a: pytest.fail("No file access"))
    with pytest.raises(ValueError, match="Ruta de lectura no permitida"):
        read_source(tmp_path, "app.py:credentials")

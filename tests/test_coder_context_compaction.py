from test_f6_real_coder import _estado, _propuesta

from ai_swe.contracts import Finding
from ai_swe.graph import nodes
from ai_swe.models import FakeModelAdapter, ModelGateway


def prompt(state, monkeypatch):
    fake = FakeModelAdapter(structured=_propuesta())
    monkeypatch.setattr(nodes, "_GATEWAY", ModelGateway([fake]))
    nodes._coder_del_modelo(state)
    assert fake.calls[0].messages[0].content == nodes.PROMPT_CODIFICACION
    return fake.calls[0].messages[1].content


def test_repetitions_do_not_evict_distinct_findings_or_change_audit(monkeypatch):
    state = _estado()
    important = Finding(
        severity="high",
        path="auth.py",
        explanation="Revisar permisos",
        evidence="unique_authorization_evidence",
    )
    repeated = Finding(
        severity="info",
        path="app.py",
        explanation="Archivo presente",
        evidence="repeated_inventory_evidence",
    )
    state.evidence.findings = [important] + [repeated] * 25
    before = state.evidence.model_dump_json()
    text = prompt(state, monkeypatch)
    assert "unique_authorization_evidence" in text
    assert text.count("repeated_inventory_evidence") == 1
    assert state.evidence.model_dump_json() == before


def test_code_excerpt_is_sent_once_and_distinct_warnings_remain(monkeypatch):
    state = _estado()
    code = "--- inicio app.py ---\ndef task_critical_function():\n    return 42\n--- fin ---"
    state.evidence.findings = [
        Finding(severity="info", path="app.py", explanation="Archivo presente", evidence=code),
        Finding(
            severity="high",
            path="app.py",
            explanation="No perder esta advertencia",
            evidence="critical_warning_evidence",
        ),
    ]
    text = prompt(state, monkeypatch)
    assert text.count("def task_critical_function()") == 1
    assert "critical_warning_evidence" in text and "No perder esta advertencia" in text
    assert "ver bloque de código" in text


def test_same_path_different_evidence_and_secret_redaction_are_preserved(monkeypatch):
    state = _estado()
    secret = "hf_" + "z" * 35
    state.evidence.findings = [
        Finding(
            severity="high",
            path="app.py",
            explanation="Primera revisión",
            evidence="warning_one " + secret,
        ),
        Finding(
            severity="high", path="app.py", explanation="Segunda revisión", evidence="warning_two"
        ),
    ]
    text = prompt(state, monkeypatch)
    assert "warning_one" in text and "warning_two" in text
    assert secret not in text and "[REDACTED]" in text
    state.evidence.findings[0].evidence = "x" * 111 + " " + secret
    assert secret[:8] not in prompt(state, monkeypatch)

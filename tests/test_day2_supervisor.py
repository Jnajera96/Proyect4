"""The supervisor records opaque JUnit bytes, never interpreting XML entities."""
import hashlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools import verify_day2_resilience as supervisor


@pytest.mark.parametrize("xml", [
    b'<testsuites><testsuite tests="1" failures="0"/></testsuites>',
    b'<!DOCTYPE x [<!ENTITY leak SYSTEM "file:///must-not-be-read">]><x>&leak;</x>',
    b'<!DOCTYPE x [<!ENTITY a "expansion"><!ENTITY b "&a;&a;&a;">]><x>&b;</x>',
])
def test_junit_is_hashed_without_parsing_or_resolving_entities(tmp_path, monkeypatch, xml):
    output = tmp_path / "evidence"
    monkeypatch.setattr(sys, "argv", ["verify_day2_resilience", str(output)])
    monkeypatch.setattr(supervisor.subprocess, "check_output", lambda *a, **kw: "fixed-head\n")
    monkeypatch.setattr(supervisor.tempfile, "mkdtemp", lambda **kw: str(tmp_path / "owned-temp"))
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        assert kwargs["timeout"] == 180
        junit = Path(next(arg.split("=", 1)[1] for arg in command if arg.startswith("--junitxml=")))
        junit.write_bytes(xml)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(supervisor.subprocess, "run", run)
    assert supervisor.main() == 0
    report = json.loads((output / "report.json").read_text(encoding="utf-8"))
    assert report["success"] is True
    assert report["junit_sha256"] == hashlib.sha256(xml).hexdigest()
    assert report["junit_report"] == str(output / "results.xml")
    assert "suites" not in report
    assert len(calls) == 1

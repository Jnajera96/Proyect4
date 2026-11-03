import os
from types import SimpleNamespace

from test_f8_test_runner import repo as repo
from test_f8_test_runner import sandbox as sandbox

from ai_swe.tools.runner import _entorno, ejecutar


def test_real_child_does_not_inherit_server_credentials(sandbox, monkeypatch):
    secrets = ["HF_TOKEN", "AI_SWE_HF_TOKEN", "OPENAI_API_KEY", "CUSTOM_DATABASE_PASSWORD"]
    for name in secrets:
        monkeypatch.setenv(name, "synthetic-secret-not-a-real-token")
    test = sandbox.raiz / "tests/test_no_server_credentials.py"
    test.write_text(
        "import os\ndef test_no_credentials():\n"
        f"    present = [key for key in {secrets!r} if key in os.environ]\n"
        "    assert not present, 'Unexpected credential names: ' + ', '.join(present)\n",
        encoding="utf-8",
    )
    result = ejecutar(sandbox, "pytest.unit", permitidos=("pytest.unit",), timeout=30,
        network_egress_enabled=True)
    assert result.exit_code == 0, result.stderr + result.stdout
    assert "synthetic-secret-not-a-real-token" not in result.stdout + result.stderr


def test_parent_python_controls_and_pytest_injection_are_not_forwarded(sandbox, monkeypatch):
    for name in ("PYTHONHOME", "PYTHONPATH", "PYTEST_ADDOPTS", "PYTEST_PLUGINS", "HTTP_PROXY"):
        monkeypatch.setenv(name, "parent-only-value")
    environment = _entorno(sandbox)
    assert environment["PYTHONPATH"] == str(sandbox.raiz / "src")
    assert environment["PYTHONDONTWRITEBYTECODE"] == "1"
    assert "parent-only-value" not in environment.values()
    assert "PATH" in environment and "PATH" in os.environ


def test_no_src_does_not_restore_parent_pythonpath(tmp_path, monkeypatch):
    monkeypatch.setenv("PYTHONPATH", "parent-repository-source")
    environment = _entorno(SimpleNamespace(raiz=tmp_path))
    assert "PYTHONPATH" not in environment
    assert environment["PYTHONDONTWRITEBYTECODE"] == "1"

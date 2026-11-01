import os
import subprocess

import pytest

from ai_swe.contracts import FileChange, FileProposal
from ai_swe.tools.dependency_detector import (
    SourceFile,
    detect_python_dependencies,
    repository_files,
)
from ai_swe.tools.policy import dependency_issues


def test_standard_library_only_never_executes_code(tmp_path):
    marker = tmp_path / "must-not-exist"
    result = detect_python_dependencies([SourceFile("app.py",
        "import os, sys, json, sqlite3\nfrom http.server import HTTPServer\n"
        "from urllib.request import urlopen\n"
        f"open({str(marker)!r}, 'w').write('executed')\n")])
    assert result.third_party_modules == [] and not marker.exists()
    assert result.stdlib_modules == ["http", "json", "os", "sqlite3", "sys", "urllib"]


def test_local_absolute_relative_and_src_namespace_imports():
    result = detect_python_dependencies([
        SourceFile("src/application/main.py",
                   "from application.utils import add\nfrom . import utils\n"),
        SourceFile("src/application/utils.py", "from .internal import helper\n"),
        SourceFile("utils/calculator.py", "def add(a,b): return a+b\n"),
        SourceFile("main.py", "from utils.calculator import add\n"),
        SourceFile("test_main.py", "from src.application.utils import add\n"),
    ])
    assert not result.third_party_modules
    assert {"application", "internal", "src", "utils"} <= set(result.local_modules)


def test_third_party_aliases_requirements_and_versions(tmp_path, monkeypatch):
    result = detect_python_dependencies([
        SourceFile("app.py", "import fastapi, uvicorn, yaml, dotenv, PIL, bs4\n"),
        SourceFile("requirements.txt",
                   "fastapi>=0.1\nuvicorn\nPyYAML\npython-dotenv\npillow\nbeautifulsoup4\n"),
    ])
    assert result.has_manifest and not result.unmet_modules
    assert result.packages == ["beautifulsoup4", "fastapi", "pillow", "python-dotenv",
                               "pyyaml", "uvicorn"]
    assert "pyyaml\n" in result.canonical_requirements
    from types import SimpleNamespace

    from ai_swe.tools.dependency_detector import installed_modules

    (tmp_path / "yaml.py").write_text("raise AssertionError('Must not import dependency')\n")
    distribution = SimpleNamespace(version="6.0.3", locate_file=lambda _: tmp_path)
    monkeypatch.setattr("importlib.metadata.distribution", lambda _: distribution)
    assert installed_modules(["yaml", "pyyaml"]) == {"yaml": "6.0.3"}


def test_manifest_is_suggested_not_written_and_file_change_does_not_invent_content(tmp_path):
    result = detect_python_dependencies([SourceFile("app.py", "import requests\n")])
    assert result.needs_manifest and result.unmet_modules == ["requests"]
    assert result.canonical_requirements == "requests\n"
    assert not (tmp_path / "requirements.txt").exists()
    unknown = detect_python_dependencies([FileChange(path="app.py", added=1, removed=0,
                                                   sha256="a" * 64)])
    assert unknown.errors and not unknown.third_party_modules
    assert dependency_issues(unknown, [], {})


@pytest.mark.parametrize("text", ["-r other.txt", "--index-url https://example.invalid",
                                  "requests @ https://example.invalid/wheel.whl", "-e ."])
def test_remote_or_indirect_requirements_are_not_authorized(text):
    result = detect_python_dependencies([SourceFile("requirements.txt", text)])
    assert result.errors and dependency_issues(result, ["requests"], {"requests": "2.0"})


def test_policy_separates_authorized_declared_available_and_version_compatible():
    manifest = detect_python_dependencies([SourceFile("app.py", "import yaml\n"),
                                           SourceFile("requirements.txt", "pyyaml>=6\n")])
    assert dependency_issues(manifest, [], {"yaml": "6.0.3"})
    assert dependency_issues(manifest, ["pyyaml"], {})
    assert dependency_issues(manifest, ["pyyaml"], {"yaml": "5.0"})
    assert not dependency_issues(manifest, ["PyYAML"], {"yaml": "6.0.3"})
    tool = detect_python_dependencies([SourceFile("test_app.py", "import pytest\n")])
    assert not dependency_issues(tool, [], {"pytest": "9.1.1"})


def test_existing_repository_modules_are_merged_with_proposal(tmp_path):
    (tmp_path / "helper.py").write_text("def add(a,b): return a+b\n")
    (tmp_path / ".env").write_text("synthetic secret")
    proposal = FileProposal(path="main.py", operation="create", rationale="test",
                            new_content="from helper import add\n")
    manifest = detect_python_dependencies(repository_files(tmp_path, [proposal]))
    assert manifest.local_modules == ["helper"] and not manifest.third_party_modules


def test_fake_coder_dependency_failure_escalates_once(tmp_path, monkeypatch):
    from test_cooperative_cancellation import repository, settings_for
    from test_project_builder_pipeline import BuilderAdapter, project_files

    from ai_swe.contracts import RunOptions
    from ai_swe.graph import RunEngine, model_routing
    from ai_swe.models import ModelGateway
    from ai_swe.state import RunStore

    files = project_files("calendar")
    files["external.py"] = "import requests\n"
    adapter = BuilderAdapter(files)
    monkeypatch.setattr(model_routing, "gateway_from_settings", lambda _: ModelGateway([adapter]))
    settings = settings_for(tmp_path)
    with RunStore(settings.state_db_path) as store:
        engine = RunEngine(store, settings=settings)
        state = engine.crear_estado("crea un calendario", options=RunOptions(
            repo_path=str(repository(tmp_path))))
        assert engine.start(state).status == "awaiting_human_requirements_confirmation"
        result = engine.resume(state.run_id, "approved")
        assert result.status == "needs_human" and len(adapter.calls) == 1
        assert not result.evidence.test_runs
        assert any(e.error_class == "DEPENDENCY_UNAVAILABLE" for e in result.errors)
        assert result.budget.used_model_calls == 1
        assert "allowed_packages" in " ".join(m.content for m in adapter.calls[0].messages)
    files["requirements.txt"] = "requests\n"
    files["external.py"] = "import requests\n\ndef version():\n    return requests.__version__\n"
    files["test_calendar.py"] += ("\n\ndef test_requests_version():\n"
                                  "    from external import version\n\n    assert version()\n")
    adapter = BuilderAdapter(files)
    settings = settings.model_copy(update={"allowed_packages": ["requests"]})
    adapter = BuilderAdapter({**files, "test_extra.py": "def test_extra():\n    assert True\n"})
    with RunStore(settings.state_db_path) as store:
        engine = RunEngine(store, settings=settings)
        limited = engine.crear_estado("crea un calendario", options=state.options)
        engine.start(limited)
        result = engine.resume(limited.run_id, "approved")
        assert result.status == "needs_human" and len(adapter.calls) == 1
        assert any("limites de 10" in error.message for error in result.errors)
    adapter = BuilderAdapter(files)
    with RunStore(settings.state_db_path) as store:
        engine = RunEngine(store, settings=settings)
        allowed = engine.crear_estado("crea un calendario", options=state.options)
        engine.start(allowed)
        result = engine.resume(allowed.run_id, "approved")
        assert result.status == "awaiting_approval", result.errors
        assert result.evidence.test_runs and all(t.passed for t in result.evidence.test_runs)
        assert len(adapter.calls) == 2


def test_launch_guide_and_batch_warn_without_importing_application(tmp_path, monkeypatch):
    from test_launch_guide import promoted

    from ai_swe.launch_guide import describe, launcher_bytes, prepare

    state = promoted(tmp_path, "main.py", "from fastapi import FastAPI\napp = FastAPI()\n")
    monkeypatch.setattr("ai_swe.tools.dependency_detector.installed_modules", lambda _: {})
    guide = describe(state)
    assert guide.missing_modules == ["fastapi", "uvicorn"]
    assert guide.available and "requirements.txt" in " ".join(guide.instructions)
    assert guide.suggested_requirements == "fastapi\nuvicorn\n"
    assert not (tmp_path / "application/iniciar.bat").exists()
    prepared = prepare(state)
    text = launcher_bytes(prepared).decode("utf-8")
    assert "-I -c" in text and "exit /b 1" in text
    assert "pip install -r requirements.txt" in text
    assert (tmp_path / "application/iniciar.bat").read_bytes() == text.encode("utf-8")


@pytest.mark.skipif(os.name != "nt", reason="Windows batch execution")
def test_missing_dependency_batch_stops_before_application_code(tmp_path):
    from test_launch_guide import promoted

    from ai_swe.launch_guide import prepare

    state = promoted(tmp_path, "main.py", "import aiswe_nonexistent_dependency_fixture\n"
                     "from pathlib import Path\nPath('executed.txt').write_text('unsafe')\n")
    guide = prepare(state)
    result = subprocess.run([os.environ["COMSPEC"], "/d", "/c", guide.launcher_path],
                            input=b"", capture_output=True, timeout=15, cwd=guide.repo_path)
    assert result.returncode == 1
    assert b"Faltan dependencias" in result.stdout
    assert b"Traceback" not in result.stderr
    assert not (tmp_path / "application/executed.txt").exists()
    second = tmp_path / "second"
    (second / "application/src").mkdir(parents=True)
    (second / "application/src/helper.py").write_text("VALUE = 42\n")
    state = promoted(second, "src/main.py", "from helper import VALUE\nfrom pathlib import Path\n"
                     "if __name__ == '__main__':\n"
                     "    Path('executed.txt').write_text(str(VALUE))\n")
    guide = prepare(state)
    result = subprocess.run([os.environ["COMSPEC"], "/d", "/c", guide.launcher_path],
                            input=b"", capture_output=True, timeout=15, cwd=guide.repo_path)
    assert result.returncode == 0, result.stderr
    assert (second / "application/executed.txt").read_text() == "42"


def test_dynamic_missing_dependency_stops_without_loop(tmp_path, monkeypatch):
    from test_cooperative_cancellation import repository, settings_for
    from test_project_builder_pipeline import BuilderAdapter, project_files

    from ai_swe.contracts import RunOptions
    from ai_swe.graph import RunEngine, model_routing
    from ai_swe.models import ModelGateway
    from ai_swe.state import RunStore

    files = project_files("calendar")
    files["test_dynamic.py"] = ("import importlib\ndef test_dynamic():\n"
                                "    importlib.import_module('aiswe_missing_dynamic_fixture')\n")
    adapter = BuilderAdapter(files)
    monkeypatch.setattr(model_routing, "gateway_from_settings", lambda _: ModelGateway([adapter]))
    with RunStore(settings_for(tmp_path).state_db_path) as store:
        engine = RunEngine(store, settings=settings_for(tmp_path))
        state = engine.crear_estado("crea un calendario", options=RunOptions(
            repo_path=str(repository(tmp_path))))
        engine.start(state)
        result = engine.resume(state.run_id, "approved")
        assert result.status == "needs_human" and len(adapter.calls) == 1
        assert len(result.evidence.test_runs) == 1
        assert result.evidence.test_runs[0].exit_code != 0
        assert any(e.error_class == "DEPENDENCY_UNAVAILABLE" for e in result.errors)


def test_unsafe_requirements_do_not_offer_installation_command(tmp_path, monkeypatch):
    from test_launch_guide import promoted

    from ai_swe.launch_guide import describe

    state = promoted(tmp_path, "main.py", "import requests\n")
    (tmp_path / "application/requirements.txt").write_text("requests @ https://example.invalid/x")
    monkeypatch.setattr("ai_swe.tools.dependency_detector.installed_modules", lambda _: {})
    guide = describe(state)
    assert not guide.installation_command
    assert not any("pip install" in line for line in guide.instructions)


@pytest.mark.skipif(not os.environ.get("AI_SWE_TEST_DOCKER_IMAGE") or os.name != "nt",
                    reason="Opt-in local Docker image required")
@pytest.mark.parametrize("forged_inventory", [False, True])
def test_real_docker_rejects_missing_modules_even_with_forged_inventory(
    tmp_path, monkeypatch, forged_inventory,
):
    from types import SimpleNamespace

    from ai_swe.tools.docker_runner import DockerSession, DockerSettings
    from ai_swe.tools.runner import RunnerError, ejecutar

    module = "aiswe_missing_offline_dependency"
    (tmp_path / "test_app.py").write_text(f"import {module}\n")
    original_ready, original_run = DockerSession.ready, DockerSession.run
    created = []

    def ready(self, policy):
        result = original_ready(self, policy)
        if forged_inventory:
            result[module] = "1.0"
        return result

    def observe(self, arguments, **kwargs):
        if arguments[:2] == ["container", "create"]:
            created.append(1)
        return original_run(self, arguments, **kwargs)

    monkeypatch.setattr(DockerSession, "ready", ready)
    monkeypatch.setattr(DockerSession, "run", observe)
    with pytest.raises(RunnerError) as raised:
        ejecutar(SimpleNamespace(raiz=tmp_path), "pytest.unit", permitidos=("pytest.unit",),
                 docker=DockerSettings(image=os.environ["AI_SWE_TEST_DOCKER_IMAGE"]))
    assert raised.value.operacion == "dependencias"
    assert bool(created) == forged_inventory

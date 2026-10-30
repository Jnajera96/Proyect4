import hashlib
import os
import subprocess
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from ai_swe.api import crear_app
from ai_swe.config import Settings
from ai_swe.contracts import Artifacts, FileChange, Instruction, RunOptions, RunState
from ai_swe.contracts.state import PromotionReceipt
from ai_swe.launch_guide import describe, prepare


def promoted(tmp_path, filename="index.html", text="<html>Aplicación</html>"):
    root = tmp_path / "application"
    root.mkdir(exist_ok=True)
    (root / filename).write_bytes(text.encode())
    now = datetime.now(UTC)
    return RunState(
        run_id="launch-test",
        trace_id="launch-test",
        created_at=now,
        updated_at=now,
        status="completed",
        instruction=Instruction(text="Crea una aplicación", source="text", confirmed_by_user=True),
        options=RunOptions(repo_path=str(root)),
        artifacts=Artifacts(
            changed_files=[
                FileChange(
                    path=filename,
                    added=1,
                    removed=0,
                    sha256=hashlib.sha256(text.encode()).hexdigest(),
                )
            ]
        ),
        promotion_receipt=PromotionReceipt(
            receipt_id="receipt",
            pre_promotion_sha="base",
            promoted_sha="result",
            head="base",
            paths=[filename],
        ),
    )


def test_html_read_is_pure_and_prepare_is_idempotent(tmp_path):
    state = promoted(tmp_path)
    guide = describe(state)
    assert guide.kind == "web_static" and guide.launch_action == "open_browser"
    launcher = tmp_path / "application/iniciar.bat"
    assert not launcher.exists()
    assert prepare(state).prepared
    before = launcher.read_bytes()
    assert prepare(state).prepared and launcher.read_bytes() == before
    assert b"index.html" in before and b"TOKEN" not in before


@pytest.mark.parametrize(
    ("text", "kind"),
    [
        ("if __name__ == '__main__':\n    print('Hola')\n", "python_cli"),
        ("from fastapi import FastAPI\napp = FastAPI()\n", "fastapi"),
    ],
)
def test_python_discovery_does_not_import_or_execute(tmp_path, text, kind):
    state = promoted(tmp_path, "app.py", text)
    guide = prepare(state)
    assert guide.kind == kind and guide.launch_action == "run_command"
    assert "python" in guide.command.lower()


@pytest.mark.skipif(os.name != "nt", reason="Windows batch launcher")
def test_prepared_cli_batch_runs_on_windows(tmp_path):
    state = promoted(
        tmp_path,
        "app.py",
        """from pathlib import Path
if __name__ == '__main__':
    Path('result.txt').write_text('started', encoding='utf-8')
""",
    )
    guide = prepare(state)
    result = subprocess.run(
        [os.environ["COMSPEC"], "/d", "/c", guide.launcher_path],
        input=b"",
        capture_output=True,
        timeout=15,
        cwd=guide.repo_path,
        env={
            key: value
            for key, value in os.environ.items()
            if key.upper() in {"SYSTEMROOT", "WINDIR", "PATH", "TEMP", "TMP"}
        },
    )
    assert result.returncode == 0, result.stderr.decode(errors="replace")
    assert (tmp_path / "application/result.txt").read_text() == "started"


def test_library_is_not_falsely_presented_as_executable(tmp_path):
    guide = describe(promoted(tmp_path, "calculator.py", "def add(a,b):\n    return a+b\n"))
    assert not guide.available and guide.kind == "python_library"


def test_existing_launcher_and_changed_code_are_preserved(tmp_path):
    state = promoted(tmp_path)
    launcher = tmp_path / "application/iniciar.bat"
    launcher.write_bytes(b"my own launcher")
    with pytest.raises(ValueError, match="Ya existe"):
        prepare(state)
    assert launcher.read_bytes() == b"my own launcher"
    (tmp_path / "application/index.html").write_text("modified")
    with pytest.raises(ValueError, match="cambiaron"):
        describe(state)


def test_modified_javascript_dependency_blocks_launch(tmp_path):
    state = promoted(tmp_path)
    script = tmp_path / "application/app.js"
    script.write_text("console.log('reviewed')", encoding="utf-8")
    state.artifacts.changed_files.append(
        FileChange(
            path="app.js",
            added=1,
            removed=0,
            sha256=hashlib.sha256(script.read_bytes()).hexdigest(),
        )
    )
    script.write_text("console.log('changed after review')", encoding="utf-8")
    with pytest.raises(ValueError, match="cambiaron"):
        prepare(state)
    assert not (script.parent / "iniciar.bat").exists()


def test_get_cannot_write_and_reader_cannot_prepare(tmp_path, monkeypatch):
    state = promoted(tmp_path)
    settings = Settings(
        _env_file=None,
        profile_mode=False,
        state_db_path=tmp_path / "api.sqlite3",
        api_keys={"reader-fixture": "reader", "operator-fixture": "operator"},
    )
    app = crear_app(settings=settings)
    monkeypatch.setattr(app.state.engine, "get", lambda _: state)
    with TestClient(app) as client:
        assert client.get("/runs/launch-test/launch-guide").status_code == 401
        response = client.get(
            "/runs/launch-test/launch-guide", headers={"X-API-Key": "reader-fixture"}
        )
        assert response.status_code == 200
        assert not (tmp_path / "application/iniciar.bat").exists()
        assert (
            client.post(
                "/runs/launch-test/launch-guide/prepare", headers={"X-API-Key": "reader-fixture"}
            ).status_code
            == 403
        )
        assert (
            client.post(
                "/runs/launch-test/launch-guide/prepare", headers={"X-API-Key": "operator-fixture"}
            ).status_code
            == 200
        )

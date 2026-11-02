"""Round-trip real proposals without changing their UTF-8 bytes or EOF semantics."""

import ast
import hashlib
import subprocess

import pytest
from test_f7_sandbox import repo as repo
from test_f7_sandbox import sandbox as sandbox

from ai_swe.contracts import CodeProposal, FileProposal
from ai_swe.graph.nodes import _cambio_desde_propuesta, _contar_desde_diff, _diff_unificado
from ai_swe.tools.patcher import _contenido_de, aplicar


@pytest.mark.parametrize("ending", ["", "\n", "\r\n"])
def test_multifile_roundtrip_preserves_exact_bytes(sandbox, ending):
    files = {
        "calculator.py": ('import math\n\ndef tangent(a):\n'
                          '    """Tangente en radianes."""\n    return math.tan(a)'),
        "test_calculator.py": ("from calculator import tangent\n\ndef test_zero():\n"
                               "    assert tangent(0) == 0"),
        "index.html": ("<!doctype html>\n<!-- Calculadora científica -->\n"
                       "<title>Calculadora</title>"),
    }
    files = {path: text.replace("\n", "\r\n" if ending == "\r\n" else "\n") + ending
             for path, text in files.items()}
    proposal = CodeProposal(rationale="fixture", files=[
        FileProposal(path=path, operation="create", rationale="fixture", new_content=text)
        for path, text in files.items()
    ])
    change = _cambio_desde_propuesta(proposal)
    assert change.diff.endswith("\n")
    assert change.diff.count("\n--- /dev/null\n") == 2
    assert change.diff.count("\\ No newline at end of file\n") == (3 if not ending else 0)
    assert _contenido_de(change) == files
    result = aplicar(sandbox, change)
    assert result.ok and set(result.aplicados) == set(files), result
    for item in change.files_changed:
        data = (sandbox.raiz / item.path).read_bytes()
        assert data == files[item.path].encode("utf-8")
        assert hashlib.sha256(data).hexdigest() == item.sha256
        if item.path.endswith(".py"):
            ast.parse(data.decode("utf-8"))


@pytest.mark.parametrize("old,new", [("a = 1", "a = 2\n"), ("a = 1\n", "a = 2"),
                                    ("a = 1", "a = 2")])
def test_eof_marker_applies_to_correct_side_and_git_accepts_diff(repo, old, new):
    (repo / "value.py").write_bytes(old.encode())
    file = FileProposal(path="value.py", operation="modify", rationale="fixture", new_content=new)
    change = _cambio_desde_propuesta(CodeProposal(files=[file], rationale="fixture"),
                                    contenidos_previos={"value.py": old})
    checked = subprocess.run(["git", "apply", "--check", "-"], cwd=repo,
                             input=change.diff.encode(), capture_output=True)
    assert checked.returncode == 0, checked.stderr
    assert _contenido_de(change)["value.py"] == new
    assert _contar_desde_diff(change.diff) == (1, 1)


def test_empty_file_is_created_and_delete_remains_distinct(sandbox):
    file = FileProposal(path="empty.py", operation="create", rationale="fixture", new_content="")
    change = _cambio_desde_propuesta(CodeProposal(files=[file], rationale="fixture"))
    assert aplicar(sandbox, change).ok
    assert (sandbox.raiz / "empty.py").read_bytes() == b""
    deleted = FileProposal(path="empty.py", operation="delete", rationale="fixture")
    assert _diff_unificado(deleted).endswith("\n")
    deleted_change = _cambio_desde_propuesta(CodeProposal(files=[deleted], rationale="fixture"))
    assert _contenido_de(deleted_change) == {
        "empty.py": None
    }


def test_written_bytes_must_match_proposal_hash(sandbox, monkeypatch):
    original = type(sandbox).escribir

    def corrupt(self, path, content):
        destination = original(self, path, content)
        destination.write_bytes(destination.read_bytes() + b"# corrupted\n")
        return destination

    monkeypatch.setattr(type(sandbox), "escribir", corrupt)
    file = FileProposal(path="value.py", operation="create", rationale="fixture",
                        new_content="a = 1\n")
    change = _cambio_desde_propuesta(CodeProposal(files=[file], rationale="fixture"))
    result = aplicar(sandbox, change)
    assert not result.ok and not result.aplicados
    assert result.fallos["value.py"] == (
        "Corrupción de parche: el SHA-256 escrito no coincide con la propuesta"
    )


@pytest.mark.parametrize("ending", ["", "\n", "\r\n"])
def test_promotion_preserves_bytes_under_autocrlf(sandbox, ending):
    from ai_swe.tools.promoter import promover

    subprocess.run(["git", "config", "core.autocrlf", "true"],
                   cwd=sandbox.repo_original, check=True, capture_output=True)
    content = "value = 42" + ending
    proposal = CodeProposal(rationale="fixture", files=[FileProposal(
        path="value.py", operation="create", rationale="fixture", new_content=content,
    )])
    change = _cambio_desde_propuesta(proposal)
    assert aplicar(sandbox, change).ok
    assert promover(sandbox, repo_autorizado=sandbox.repo_original,
                    expected_diff=sandbox.diff()).applied
    assert (sandbox.repo_original / "value.py").read_bytes() == content.encode()

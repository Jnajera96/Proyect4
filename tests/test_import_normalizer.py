import hashlib

from ai_swe.contracts import CodeProposal
from ai_swe.tools.import_normalizer import normalize_imports


def proposal(content, path="test_calculator.py"):
    return CodeProposal(files=[dict(path=path, operation="create", new_content=content,
                                   rationale="prueba")], rationale="Prueba de normalizacion")


def test_imports_normalized_in_memory_with_hashes_and_no_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    text = ("import pytest\nfrom calculator import subtract, add\n\n\n"
            "def test_add():\n    assert add(1, 2) == 3\n")
    initial = proposal(text)
    initial.files.append(proposal("def add(a, b):\n    return a + b\n", "calculator.py").files[0])
    result, records = normalize_imports(initial)
    assert initial.files[0].new_content == text
    assert "import pytest\n\nfrom calculator import add, subtract" in result.files[0].new_content
    assert records[0]["before_sha256"] == hashlib.sha256(text.encode()).hexdigest()
    expected_hash = hashlib.sha256(result.files[0].new_content.encode()).hexdigest()
    assert records[0]["after_sha256"] == expected_hash
    assert list(tmp_path.iterdir()) == []
    assert normalize_imports(result)[1] == []


def test_no_semantic_fix_or_test_success_is_fabricated():
    text = "def f():\n    return undefined_name\n"
    result, records = normalize_imports(proposal(text, "app.py"))
    assert result.files[0].new_content == text
    assert records == []


def test_invalid_syntax_and_non_python_are_preserved():
    for text, path in [("def broken(:\n", "app.py"), ("import z\nimport a\n", "README.md")]:
        result, records = normalize_imports(proposal(text, path))
        assert result.files[0].new_content == text
        assert records == []


def test_missing_formatter_preserves_source(monkeypatch):
    import ai_swe.tools.import_normalizer as normalizer

    def unavailable(*args, **kwargs):
        raise OSError("unavailable")

    monkeypatch.setattr(normalizer.subprocess, "run", unavailable)
    initial = proposal("import z\nimport a\n")
    result, records = normalize_imports(initial)
    assert result == initial
    assert records == []

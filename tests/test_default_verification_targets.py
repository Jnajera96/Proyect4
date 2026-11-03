from ai_swe.config import Settings
from ai_swe.sandbox import Sandbox
from ai_swe.tools.runner import ejecutar


def test_defaults_discover_local_tests_without_requiring_optional_marker(tmp_path):
    settings = Settings(_env_file=None)
    assert settings.allowed_test_targets == ["pytest.unit", "ruff.check"]
    explicit = Settings(_env_file=None, allowed_test_targets=["pytest.integration"])
    assert explicit.allowed_test_targets == ["pytest.integration"]
    (tmp_path / "test_math.py").write_text("def test_math():\n    assert 2 + 2 == 4\n")
    sandbox = Sandbox(raiz=tmp_path, repo_original=tmp_path, base_commit="",
                      run_id="targets", creado_por_nosotros=False)
    unit = ejecutar(sandbox, "pytest.unit", permitidos=settings.allowed_test_targets,
        network_egress_enabled=True)
    assert unit.exit_code == 0, unit.stdout + unit.stderr
    integration = ejecutar(sandbox, "pytest.integration", permitidos=explicit.allowed_test_targets,
        network_egress_enabled=True)
    assert integration.exit_code == 5  # Absence is never rewritten to PASS.


def test_empty_project_still_fails_default_pytest(tmp_path):
    sandbox = Sandbox(raiz=tmp_path, repo_original=tmp_path, base_commit="",
                      run_id="empty", creado_por_nosotros=False)
    assert ejecutar(sandbox, "pytest.unit", permitidos=["pytest.unit"],
        network_egress_enabled=True).exit_code == 5

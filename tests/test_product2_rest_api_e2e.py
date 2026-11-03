"""Full fixed-product REST E2E: actual runner, human gates, promotion and destination tests."""

from tools.verify_product2_rest_api_e2e import run_product2_verification


def test_product2_rest_api_e2e():
    report = run_product2_verification()
    assert report["stages"] == [
        "awaiting_human_requirements_confirmation",
        "awaiting_approval",
        "completed",
    ]
    assert report["http_statuses_asserted"] == [200, 201, 404, 422]
    assert report["model"]["roles"] == ["coder", "reviewer"]
    assert report["model"]["paid_spend_usd"] == 0
    assert report["network"]["guard_negative_probe_passed"]
    assert len(report["artifacts"]) == 4

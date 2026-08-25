import re

from sentinel.models import SentinelCheckResult, SentinelFinding, SentinelRun


def test_model_serialization_is_json_safe():
    check = SentinelCheckResult(
        check_id="runtime",
        name="Sentinel Runtime",
        category="runtime",
        status="healthy",
        message="Python 3.11+ is available.",
        evidence={"python_version": "3.11.0"},
    )
    finding = SentinelFinding(
        finding_id="f-001",
        severity="medium",
        title="Minor warning",
        description="A local check reported a warning.",
        affected_component="Sentinel foundation",
        evidence={"detail": "non-critical"},
        recommendation="Keep monitoring.",
        status="warning",
    )
    run = SentinelRun(overall_status="healthy", checks=[check], findings=[finding])

    payload = run.to_dict()
    assert payload["run_id"].startswith("SEN-")
    assert payload["checks"][0]["status"] == "healthy"
    assert payload["findings"][0]["status"] == "warning"


def test_run_id_generation_format():
    run = SentinelRun()
    assert re.fullmatch(r"SEN-\d{6}", run.run_id)

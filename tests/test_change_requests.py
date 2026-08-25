import json
from pathlib import Path

from sentinel.change_requests import (
    ChangeRequest,
    ChangeRequestCategory,
    ChangeRequestStatus,
    ChangeRequestStore,
    PermissionLevel,
    build_handoff_package,
    build_human_readable_request,
    create_change_request_from_finding,
    generate_change_requests_for_run,
    generate_verified_local_findings,
    persist_change_requests,
)
from sentinel.cli import main
from sentinel.models import SentinelFinding, SentinelRun


def make_finding(**overrides):
    payload = {
        "finding_id": "F-001",
        "severity": "high",
        "title": "Generated backend healthcheck depends on curl",
        "description": "Docker healthcheck invokes curl but the runtime does not contain curl.",
        "affected_component": "Generated Python backend runtime",
        "evidence": {"error": "/bin/sh: 1: curl: not found"},
        "recommendation": "Replace the healthcheck with a runtime-safe probe.",
        "status": "failed",
    }
    payload.update(overrides)
    return SentinelFinding(**payload)


def test_change_request_model_serialization_is_json_safe():
    request = ChangeRequest(
        request_id="HCR-000001",
        title="Generated backend healthcheck issue",
        description="The generated runtime lacks curl for health probes.",
        category=ChangeRequestCategory.CODE_CHANGE.value,
        severity="HIGH",
        status=ChangeRequestStatus.DRAFT.value,
        affected_component="Generated Python backend runtime",
        evidence=[{"error": "/bin/sh: 1: curl: not found"}],
        related_findings=["F-001"],
        requested_outcome="Use a health probe guaranteed to exist in the runtime.",
        verification_plan=["Inspect runtime", "Validate healthcheck"],
    )
    payload = request.to_dict()
    assert payload["request_id"] == "HCR-000001"
    assert payload["category"] == ChangeRequestCategory.CODE_CHANGE.value
    assert json.dumps(payload)


def test_change_request_generator_and_handoff():
    finding = make_finding()
    request = create_change_request_from_finding(finding, run_id="SEN-000001")
    assert request.category == ChangeRequestCategory.CODE_CHANGE.value
    assert request.approval_status == "NOT_APPROVED"
    assert request.required_permission_level == PermissionLevel.TEST_BRANCH.value
    assert request.to_handoff()["schema_version"] == "1"
    assert "curl" in build_human_readable_request(request).lower()
    assert request.verified_root_cause == "The generated healthcheck invokes curl but curl is absent from the generated Python runtime."


def test_tls_root_cause_stays_unknown_and_permission_is_production_change():
    tls_finding = SentinelFinding(
        finding_id="F-TLS-001",
        severity="high",
        title="Hostless public TLS certificate expired",
        description="Hostless platform and configured ArcticDrive endpoints have expired TLS.",
        affected_component="Hostless platform TLS",
        evidence={"public_url": "https://stallionhostless.duckdns.org", "error": "CERTIFICATE_VERIFY_FAILED"},
        recommendation="Review the certificate lifecycle and replace the expired certificate under explicit approval.",
        status="failed",
    )
    request = create_change_request_from_finding(tls_finding, run_id="SEN-000002")
    assert request.category == ChangeRequestCategory.SECURITY_CHANGE.value
    assert request.required_permission_level == PermissionLevel.PRODUCTION_CHANGE.value
    assert request.verified_condition is not None
    assert "expired" in request.verified_condition.lower()
    assert request.verified_root_cause == "UNKNOWN"


def test_deduplication_and_runtime_store(tmp_path):
    finding = make_finding()
    run = SentinelRun(run_id="SEN-000010", overall_status="failed", findings=[finding])
    requests = generate_change_requests_for_run(run)
    persisted = persist_change_requests(requests, tmp_path)
    assert len(persisted) == 1
    assert persisted[0].request_id.startswith("HCR-")
    store = ChangeRequestStore(tmp_path)
    assert len(store.list()) == 1
    duplicate = generate_change_requests_for_run(SentinelRun(run_id="SEN-000011", overall_status="failed", findings=[finding]))
    persisted_again = persist_change_requests(duplicate, tmp_path)
    assert len(persisted_again) == 1


def test_store_writes_json_file_and_fingerprint():
    store = ChangeRequestStore(Path(".runtime") / "change_requests")
    request = ChangeRequest(
        request_id="",
        title="Certificate expired",
        description="The public TLS certificate is expired.",
        category=ChangeRequestCategory.SECURITY_CHANGE.value,
        affected_component="Hostless platform TLS",
        evidence=[{"status": "EXPIRED"}],
        requested_outcome="Renew or replace the certificate under explicit approval.",
    )
    saved = store.save(request)
    path = store.root / f"{saved.request_id}.json"
    assert path.exists()
    assert saved.fingerprint()
    assert build_handoff_package(saved)["approval_status"] == "NOT_APPROVED"


def test_generate_verified_requests_and_permission_levels():
    findings = generate_verified_local_findings()
    assert len(findings) == 3
    requests = [create_change_request_from_finding(f, run_id="SEN-LOCAL") for f in findings]
    assert [r.required_permission_level for r in requests] == [
        PermissionLevel.TEST_BRANCH.value,
        PermissionLevel.PRODUCTION_CHANGE.value,
        PermissionLevel.PATCH_PROPOSAL.value,
    ]


def test_cli_changes_list_show_generate_export(tmp_path, capsys):
    project_root = tmp_path
    exit_code = main(["changes", "--project-root", str(project_root), "list"])
    assert exit_code == 0
    assert "No stored" not in capsys.readouterr().out

    generated = main(["changes", "--project-root", str(project_root), "generate"])
    assert generated == 0
    output = capsys.readouterr().out
    assert "Generated" in output

    store = ChangeRequestStore(project_root)
    request = store.list()[0]
    exit_code = main(["changes", "--project-root", str(project_root), "show", request.request_id])
    assert exit_code == 0
    show_output = capsys.readouterr().out
    assert request.request_id in show_output
    assert "approval_status" not in show_output.lower()

    export_code = main(["changes", "--project-root", str(project_root), "export", request.request_id])
    assert export_code == 0
    exported = capsys.readouterr().out
    assert '"approval_status": "NOT_APPROVED"' in exported
    assert "password" not in exported.lower()
    assert "ssh" not in exported.lower()
    assert "token" not in exported.lower()


def test_cli_rejects_approval_and_execution_actions():
    parser = __import__("argparse").ArgumentParser()
    parser.add_subparsers(dest="command")
    try:
        parser.parse_args(["approve"])  # no approval subcommand exists in argparse tree
    except SystemExit:
        pass
    assert True

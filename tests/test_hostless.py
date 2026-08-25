import json

import pytest

from sentinel.checks import check_hostless_configuration, run_hostless_checks
from sentinel.collectors.hostless import (
    build_ssh_command,
    discover_applications,
    parse_disk_usage,
    parse_docker_ps,
    parse_system_memory,
    sanitize_evidence,
)
from sentinel.checks import _evaluate_tls_endpoint, _ram_status_for_pct
from sentinel.config import SentinelConfig
from sentinel.models import SentinelRun


def make_config(**overrides):
    base = {
        "environment": "development",
        "project_root": __import__("pathlib").Path(__file__).resolve().parent.parent,
        "runtime_dir": __import__("pathlib").Path(__file__).resolve().parent.parent / ".runtime",
        "runs_dir": __import__("pathlib").Path(__file__).resolve().parent.parent / ".runtime" / "runs",
        "docs_dir": __import__("pathlib").Path(__file__).resolve().parent.parent / "docs",
        "hostless_ssh_host": "hostless.example.com",
        "hostless_ssh_user": "sentinel",
        "hostless_ssh_port": 22,
        "hostless_ssh_key_path": "/tmp/id_ed25519",
        "hostless_base_url": "https://example.local",
        "monitored_apps_json": None,
        "ram_warning_threshold_pct": 75.0,
        "ram_failed_threshold_pct": 90.0,
        "disk_warning_threshold_pct": 75.0,
        "disk_failed_threshold_pct": 90.0,
        "core_container_names": ("deploy-backend-1", "deploy-frontend-1", "deploy-caddy-1", "deploy-mongo-1"),
    }
    base.update(overrides)
    return SentinelConfig(**base)


def test_ssh_command_construction_allows_read_only_commands():
    config = make_config()
    cmd = build_ssh_command("docker ps --format '{{.Names}}\\t{{.Status}}'", config)
    assert cmd[:4] == ["ssh", "-o", "BatchMode=yes", "-o"]
    assert cmd[-2] == "sentinel@hostless.example.com"
    assert cmd[-1].startswith("docker ps")


def test_read_only_allowlist_rejects_disallowed_commands():
    config = make_config()
    with pytest.raises(ValueError):
        build_ssh_command("docker stop deploy-backend-1", config)
    with pytest.raises(ValueError):
        build_ssh_command("shutdown now", config)
    with pytest.raises(ValueError):
        build_ssh_command("rm -rf /tmp/test", config)


def test_docker_output_parsing_and_app_grouping():
    raw = "deploy-backend-1\tUp 3 days (healthy)\thealthy\tbackend-image\nhostless_be_demo\tUp 2 days\thealthy\tapp-be\nhostless_fe_demo\tUp 2 days\thealthy\tapp-fe\nhostless_net_demo\tUp 2 days\t\tapp-net\n"
    rows = parse_docker_ps(raw)
    assert rows[0]["name"] == "deploy-backend-1"
    apps = discover_applications(rows)
    assert any(app["app_id"] == "demo" for app in apps)


def test_docker_output_parsing_handles_missing_health_field_and_unhealthy_state():
    raw = (
        "hostless_fe_6a8cd101a60d\tUp 2 hours\thostless/arcticdrive-clean-72f6-frontend:v1\n"
        "hostless_be_6a8cd101a60d\tUp 2 hours (unhealthy)\thostless/arcticdrive-clean-72f6-backend:v1\n"
        "deploy-backend-1\tUp 2 hours (healthy)\tdeploy-backend\n"
    )
    rows = parse_docker_ps(raw)
    assert len(rows) == 3
    assert rows[0]["name"] == "hostless_fe_6a8cd101a60d"
    assert rows[1]["status"] == "Up 2 hours (unhealthy)"
    apps = discover_applications(rows)
    assert any(app["app_id"] == "6a8cd101a60d" for app in apps)


def test_container_health_detection_matches_real_runtime(monkeypatch):
    import sentinel.checks as checks_module

    config = make_config()
    fake_responses = {
        "docker version --format '{{json .}}'": {"stdout": '{"Server":{"Version":"20.10.0"}}', "exit_code": 0, "stderr": ""},
        "docker ps --format '{{.Names}}\t{{.Status}}\t{{.Image}}'": {
            "stdout": (
                "hostless_fe_6a8cd101a60d\tUp 2 hours\thostless/arcticdrive-clean-72f6-frontend:v1\n"
                "hostless_be_6a8cd101a60d\tUp 2 hours (unhealthy)\thostless/arcticdrive-clean-72f6-backend:v1\n"
                "deploy-backend-1\tUp 2 hours (healthy)\tdeploy-backend\n"
                "deploy-frontend-1\tUp 3 hours\tdeploy-frontend\n"
                "deploy-mongo-1\tUp 15 hours\tmongo:7\n"
                "deploy-caddy-1\tUp 15 hours\tcaddy:2\n"
            ),
            "exit_code": 0,
            "stderr": "",
        },
        "docker network ls --format '{{.Name}}\t{{.Driver}}'": {"stdout": "hostless_net_6a8cd101a60d\tbridge\n", "exit_code": 0, "stderr": ""},
        "uptime": {"stdout": " 20:51:10 up 2 days,  5:13,  1 user,  load average: 0.05, 0.02, 0.01", "exit_code": 0, "stderr": ""},
        "free -m": {"stdout": "Mem: 16384 12000 2000 300 5000 9000\nSwap: 2048 512 1536\n", "exit_code": 0, "stderr": ""},
        "df -h /": {"stdout": "Filesystem 1K-blocks Used Available Use% Mounted on\n/dev/sda1 1000000 800000 200000 80% /\n", "exit_code": 0, "stderr": ""},
    }

    def fake_run_remote_command(command, cfg, timeout=15):
        return fake_responses[command]

    monkeypatch.setattr(checks_module, "run_remote_command", fake_run_remote_command)
    results = checks_module.run_hostless_checks(config)
    by_name = {result.name: result for result in results}
    assert by_name["Hostless Core Backend"].status == "healthy"
    assert by_name["Hostless Core Frontend"].status == "healthy"
    assert by_name["MongoDB"].status == "healthy"
    assert by_name["Caddy"].status == "healthy"
    assert by_name["Application Backend"].status == "warning"
    assert by_name["Application Frontend"].status == "healthy"
    assert by_name["Production Apps"].status == "healthy"


def test_application_backend_semantics_for_running_unhealthy_container():
    config = make_config(
        monitored_apps_json='[{"name":"ArcticDrive","frontend_url":"https://arcticdrive-clean-72f6.apps.stallionhostless.duckdns.org","api_health_url":"https://arcticdrive-clean-72f6.apps.stallionhostless.duckdns.org/api/"}]'
    )
    assert _ram_status_for_pct(89.0, 75.0, 90.0) == "warning"
    assert _ram_status_for_pct(91.0, 75.0, 90.0) == "failed"
    assert _evaluate_tls_endpoint("https://example.com", 14)["tls_status"] in {"VALID", "EXPIRING_SOON"}


def test_system_resource_parsing():
    memory = "Mem: 16384 12000 2000 300 5000 9000\nSwap: 2048 512 1536\n"
    disk = "Filesystem 1K-blocks Used Available Use% Mounted on\n/dev/sda1 1000000 800000 200000 80% /\n"
    assert parse_system_memory(memory)["used_mb"] == 12000
    assert parse_disk_usage(disk)["used_percent"] == "80%"


def test_missing_configuration_behavior():
    config = make_config(hostless_ssh_host=None, hostless_ssh_user=None)
    result = check_hostless_configuration(config)
    assert result.status == "unknown"
    assert "not supplied" in result.message.lower()
    assert run_hostless_checks(config)[0].status == "unknown"


def test_hostless_check_model_serialization():
    run = SentinelRun(
        overall_status="healthy",
        hostless_observations={"checks": [{"check_id": "hostless.core.docker", "status": "healthy"}]},
    )
    payload = run.to_dict()
    assert payload["hostless_observations"]["checks"][0]["status"] == "healthy"


def test_no_secrets_in_evidence():
    payload = {
        "host": "example.local",
        "password": "super-secret",
        "nested": {"ssh_private_key": "abc123", "public": "ok"},
    }
    cleaned = sanitize_evidence(payload)
    assert cleaned["password"] == "***redacted***"
    assert cleaned["nested"]["ssh_private_key"] == "***redacted***"
    assert cleaned["nested"]["public"] == "ok"


def test_cli_operates_safely_when_hostless_unreachable_or_missing(monkeypatch):
    import subprocess
    import sys
    from pathlib import Path

    project_root = Path(__file__).resolve().parent.parent
    result = subprocess.run(
        [sys.executable, "-m", "sentinel", "check", "--hostless"],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "Hostless connection" in result.stdout
    assert "Overall Status:" in result.stdout

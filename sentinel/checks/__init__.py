from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

from sentinel.collectors.hostless import (
    build_ssh_command,
    discover_applications,
    parse_disk_usage,
    parse_docker_ps,
    parse_hostless_docker_json,
    parse_network_ls,
    parse_system_memory,
    run_remote_command,
    sanitize_evidence,
)
from sentinel.config import load_config
from sentinel.models import SentinelCheckResult, SentinelFinding, SentinelRun, utc_now_iso


def _normalize_status(status: str) -> str:
    return status.lower() if status else "unknown"


def _overall_status_for(checks: list[SentinelCheckResult]) -> str:
    if any(check.status == "failed" for check in checks):
        return "failed"
    if any(check.status == "warning" for check in checks):
        return "warning"
    if any(check.status == "unknown" for check in checks):
        return "unknown"
    return "healthy"


def check_runtime() -> SentinelCheckResult:
    version = sys.version_info
    is_healthy = version >= (3, 11)
    return SentinelCheckResult(
        check_id="runtime",
        name="Sentinel Runtime",
        category="runtime",
        status="healthy" if is_healthy else "failed",
        message=(
            "Python 3.11+ is available for the Sentinel foundation."
            if is_healthy
            else "Python 3.11+ is required."
        ),
        evidence={"python_version": f"{version.major}.{version.minor}.{version.micro}"},
    )


def check_configuration() -> SentinelCheckResult:
    config = load_config()
    return SentinelCheckResult(
        check_id="configuration",
        name="Configuration",
        category="config",
        status="healthy",
        message="Environment-based Sentinel configuration loaded successfully.",
        evidence={
            "environment": config.environment,
            "runtime_dir": str(config.runtime_dir),
            "docs_dir": str(config.docs_dir),
            "hostless_ssh_host": config.hostless_ssh_host,
            "hostless_base_url": config.hostless_base_url,
        },
    )


def check_documentation() -> SentinelCheckResult:
    config = load_config()
    docs_root = config.docs_dir
    required_files = {
        "internal": [
            "README.md",
            "CHANGELOG.md",
            "FINDINGS.md",
            "INCIDENTS.md",
            "COMPATIBILITY.md",
        ],
        "ai": [
            "SYSTEM_CONTEXT.md",
            "ACTIVE_ISSUES.md",
            "RESOLVED_ISSUES.md",
            "ARCHITECTURE.md",
            "TROUBLESHOOTING_HISTORY.md",
        ],
        "public": [
            "README.md",
            "CAPABILITIES.md",
            "SUPPORTED_APPS.md",
            "KNOWN_ISSUES.md",
            "ROADMAP.md",
        ],
    }
    missing = []
    for stream, names in required_files.items():
        stream_dir = docs_root / stream
        if not stream_dir.exists():
            missing.append(f"{stream_dir}")
            continue
        for name in names:
            if not (stream_dir / name).exists():
                missing.append(str(stream_dir / name))
    status = "healthy" if not missing else "failed"
    return SentinelCheckResult(
        check_id="documentation",
        name="Documentation",
        category="documentation",
        status=status,
        message=(
            "Required Sentinel documentation files are present."
            if not missing
            else "Required documentation files are missing."
        ),
        evidence={
            "docs_root": str(docs_root),
            "missing_files": missing,
        },
    )


def check_runtime_dir_writable() -> SentinelCheckResult:
    config = load_config()
    runtime_dir = config.runtime_dir
    runtime_dir.mkdir(parents=True, exist_ok=True)
    test_path = runtime_dir / ".sentinel-write-test"
    try:
        test_path.write_text("ok", encoding="utf-8")
        test_path.unlink(missing_ok=True)
        status = "healthy"
        message = "Sentinel runtime directory is writable for local logs and output."
    except OSError as exc:
        status = "failed"
        message = f"Sentinel runtime directory is not writable: {exc}"
    return SentinelCheckResult(
        check_id="runtime_writable",
        name="Runtime Directory",
        category="runtime",
        status=status,
        message=message,
        evidence={"runtime_dir": str(runtime_dir)},
    )


def check_hostless_configuration() -> SentinelCheckResult:
    config = load_config()
    if not config.hostless_configured:
        return SentinelCheckResult(
            check_id="hostless.connection",
            name="Hostless connection",
            category="hostless",
            status="unknown",
            message="Hostless SSH configuration not supplied.",
            evidence={"configured": False, "ssh_host": config.hostless_ssh_host, "ssh_user": config.hostless_ssh_user},
        )
    return SentinelCheckResult(
        check_id="hostless.connection",
        name="Hostless connection",
        category="hostless",
        status="healthy",
        message="Hostless SSH configuration is present.",
        evidence={"configured": True, "ssh_host": config.hostless_ssh_host, "ssh_user": config.hostless_ssh_user},
    )


def run_hostless_checks(config=None) -> list[SentinelCheckResult]:
    config = config or load_config()
    if not config.hostless_configured:
        return [check_hostless_configuration()]

    try:
        docker_version = run_remote_command("docker version --format '{{json .}}'", config, timeout=15)
        docker_ps = run_remote_command("docker ps --format '{{.Names}}\t{{.Status}}\t{{.Health}}\t{{.Image}}'", config, timeout=15)
        docker_networks = run_remote_command("docker network ls --format '{{.Name}}\t{{.Driver}}'", config, timeout=15)
        system_uptime = run_remote_command("uptime", config, timeout=15)
        system_memory = run_remote_command("free -m", config, timeout=15)
        disk_usage = run_remote_command("df -h /", config, timeout=15)
    except Exception as exc:  # pragma: no cover - exercised through mocked remote execution in tests
        return [
            SentinelCheckResult(
                check_id="hostless.connection",
                name="Hostless connection",
                category="hostless",
                status="failed",
                message=f"Unable to reach Hostless over SSH: {exc}",
                evidence={"configured": True, "ssh_host": config.hostless_ssh_host, "error": str(exc)},
            )
        ]

    container_rows = parse_docker_ps(docker_ps.get("stdout", ""))
    container_lookup = {row["name"]: row for row in container_rows}
    network_rows = parse_network_ls(docker_networks.get("stdout", ""))
    network_names = [row["name"] for row in network_rows]
    apps = discover_applications(container_rows)

    checks: list[SentinelCheckResult] = []
    checks.append(
        SentinelCheckResult(
            check_id="hostless.connection",
            name="Hostless connection",
            category="hostless",
            status="healthy" if docker_version.get("exit_code") == 0 else "failed",
            message="Hostless SSH connection was reachable and responded to a read-only Docker command." if docker_version.get("exit_code") == 0 else "Hostless SSH connection did not respond successfully.",
            evidence=sanitize_evidence({
                "configured": True,
                "ssh_host": config.hostless_ssh_host,
                "ssh_user": config.hostless_ssh_user,
                "exit_code": docker_version.get("exit_code"),
                "stderr": docker_version.get("stderr"),
            }),
        )
    )

    docker_engine_status = "healthy" if docker_version.get("exit_code") == 0 else "failed"
    checks.append(
        SentinelCheckResult(
            check_id="hostless.core.docker",
            name="Docker Engine",
            category="hostless",
            status=docker_engine_status,
            message="Docker Engine is reachable." if docker_engine_status == "healthy" else "Docker Engine is not reachable.",
            evidence=sanitize_evidence({
                "docker_version": parse_hostless_docker_json(docker_version.get("stdout", "")),
                "exit_code": docker_version.get("exit_code"),
                "stderr": docker_version.get("stderr"),
            }),
        )
    )

    def status_for_container(target_name: str, label: str) -> SentinelCheckResult:
        row = container_lookup.get(target_name)
        if not row:
            return SentinelCheckResult(
                check_id=f"hostless.core.{label.lower()}",
                name=label,
                category="hostless",
                status="failed",
                message=f"{label} container {target_name} was not found.",
                evidence={"container": target_name, "observed_containers": [item["name"] for item in container_rows]},
            )
        status = "healthy" if "up" in row.get("status", "").lower() else "failed"
        return SentinelCheckResult(
            check_id=f"hostless.core.{label.lower()}",
            name=label,
            category="hostless",
            status=status,
            message=f"{label} container {target_name} is running." if status == "healthy" else f"{label} container {target_name} is not running.",
            evidence=sanitize_evidence({
                "container": target_name,
                "state": row.get("status"),
                "health": row.get("health"),
                "image": row.get("image"),
            }),
        )

    target_containers = {
        "backend": config.core_container_names[0],
        "frontend": config.core_container_names[1],
        "mongodb": config.core_container_names[3],
        "caddy": config.core_container_names[2],
    }
    checks.append(status_for_container(target_containers["backend"], "Hostless Backend"))
    checks.append(status_for_container(target_containers["frontend"], "Hostless Frontend"))
    checks.append(status_for_container(target_containers["mongodb"], "MongoDB"))
    checks.append(status_for_container(target_containers["caddy"], "Caddy"))

    if config.hostless_base_url:
        try:
            req = urllib.request.Request(config.hostless_base_url, method="GET")
            with urllib.request.urlopen(req, timeout=10) as response:
                payload = {"status": response.status, "url": config.hostless_base_url, "latency_ms": None}
                status = "healthy" if response.status < 400 else "failed"
                message = "Public Hostless URL responded successfully." if status == "healthy" else "Public Hostless URL responded with an error status."
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            payload = {"status": "unreachable", "url": config.hostless_base_url, "error": str(exc)}
            status = "failed"
            message = f"Public Hostless URL check failed: {exc}"
        checks.append(
            SentinelCheckResult(
                check_id="hostless.public.url",
                name="Public Hostless URL",
                category="hostless",
                status=status,
                message=message,
                evidence=sanitize_evidence(payload),
            )
        )

    memory = parse_system_memory(system_memory.get("stdout", ""))
    ram_total = float(memory["total_mb"])
    ram_used = float(memory["used_mb"])
    ram_pct = (ram_used / ram_total * 100.0) if ram_total else 0.0
    ram_status = "healthy" if ram_pct < config.ram_warning_threshold_pct else "warning" if ram_pct < config.ram_failed_threshold_pct else "failed"
    checks.append(
        SentinelCheckResult(
            check_id="hostless.system.ram",
            name="RAM",
            category="hostless",
            status=ram_status,
            message=f"RAM usage is {ram_pct:.1f}%.",
            evidence=sanitize_evidence({
                "total_mb": ram_total,
                "used_mb": ram_used,
                "available_mb": memory.get("available_mb"),
                "used_percent": round(ram_pct, 2),
            }),
        )
    )

    disk = parse_disk_usage(disk_usage.get("stdout", ""))
    disk_pct = float(disk["used_percent"].rstrip("%")) if str(disk["used_percent"]).endswith("%") else float(disk["used_percent"])
    disk_status = "healthy" if disk_pct < config.disk_warning_threshold_pct else "warning" if disk_pct < config.disk_failed_threshold_pct else "failed"
    checks.append(
        SentinelCheckResult(
            check_id="hostless.system.disk",
            name="Disk",
            category="hostless",
            status=disk_status,
            message=f"Disk usage is {disk_pct:.1f}%.",
            evidence=sanitize_evidence({
                "filesystem": disk.get("filesystem"),
                "total_mb": disk.get("total_mb"),
                "used_mb": disk.get("used_mb"),
                "available_mb": disk.get("available_mb"),
                "used_percent": disk_pct,
            }),
        )
    )

    checks.append(
        SentinelCheckResult(
            check_id="hostless.networks",
            name="Core Docker Network",
            category="hostless",
            status="healthy" if network_names else "warning",
            message="Docker networks were discovered." if network_names else "No Docker networks were discovered.",
            evidence=sanitize_evidence({
                "networks": network_names,
                "caddy_connected": [name for name in network_names if name.startswith("caddy")],
                "mongo_connected": [name for name in network_names if name.startswith("mongo")],
            }),
        )
    )

    checks.append(
        SentinelCheckResult(
            check_id="hostless.applications",
            name="Production Apps",
            category="hostless",
            status="healthy" if apps else "warning",
            message=f"Discovered {len(apps)} Hostless application group(s)." if apps else "No Hostless application groups were discovered from container naming patterns.",
            evidence=sanitize_evidence({"apps": apps}),
        )
    )

    return checks


def run_foundation_checks(project_root: str | Path | None = None) -> SentinelRun:
    _ = Path(project_root) if project_root else Path(__file__).resolve().parent.parent.parent
    checks = [
        check_runtime(),
        check_configuration(),
        check_runtime_dir_writable(),
        check_documentation(),
    ]
    findings: list[SentinelFinding] = []
    overall_status = "healthy"
    for result in checks:
        if result.status == "failed":
            overall_status = "failed"
            findings.append(
                SentinelFinding(
                    finding_id=f"find-{result.check_id}",
                    severity="high" if result.check_id == "documentation" else "medium",
                    title=f"{result.name} check failed",
                    description=result.message,
                    affected_component="Sentinel foundation",
                    evidence=result.evidence,
                    recommendation="Review the evidence and fix the issue before expanding to production monitoring.",
                    status="unknown",
                )
            )
    run = SentinelRun(
        overall_status=overall_status,
        checks=checks,
        findings=findings,
    )
    run.completed_at = utc_now_iso()
    return run


def write_run_json(run: SentinelRun, root: str | Path | None = None) -> Path:
    project_root = Path(root) if root else Path(__file__).resolve().parent.parent.parent
    run_dir = project_root / ".runtime" / "runs"
    run_dir.mkdir(parents=True, exist_ok=True)
    run_path = run_dir / f"{run.run_id}.json"
    run_path.write_text(json.dumps(run.to_dict(), indent=2), encoding="utf-8")
    return run_path

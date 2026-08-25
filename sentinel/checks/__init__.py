from __future__ import annotations

import json
import socket
import ssl
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

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


def _ram_status_for_pct(pct: float, warning_threshold: float, failed_threshold: float) -> str:
    if pct >= failed_threshold:
        return "failed"
    if pct >= warning_threshold:
        return "warning"
    return "healthy"


def _probe_http_url(url: str) -> dict[str, Any]:
    if not url:
        return {"status": "unknown", "http_health": "unknown", "status_code": None, "error": "not_configured"}
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=10) as response:
            return {
                "status": "healthy" if response.status < 400 else "failed",
                "http_health": "healthy" if response.status < 400 else "failed",
                "status_code": response.status,
                "final_url": response.geturl(),
                "error": None,
            }
    except urllib.error.HTTPError as exc:
        return {
            "status": "failed",
            "http_health": "failed",
            "status_code": exc.code,
            "final_url": exc.geturl() or url,
            "error": str(exc),
        }
    except (urllib.error.URLError, TimeoutError, ValueError, ssl.SSLError) as exc:
        return {
            "status": "unknown",
            "http_health": "unknown",
            "status_code": None,
            "final_url": url,
            "error": str(exc),
        }


def _evaluate_tls_endpoint(url: str, warning_days: int = 14) -> dict[str, Any]:
    if not url:
        return {
            "hostname": None,
            "validation_result": "not_configured",
            "not_before": None,
            "not_after": None,
            "days_remaining": None,
            "tls_status": "UNKNOWN",
        }
    parsed = urlparse(url)
    hostname = parsed.hostname or ""
    scheme = (parsed.scheme or "").lower()
    port = parsed.port or (443 if scheme == "https" else 80)
    if scheme != "https":
        return {
            "hostname": hostname,
            "validation_result": "unsupported_scheme",
            "not_before": None,
            "not_after": None,
            "days_remaining": None,
            "tls_status": "UNKNOWN",
        }
    try:
        context = ssl.create_default_context()
        with socket.create_connection((hostname, port), timeout=10) as sock:
            with context.wrap_socket(sock, server_hostname=hostname) as tls_sock:
                cert = tls_sock.getpeercert()
        if not cert:
            return {
                "hostname": hostname,
                "validation_result": "no_certificate",
                "not_before": None,
                "not_after": None,
                "days_remaining": None,
                "tls_status": "INVALID",
            }
        not_after_raw = cert.get("notAfter")
        if not not_after_raw:
            return {
                "hostname": hostname,
                "validation_result": "missing_not_after",
                "not_before": cert.get("notBefore"),
                "not_after": None,
                "days_remaining": None,
                "tls_status": "UNKNOWN",
            }
        not_after = datetime.strptime(not_after_raw, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
        days_remaining = (not_after - datetime.now(timezone.utc)).days
        if days_remaining <= 0:
            tls_status = "EXPIRED"
        elif days_remaining <= warning_days:
            tls_status = "EXPIRING_SOON"
        else:
            tls_status = "VALID"
        return {
            "hostname": hostname,
            "validation_result": "verified",
            "not_before": cert.get("notBefore"),
            "not_after": not_after_raw,
            "days_remaining": days_remaining,
            "tls_status": tls_status,
        }
    except (ssl.SSLCertVerificationError, ssl.SSLError) as exc:
        return {
            "hostname": hostname,
            "validation_result": str(exc),
            "not_before": None,
            "not_after": None,
            "days_remaining": None,
            "tls_status": "INVALID",
        }
    except OSError as exc:
        return {
            "hostname": hostname,
            "validation_result": str(exc),
            "not_before": None,
            "not_after": None,
            "days_remaining": None,
            "tls_status": "UNKNOWN",
        }


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


def check_hostless_configuration(config=None) -> SentinelCheckResult:
    config = config or load_config()
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
        return [check_hostless_configuration(config)]

    try:
        docker_version = run_remote_command("docker version --format '{{json .}}'", config, timeout=15)
        docker_ps = run_remote_command("docker ps --format '{{.Names}}\t{{.Status}}\t{{.Image}}'", config, timeout=15)
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
        status_text = (row.get("status") or "").lower()
        health_text = (row.get("health") or "").lower()
        if "unhealthy" in status_text or health_text == "unhealthy":
            status = "failed"
            message = f"{label} container {target_name} is running but unhealthy."
        elif "up" in status_text or health_text in {"healthy", "starting", "running"} or not health_text:
            status = "healthy"
            message = f"{label} container {target_name} is running."
        else:
            status = "failed"
            message = f"{label} container {target_name} is not running."
        return SentinelCheckResult(
            check_id=f"hostless.core.{label.lower()}",
            name=label,
            category="hostless",
            status=status,
            message=message,
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
    checks.append(status_for_container(target_containers["backend"], "Hostless Core Backend"))
    checks.append(status_for_container(target_containers["frontend"], "Hostless Core Frontend"))
    checks.append(status_for_container(target_containers["mongodb"], "MongoDB"))
    checks.append(status_for_container(target_containers["caddy"], "Caddy"))

    configured_apps = config.monitored_apps()
    app_backend_name = next((row["name"] for row in container_rows if row["name"].startswith("hostless_be_")), None)
    app_frontend_name = next((row["name"] for row in container_rows if row["name"].startswith("hostless_fe_")), None)
    backend_row = container_lookup.get(app_backend_name) if app_backend_name else None
    frontend_row = container_lookup.get(app_frontend_name) if app_frontend_name else None

    def build_application_component(container_name: str | None, label: str, url: str | None, url_kind: str) -> dict[str, Any]:
        row = container_lookup.get(container_name) if container_name else None
        state = (row.get("status") if row else "missing") or "missing"
        docker_health = (row.get("health") or "not_configured") if row else "missing"
        http_probe = _probe_http_url(url) if url else {"status": "unknown", "http_health": "unknown", "status_code": None, "error": "not_configured"}
        if row and "unhealthy" in state.lower():
            health_reason = "Docker healthcheck reports unhealthy."
        elif row and "up" in state.lower():
            health_reason = "Container is running and Docker health is not reporting unhealthy."
        else:
            health_reason = "Container state is not running or not found."
        if row and "unhealthy" in state.lower() and http_probe["status"] == "unknown":
            component_status = "warning"
            component_message = f"{label} container is running but Docker health is unhealthy; {url_kind} availability is unknown."
        elif http_probe["status"] == "failed":
            component_status = "failed"
            component_message = f"{label} {url_kind} probe failed."
        elif row and "up" in state.lower():
            component_status = "healthy"
            component_message = f"{label} container is running and {url_kind} health is healthy or not configured."
        elif row:
            component_status = "warning"
            component_message = f"{label} container is present but {url_kind} health is unknown."
        else:
            component_status = "unknown"
            component_message = f"{label} container is missing and {url_kind} health is unknown."
        return {
            "label": label,
            "container_name": container_name,
            "container_state": state,
            "docker_health": docker_health,
            "docker_health_reason": health_reason,
            "http_health": http_probe["http_health"],
            "url": url,
            "status": component_status,
            "message": component_message,
            "http_status_code": http_probe.get("status_code"),
            "http_error": http_probe.get("error"),
        }

    app_backend_observation = build_application_component(app_backend_name, "Application Backend", configured_apps[0].get("api_health_url") if configured_apps else None, "API")
    app_frontend_observation = build_application_component(app_frontend_name, "Application Frontend", configured_apps[0].get("frontend_url") if configured_apps else None, "frontend")
    checks.append(
        SentinelCheckResult(
            check_id="hostless.application.backend",
            name="Application Backend",
            category="hostless",
            status=app_backend_observation["status"],
            message=app_backend_observation["message"],
            evidence=sanitize_evidence(app_backend_observation),
        )
    )
    checks.append(
        SentinelCheckResult(
            check_id="hostless.application.frontend",
            name="Application Frontend",
            category="hostless",
            status=app_frontend_observation["status"],
            message=app_frontend_observation["message"],
            evidence=sanitize_evidence(app_frontend_observation),
        )
    )

    app_map = discover_applications(container_rows)
    app_entries = []
    for app in app_map:
        app_cfg = None
        for entry in configured_apps:
            if (entry.get("name") or "").lower() in (app["app_id"] or "").lower() or app["app_id"].lower() in (entry.get("name") or "").lower():
                app_cfg = entry
                break
        backend_container = app.get("backend_container")
        frontend_container = app.get("frontend_container")
        backend_row = container_lookup.get(backend_container) if backend_container else None
        frontend_row = container_lookup.get(frontend_container) if frontend_container else None
        backend_state = (backend_row.get("status") if backend_row else "missing") or "missing"
        frontend_state = (frontend_row.get("status") if frontend_row else "missing") or "missing"
        backend_http = _probe_http_url(app_cfg.get("api_health_url")) if app_cfg and app_cfg.get("api_health_url") else {"status": "unknown", "http_health": "unknown", "status_code": None, "error": "not_configured"}
        frontend_http = _probe_http_url(app_cfg.get("frontend_url")) if app_cfg and app_cfg.get("frontend_url") else {"status": "unknown", "http_health": "unknown", "status_code": None, "error": "not_configured"}
        app_status = "healthy"
        if backend_http["status"] == "failed" or frontend_http["status"] == "failed":
            app_status = "failed"
        elif backend_http["status"] == "unknown" or frontend_http["status"] == "unknown":
            app_status = "warning"
        elif "unhealthy" in backend_state.lower() or "unhealthy" in frontend_state.lower():
            app_status = "warning"
        app_entries.append({
            "app_id": app["app_id"],
            "friendly_name": (app_cfg.get("name") if app_cfg else app["app_id"]),
            "backend_container": backend_container,
            "frontend_container": frontend_container,
            "network": (app.get("networks") or [None])[0] if app.get("networks") else None,
            "backend_state": backend_state,
            "backend_docker_health": (backend_row.get("health") or "not_configured") if backend_row else "missing",
            "backend_http_health": backend_http["http_health"],
            "frontend_state": frontend_state,
            "frontend_docker_health": (frontend_row.get("health") or "not_configured") if frontend_row else "missing",
            "frontend_http_health": frontend_http["http_health"],
            "frontend_url": app_cfg.get("frontend_url") if app_cfg else None,
            "api_health_url": app_cfg.get("api_health_url") if app_cfg else None,
            "frontend_tls_status": _evaluate_tls_endpoint(app_cfg.get("frontend_url"), warning_days=14).get("tls_status") if app_cfg and app_cfg.get("frontend_url") else "UNKNOWN",
            "api_tls_status": _evaluate_tls_endpoint(app_cfg.get("api_health_url"), warning_days=14).get("tls_status") if app_cfg and app_cfg.get("api_health_url") else "UNKNOWN",
            "overall_status": app_status,
            "findings": [
                f"Backend container state: {backend_state}",
                f"Frontend container state: {frontend_state}",
            ],
        })

    checks.append(
        SentinelCheckResult(
            check_id="hostless.application.map",
            name="Application Map",
            category="hostless",
            status="healthy" if app_entries else "warning",
            message=f"Mapped {len(app_entries)} application group(s)." if app_entries else "No application groups were discovered.",
            evidence=sanitize_evidence({"applications": app_entries}),
        )
    )

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

    platform_tls = _evaluate_tls_endpoint(config.hostless_base_url, warning_days=14)
    checks.append(
        SentinelCheckResult(
            check_id="hostless.tls.platform",
            name="Hostless Platform TLS",
            category="hostless",
            status="failed" if platform_tls.get("tls_status") in {"EXPIRED", "INVALID"} else "warning" if platform_tls.get("tls_status") == "EXPIRING_SOON" else "healthy" if platform_tls.get("tls_status") == "VALID" else "unknown",
            message=f"Platform TLS status: {platform_tls.get('tls_status', 'UNKNOWN')}",
            evidence=sanitize_evidence(platform_tls),
        )
    )

    app_tls = []
    for app in configured_apps:
        for field_name in ("frontend_url", "api_health_url"):
            url = app.get(field_name)
            if url:
                app_tls.append({"endpoint": field_name, **_evaluate_tls_endpoint(url, warning_days=14)})
    if app_tls:
        checks.append(
            SentinelCheckResult(
                check_id="hostless.tls.applications",
                name="Application TLS",
                category="hostless",
                status="failed" if any(item.get("tls_status") in {"EXPIRED", "INVALID"} for item in app_tls) else "warning" if any(item.get("tls_status") == "EXPIRING_SOON" for item in app_tls) else "healthy" if any(item.get("tls_status") == "VALID" for item in app_tls) else "unknown",
                message="Application TLS states were evaluated for the configured app endpoints.",
                evidence=sanitize_evidence({"endpoints": app_tls}),
            )
        )

    memory = parse_system_memory(system_memory.get("stdout", ""))
    ram_total = float(memory["total_mb"])
    ram_used = float(memory["used_mb"])
    ram_pct = (ram_used / ram_total * 100.0) if ram_total else 0.0
    ram_status = "healthy" if ram_pct < config.ram_warning_threshold_pct else "warning" if ram_pct < config.ram_failed_threshold_pct else "failed"
    ram_status = _ram_status_for_pct(ram_pct, config.ram_warning_threshold_pct, config.ram_failed_threshold_pct)
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
                "warning_threshold_pct": config.ram_warning_threshold_pct,
                "failed_threshold_pct": config.ram_failed_threshold_pct,
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

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sentinel.checks import run_foundation_checks, run_hostless_checks, write_run_json
from sentinel.config import load_config

_original_run_foundation_checks = run_foundation_checks
_original_run_hostless_checks = run_hostless_checks


def get_project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def _safe_redact(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            normalized = str(key).lower()
            if any(token in normalized for token in ["password", "secret", "token", "mongo", "key", "credential", "env"]):
                redacted[key] = "***redacted***"
            else:
                redacted[key] = _safe_redact(item)
        return redacted
    if isinstance(value, list):
        return [_safe_redact(item) for item in value]
    return value


def _get_runtimes(project_root: Path) -> list[Path]:
    runs_dir = project_root / ".runtime" / "runs"
    if not runs_dir.exists():
        return []
    return sorted(runs_dir.glob("*.json"), key=lambda p: p.name)


def load_latest_run(project_root: Path | None = None) -> dict[str, Any] | None:
    root = project_root or get_project_root()
    runs = _get_runtimes(root)
    if not runs:
        return None
    latest = runs[-1]
    return json.loads(latest.read_text(encoding="utf-8"))


def load_change_requests(project_root: Path | None = None) -> list[dict[str, Any]]:
    root = project_root or get_project_root()
    requests_dir = root / ".runtime" / "change_requests"
    if not requests_dir.exists():
        return []
    items: list[dict[str, Any]] = []
    for path in sorted(requests_dir.glob("*.json")):
        if path.name.endswith(".handoff.json"):
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if "request_id" in payload:
            items.append(_safe_redact(payload))
    return items


def load_docs_file(path: str, project_root: Path | None = None) -> str:
    root = project_root or get_project_root()
    safe = Path(path)
    if safe.is_absolute() or ".." in safe.parts:
        raise ValueError("Invalid documentation path")
    target = (root / "docs" / safe).resolve()
    docs_root = (root / "docs").resolve()
    if docs_root not in target.parents and target != docs_root:
        raise ValueError("Path traversal denied")
    if not target.exists() or not target.is_file():
        raise FileNotFoundError(path)
    return target.read_text(encoding="utf-8")


def get_status_summary(project_root: Path | None = None) -> dict[str, Any]:
    run = load_latest_run(project_root)
    if run is None:
        return {
            "overall_status": "unknown",
            "last_checked": None,
            "summary": "No heartbeat has been recorded yet.",
            "hostless_configured": bool(load_config().hostless_ssh_host),
            "core_services": [],
            "applications": [],
            "open_change_requests": 0,
            "active_findings": 0,
            "last_run_id": None,
        }

    checks = run.get("checks", [])
    core_services = [
        {
            "name": check.get("name"),
            "status": check.get("status"),
            "message": check.get("message"),
            "evidence": _safe_redact(check.get("evidence", {})),
        }
        for check in checks
        if "core" in str(check.get("category", "")).lower() or check.get("name", "").lower() in {"docker engine", "hostless core backend", "hostless core frontend", "mongodb", "caddy", "hostless platform tls", "ram", "disk"}
    ]
    apps = []
    for check in checks:
        evidence = check.get("evidence") or {}
        if "applications" in evidence or "apps" in evidence:
            apps_payload = evidence.get("applications") or evidence.get("apps") or []
            if isinstance(apps_payload, list):
                for app in apps_payload:
                    if isinstance(app, dict):
                        apps.append({
                            "app_id": app.get("app_id") or app.get("friendly_name") or "unknown",
                            "friendly_name": app.get("friendly_name") or app.get("app_id") or "unknown",
                            "overall_status": app.get("overall_status") or app.get("status") or "unknown",
                            "backend_container": app.get("backend_container"),
                            "frontend_container": app.get("frontend_container"),
                            "backend_state": app.get("backend_state"),
                            "frontend_state": app.get("frontend_state"),
                            "backend_http_health": app.get("backend_http_health"),
                            "frontend_http_health": app.get("frontend_http_health"),
                            "tls_status": app.get("frontend_tls_status") or app.get("api_tls_status") or "UNKNOWN",
                        })
    if not apps:
        for check in checks:
            if "app" in str(check.get("name", "")).lower() and isinstance(check.get("evidence"), dict):
                details = check["evidence"]
                app_name = details.get("label") or details.get("container_name") or "unknown"
                apps.append({
                    "app_id": details.get("container_name") or app_name,
                    "friendly_name": details.get("label") or app_name,
                    "overall_status": details.get("status") or "unknown",
                    "backend_container": details.get("container_name"),
                    "frontend_container": details.get("container_name"),
                    "backend_state": details.get("container_state"),
                    "frontend_state": details.get("container_state"),
                    "backend_http_health": details.get("http_health"),
                    "frontend_http_health": details.get("http_health"),
                    "tls_status": "UNKNOWN",
                })

    reqs = load_change_requests(project_root)
    findings = run.get("findings", []) or []
    summary = build_summary_text(run, reqs, apps)
    return {
        "overall_status": run.get("overall_status", "unknown"),
        "last_checked": run.get("completed_at") or run.get("started_at"),
        "summary": summary,
        "hostless_configured": bool(load_config().hostless_ssh_host),
        "core_services": core_services,
        "applications": apps,
        "open_change_requests": sum(1 for req in reqs if req.get("approval_status") != "APPROVED"),
        "active_findings": len(findings),
        "last_run_id": run.get("run_id"),
    }


def build_summary_text(run: dict[str, Any], requests: list[dict[str, Any]], apps: list[dict[str, Any]]) -> str:
    text_parts: list[str] = []
    if run.get("overall_status") == "healthy":
        text_parts.append("Hostless is currently healthy.")
    elif run.get("overall_status") == "warning":
        text_parts.append("Hostless core services are running, but the server needs attention.")
    else:
        text_parts.append("Hostless needs attention.")

    checks = run.get("checks", [])
    memory = next((check for check in checks if str(check.get("name", "")).lower() == "ram"), None)
    tls = next((check for check in checks if "tls" in str(check.get("name", "")).lower() and "platform" in str(check.get("name", "")).lower()), None)
    app_health = next((check for check in checks if "application backend" in str(check.get("name", "")).lower()), None)
    if memory:
        evidence = memory.get("evidence", {})
        pct = evidence.get("used_percent") or evidence.get("ram_percent")
        if pct is not None:
            text_parts.append(f"Memory is at {pct}% and above the configured threshold.")
    if tls:
        text_parts.append("The public security certificate is expired or invalid.")
    if app_health:
        if app_health.get("status") == "warning":
            text_parts.append("ArcticDrive is running, but its Docker health test is broken.")
    if apps:
        text_parts.append(f"{len(apps)} hosted application(s) are mapped in the latest Sentinel run.")
    if requests:
        text_parts.append(f"{len(requests)} change request(s) are awaiting review.")
    return " ".join(text_parts)


def create_refresh_run(project_root: Path | None = None) -> dict[str, Any]:
    root = project_root or get_project_root()
    run = _original_run_foundation_checks(root)
    try:
        hostless_checks = _original_run_hostless_checks(root)
        run.checks.extend(hostless_checks)
        run.hostless_observations = {"checks": [check.to_dict() for check in hostless_checks]}
    except Exception:
        run.hostless_observations = {"checks": [], "error": "Hostless read-only check unavailable"}
    run.completed_at = run.completed_at or run.started_at
    write_run_json(run, root)
    return run.to_dict()

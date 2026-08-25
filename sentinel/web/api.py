from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from sentinel.web.service import (
    create_refresh_run,
    get_project_root,
    get_status_summary,
    load_change_requests,
    load_docs_file,
    load_latest_run,
)

app = FastAPI(title="Stallion Sentinel Operations Console", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/status")
def status() -> dict[str, Any]:
    return get_status_summary(get_project_root())


@app.get("/api/heartbeat/latest")
def latest_heartbeat() -> dict[str, Any]:
    run = load_latest_run(get_project_root())
    if run is None:
        raise HTTPException(status_code=404, detail="No heartbeat has been recorded yet.")
    return run


@app.post("/api/heartbeat/refresh")
def refresh_heartbeat() -> dict[str, Any]:
    run = create_refresh_run(get_project_root())
    return {"success": True, "run": run, "summary": get_status_summary(get_project_root())}


@app.get("/api/apps")
def list_apps() -> list[dict[str, Any]]:
    run = load_latest_run(get_project_root())
    if not run:
        return []
    checks = run.get("checks", [])
    apps: list[dict[str, Any]] = []
    for check in checks:
        evidence = check.get("evidence") or {}
        if "applications" in evidence or "apps" in evidence:
            payload = evidence.get("applications") or evidence.get("apps") or []
            if isinstance(payload, list):
                for app in payload:
                    if isinstance(app, dict):
                        apps.append({
                            "id": app.get("app_id") or app.get("friendly_name") or "unknown",
                            "friendly_name": app.get("friendly_name") or app.get("app_id") or "unknown",
                            "overall_status": app.get("overall_status") or app.get("status") or "unknown",
                            "backend_container": app.get("backend_container"),
                            "frontend_container": app.get("frontend_container"),
                            "backend_state": app.get("backend_state"),
                            "frontend_state": app.get("frontend_state"),
                            "backend_http_health": app.get("backend_http_health"),
                            "frontend_http_health": app.get("frontend_http_health"),
                            "tls_status": app.get("frontend_tls_status") or app.get("api_tls_status") or "UNKNOWN",
                            "last_checked": check.get("checked_at"),
                        })
    return apps


@app.get("/api/apps/{app_id}")
def app_detail(app_id: str) -> dict[str, Any]:
    apps = list_apps()
    match = next((item for item in apps if item["id"] == app_id), None)
    if match is None:
        raise HTTPException(status_code=404, detail=f"App not found: {app_id}")
    return match


@app.get("/api/findings")
def findings() -> list[dict[str, Any]]:
    run = load_latest_run(get_project_root())
    if run is None:
        return []
    return run.get("findings", [])


@app.get("/api/change-requests")
def change_requests() -> list[dict[str, Any]]:
    return load_change_requests(get_project_root())


@app.get("/api/change-requests/{request_id}")
def change_request_detail(request_id: str) -> dict[str, Any]:
    for item in load_change_requests(get_project_root()):
        if item.get("request_id") == request_id:
            return item
    raise HTTPException(status_code=404, detail=f"Request not found: {request_id}")


@app.get("/api/activity")
def activity() -> list[dict[str, Any]]:
    run = load_latest_run(get_project_root())
    requests = load_change_requests(get_project_root())
    events: list[dict[str, Any]] = []
    if run:
        events.append({
            "time": run.get("completed_at") or run.get("started_at"),
            "type": "heartbeat",
            "status": run.get("overall_status", "unknown"),
            "message": f"Heartbeat completed: {run.get('run_id')}",
            "details": {"run_id": run.get("run_id")},
        })
    for request in requests:
        events.append({
            "time": request.get("updated_at") or request.get("created_at"),
            "type": "change_request",
            "status": request.get("approval_status", "NOT_APPROVED"),
            "message": request.get("title", "Change request created"),
            "details": {"request_id": request.get("request_id")},
        })
    return sorted(events, key=lambda item: item.get("time") or "", reverse=True)


@app.get("/api/docs/{stream}/{document}")
def docs_document(stream: str, document: str) -> dict[str, Any]:
    safe_path = Path(stream) / document
    try:
        content = load_docs_file(str(safe_path), get_project_root())
    except (ValueError, FileNotFoundError):
        raise HTTPException(status_code=404, detail="Document not found")

    return {"stream": stream, "document": document, "content": content}


@app.get("/api/settings/public")
def public_settings() -> dict[str, Any]:
    config = __import__("sentinel.config", fromlist=["load_config"]).load_config()
    return {
        "mode": "OBSERVATION",
        "hostless_configured": bool(config.hostless_ssh_host),
        "hostless_ssh_host": "CONFIGURED" if config.hostless_ssh_host else "NOT_CONFIGURED",
        "hostless_ssh_user": "CONFIGURED" if config.hostless_ssh_user else "NOT_CONFIGURED",
        "ssh_key_configured": bool(config.hostless_ssh_key_path),
        "last_successful_ssh_observation": "AVAILABLE" if config.hostless_ssh_host else "NOT_CONFIGURED",
        "auto_refresh": False,
        "refresh_interval_seconds": 30,
        "view_preference": "simple",
    }


@app.get("/")
def root() -> dict[str, str]:
    return {"status": "ok", "service": "Stallion Sentinel Operations Console"}

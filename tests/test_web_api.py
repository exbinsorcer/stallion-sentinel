from pathlib import Path

from fastapi.testclient import TestClient

from sentinel.web.api import app

client = TestClient(app)


def test_api_status_and_latest_heartbeat():
    status = client.get("/api/status")
    assert status.status_code == 200
    payload = status.json()
    assert "overall_status" in payload
    assert payload["overall_status"] in {"healthy", "warning", "failed", "unknown"}

    latest = client.get("/api/heartbeat/latest")
    assert latest.status_code == 200
    data = latest.json()
    assert "run_id" in data
    assert data["run_id"].startswith("SEN-")


def test_api_app_and_change_request_listing():
    apps = client.get("/api/apps")
    assert apps.status_code == 200
    app_payload = apps.json()
    assert isinstance(app_payload, list)

    requests = client.get("/api/change-requests")
    assert requests.status_code == 200
    request_payload = requests.json()
    assert isinstance(request_payload, list)
    assert request_payload


def test_docs_access_and_path_traversal_protection():
    response = client.get("/api/docs/internal/README.md")
    assert response.status_code == 200
    body = response.json()
    assert "content" in body
    assert "Sentinel" in body["content"]

    blocked = client.get("/api/docs/../.env")
    assert blocked.status_code == 404


def test_public_settings_are_sanitized():
    response = client.get("/api/settings/public")
    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "OBSERVATION"
    assert "hostless_ssh_host" in payload
    assert "key" not in payload
    assert "path" not in payload


def test_refresh_endpoint_is_read_only_and_safe(monkeypatch):
    import sentinel.web.service as service

    def fake_foundation(root):
        return service.run_foundation_checks(root)

    monkeypatch.setattr(service, "run_foundation_checks", fake_foundation)
    monkeypatch.setattr(service, "run_hostless_checks", lambda: [])

    response = client.post("/api/heartbeat/refresh")
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert "summary" in payload
    assert payload["summary"]["overall_status"] in {"healthy", "warning", "failed", "unknown"}


def test_invalid_request_and_app_ids_return_404():
    assert client.get("/api/apps/missing-app").status_code == 404
    assert client.get("/api/change-requests/NOPE").status_code == 404

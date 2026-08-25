from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_ENVIRONMENT = "development"


def _load_env_file(project_root: Path) -> dict[str, str]:
    env_path = project_root / ".env"
    if not env_path.exists():
        return {}
    values: dict[str, str] = {}
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        values[key] = value
    return values


@dataclass(frozen=True)
class SentinelConfig:
    environment: str
    project_root: Path
    runtime_dir: Path
    runs_dir: Path
    docs_dir: Path
    hostless_ssh_host: str | None
    hostless_ssh_user: str | None
    hostless_ssh_port: int
    hostless_ssh_key_path: str | None
    hostless_base_url: str | None
    monitored_apps_json: str | None
    ram_warning_threshold_pct: float
    ram_failed_threshold_pct: float
    disk_warning_threshold_pct: float
    disk_failed_threshold_pct: float
    core_container_names: tuple[str, ...]

    @classmethod
    def from_env(cls) -> "SentinelConfig":
        project_root = Path(__file__).resolve().parent.parent
        env_values = _load_env_file(project_root)
        env_values.update(os.environ)
        hostless_ssh_host = env_values.get("HOSTLESS_SSH_HOST") or None
        hostless_ssh_user = env_values.get("HOSTLESS_SSH_USER") or None
        hostless_ssh_port = int(env_values.get("HOSTLESS_SSH_PORT", "22"))
        hostless_ssh_key_path = env_values.get("HOSTLESS_SSH_KEY_PATH") or None
        hostless_base_url = env_values.get("HOSTLESS_BASE_URL") or None
        monitored_apps_json = env_values.get("SENTINEL_MONITORED_APPS_JSON") or None
        return cls(
            environment=env_values.get("SENTINEL_ENVIRONMENT", DEFAULT_ENVIRONMENT),
            project_root=project_root,
            runtime_dir=project_root / ".runtime",
            runs_dir=project_root / ".runtime" / "runs",
            docs_dir=project_root / "docs",
            hostless_ssh_host=hostless_ssh_host,
            hostless_ssh_user=hostless_ssh_user,
            hostless_ssh_port=hostless_ssh_port,
            hostless_ssh_key_path=hostless_ssh_key_path,
            hostless_base_url=hostless_base_url,
            monitored_apps_json=monitored_apps_json,
            ram_warning_threshold_pct=float(env_values.get("SENTINEL_RAM_WARNING_THRESHOLD", "75")),
            ram_failed_threshold_pct=float(env_values.get("SENTINEL_RAM_FAILED_THRESHOLD", "90")),
            disk_warning_threshold_pct=float(env_values.get("SENTINEL_DISK_WARNING_THRESHOLD", "75")),
            disk_failed_threshold_pct=float(env_values.get("SENTINEL_DISK_FAILED_THRESHOLD", "90")),
            core_container_names=(
                "deploy-backend-1",
                "deploy-frontend-1",
                "deploy-caddy-1",
                "deploy-mongo-1",
            ),
        )

    @property
    def hostless_configured(self) -> bool:
        return bool(self.hostless_ssh_host and self.hostless_ssh_user)

    def monitored_apps(self) -> list[dict[str, str]]:
        if not self.monitored_apps_json:
            return []
        try:
            payload = json.loads(self.monitored_apps_json)
            if isinstance(payload, list):
                return [item for item in payload if isinstance(item, dict)]
        except json.JSONDecodeError:
            return []
        return []

    def to_dict(self) -> dict[str, Any]:
        return {
            "environment": self.environment,
            "project_root": str(self.project_root),
            "runtime_dir": str(self.runtime_dir),
            "runs_dir": str(self.runs_dir),
            "docs_dir": str(self.docs_dir),
            "hostless_ssh_host": self.hostless_ssh_host,
            "hostless_ssh_user": self.hostless_ssh_user,
            "hostless_ssh_port": self.hostless_ssh_port,
            "hostless_ssh_key_path": self.hostless_ssh_key_path,
            "hostless_base_url": self.hostless_base_url,
            "hostless_configured": self.hostless_configured,
            "ram_warning_threshold_pct": self.ram_warning_threshold_pct,
            "ram_failed_threshold_pct": self.ram_failed_threshold_pct,
            "disk_warning_threshold_pct": self.disk_warning_threshold_pct,
            "disk_failed_threshold_pct": self.disk_failed_threshold_pct,
            "core_container_names": list(self.core_container_names),
        }


def load_config() -> SentinelConfig:
    return SentinelConfig.from_env()


def get_default_config() -> dict[str, Any]:
    config = load_config()
    return {
        "environment": config.environment,
        "project_root": str(config.project_root),
        "runtime_dir": str(config.runtime_dir),
        "runs_dir": str(config.runs_dir),
        "docs_dir": str(config.docs_dir),
    }

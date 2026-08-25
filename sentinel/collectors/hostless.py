from __future__ import annotations

import json
import re
import shlex
import subprocess
from typing import Any

from sentinel.config import SentinelConfig


DISALLOWED_TOKENS = (
    ";",
    "&&",
    "||",
    "`",
    "$(",
    "rm ",
    "shutdown",
    "reboot",
    "docker stop",
    "docker restart",
    "docker kill",
    "docker rm",
    "docker network connect",
    "docker network disconnect",
    "docker compose down",
)

ALLOWED_REMOTE_PREFIXES = (
    "uptime",
    "cat /proc/loadavg",
    "free -m",
    "df -h /",
    "docker ps --format",
    "docker version --format",
    "docker network ls --format",
    "docker network inspect ",
    "docker inspect ",
)


def sanitize_evidence(payload: Any) -> Any:
    if isinstance(payload, dict):
        cleaned: dict[str, Any] = {}
        for key, value in payload.items():
            lowered = str(key).lower()
            if any(secret in lowered for secret in ("password", "passwd", "secret", "token", "key", "credential", "ssh")):
                cleaned[key] = "***redacted***"
            else:
                cleaned[key] = sanitize_evidence(value)
        return cleaned
    if isinstance(payload, list):
        return [sanitize_evidence(item) for item in payload]
    return payload


def build_ssh_command(command: str, config: SentinelConfig) -> list[str]:
    if not command or not command.strip():
        raise ValueError("Remote command cannot be empty.")

    normalized = command.strip()
    lowered = normalized.lower()
    for forbidden in DISALLOWED_TOKENS:
        if forbidden in lowered:
            raise ValueError(f"Disallowed remote command pattern: {forbidden!r}")

    if "\n" in normalized or "\r" in normalized:
        raise ValueError("Remote command contains unsafe newline characters.")

    try:
        tokens = shlex.split(normalized, posix=True)
    except ValueError as exc:  # pragma: no cover - from malformed input
        raise ValueError(f"Malformed remote command: {command}") from exc

    if not tokens:
        raise ValueError("Remote command is empty after parsing.")

    allowed = False
    if tokens[0] in {"uptime", "cat", "free", "df", "docker", "hostname"}:
        if tokens[0] == "docker" and len(tokens) >= 2:
            if tokens[1] == "ps" and "--format" in tokens:
                allowed = True
            elif tokens[1] == "version" and "--format" in tokens:
                allowed = True
            elif tokens[1] == "network" and len(tokens) >= 3 and tokens[2] in {"ls", "inspect"}:
                if tokens[2] == "ls" and "--format" in tokens:
                    allowed = True
                elif tokens[2] == "inspect" and len(tokens) >= 4:
                    allowed = True
            elif tokens[1] == "inspect" and len(tokens) >= 3:
                if "--help" not in tokens and "-h" not in tokens:
                    allowed = True
        elif tokens[0] in {"uptime", "cat", "free", "df", "hostname"}:
            allowed = True

    if not allowed:
        raise ValueError(f"Remote command is not in the read-only allowlist: {command}")

    host = config.hostless_ssh_host
    user = config.hostless_ssh_user
    if not host or not user:
        raise ValueError("Hostless SSH configuration is not supplied.")

    cmd = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", "-o", "StrictHostKeyChecking=yes"]
    if config.hostless_ssh_port:
        cmd.extend(["-p", str(config.hostless_ssh_port)])
    if config.hostless_ssh_key_path:
        cmd.extend(["-i", config.hostless_ssh_key_path])
    cmd.extend([f"{user}@{host}", normalized])
    return cmd


def run_remote_command(command: str, config: SentinelConfig, timeout: int = 15) -> dict[str, Any]:
    ssh_command = build_ssh_command(command, config)
    completed = subprocess.run(
        ssh_command,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    return {
        "command": command,
        "exit_code": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
    }


def parse_docker_ps(raw_stdout: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for line in raw_stdout.splitlines():
        if not line.strip():
            continue
        parts = [part.strip() for part in line.split("\t")]
        if len(parts) >= 4:
            rows.append({
                "name": parts[0],
                "status": parts[1],
                "health": parts[2],
                "image": parts[3],
            })
    return rows


def parse_network_ls(raw_stdout: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for line in raw_stdout.splitlines():
        if not line.strip():
            continue
        parts = [part.strip() for part in line.split("\t")]
        if len(parts) >= 2:
            rows.append({
                "name": parts[0],
                "driver": parts[1],
            })
    return rows


def parse_system_memory(raw_stdout: str) -> dict[str, float | int | str]:
    for line in raw_stdout.splitlines():
        if line.lower().startswith("mem:"):
            parts = line.split()
            total = parts[1]
            used = parts[2]
            free = parts[3]
            available = parts[6]
            return {
                "total_mb": int(total),
                "used_mb": int(used),
                "free_mb": int(free),
                "available_mb": int(available),
            }
    raise ValueError("Could not parse memory output.")


def parse_disk_usage(raw_stdout: str) -> dict[str, float | int | str]:
    lines = [line for line in raw_stdout.splitlines() if line.strip()]
    if len(lines) < 2:
        raise ValueError("Could not parse disk output.")
    columns = lines[1].split()
    if len(columns) < 5:
        raise ValueError("Disk output missing required fields.")
    return {
        "filesystem": columns[0],
        "total_mb": int(float(columns[1]) * 1024 / 1024),
        "used_mb": int(float(columns[2]) * 1024 / 1024),
        "available_mb": int(float(columns[3]) * 1024 / 1024),
        "used_percent": columns[4],
    }


def discover_applications(container_rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for row in container_rows:
        name = row.get("name", "")
        match = re.match(r"hostless_(be|fe|net)_([A-Za-z0-9._-]+)", name)
        if not match:
            continue
        app_kind, app_id = match.groups()
        app_entry = grouped.setdefault(app_id, {
            "app_id": app_id,
            "backend_container": None,
            "frontend_container": None,
            "networks": [],
            "running_state": None,
            "health": None,
            "image": None,
        })
        if app_kind == "be":
            app_entry["backend_container"] = name
        elif app_kind == "fe":
            app_entry["frontend_container"] = name
        elif app_kind == "net":
            app_entry["networks"].append(name)
        app_entry["running_state"] = row.get("status", "unknown")
        app_entry["health"] = row.get("health", "unknown")
        app_entry["image"] = row.get("image")

    return [
        {
            "app_id": data["app_id"],
            "backend_container": data["backend_container"],
            "frontend_container": data["frontend_container"],
            "networks": data["networks"],
            "running_state": data["running_state"],
            "health": data["health"],
            "image": data["image"],
        }
        for data in grouped.values()
    ]


def parse_hostless_docker_json(raw_stdout: str) -> dict[str, Any]:
    text = (raw_stdout or "").strip()
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"raw": text}

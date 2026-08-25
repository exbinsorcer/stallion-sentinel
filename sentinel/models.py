from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


_STATUS_VALUES = {"healthy", "warning", "failed", "unknown"}
_RUN_ID_COUNTER = 1


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def generate_run_id() -> str:
    global _RUN_ID_COUNTER
    run_id = f"SEN-{_RUN_ID_COUNTER:06d}"
    _RUN_ID_COUNTER += 1
    return run_id


@dataclass
class SentinelCheckResult:
    check_id: str
    name: str
    category: str
    status: str
    message: str
    evidence: Any = None
    checked_at: str = field(default_factory=utc_now_iso)

    def __post_init__(self) -> None:
        if self.status not in _STATUS_VALUES:
            raise ValueError(f"Unsupported status: {self.status}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SentinelFinding:
    finding_id: str
    severity: str
    title: str
    description: str
    affected_component: str
    evidence: Any = None
    recommendation: str = "Review the component and collect a fresh evidence trail."
    status: str = "unknown"

    def __post_init__(self) -> None:
        if self.status not in _STATUS_VALUES:
            raise ValueError(f"Unsupported status: {self.status}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SentinelRun:
    run_id: str = field(default_factory=generate_run_id)
    started_at: str = field(default_factory=utc_now_iso)
    completed_at: str | None = None
    overall_status: str = "unknown"
    checks: list[SentinelCheckResult] = field(default_factory=list)
    findings: list[SentinelFinding] = field(default_factory=list)
    hostless_observations: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.overall_status not in _STATUS_VALUES:
            raise ValueError(f"Unsupported overall_status: {self.overall_status}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "overall_status": self.overall_status,
            "checks": [check.to_dict() for check in self.checks],
            "findings": [finding.to_dict() for finding in self.findings],
            "hostless_observations": self.hostless_observations,
        }

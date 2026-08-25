from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Iterable

from sentinel.models import SentinelFinding, SentinelRun, utc_now_iso


class ChangeRequestCategory(str, Enum):
    CODE_CHANGE = "CODE_CHANGE"
    INFRASTRUCTURE_CHANGE = "INFRASTRUCTURE_CHANGE"
    CONFIGURATION_CHANGE = "CONFIGURATION_CHANGE"
    OPERATIONAL_ATTENTION = "OPERATIONAL_ATTENTION"
    SECURITY_CHANGE = "SECURITY_CHANGE"
    CAPACITY_CHANGE = "CAPACITY_CHANGE"
    DOCUMENTATION_CHANGE = "DOCUMENTATION_CHANGE"
    UNKNOWN = "UNKNOWN"


class ChangeRequestStatus(str, Enum):
    DRAFT = "DRAFT"
    READY_FOR_REVIEW = "READY_FOR_REVIEW"
    APPROVED_FOR_IMPLEMENTATION = "APPROVED_FOR_IMPLEMENTATION"
    REJECTED = "REJECTED"
    IMPLEMENTATION_IN_PROGRESS = "IMPLEMENTATION_IN_PROGRESS"
    IMPLEMENTED = "IMPLEMENTED"
    VERIFICATION_PENDING = "VERIFICATION_PENDING"
    VERIFIED = "VERIFIED"
    CLOSED = "CLOSED"


class PermissionLevel(str, Enum):
    OBSERVE = "OBSERVE"
    PATCH_PROPOSAL = "PATCH_PROPOSAL"
    TEST_BRANCH = "TEST_BRANCH"
    PREPARE_RELEASE = "PREPARE_RELEASE"
    PRODUCTION_CHANGE = "PRODUCTION_CHANGE"

    LEVEL_0 = OBSERVE
    LEVEL_1 = PATCH_PROPOSAL
    LEVEL_2 = TEST_BRANCH
    LEVEL_3 = PREPARE_RELEASE
    LEVEL_4 = PRODUCTION_CHANGE

    @classmethod
    def normalize(cls, value: str | None) -> str:
        text = str(value or "").strip().upper().replace(" ", "_")
        aliases = {
            "LEVEL_0": cls.OBSERVE.value,
            "LEVEL_1": cls.PATCH_PROPOSAL.value,
            "LEVEL_2": cls.TEST_BRANCH.value,
            "LEVEL_3": cls.PREPARE_RELEASE.value,
            "LEVEL_4": cls.PRODUCTION_CHANGE.value,
            "OBSERVE": cls.OBSERVE.value,
            "PATCH_PROPOSAL": cls.PATCH_PROPOSAL.value,
            "TEST_BRANCH": cls.TEST_BRANCH.value,
            "PREPARE_RELEASE": cls.PREPARE_RELEASE.value,
            "PRODUCTION_CHANGE": cls.PRODUCTION_CHANGE.value,
        }
        return aliases.get(text, text if text else cls.OBSERVE.value)


class ApprovalStatus(str, Enum):
    NOT_APPROVED = "NOT_APPROVED"
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


@dataclass
class ChangeRequest:
    request_id: str
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    source: str = "sentinel"
    title: str = ""
    description: str = ""
    category: str = ChangeRequestCategory.UNKNOWN.value
    severity: str = "medium"
    priority: str = "normal"
    status: str = ChangeRequestStatus.DRAFT.value
    affected_system: str = "Hostless"
    affected_component: str = "unknown"
    affected_app: str | None = None
    affected_files: list[str] = field(default_factory=list)
    affected_services: list[str] = field(default_factory=list)
    evidence: list[dict[str, Any]] = field(default_factory=list)
    related_findings: list[str] = field(default_factory=list)
    related_run_ids: list[str] = field(default_factory=list)
    verified_condition: str | None = None
    verified_root_cause: str | None = None
    unresolved_questions: list[str] = field(default_factory=list)
    requested_outcome: str = ""
    recommended_approach: str = ""
    constraints: list[str] = field(default_factory=list)
    do_not_repeat: list[str] = field(default_factory=list)
    verification_plan: list[str] = field(default_factory=list)
    rollback_expectation: str = "No automatic rollback is performed by Sentinel; owner authorization remains required."
    required_permission_level: str = PermissionLevel.OBSERVE.value
    approval_status: str = ApprovalStatus.NOT_APPROVED.value
    approved_by: str | None = None
    approved_at: str | None = None
    implementation_status: str = "NOT_STARTED"
    verification_status: str = "PENDING"
    closed_at: str | None = None

    def __post_init__(self) -> None:
        self.updated_at = utc_now_iso()

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["required_permission_level"] = PermissionLevel.normalize(payload.get("required_permission_level"))
        return payload

    def fingerprint(self) -> str:
        text = "||".join(
            str(part).lower().strip()
            for part in (
                self.category,
                self.affected_system,
                self.affected_component,
                self.affected_app,
                self.verified_root_cause or self.description,
            )
            if part
        )
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]

    def to_handoff(self) -> dict[str, Any]:
        return {
            "schema_version": "1",
            "request_id": self.request_id,
            "title": self.title,
            "category": self.category,
            "severity": self.severity,
            "problem": self.description,
            "evidence": self.evidence,
            "verified_condition": self.verified_condition,
            "verified_root_cause": self.verified_root_cause,
            "requested_outcome": self.requested_outcome,
            "constraints": self.constraints,
            "verification_plan": self.verification_plan,
            "required_permission_level": PermissionLevel.normalize(self.required_permission_level),
            "approval_status": self.approval_status,
        }

    def to_human_readable(self) -> str:
        lines = [
            "HOSTLESS CHANGE REQUEST",
            f"{self.request_id}",
            "",
            "Status:",
            self.status,
            "",
            "Severity:",
            str(self.severity).upper(),
            "",
            "Category:",
            str(self.category),
            "",
            "Component:",
            self.affected_component,
            "",
            "Problem:",
            self.description,
            "",
            "Verified Condition:",
            self.verified_condition or "Not recorded.",
            "",
            "Evidence:",
        ]
        if self.evidence:
            for item in self.evidence:
                lines.append(json.dumps(item, sort_keys=True))
        else:
            lines.append("No structured evidence provided.")
        lines.extend([
            "",
            "Verified Root Cause:",
            self.verified_root_cause or "No verified root cause recorded.",
            "",
            "Requested Outcome:",
            self.requested_outcome or "Not specified.",
            "",
            "Constraints:",
        ])
        if self.constraints:
            lines.extend(f"- {constraint}" for constraint in self.constraints)
        else:
            lines.append("- None.")
        lines.extend([
            "",
            "Verification:",
        ])
        if self.verification_plan:
            lines.extend(f"- {step}" for step in self.verification_plan)
        else:
            lines.append("- Not specified.")
        lines.extend([
            "",
            "Permission Required:",
            self.required_permission_level,
            "",
            "OWNER APPROVAL:",
            self.approval_status,
            "",
            "ACTION TAKEN:",
            "NONE",
        ])
        return "\n".join(lines)


class ChangeRequestStore:
    def __init__(self, root: str | Path | None = None):
        project_root = Path(root) if root else Path(__file__).resolve().parent.parent
        self.root = project_root / ".runtime" / "change_requests"
        self.root.mkdir(parents=True, exist_ok=True)

    def _next_request_id(self) -> str:
        next_number = 1
        for path in sorted(self.root.glob("*.json")):
            if path.name.endswith(".handoff.json"):
                continue
            stem = path.stem
            if stem.startswith("HCR-"):
                try:
                    next_number = max(next_number, int(stem.split("-", 1)[1]) + 1)
                except ValueError:
                    continue
        return f"HCR-{next_number:06d}"

    def save(self, request: ChangeRequest) -> ChangeRequest:
        if not request.request_id:
            request.request_id = self._next_request_id()
        request.updated_at = utc_now_iso()
        target = self.root / f"{request.request_id}.json"
        target.write_text(json.dumps(request.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
        return request

    def load(self, request_id: str) -> ChangeRequest | None:
        target = self.root / f"{request_id}.json"
        if not target.exists():
            return None
        payload = json.loads(target.read_text(encoding="utf-8"))
        if "problem" in payload or "schema_version" in payload:
            return None
        return ChangeRequest(**payload)

    def list(self) -> list[ChangeRequest]:
        records: list[ChangeRequest] = []
        for path in sorted(self.root.glob("*.json")):
            if path.name.endswith(".handoff.json"):
                continue
            record = self.load(path.stem)
            if record is not None:
                records.append(record)
        return records

    def find_by_fingerprint(self, fingerprint: str) -> ChangeRequest | None:
        for record in self.list():
            if record.fingerprint() == fingerprint:
                return record
        return None

    def update_or_create(self, request: ChangeRequest) -> ChangeRequest:
        existing = self.find_by_fingerprint(request.fingerprint())
        if existing is not None:
            request.request_id = existing.request_id
            existing.updated_at = utc_now_iso()
            existing.related_findings = sorted(set(existing.related_findings + request.related_findings))
            existing.related_run_ids = sorted(set(existing.related_run_ids + request.related_run_ids))
            existing.evidence = existing.evidence + request.evidence
            self.save(existing)
            return existing
        return self.save(request)


def _normalize_issue_type(value: str) -> str:
    return " ".join(str(value).lower().replace("-", " ").replace("_", " ").split())


def _infer_category_and_fields(finding: SentinelFinding) -> tuple[str, str, str, str | None, list[str], str, str, str]:
    title = finding.title or ""
    description = finding.description or ""
    text = f"{title} {description}".lower()
    if "certificate" in text or "tls" in text or "ssl" in text or "expired" in text:
        return (
            ChangeRequestCategory.SECURITY_CHANGE.value,
            "Expired or invalid public-facing certificate",
            "Investigate and remediate the certificate state for the affected Hostless endpoint.",
            "Hostless",
            ["certificate renewal", "tls trust verification"],
            "The Hostless public certificate is expired or otherwise invalid, and TLS validation fails.",
            "UNKNOWN",
            PermissionLevel.PRODUCTION_CHANGE.value,
        )
    if "healthcheck" in text or "curl" in text or "docker health" in text:
        return (
            ChangeRequestCategory.CODE_CHANGE.value,
            "Generated backend healthcheck depends on an unavailable binary",
            "Replace the generated healthcheck with a probe guaranteed to exist in the runtime or ensure the required binary is installed intentionally.",
            "Generated Python backend runtime",
            ["healthcheck implementation", "generated runtime"],
            "The generated backend healthcheck calls curl, but curl is not installed in the generated Python runtime.",
            "The generated healthcheck invokes curl but curl is absent from the generated Python runtime.",
            PermissionLevel.TEST_BRANCH.value,
        )
    if "memory" in text or "ram" in text or "capacity" in text:
        return (
            ChangeRequestCategory.CAPACITY_CHANGE.value,
            "Hostless memory pressure requires operational review",
            "Reassess memory usage and the server capacity model without changing the application code unnecessarily.",
            "Hostless host",
            ["host memory", "capacity planning"],
            "RAM usage is above the configured threshold and warrants investigation before any production change decision.",
            "UNKNOWN",
            PermissionLevel.PATCH_PROPOSAL.value,
        )
    if "documentation" in text:
        return (
            ChangeRequestCategory.DOCUMENTATION_CHANGE.value,
            "Documentation update required",
            "Update the Sentinel and Hostless engineering notes to reflect the validated runtime behavior.",
            "Sentinel documentation",
            ["internal docs", "ai docs"],
            "The documented behavior is incomplete or outdated.",
            "UNKNOWN",
            PermissionLevel.OBSERVE.value,
        )
    return (
        ChangeRequestCategory.UNKNOWN.value,
        title or "Operational issue requires review",
        description or "No explicit change request rationale was recorded.",
        None,
        [],
        "The condition requires review but has not been formally validated.",
        "UNKNOWN",
        PermissionLevel.OBSERVE.value,
    )


def _issue_signature(finding: SentinelFinding) -> str:
    text = " ".join(
        str(value).lower() for value in [finding.title, finding.description, finding.affected_component]
    )
    return _normalize_issue_type(text)


def create_change_request_from_finding(finding: SentinelFinding, *, source: str = "sentinel", run_id: str | None = None) -> ChangeRequest:
    category, title, description, affected_app, affected_services, condition, root_cause, required_permission = _infer_category_and_fields(finding)
    evidence_payload: dict[str, Any] = {
        "finding_id": finding.finding_id,
        "title": finding.title,
        "description": finding.description,
    }
    if isinstance(finding.evidence, dict):
        evidence_payload.update(finding.evidence)
    elif finding.evidence is not None:
        evidence_payload["detail"] = finding.evidence
    request = ChangeRequest(
        request_id="",
        source=source,
        title=title,
        description=description,
        category=category,
        severity=str(finding.severity).upper(),
        priority="high" if str(finding.severity).lower() in {"high", "critical"} else "normal",
        status=ChangeRequestStatus.DRAFT.value,
        affected_system="Hostless",
        affected_component=finding.affected_component,
        affected_app=affected_app,
        affected_files=[],
        affected_services=affected_services,
        evidence=[evidence_payload],
        related_findings=[finding.finding_id],
        related_run_ids=[run_id] if run_id else [],
        verified_condition=condition,
        verified_root_cause=root_cause,
        unresolved_questions=["No explicit owner approval is present yet."],
        requested_outcome="Request owner review and a future authorized engineering decision for remediation or operational follow-up.",
        recommended_approach="Use the existing approval boundary; do not apply or self-approve changes from Sentinel.",
        constraints=[
            "Do not modify production without explicit owner approval.",
            "Do not grant permission from within Sentinel.",
            "Do not expose secrets or credentials.",
        ],
        do_not_repeat=[
            "Do not repeat the same broken healthcheck pattern.",
            "Do not assume every container has a healthcheck binary installed.",
            "Do not auto-renew certificates without explicit permission.",
        ],
        verification_plan=[
            "Collect fresh evidence after any proposed change.",
            "Verify the affected endpoint or service under read-only checks.",
            "Confirm the change request is resolved before closing.",
        ],
        required_permission_level=PermissionLevel.normalize(required_permission),
        approval_status=ApprovalStatus.NOT_APPROVED.value,
        implementation_status="NOT_STARTED",
        verification_status="PENDING",
    )
    return request


def generate_change_requests_for_run(run: SentinelRun, *, source: str = "sentinel") -> list[ChangeRequest]:
    if not run.findings:
        return []
    requests: list[ChangeRequest] = []
    seen: set[str] = set()
    for finding in run.findings:
        request = create_change_request_from_finding(finding, source=source, run_id=run.run_id)
        signature = _issue_signature(finding)
        if signature in seen:
            continue
        seen.add(signature)
        requests.append(request)
    return requests


def load_runtime_store(project_root: str | Path | None = None) -> ChangeRequestStore:
    return ChangeRequestStore(project_root)


def persist_change_requests(requests: Iterable[ChangeRequest], project_root: str | Path | None = None) -> list[ChangeRequest]:
    store = load_runtime_store(project_root)
    persisted: list[ChangeRequest] = []
    for request in requests:
        persisted.append(store.update_or_create(request))
    return persisted


def build_handoff_package(request: ChangeRequest) -> dict[str, Any]:
    return request.to_handoff()


def build_human_readable_request(request: ChangeRequest) -> str:
    return request.to_human_readable()


def generate_verified_local_findings() -> list[SentinelFinding]:
    return [
        SentinelFinding(
            finding_id="hostless-healthcheck-001",
            severity="high",
            title="Generated backend healthcheck depends on curl",
            description="Docker healthcheck invokes curl but the runtime does not contain curl.",
            affected_component="Generated Python backend runtime",
            evidence={
                "healthcheck": "curl -f http://localhost:8001/api/ || exit 1",
                "error": "/bin/sh: 1: curl: not found",
            },
            recommendation="Replace the healthcheck with a runtime-safe probe.",
            status="failed",
        ),
        SentinelFinding(
            finding_id="hostless-tls-001",
            severity="high",
            title="Hostless public TLS certificate expired",
            description="Hostless platform and configured ArcticDrive endpoints have expired TLS.",
            affected_component="Hostless platform TLS",
            evidence={
                "public_url": "https://stallionhostless.duckdns.org",
                "condition": "certificate verify failed",
                "validation_result": "CERTIFICATE_VERIFY_FAILED: certificate has expired",
            },
            recommendation="Review the certificate lifecycle and replace the expired certificate under explicit approval.",
            status="failed",
        ),
        SentinelFinding(
            finding_id="hostless-ram-001",
            severity="warning",
            title="Hostless memory pressure exceeds configured failure threshold",
            description="RAM usage is 90.6% with failure threshold 90%.",
            affected_component="Hostless host memory",
            evidence={
                "ram_percent": 90.6,
                "warning_threshold_pct": 75.0,
                "failure_threshold_pct": 90.0,
            },
            recommendation="Review memory pressure and capacity assumptions before any production change decision.",
            status="failed",
        ),
    ]


def generate_verified_requests_from_local_evidence(project_root: str | Path | None = None) -> list[ChangeRequest]:
    run = SentinelRun(run_id="SEN-LOCAL-001", overall_status="failed", findings=generate_verified_local_findings())
    requests = generate_change_requests_for_run(run)
    if project_root is not None:
        return persist_change_requests(requests, project_root)
    return requests


def export_request_handoff(request: ChangeRequest, project_root: str | Path | None = None) -> dict[str, Any]:
    payload = build_handoff_package(request)
    export_root = Path(project_root) if project_root is not None else Path(__file__).resolve().parent.parent
    export_dir = export_root / ".runtime" / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    target = export_dir / f"{request.request_id}.handoff.json"
    target.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return payload

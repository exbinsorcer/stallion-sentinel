from __future__ import annotations

import argparse
import json
from pathlib import Path

from sentinel.change_requests import (
    ChangeRequestStore,
    build_handoff_package,
    build_human_readable_request,
    export_request_handoff,
    generate_verified_requests_from_local_evidence,
)
from sentinel.checks import run_foundation_checks, run_hostless_checks, write_run_json


def _status_label(status: str) -> str:
    return {"healthy": "PASS", "warning": "WARN", "failed": "FAIL", "unknown": "UNK"}.get(status, "UNK")


def _print_summary(run) -> None:
    print("Stallion Sentinel")
    print(f"Run: {run.run_id}")
    print()
    for check in run.checks:
        print(f"{check.name:<24} {_status_label(check.status)}")
    print()
    print(f"Overall Status: {run.overall_status.upper()}")


def _changes_list(project_root: Path) -> list[str]:
    store = ChangeRequestStore(project_root)
    requests = store.list()
    for request in requests:
        print(f"{request.request_id} | {request.title} | {request.category} | {request.status} | {request.approval_status}")
    return [request.request_id for request in requests]


def _changes_show(request_id: str, project_root: Path) -> str:
    store = ChangeRequestStore(project_root)
    request = store.load(request_id)
    if request is None:
        print(f"Request not found: {request_id}")
        return ""
    text = build_human_readable_request(request)
    print(text)
    return text


def _changes_generate(project_root: Path) -> list[str]:
    requests = generate_verified_requests_from_local_evidence(project_root)
    for request in requests:
        print(f"Generated {request.request_id} | {request.title} | {request.category} | {request.status} | {request.approval_status}")
    return [request.request_id for request in requests]


def _changes_export(request_id: str, project_root: Path) -> dict:
    store = ChangeRequestStore(project_root)
    request = store.load(request_id)
    if request is None:
        raise ValueError(f"Request not found: {request_id}")
    payload = export_request_handoff(request, project_root)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Stallion Sentinel read-only foundation checks.")
    subparsers = parser.add_subparsers(dest="command")

    check_parser = subparsers.add_parser("check", help="Run the local read-only foundation checks")
    check_parser.add_argument("--hostless", action="store_true", help="Include Hostless read-only observation checks when configured")

    changes_parser = subparsers.add_parser("changes", help="Inspect or generate proposal-only change requests")
    changes_parser.add_argument("--project-root", default=str(Path(__file__).resolve().parent.parent), help="Project root for runtime data")
    changes_subparsers = changes_parser.add_subparsers(dest="changes_command")

    changes_subparsers.add_parser("list", help="List stored change requests")
    show_parser = changes_subparsers.add_parser("show", help="Show a stored change request")
    show_parser.add_argument("request_id")
    generate_parser = changes_subparsers.add_parser("generate", help="Generate proposal-only requests from local evidence")
    generate_parser.add_argument("--from-latest", action="store_true", help="Generate from the latest local evidence run")
    export_parser = changes_subparsers.add_parser("export", help="Export a sanitized handoff for a request")
    export_parser.add_argument("request_id")

    args = parser.parse_args(argv)
    project_root = Path(getattr(args, "project_root", Path(__file__).resolve().parent.parent))

    if args.command == "check":
        run = run_foundation_checks(project_root)
        if getattr(args, "hostless", False):
            hostless_checks = run_hostless_checks()
            run.checks.extend(hostless_checks)
            run.hostless_observations = {"checks": [check.to_dict() for check in hostless_checks]}
            run.overall_status = max(
                [run.overall_status, max((check.status for check in hostless_checks), default="healthy")],
                key=lambda s: {"healthy": 0, "warning": 1, "unknown": 2, "failed": 3}.get(s, 0),
            )
            if not any(check.status == "failed" for check in hostless_checks) and not any(check.status == "warning" for check in hostless_checks):
                if any(check.status == "unknown" for check in hostless_checks):
                    run.overall_status = "unknown"
        run.completed_at = run.completed_at or run.started_at
        write_run_json(run, project_root)
        _print_summary(run)
        return 0 if run.overall_status != "failed" else 1

    if args.command == "changes":
        if args.changes_command == "list":
            _changes_list(project_root)
            return 0
        if args.changes_command == "show":
            if not _changes_show(args.request_id, project_root):
                return 1
            return 0
        if args.changes_command == "generate":
            _changes_generate(project_root)
            return 0
        if args.changes_command == "export":
            try:
                _changes_export(args.request_id, project_root)
                return 0
            except ValueError:
                return 1

    parser.print_help()
    return 0

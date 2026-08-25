from __future__ import annotations

import argparse
from pathlib import Path

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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Stallion Sentinel read-only foundation checks.")
    subparsers = parser.add_subparsers(dest="command")
    check_parser = subparsers.add_parser("check", help="Run the local read-only foundation checks")
    check_parser.add_argument("--hostless", action="store_true", help="Include Hostless read-only observation checks when configured")

    args = parser.parse_args(argv)
    if args.command == "check":
        project_root = Path(__file__).resolve().parent.parent
        run = run_foundation_checks(project_root)
        if args.hostless:
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

    parser.print_help()
    return 0

# Internal Engineering Documentation

This directory stores engineering notes, incident records, compatibility findings, and operational evidence for Sentinel and Hostless.

## Principles

- Prefer read-only observation.
- Record evidence before recommending action.
- Keep root cause and remediation notes separate from public status updates.
- Mark unresolved work explicitly.

## Task #2 Hostless baseline

This milestone introduces the first read-only Hostless observation layer. Sentinel can now evaluate configuration, Docker engine reachability, Hostless core containers, basic system metrics, and network discovery without modifying infrastructure.

## Currently monitored

- Local Sentinel runtime and configuration checks
- Hostless SSH configuration availability
- Docker engine availability through a safe remote command allowlist
- Hostless backend, frontend, MongoDB, and Caddy container presence/state
- Docker network listing and application naming pattern discovery
- Basic memory and disk metrics
- Hostless public URL health checks when explicitly configured

## Deliberately not monitored

- No destructive Docker actions
- No container restarts, stops, removals, or network changes
- No automatic repairs or self-healing
- No production writes, config mutations, or Hostless source modifications
- No secret-bearing environment dumps from container inspection or logs

## Configuration required

Sentinel expects environment variables for Hostless SSH host/user/port/key path and optional public URL configuration. These values must remain out of source control.

## Security and read-only boundaries

The SSH layer intentionally rejects arbitrary commands and only allows a narrow set of safe read-only operations. Evidence is limited to relevant operational data and secrets are redacted before any result is serialized.

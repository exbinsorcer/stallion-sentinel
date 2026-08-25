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

## Observed parser edge case

Live Docker output is not uniform across all containers. Some containers expose an explicit `Up ... (unhealthy)` state, while others omit the `Health` field entirely. Sentinel must treat missing health metadata as non-failing unless an explicit unhealthy state is present, and must handle both 3-column and 4-column `docker ps` output safely.

## Verified production findings

- Hostless core deployment containers remain up and healthy: `deploy-backend-1`, `deploy-frontend-1`, `deploy-mongo-1`, and `deploy-caddy-1`.
- The deployed customer backend `hostless_be_6a8cd101a60d` is running but Docker reports `unhealthy`; the latest healthcheck entries show `/bin/sh: 1: curl: not found`. This indicates the healthcheck command is failing because curl is not installed in the container runtime.
- The public Hostless HTTPS certificate is expired; TLS verification fails with `CERTIFICATE_VERIFY_FAILED` on `https://stallionhostless.duckdns.org`.
- Deployed applications and Hostless core services must be reported separately to avoid mislabeling customer app issues as Hostless control-plane problems.

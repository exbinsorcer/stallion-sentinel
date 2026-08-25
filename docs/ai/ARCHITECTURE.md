# Architecture

Stallion Sentinel is intentionally a small, incremental foundation.

## Current architecture

- `sentinel/config.py` provides environment-based configuration.
- `sentinel/models.py` defines serializable run, check, and finding types.
- `sentinel/checks` runs local, read-only validation logic and Hostless observations.
- `sentinel/collectors/hostless.py` provides the SSH transport and read-only command allowlist.
- `sentinel/cli.py` exposes the project CLI.
- Documentation and issue tracking remain separated into internal, AI, and public streams.

## Hostless observation model

Sentinel V1 observes Hostless using a read-only SSH transport and a strict command allowlist. The system is intentionally limited to commands such as `docker ps`, `docker version`, `docker network ls`, `uptime`, `free -m`, and `df -h /`.

The current observation flow is:

1. Load configuration from environment variables.
2. Validate that Hostless SSH settings are supplied.
3. Build an SSH command only from an explicit allowlist.
4. Capture stdout/stderr and structured exit codes.
5. Parse the output into structured evidence.
6. Save the resulting run as JSON under `.runtime/runs/`.

## Safety boundary

OBSERVATION BEFORE INTERVENTION.

Sentinel V1 does not repair Hostless and does not alter Docker, networking, app deployments, or environment settings. This is a safety boundary designed to keep the project focused and auditable.

## Planned future additions

- Monitoring collectors
- Regression checks
- Compatibility data gathering
- Operational incident knowledge bases
- Approved automation phases only after explicit review

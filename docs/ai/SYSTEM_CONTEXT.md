# System Context

Stallion Sentinel is a read-only foundation for monitoring Stallion Hostless and its deployed workloads.

## Mission

- Observe host and application health.
- Maintain a safe and structured evidence trail.
- Produce operational knowledge that can later guide automated responses in approved phases.

## Safety rules

- Read-only by default.
- No destructive infrastructure actions without explicit approval.
- No automatic modifications of Hostless source code.
- Never disclose credentials or secrets.

## OBSERVATION BEFORE INTERVENTION

Sentinel V1 is designed to inspect, measure, and document. It does not repair Hostless, restart services, or modify configuration. Any future intervention must be explicitly authorized and designed in a later phase.

## KNOWN / DISCOVERED / CONFIGURED / UNVERIFIED

- KNOWN: Hostless runs on Ubuntu with Docker and includes core services such as backend, frontend, Caddy, and MongoDB.
- DISCOVERED: The current production naming convention includes deploy-* container names and hostless_be_*, hostless_fe_*, hostless_net_* application containers.
- CONFIGURED: Sentinel supports SSH host, user, port, key path, base URL, and monitored app configuration through environment variables.
- DISCOVERED: Docker `ps` output can omit a `Health` column for some containers, while other containers expose `Up ... (unhealthy)`. Sentinel must not reject healthy-up containers simply because a health field is absent.
- DISCOVERED: Hostless core services (`deploy-backend-1`, `deploy-frontend-1`, `deploy-mongo-1`, `deploy-caddy-1`) must be reported separately from deployed application containers such as `hostless_be_*` and `hostless_fe_*`.
- VERIFIED: The customer application backend container `hostless_be_6a8cd101a60d` is running but reports Docker health `unhealthy`; the latest health log shows `curl: not found`, which means the healthcheck command itself is failing because the runtime lacks curl.
- VERIFIED: The public Hostless URL `https://stallionhostless.duckdns.org` currently fails certificate verification because the certificate is expired.
- UNVERIFIED: Exact production topology, app domains, and live runtime state are not assumed until an authorized observation run is completed.

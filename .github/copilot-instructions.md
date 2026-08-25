# Stallion Sentinel Copilot Instructions

## Project identity

- This project is Stallion Sentinel.
- Sentinel protects and studies Stallion Hostless.
- Hostless may contain production workloads.

## Safety and default behavior

- Prefer observation over intervention.
- Default to read-only behavior.
- Never perform destructive infrastructure actions without explicit approval.
- Never modify Hostless source code automatically.
- Never expose secrets.
- Never commit credentials.

## Engineering expectations

- Every check should produce structured evidence.
- Important incidents and fixes must be documented.
- Public roadmap changes require owner approval.
- Self-healing will be introduced only in later approved phases.
- Avoid large architectural rewrites unless specifically requested.
- Build Sentinel incrementally.

## Scope guardrails

- Do not start actual Hostless monitoring before the approved roadmap calls for it.
- Keep changes narrow and safe.
- Favor small, observable improvements over broad system rewrites.

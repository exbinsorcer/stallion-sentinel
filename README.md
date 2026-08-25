# Stallion Sentinel

Stallion Sentinel is the read-only safety and observability foundation for Stallion Hostless. This initial milestone establishes the project structure, configuration, typed models, CLI skeleton, and documentation scaffolding without making any active infrastructure changes.

## Goals for this milestone

- Keep Sentinel read-only by default.
- Define a simple data model for runs, checks, and findings.
- Provide a local CLI foundation check.
- Capture structured evidence and JSON run output under `.runtime/runs/`.
- Set up developer and AI-facing documentation without creating a production integration yet.

## Quick start

```bash
cd stallion-sentinel
python -m pip install -r requirements.txt
python -m sentinel check
```

## Safety rules

- Never modify Hostless source code automatically.
- Never change infrastructure state or configuration without explicit approval.
- Prefer observation over intervention.
- Never expose credentials or commit secrets.

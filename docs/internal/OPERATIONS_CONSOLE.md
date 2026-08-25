# Sentinel Operations Console

## Purpose

The Operations Console is the local visual layer for Sentinel V1 Task #4. It is a read-only presentation surface built on top of the already-approved FastAPI service layer. It never executes changes, repairs, or production actions.

## Stack

- React
- TypeScript
- Vite
- Dark operations-console styling
- FastAPI API at `http://127.0.0.1:8000`

## Architecture

The frontend reads from the existing runtime sources preserved by Sentinel:

- `GET /api/status`
- `GET /api/heartbeat/latest`
- `GET /api/apps`
- `GET /api/change-requests`
- `GET /api/findings`
- `GET /api/activity`
- `GET /api/docs/...`
- `GET /api/settings/public`
- `POST /api/heartbeat/refresh`

The UI always renders current runtime data when present. If a value is missing, it appears as `UNKNOWN`, `NO DATA`, or `NOT CONFIGURED` instead of using fake placeholders.

## Simple vs Technical mode

- Simple mode prioritizes plain language explanations.
- Technical mode reveals evidence, runtime details, thresholds, and safe metadata.
- The preference is saved in local storage so the user can keep their preferred view.

## Safety model

- Read-only only.
- No approve, execute, repair, deploy, or restart endpoint is added.
- Secrets remain redacted by the backend before they reach the UI.
- The refresh endpoint uses the same safe read-only observation route already approved by the project.

## Localization and data boundaries

This UI is intentionally local only. It does not mutate Hostless systems or grant runtime permission. It is designed to help an owner understand the current state without creating any automation authority.

## Current limitations

- Data is only as good as the latest recorded Sentinel run.
- Some Hostless values remain unknown until a fresh observation is recorded.
- The UI intentionally does not imply a fix path or approval action.

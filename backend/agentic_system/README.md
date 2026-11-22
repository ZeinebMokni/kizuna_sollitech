# QATRA Agentic System

This folder is the decision layer connected to the QATRA frontend.

## Current agents

- `water-agriculture`: moisture thresholds and irrigation recommendations.
- `energy-optimizer`: solar surplus, pump demand and battery constraints.
- `safety-guard`: emergency stop and command blocking.
- `orchestrator`: combines findings, sources and human checkpoints.

## Frontend contract

Start the backend from `backend/` and call:

```text
GET  /api/agentic/agents
GET  /api/agentic/health
POST /api/agentic/decisions
```

The decision response is designed for the frontend agent panels: status,
recommendation, expected impact, findings, sources and checkpoints.

This is a deterministic scaffold. Before production, connect authenticated
telemetry, a database, MQTT, Sentinel-2, weather and a model provider. Critical
actions must remain human-approved.

## Imported decision engine

The full QATRA AI engine from the `AIengine` branch is included at:

```text
backend/agentic_system/ai_engine/
```

It is kept separate from the frontend-facing scaffold so the current API keeps
working while the adapter is implemented. The engine package is `qatra_ai` and
its read-only service entrypoint is `qatra_ai.service.app:app`.

Check availability from the frontend with:

```text
GET /api/agentic/engine
```

The next adapter can map QATRA zone telemetry into the engine's farm profiles,
then return the engine's provenance, confidence, checkpoints and predicted
impact through `/api/agentic/decisions`. Optional engine dependencies should be
installed from `ai_engine/pyproject.toml` rather than imported by the base API
until that adapter is enabled.

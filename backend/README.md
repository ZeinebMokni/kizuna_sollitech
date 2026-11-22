# QATRA Platform Backend

FastAPI, PostgreSQL/PostGIS and TimescaleDB foundation for the authenticated platform API.

## Run

Start PostgreSQL/PostGIS/TimescaleDB:

```powershell
cd ..\infra
docker compose up -d db
```

Apply migrations and start the API:

```powershell
cd ..\backend
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Health:

```text
http://127.0.0.1:8000/health
```

OpenAPI:

```text
http://127.0.0.1:8000/docs
```

## Test

```powershell
$env:QATRA_DATABASE_URL="postgresql+psycopg://qatra:qatra_dev_password@localhost:5433/qatra_test"
uv run pytest
```

The test database is created with PostGIS and TimescaleDB by `infra/db/init/01-init.sql`.

## Foundation endpoints

- `POST /auth/register`
- `POST /auth/login`
- `GET /auth/me`
- `GET /farms`
- `POST /farms`
- `GET /farms/{farm_id}`
- `POST /farms/{farm_id}/parcels`
- `POST /farms/{farm_id}/parcels/{parcel_id}/zones`

## Phase 2 data integration endpoints

- `GET /data/sources`
- `POST /data/weather`
- `GET /data/weather?start=YYYY-MM-DD&end=YYYY-MM-DD`

Weather observations require a registered source, timezone-aware retrieval timestamp,
WGS84 coordinates and an explicit data class. Duplicate source/point/date observations
are rejected. Public provider readers remain in `ai_engine`; this API stores normalized
readings and provenance.

## Phase 3 field operations

- `POST /farms/{farm_id}/devices`
- `POST /farms/{farm_id}/devices/{device_id}/sensors`
- `POST /farms/{farm_id}/devices/{device_id}/measurements`
- `POST /farms/{farm_id}/irrigation-events`

Device registration returns an API key once. Measurement ingestion requires
`X-Device-Key`, validates sensor/unit/zone association and timezone, rejects
future timestamps, and deduplicates sensor/timestamp pairs. Irrigation events
record measured or farmer-reported provenance and reject exact duplicates.
Physical actuation is not implemented in this phase.

## Phase 4 decision intelligence

- `POST /farms/{farm_id}/recommendations/run`
- `GET /farms/{farm_id}/recommendations`
- `POST /farms/{farm_id}/recommendations/{recommendation_id}/approval`

Recommendations are explainable, persist input hashes and provenance evidence,
and record human approvals. The current guard refuses irrigation proposals unless
a usable, calibrated current soil-moisture state is present. No LLM or optimization
result can execute physical actuation.

## Phase 5 advanced modules

- `POST /farms/{farm_id}/satellite-observations`
- `POST /farms/{farm_id}/optimization-runs`
- `POST /farms/{farm_id}/climate-scenarios`
- `POST /farms/{farm_id}/incidents`
- `POST /farms/{farm_id}/incidents/{incident_id}/evidence`

Allocation requests are forwarded to the existing physics/LP engine and stored with
their disclaimer and inputs hash. Climate scenarios are explicitly labelled as
historical, projected or hypothetical; no hypothetical run is presented as a forecast.
Satellite observations are remote-sensed estimates and incident evidence remains
unverified until independently reviewed.

Authentication uses a bearer access token. Farm operations are restricted to platform
administrators or the user's farm membership.

## Phase 2 telemetry

The platform API subscribes to MQTT when `MQTT_ENABLED=true`. The broker is
available as the `mqtt` Docker Compose service on port 1883.

Topic format:

```text
qatra/{farm_uuid}/{device_uuid}/measurements/{sensor_external_id}
```

Payload:

```json
{
  "api_key": "one-time-registered-device-key",
  "observed_at": "2026-11-22T04:00:00Z",
  "value": 21.5,
  "unit": "%",
  "quality": "valid",
  "quality_note": "optional",
  "idempotency_key": "optional-unique-key"
}
```

The MQTT subscriber validates the device key, farm, zone, sensor, unit,
timezone, future timestamps and duplicate sensor/timestamp or idempotency keys.
Accepted, duplicate and rejected deliveries are recorded in
`device_communications`. The development broker allows anonymous network access;
production deployments require Mosquitto authentication, TLS and ACL rules.

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

Authentication uses a bearer access token. Farm operations are restricted to platform
administrators or the user's farm membership.

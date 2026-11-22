# QATRA PostgreSQL integration

Start PostgreSQL/PostGIS from the repository root:

```bash
docker compose up -d postgres
```

Install the backend requirements, then set:

```text
DATABASE_URL=postgresql+psycopg2://qatra:qatra@localhost:5433/qatra
```

Initialize the relational schema:

```bash
curl -X POST http://localhost:8000/api/database/init
```

Seed the initial farm, zones, agents and gateway graph:

```bash
python -m database.seed
```

Inspect the API-to-feature relationship map:

```text
GET /api/database/relationship-map
GET /api/database/health
```

The schema is organized around `farms` and `farm_zones`. Telemetry, satellite
observations, agent decisions, evidence, checkpoints, commands, alerts,
connections, marketplace economics, and measured impacts all reference those
entities. This preserves traceability from a sensor reading to a decision and
then to the real result.

Privacy is explicit: users have roles and privacy scopes, farms default to
private, and sharing between farms is represented separately by
`farm_connections`.

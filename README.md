# QATRA

Agricultural water decision support for pump-irrigated farms in Tunisia. Its central question: when water, energy and information are scarce, where should we intervene first to prevent the most irreversible damage?

> **Status: research prototype.** Nothing is validated on real farms yet. The irrigation scheduler and the anomaly detectors are simulation-tested; everything else relies on published parameters (FAO‑56, FAO‑33, FAO‑29). The dashboard runs on a **hypothetical demo farm**, with real weather and soil for its location.

## What is here

| Folder | What it is | Docs |
|---|---|---|
| [ai_engine/](ai_engine/) | The decision engine (`qatra_ai`, Python): agronomy, scheduling, allocation, anomaly detection, suitability, climate scenarios, decision ranking, assistant, and a read-only HTTP API | [ai_engine/README.md](ai_engine/README.md) |
| [frontend/](frontend/) | Dashboard (Next.js) over the engine API | [frontend/README.md](frontend/README.md) |
| [backend/](backend/) | Paused scaffold of the multi-farm platform (auth, farms, PostGIS). Not runnable yet | [docs/BLUEPRINT.md](docs/BLUEPRINT.md) |
| [docs/](docs/) | Blueprints, methodology for reviewers, evaluation and scenario reports | [docs/METHODOLOGY.md](docs/METHODOLOGY.md) |

## Run the dashboard

You need Python with [uv](https://docs.astral.sh/uv/), and Node.js 22 or later.

```bash
# 1. Engine API (first start downloads NASA POWER weather and SoilGrids soil, then caches them)
cd ai_engine
uv sync
uv run uvicorn qatra_ai.service.app:app --port 8100

# 2. Optional: climate 2050 results for the Climate page (slow on first run; cached afterwards)
uv run python examples/climate_2050.py

# 3. Dashboard, in another terminal
cd frontend
npm install
npm run dev          # http://localhost:3000
```

The Assistant page needs `ANTHROPIC_API_KEY` set for the engine API, and each question is billed. Without a key, it shows the engine's ranked proposals instead.

## Data and licences

- **NASA POWER:** free.
- **SoilGrids:** CC BY 4.0.
- **NASA NEX-GDDP-CMIP6:** per CMIP6 model terms.
- **OpenStreetMap tiles:** © OpenStreetMap contributors; the public tile server is for light use only.
- **Open-Meteo** (optional reader): its free API is non-commercial only.

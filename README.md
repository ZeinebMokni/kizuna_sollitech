# QATRA

Agricultural water decision support for pump-irrigated farms in Tunisia. Its central question: when water, energy and information are scarce, where should we intervene first to prevent the most irreversible damage?

> **Status: research prototype.** Nothing is validated on real farms yet. The irrigation scheduler and the anomaly detectors are simulation-tested; everything else relies on published parameters (FAO‑56, FAO‑33, FAO‑29). The dashboard runs on a **hypothetical demo farm**, with real weather and soil for its location.

## What is here

| Folder | What it is | Docs |
|---|---|---|
| [ai_engine/](ai_engine/) | The decision engine (`qatra_ai`, Python): agronomy, scheduling, allocation, anomaly detection, suitability, climate scenarios, decision ranking, assistant, and a read-only HTTP API | [ai_engine/README.md](ai_engine/README.md) |
| [frontend/](frontend/) | Dashboard (Next.js) over the engine API | [frontend/README.md](frontend/README.md) |
| [backend/](backend/) | Authenticated FastAPI/PostgreSQL foundation for users, farms, parcels and irrigation zones | [backend/README.md](backend/README.md), [docs/BLUEPRINT.md](docs/BLUEPRINT.md) |
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

### Your own farms

QATRA runs on any farm described by a profile. Add `data/farms/<farm_id>.yaml`; [data/farms/README.md](data/farms/README.md) has a template. Profiles are git-ignored because they contain your farm's location. Then check them:

```bash
cd ai_engine
uv run python -m qatra_ai.farms.check
```

- **Live mode:** real farms are planned for today. Past weather comes from NASA POWER and Open-Meteo; the next days come from the Open-Meteo forecast.
- **Replay mode:** the demo farm replays its 2025 season.
- **API:** `GET /api/farms` lists the farms. Each farm's results are under `/api/farms/<farm_id>/` (`decision`, `water-balance`, `suitability`, `climate`, `anomalies`, `assistant`). The older routes (`/api/decision`, ...) answer for `QATRA_DEFAULT_FARM`, which defaults to the demo farm.
- **Missing inputs are refused, not guessed.**
  - No irrigation history: the API answers 409 and says what to add.
  - No soil data at the location: same (409).
  - A failed weather or soil download: 503.

### Assistant: choose Gemini or Claude

Add the settings to `.env` in the project root. The file is git-ignored.

```
# Gemini
QATRA_LLM_PROVIDER=gemini
GEMINI_API_KEY=your-key-from-google-ai-studio
# QATRA_GEMINI_MODEL=gemini-4-hydrogen   (default; any Gemini model ID works)

# or Claude
# QATRA_LLM_PROVIDER=anthropic
# ANTHROPIC_API_KEY=sk-ant-...
```

Then start the engine API with the file loaded:

```bash
uv run uvicorn qatra_ai.service.app:app --port 8100 --env-file ../.env
```

- **Provider choice:** if `QATRA_LLM_PROVIDER` is unset and only a Gemini key is present, Gemini is used.
- **Billing:** each question makes a few calls, billed by the provider.
- **Same checks either way:** the read-only tools, the grounding check and the fallback apply whichever model is used. Without a key, the page shows the engine's ranked proposals instead.

## Data and licences

- **NASA POWER:** free.
- **SoilGrids:** CC BY 4.0.
- **NASA NEX-GDDP-CMIP6:** per CMIP6 model terms.
- **OpenStreetMap tiles:** © OpenStreetMap contributors; the public tile server is for light use only.
- **Open-Meteo** (optional reader): its free API is non-commercial only.

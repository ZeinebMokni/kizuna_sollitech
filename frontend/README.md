# QATRA dashboard

Next.js 16 (App Router, `cacheComponents`), Tailwind 4, Recharts and Leaflet.
The dashboard combines the read-only engine API with the authenticated platform API.

## Run

```bash
npm install
npm run dev            # http://localhost:3000
```

The browser calls same-origin routes:

- `/api/*` -> engine API (`ENGINE_API_URL`, default `http://localhost:8100`)
- `/platform-api/*` -> authenticated platform API (`PLATFORM_API_URL`, default `http://localhost:8000`)

## Pages

| Route | Shows |
|---|---|
| `/` | Ranked interventions for the chosen day, key figures, farm map, data provenance |
| `/decisions` | Every decision package with reasons, evidence, alternatives, limits |
| `/schedule` | 72‑hour pump timeline, outcome by zone, binding limits and shadow prices |
| `/water` | Root-zone depletion against stress thresholds, per zone |
| `/crops` | FAO limiting-factor suitability by crop, with provisional factors marked |
| `/climate` | Change in dry-year irrigation need to 2041–2060, as a range across models |
| `/anomalies` | Water anomaly alerts on **simulated** hydraulic data |
| `/assistant` | Questions in Arabic, French or English, answered from engine results |
| `/platform/login` | Platform account login |
| `/platform/farms` | Authenticated farm registration and listing |
| `/platform/live` | Registered devices and measured sensor observations |
| `/platform/incidents` | Farmer reports and unverified evidence |

# QATRA dashboard

Next.js 16 (App Router, `cacheComponents`), Tailwind 4, Recharts and Leaflet. A read-only view over the QATRA engine API for the hypothetical demo farm.

## Run

```bash
npm install
npm run dev            # http://localhost:3000
```

The browser calls same-origin `/api/*`; [next.config.ts](next.config.ts) proxies those requests to the engine API at `ENGINE_API_URL` (default `http://localhost:8100`). Start the API first: see the [root README](../README.md).

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

## Not built yet

- Login and roles.
- Real farms and a database.
- The approval workflow; the button is disabled.
- Arabic and French interface text. Only the assistant answers in those languages.

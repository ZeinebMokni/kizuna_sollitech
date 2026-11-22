"""Farm strategy agent on the demo farm: web trend research + sensor-based engine state.

Uses the same LLM as the assistant (QATRA_LLM_PROVIDER / GEMINI_API_KEY or ANTHROPIC_API_KEY);
each run makes billed or quota-counted calls plus web searches. If web search is unavailable
it still returns an engine-based strategy; without any key, the engine-only fallback.
The demo farm's location, weather and soil are real; its zones and equipment are hypothetical.

    uv run --env-file ../.env python examples/strategy_demo.py [farm_id] ["question"] [ar|fr|en]
"""

from __future__ import annotations

import sys

from fastapi.testclient import TestClient

from qatra_ai.service.app import create_app

sys.stdout.reconfigure(encoding="utf-8")  # Arabic/French text on Windows consoles
farm = sys.argv[1] if len(sys.argv) > 1 else "demo-farm"
body: dict = {}
if len(sys.argv) > 2:
    body["question"] = sys.argv[2]
if len(sys.argv) > 3:
    body["language"] = sys.argv[3]

resp = TestClient(create_app()).post(f"/api/farms/{farm}/strategy", json=body)
resp.raise_for_status()
r = resp.json()["data"]
s = r["strategy"]
state = "verified" if r["verified"] else f"FALLBACK ({r['fallback_reason']})"
print(f"Strategy for {r['region']} as of {r['as_of']}  [{state}; {r['web_searches']} searches]\n")
print(s["summary"], "\n")
print("Now (from the farm's sensors, needs your approval):")
for a in s["immediate_actions"]:
    print(f"  - {a['action']} -> {a['target']}: {a['why']}")
print("\nSeason strategy:")
for x in s["season_strategy"]:
    print(f"  - {x['recommendation']} ({x['rationale']})")
print("\nMarket trends (web sources, not verified by QATRA):")
for t in s["market_trends"]:
    print(f"  - {t['crop']}: {t['trend']} [{t['direction']}, {t['published']}, {t['source_kind']}]")
for label, key in (("Risks", "risks"), ("Watch next", "watch_next"), ("Data gaps", "data_gaps")):
    if s[key]:
        print(f"\n{label}:")
        for x in s[key]:
            print(f"  - {x}")
if r["sources"]:
    print("\nSources:")
    for src in r["sources"]:
        print(f"  {src['url']}  {src.get('page_age') or ''}")
print(f"\n{r['disclaimer']}")

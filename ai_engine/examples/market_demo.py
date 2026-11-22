"""Market reflexivity demo: what happens to price if many farms follow one crop recommendation.

EVERY NUMBER BELOW IS HYPOTHETICAL. None comes from a Tunisian price or production series;
they only show what the module does. Replace them with verified data before any use.
"""

from __future__ import annotations

from qatra_ai.contracts import DataClass
from qatra_ai.market import (
    MarketOutlookRequest,
    MarketReference,
    Range,
    SupplyScenario,
    YieldDistribution,
    market_outlook,
)

HYPO = "HYPOTHETICAL demo value, not a real statistic"

req = MarketOutlookRequest(
    crop="tomato",
    region="demo region",
    price_unit="TND/t",
    reference=MarketReference(
        price=900.0,
        production_t=120_000,
        net_imports_t=0,
        elasticity=Range(low=-0.8, high=-0.3),
        source=HYPO,
        data_class=DataClass.SIMULATED,
    ),
    scenario=SupplyScenario(
        name="normal year, little trade",
        other_production_t=Range(low=105_000, high=130_000),
        imports_t=Range(low=0, high=3_000),
        exports_t=Range(low=0, high=8_000),
        source=HYPO,
    ),
    candidate_area_ha=800,
    yield_t_per_ha=YieldDistribution(p10=40, p50=55, p90=65, source=HYPO),
    cost_per_ha=22_000,
    alternative_margin_per_ha=15_000,
)

env = market_outlook(req)
out = env.payload
print(f"{out.crop} / {out.region}  [{out.scenario_kind}: {out.scenario_name}]")
print(f"confidence: {env.confidence.value}  ({'; '.join(env.confidence_reasons)})\n")
print("If this share of candidate farms follows the recommendation:")
print(f"{'share':>6} {'area ha':>8} {'price P10-P50-P90 (TND/t)':>28} "
      f"{'margin P50 TND/ha':>18} {'P(worse than alt.)':>19}")  # fmt: skip
for p in out.adoption:
    lo, hi = p.price.interval
    print(
        f"{p.share:>6.0%} {p.followed_area_ha:>8.0f} {lo:>9.0f} - {p.price.value:>5.0f} - "
        f"{hi:<6.0f} {p.margin_per_ha.value:>18.0f} {p.prob_below_alternative:>19.0%}"
    )
r = out.reflexivity
print(f"\nadoption cap: {r.adoption_cap_share:.0%} of candidate area ({r.adoption_cap_area_ha} ha)")
print(f"cobweb (everyone follows last season's price): {r.cobweb_behaviour}")
print(f"\nWhat moves the price most (at {out.influence_share:.0%} adoption):")
for d in out.influences:
    print(
        f"  {d.driver:<28} {d.price_at_low:>7.0f} -> {d.price_at_high:<7.0f} (swing {d.swing:.0f})"
    )
print("\nSignals:")
for s in out.signals:
    print(f"  [{s.severity}] {s.code}: {s.text}")
print(f"\n{out.disclaimer}")

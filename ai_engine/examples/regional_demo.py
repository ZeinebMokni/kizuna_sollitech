"""Regional reflexivity demo: the crop plan a group of following farms gets when the engine
ignores its own effect on prices, versus the plan that is still best at the prices it creates.

EVERY NUMBER BELOW IS HYPOTHETICAL. None comes from Tunisian statistics; replace them with
verified data before any use.
"""

from __future__ import annotations

from qatra_ai.contracts import DataClass
from qatra_ai.market.regional import CropMarket, RegionalRequest, regional_equilibrium
from qatra_ai.market.scenarios import MarketReference, Range, SupplyScenario, YieldDistribution

HYPO = "HYPOTHETICAL demo value, not a real statistic"


def crop(code, price, prod, eps, y, cost, water, trade=(0, 0)):
    return CropMarket(
        crop=code,
        reference=MarketReference(
            price=price,
            production_t=prod,
            elasticity=Range(low=eps[0], high=eps[1]),
            source=HYPO,
            data_class=DataClass.SIMULATED,
        ),
        scenario=SupplyScenario(
            name="normal year",
            other_production_t=Range(low=0.85 * prod, high=1.1 * prod),
            imports_t=Range(low=0, high=trade[0]),
            exports_t=Range(low=0, high=trade[1]),
            source=HYPO,
        ),
        yield_t_per_ha=YieldDistribution(p10=y[0], p50=y[1], p90=y[2], source=HYPO),
        cost_per_ha=cost,
        water_m3_per_ha=water,
    )


req = RegionalRequest(
    region="demo region",
    followers_land_ha=1500,
    followers_water_m3=1500 * 5000,
    crops=[
        crop("tomato", 900, 120_000, (-0.6, -0.3), (40, 55, 65), 22_000, 7000, (0, 8000)),
        crop("potato", 800, 90_000, (-0.7, -0.4), (20, 28, 34), 12_000, 5000, (5000, 0)),
        crop("durum_wheat", 950, 500_000, (-1.5, -0.8), (2.0, 3.5, 4.5), 1800, 3500),
    ],
    beta=0.3,
)

out = regional_equilibrium(req).payload
money = out.money_unit


def show(title, plan):
    areas = ", ".join(f"{c} {a:g} ha" for c, a in plan.area_ha.items() if a > 0.05)
    print(f"{title}: {areas or 'nothing'} (fallow {plan.fallow_ha:g} ha)")
    for c, q in plan.prices.items():
        print(f"    {c:<12} price P10-P50-P90: {q.interval[0]:g} - {q.value:g} - {q.interval[1]:g}")
    print(
        f"    group margin: expected {plan.expected_margin:,.0f} {money}, "
        f"worst-10% average {plan.cvar_margin:,.0f} {money}, P(loss) {plan.prob_loss:.0%}"
    )


n = out.naive
print(f"[{out.scenario_kind}] {out.region}: {req.followers_land_ha:g} ha of following farms\n")
show("Naive plan (ignores its own price effect)", n.plan)
print(
    f"    it promised {n.promised_expected_margin:,.0f} {money}; "
    f"overstatement {n.overstatement_pct:.0f}%\n"
)
if out.equilibrium:
    show(f"Equilibrium plan (converged in {out.iterations} iterations)", out.equilibrium)
else:
    print(f"No equilibrium found in {out.iterations} iterations.")
print(f"\nRe-planning every season from last season's prices: {out.undamped_behaviour}")
print("\nSignals:")
for s in out.signals:
    print(f"  {s['code']}: {s['text']}")
print(f"\n{out.disclaimer}")

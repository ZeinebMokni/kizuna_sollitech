"""Crop portfolio LP and regional reflexivity loop, on SYNTHETIC inputs (labelled test values)."""

import numpy as np
import pytest
from pydantic import ValidationError

from qatra_ai.contracts import Confidence, DataClass
from qatra_ai.market.regional import CropMarket, RegionalRequest, _Region, regional_equilibrium
from qatra_ai.market.scenarios import MarketReference, Range, SupplyScenario, YieldDistribution
from qatra_ai.optimization.portfolio import (
    CropOption,
    PortfolioRequest,
    evaluate_plan,
    solve_portfolio,
)

# --- portfolio LP ---------------------------------------------------------------------------


def opt(crop, margins, water=5000.0, **kw):
    return CropOption(crop=crop, water_m3_per_ha=water, margin_samples=list(margins), **kw)


def test_water_binds_and_has_positive_marginal_value():
    r = solve_portfolio(
        PortfolioRequest(land_ha=10, water_m3=20_000, options=[opt("a", [1000.0] * 50)], beta=0)
    )
    assert r.area_ha["a"] == pytest.approx(4.0)  # 20000 / 5000
    w = next(c for c in r.constraints if c.name == "water_m3")
    land = next(c for c in r.constraints if c.name == "land_ha")
    assert w.binding and not land.binding
    assert w.marginal_value == pytest.approx(1000 / 5000, rel=1e-3)


def test_risk_aversion_diversifies():
    rng = np.random.default_rng(0)
    s = rng.standard_normal(400)
    risky = 3000 + 4000 * s  # higher mean, large spread
    safe = 2500 - 300 * s  # lower mean, small spread, anti-correlated
    opts = [opt("risky", risky, water=0), opt("safe", safe, water=0)]
    neutral = solve_portfolio(PortfolioRequest(land_ha=10, water_m3=0, options=opts, beta=0))
    averse = solve_portfolio(PortfolioRequest(land_ha=10, water_m3=0, options=opts, beta=2))
    assert neutral.area_ha["risky"] == pytest.approx(10)
    assert 0 < averse.area_ha["risky"] < 10 and averse.area_ha["safe"] > 0
    assert averse.cvar_margin > neutral.cvar_margin
    assert averse.expected_margin < neutral.expected_margin


def test_cvar_from_lp_matches_direct_evaluation():
    rng = np.random.default_rng(1)
    m = {"a": 2000 + 1500 * rng.standard_normal(200), "b": 1500 + 500 * rng.standard_normal(200)}
    r = solve_portfolio(
        PortfolioRequest(
            land_ha=5,
            water_m3=1e9,
            options=[opt(k, v) for k, v in m.items()],
            beta=1.0,
            alpha=0.9,
        )
    )
    exp, cvar, _ = evaluate_plan(r.area_ha, m, 0.9)
    assert r.objective == pytest.approx(exp + 1.0 * cvar, rel=1e-4)


def test_exclusion_fallow_and_infeasibility():
    r = solve_portfolio(
        PortfolioRequest(
            land_ha=10,
            water_m3=1e9,
            options=[opt("n_class", [5000.0] * 20, excluded=True), opt("loser", [-100.0] * 20)],
        )
    )
    assert r.area_ha == {"n_class": 0.0, "loser": 0.0} and r.fallow_ha == 10
    bad = solve_portfolio(
        PortfolioRequest(land_ha=10, water_m3=1000, options=[opt("a", [1.0] * 5, min_ha=2)])
    )
    assert not bad.feasible and "minimum areas" in bad.note
    with pytest.raises(ValidationError):
        PortfolioRequest(land_ha=1, water_m3=1, options=[opt("a", [1.0]), opt("b", [1.0, 2.0])])


# --- regional reflexivity -------------------------------------------------------------------


def market(crop, price, prod, eps=(-0.5, -0.3), y=(40, 55, 65), cost=25_000, water=6000, **kw):
    return CropMarket(
        crop=crop,
        reference=MarketReference(
            price=price,
            production_t=prod,
            elasticity=Range(low=eps[0], high=eps[1]),
            source="synthetic test",
            data_class=DataClass.SIMULATED,
        ),
        scenario=SupplyScenario(
            name="t", other_production_t=Range(low=0.9 * prod, high=1.1 * prod), source="test"
        ),
        yield_t_per_ha=YieldDistribution(p10=y[0], p50=y[1], p90=y[2], source="synthetic"),
        cost_per_ha=cost,
        water_m3_per_ha=water,
        **kw,
    )


def region_req(land=2000.0, **kw):
    base = dict(
        region="test",
        followers_land_ha=land,
        followers_water_m3=land * 6000,
        crops=[
            market("tomato", 1000, 100_000),  # attractive but small, inelastic market
            market("wheat", 900, 400_000, eps=(-1.5, -1.0), y=(2, 3.5, 4.5), cost=1500, water=3000),
        ],
        beta=0.3,
        n_samples=400,
    )
    base.update(kw)
    return RegionalRequest(**base)


def test_large_follower_group_crowds_its_own_market():
    env = regional_equilibrium(region_req())
    out = env.payload
    assert out.converged
    assert out.naive.overstatement_pct > 10
    assert out.equilibrium.area_ha["tomato"] < out.naive.plan.area_ha["tomato"]
    codes = {s["code"] for s in out.signals}
    assert {"NAIVE_PLAN_OVERSTATES", "CROWDED_CROP"} <= codes
    assert env.confidence == Confidence.LOW and out.scenario_kind == "hypothetical"
    for q in out.equilibrium.prices.values():
        assert q.interval_kind == "quantile_10_90"


def test_equilibrium_is_optimal_at_its_own_prices():
    req = region_req()
    out = regional_equilibrium(req).payload
    region = _Region(req)
    x = out.equilibrium.area_ha
    m = region.margins(x)
    best = region.portfolio(m)
    gap = region.objective(best.area_ha, m) - region.objective(x, m)
    assert gap <= req.tol * abs(region.objective(best.area_ha, m)) + 1.0


def test_small_follower_group_is_a_price_taker():
    out = regional_equilibrium(region_req(land=5.0)).payload
    assert out.converged and abs(out.naive.overstatement_pct) < 2
    assert out.equilibrium.area_ha == pytest.approx(out.naive.plan.area_ha, abs=0.05)
    assert "NAIVE_PLAN_OVERSTATES" not in {s["code"] for s in out.signals}


def test_regional_cap_is_respected():
    out = regional_equilibrium(region_req(max_share_per_crop=0.1)).payload
    for plan in (out.naive.plan, out.equilibrium):
        assert all(a <= 200 + 1e-6 for a in plan.area_ha.values())


def test_undamped_replanning_cycles_when_crowded():
    out = regional_equilibrium(region_req()).payload
    assert out.undamped_behaviour == "cycles"
    assert "BOOM_BUST_RISK" in {s["code"] for s in out.signals}

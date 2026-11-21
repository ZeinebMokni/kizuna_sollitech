"""Allocation tests on SYNTHETIC farms (labelled test input)."""

import pytest

from qatra_ai.optimization.allocation import (
    DISCLAIMER,
    AllocationPolicy,
    AllocationRequest,
    AquiferUnit,
    CropBlock,
    Farm,
    _gini,
    _jain,
    compare_allocations,
    water_fill,
)


def farms():
    return [
        Farm(
            farm_id="F1-olive",
            aquifer_id="A",
            pump_capacity_m3=5000,
            permit_m3=3000,
            blocks=[
                CropBlock(block_id="olive", crop="olive", area_ha=4, demand_m3=4000, perennial=True)
            ],
        ),
        Farm(
            farm_id="F2-tomato",
            aquifer_id="A",
            pump_capacity_m3=5000,
            permit_m3=3000,
            blocks=[
                CropBlock(block_id="tomato", crop="tomato", area_ha=2, demand_m3=4000, ky=1.05)
            ],
        ),
        Farm(
            farm_id="F3-mixed",
            aquifer_id="A",
            pump_capacity_m3=2500,
            permit_m3=2000,
            vulnerability_weight=1.5,
            blocks=[
                CropBlock(block_id="potato", crop="potato", area_ha=1, demand_m3=1500, ky=1.1),
                CropBlock(block_id="wheat", crop="durum_wheat", area_ha=2, demand_m3=1500, ky=1.15),
            ],
        ),
    ]


def request(available, human=0.0, **kw):
    return AllocationRequest(
        period_label="test week",
        farms=kw.pop("farms_", farms()),
        aquifers=[
            AquiferUnit(
                aquifer_id="A",
                sustainable_yield_m3=available,
                human_reservation_m3=human,
                source_note="synthetic test value",
            )
        ],
        **kw,
    )


def results(env):
    return {s.strategy: s for s in env.payload.strategies}


def test_abundant_water_everyone_satisfied():
    r = results(compare_allocations(request(50_000)))
    for s in r.values():
        assert s.feasible
        for f in s.farms:
            expected = min(f.demand_m3, 2500 if f.farm_id == "F3-mixed" else 5000)
            assert f.allocation_m3 == pytest.approx(expected, rel=1e-6)


def test_hard_limits_respected_by_every_strategy():
    env = compare_allocations(request(9000, human=1000))  # 8000 available
    assert env.payload.available_by_aquifer_m3["A"] == 8000
    caps = {f.farm_id: f.pump_capacity_m3 for f in farms()}
    for s in results(env).values():
        if not s.feasible:
            continue
        assert s.total_allocated_m3 <= 8000 + 1e-6
        for f in s.farms:
            assert f.allocation_m3 <= caps[f.farm_id] + 1e-6
            assert f.allocation_m3 <= f.demand_m3 + 1e-6


def test_min_loss_is_optimal_and_max_min_is_fairest():
    # With all vulnerability weights = 1, S4's objective equals the reported total loss,
    # so no other strategy may report a lower loss.
    flat = [f.model_copy(update={"vulnerability_weight": 1.0}) for f in farms()]
    rf = results(compare_allocations(request(6000, farms_=flat)))
    for sid, s in rf.items():
        if s.feasible:
            assert rf["S4"].total_loss_ha_eq <= s.total_loss_ha_eq + 1e-6, sid
    # With real weights, S4 minimises the *weighted* loss.
    rw = results(compare_allocations(request(6000)))
    for sid, s in rw.items():
        if s.feasible:
            assert rw["S4"].weighted_loss <= s.weighted_loss + 1e-6, sid
    # S6 maximises the worst-off farm's satisfaction.
    r = results(compare_allocations(request(6000)))
    for sid, s in r.items():
        if s.feasible:
            assert r["S6"].fairness["min_satisfaction"] >= s.fairness["min_satisfaction"] - 1e-6, (
                sid
            )


def test_proportional_to_permits_when_uncapped():
    r = results(compare_allocations(request(4000)))  # well below every cap
    s1 = {f.farm_id: f.allocation_m3 for f in r["S1"].farms}
    assert s1["F1-olive"] == pytest.approx(s1["F2-tomato"])
    assert s1["F1-olive"] / s1["F3-mixed"] == pytest.approx(3000 / 2000, rel=1e-4)
    assert all(f.delta_vs_s1_m3 == 0 for f in r["S1"].farms)


def test_crop_priority_serves_perennial_first():
    r = results(compare_allocations(request(3000)))
    s3 = {f.farm_id: f.allocation_m3 for f in r["S3"].farms}
    assert s3["F1-olive"] == pytest.approx(3000)
    assert s3["F2-tomato"] == 0


def test_irreversibility_penalty_protects_perennial_in_min_loss():
    r = results(compare_allocations(request(5000)))
    olive = next(f for f in r["S4"].farms if f.farm_id == "F1-olive")
    assert olive.satisfaction >= 0.5 - 1e-6  # kept at/above its survival threshold
    assert olive.irreversible_loss_ha_eq == pytest.approx(0, abs=1e-6)


def test_infeasible_floors_are_explained():
    pol = AllocationPolicy(phi_min_satisfaction=0.9)
    r = results(compare_allocations(request(5000, policy=pol)))
    assert not r["S5"].feasible
    assert "highest equal satisfaction" in r["S5"].note


def test_marginal_value_positive_under_scarcity_zero_when_abundant():
    scarce = results(compare_allocations(request(6000)))["S4"]
    plenty = results(compare_allocations(request(50_000)))["S4"]
    assert scarce.marginal_loss_avoided_per_m3["A"] > 0
    assert plenty.marginal_loss_avoided_per_m3["A"] == pytest.approx(0, abs=1e-9)


def test_disclaimer_and_unknown_ky_flag():
    env = compare_allocations(request(6000))
    assert env.payload.disclaimer == DISCLAIMER
    assert any("Ky missing" in r for r in env.confidence_reasons)  # olive has no Ky


def test_water_fill_and_fairness_indices():
    out = water_fill({"a": 1, "b": 1, "c": 2}, {"a": 10, "b": 100, "c": 100}, 100)
    assert out["a"] == pytest.approx(10) and out["b"] == pytest.approx(30)
    assert out["c"] == pytest.approx(60)
    assert _gini([0.5, 0.5, 0.5]) == pytest.approx(0) and _jain([0.5, 0.5]) == pytest.approx(1)
    assert _gini([0, 0, 1]) == pytest.approx(2 / 3)


def test_unknown_aquifer_rejected():
    with pytest.raises(ValueError, match="unknown aquifer"):
        AllocationRequest(
            period_label="x",
            farms=farms(),
            aquifers=[AquiferUnit(aquifer_id="B", sustainable_yield_m3=1, source_note="t")],
        )

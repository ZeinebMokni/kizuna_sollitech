"""Orchestrator tests on SYNTHETIC farms and hydraulic data (labelled test input)."""

import json
from datetime import date, datetime, timedelta

import pandas as pd

from qatra_ai.agronomy.crops import get_crop
from qatra_ai.agronomy.soil import SoilWaterProperties
from qatra_ai.agronomy.water_balance import ZoneSetup
from qatra_ai.contracts import Confidence, DataClass, Provenance
from qatra_ai.evaluation.synthetic_water import generate
from qatra_ai.optimization.schedule_models import PumpSystem
from qatra_ai.orchestrator.decision import FarmContext, HydraulicData, ZoneContext, decide
from qatra_ai.predictive.anomaly import FORBIDDEN_TERMS

SOIL = SoilWaterProperties(
    theta_fc=0.28, theta_wp=0.155, data_class=DataClass.INFERRED, source="t", method="t"
)
PROV = Provenance(data_class=DataClass.INFERRED, source="water_balance", quality_grade="C")


def zone(zid, crop, start, dr, flow=10.0, prov=PROV):
    return ZoneContext(
        zid,
        ZoneSetup(
            crop=get_crop(crop),
            season_start=start,
            soil=SOIL,
            area_ha=1.0,
            application_efficiency=0.9,
        ),
        flow,
        dr,
        prov,
    )


def ctx(zones, as_of=datetime(2026, 6, 15), **kw):
    idx = pd.date_range(as_of.date(), periods=5, freq="D")
    fc = pd.DataFrame({"et0": 7.0, "precip": 0.0, "rs": 28.0}, index=idx)
    base = dict(
        farm_id="F1",
        as_of=as_of,
        zones=zones,
        forecast_daily=fc,
        forecast_source="synthetic",
        grid_hours=frozenset(range(24)),
        grid_max_kw=20,
        pump=PumpSystem(
            max_flow_m3h=12, max_simultaneous_zones=1, total_head_m=50, pump_efficiency=0.55
        ),
    )
    base.update(kw)
    return FarmContext(**base)


def by_target(env):
    return {p.target: p for p in env.payload.packages}


def test_ranking_tiers_and_actions():
    zones = [
        zone("citrus", "citrus", date(2026, 3, 1), 0.0),  # deep roots at FC: no stress
        zone("tomato", "tomato", date(2026, 4, 1), 30.0),  # mid stage (Ky 1.1), near RAW
        zone("olive", "olive", date(2026, 3, 1), 140.0),  # perennial, heading to severe
    ]
    env = decide(ctx(zones))
    pk = by_target(env)
    assert pk["olive"].tier == 1 and pk["tomato"].tier == 1
    assert pk["citrus"].tier == 3 and pk["citrus"].action == "no_action"
    ranks = [p.target for p in env.payload.packages]
    assert ranks.index("citrus") == 2  # no-action zone ranked last
    for p in env.payload.packages:
        assert p.priority_trace and p.reasons
        if p.action == "irrigate":
            assert p.requires_human_approval and p.amount.unit == "m3" and p.windows


def test_shallow_rooted_zone_near_harvest_still_flags_stress():
    # Potato late stage: TAW ~50 mm, ETc ~6 mm/d -> stress in ~1.5 days (engine, not test, knows)
    env = decide(ctx([zone("potato", "potato", date(2026, 3, 1), 0.0)]))
    p = by_target(env)["potato"]
    assert p.tier == 2 and any("days to stress" in t for t in p.priority_trace)


def test_quality_gate_unknown_state():
    zones = [
        zone("tomato", "tomato", date(2026, 4, 1), None, prov=None),
        zone("potato", "potato", date(2026, 3, 1), 0.0),
    ]
    env = decide(ctx(zones))
    t = by_target(env)["tomato"]
    assert t.action == "insufficient_evidence"
    assert t.confidence == Confidence.INSUFFICIENT_EVIDENCE
    assert env.confidence == Confidence.INSUFFICIENT_EVIDENCE  # weakest package


def test_safety_veto_holds_zone_with_burst_and_ranks_first():
    sysd = generate(seed=3, faults=("burst_zone_B",))
    burst = sysd.faults[0]
    as_of = (burst.end + pd.Timedelta(hours=1)).to_pydatetime()
    hyd = HydraulicData(
        sysd.data.loc[: burst.end], sysd.schedule.loc[: burst.end], sysd.design_flow_m3h
    )
    zones = [
        zone("A", "tomato", date(2026, 4, 1), 40.0),
        zone("B", "tomato", date(2026, 4, 1), 40.0),
    ]
    env = decide(ctx(zones, as_of=as_of, hydraulics=hyd))
    first = env.payload.packages[0]
    assert first.tier == 0
    b = [p for p in env.payload.packages if p.target == "B"]
    assert any(p.action == "hold_zone" for p in b)
    assert not any(p.action == "irrigate" for p in b)  # held zone is never scheduled
    assert env.payload.anomalies_detected >= 1


def test_no_accusatory_language_and_physical_actions_need_approval():
    sysd = generate(seed=4, faults=("valve_C_stuck_open", "burst_zone_B"))
    end = max(f.end for f in sysd.faults)
    hyd = HydraulicData(sysd.data.loc[:end], sysd.schedule.loc[:end], sysd.design_flow_m3h)
    zones = [zone(z, "tomato", date(2026, 4, 1), 35.0) for z in ("A", "B", "C")]
    env = decide(ctx(zones, as_of=(end + timedelta(hours=1)).to_pydatetime(), hydraulics=hyd))
    text = json.dumps(env.model_dump(mode="json")).lower()
    for term in FORBIDDEN_TERMS:
        assert term not in text
    for p in env.payload.packages:
        if p.action in ("irrigate", "hold_zone"):
            assert p.requires_human_approval


def test_accept_deficit_explained_when_resources_insufficient():
    zones = [zone("tomato", "tomato", date(2026, 4, 1), 60.0)]
    env = decide(ctx(zones, grid_hours=frozenset(), grid_max_kw=0))  # no energy at all
    t = by_target(env)["tomato"]
    assert t.action == "accept_deficit"
    assert any(r.code == "ENERGY_LIMITED" for r in t.reasons)

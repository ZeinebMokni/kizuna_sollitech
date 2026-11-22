"""Zone water assessment: runs the agronomic chain and wraps it in an EngineEnvelope.

Chain: daily ET0 table -> water balance (with optional assimilation) -> current state,
seasonal totals, stage-wise relative yield, refill requirement, optional days-to-stress.

Confidence is derived from explicit rules (never from a hidden score). Each rule caps the
confidence level and adds a human-readable reason.
"""

from __future__ import annotations

import uuid
from collections import Counter
from datetime import date

import pandas as pd
from pydantic import BaseModel

from qatra_ai.agronomy.daily_et0 import METHOD_HS, METHOD_PM
from qatra_ai.agronomy.irrigation import IrrigationRequirement, irrigation_requirement
from qatra_ai.agronomy.water_balance import ZoneSetup, days_to_stress, simulate_water_balance
from qatra_ai.agronomy.yield_response import relative_yield_stagewise
from qatra_ai.contracts import (
    Confidence,
    DataClass,
    EngineEnvelope,
    ModelInfo,
    Quantity,
    ValidationStatus,
    inputs_hash,
)

ENGINE = "agronomy.zone_water_assessment"
MODEL = ModelInfo(
    model_id="fao56_single_kc_water_balance",
    version="0.1.0",
    validation_status=ValidationStatus.LITERATURE_PARAMETERISED,
    references=[
        "FAO-56 (Allen et al., 1998)",
        "FAO-33 (Doorenbos & Kassam, 1979)",
        "Saxton & Rawls (2006)",
    ],
)

_ORDER = [Confidence.INSUFFICIENT_EVIDENCE, Confidence.LOW, Confidence.MEDIUM, Confidence.HIGH]

STANDING_LIMITATIONS = [
    "Runoff and capillary rise are assumed to be zero.",
    "Rain below 0.2 x ET0 is treated as fully evaporated.",
    "Single crop coefficient: soil evaporation after wetting is not modelled separately.",
]


class ZoneWaterAssessment(BaseModel):
    as_of: date
    season_day: int
    stage: str
    depletion: Quantity
    total_available_water: Quantity
    readily_available_water: Quantity
    ks: float
    stressed: bool
    days_to_stress: int | None
    season_totals: dict[str, Quantity]
    relative_transpiration: float | None
    relative_yield_estimate: float | None
    relative_yield_unavailable_reasons: list[str]
    refill_requirement: IrrigationRequirement
    daily: list[dict]


def _cap(current: Confidence, cap: Confidence) -> Confidence:
    return min(current, cap, key=_ORDER.index)


def assess_zone_water(
    setup: ZoneSetup,
    weather: pd.DataFrame,
    *,
    weather_source: str,
    weather_data_class: DataClass,
    irrigation_gross_mm: pd.Series | None = None,
    soil_moisture_obs: pd.DataFrame | None = None,
    forecast: pd.DataFrame | None = None,
    design_flow_m3h: float | None = None,
    request_id: str | None = None,
) -> EngineEnvelope[ZoneWaterAssessment]:
    """`weather` must contain et0 + et0_method (see daily_et0.compute_daily_et0) and precip."""
    request_id = request_id or str(uuid.uuid4())

    def records(obj: pd.DataFrame | pd.Series | None) -> list[dict] | None:
        if obj is None:
            return None
        frame = obj.to_frame("value") if isinstance(obj, pd.Series) else obj
        return frame.reset_index().astype(str).to_dict("records")

    snapshot = {
        "setup": setup.model_dump(mode="json"),
        "weather": records(weather),
        "irrigation": records(irrigation_gross_mm),
        "obs": records(soil_moisture_obs),
        "forecast": records(forecast),
        "design_flow_m3h": design_flow_m3h,
    }
    env_common = dict(
        request_id=request_id, engine=ENGINE, model=MODEL, inputs_hash=inputs_hash(snapshot)
    )

    # --- Quality gate ------------------------------------------------------------------
    missing: list[str] = []
    methods = weather.get("et0_method", pd.Series("unknown", index=weather.index))
    share_missing = float((methods == "missing").mean()) if len(methods) else 1.0
    if share_missing > 0.3:
        missing.append("ET0 for more than 30 % of days")
    if "precip" not in weather or weather["precip"].isna().any():
        missing.append("complete daily precipitation")
    if missing:
        return EngineEnvelope[ZoneWaterAssessment](
            **env_common,
            confidence=Confidence.INSUFFICIENT_EVIDENCE,
            confidence_reasons=["required inputs missing"],
            missing_inputs=missing,
            limitations=STANDING_LIMITATIONS,
        )

    table, notes = simulate_water_balance(setup, weather, irrigation_gross_mm, soil_moisture_obs)
    last = table.iloc[-1]

    # --- Confidence rules ----------------------------------------------------------------
    conf, reasons = Confidence.HIGH, []
    limitations = list(STANDING_LIMITATIONS) + notes + list(setup.crop.limitations)

    if setup.crop.review_status != "reviewed":
        conf = _cap(conf, Confidence.MEDIUM)
        reasons.append(
            f"crop parameters for '{setup.crop.code}' are literature values, not locally reviewed"
        )
    if setup.soil.data_class != DataClass.MEASURED:
        conf = _cap(conf, Confidence.MEDIUM)
        reasons.append(
            f"soil FC/WP are {setup.soil.data_class.value} ({setup.soil.method}), not measured"
        )
    assimilated = int(table["flags"].str.split(",").apply(lambda f: "assimilated" in f).sum())
    if setup.initial_depletion_mm is None and assimilated == 0:
        conf = _cap(conf, Confidence.LOW)
        reasons.append("initial soil water unknown and no calibrated sensor corrected it")
    share_hs = float((methods == METHOD_HS).mean())
    if share_hs > 0.2:
        conf = _cap(conf, Confidence.MEDIUM if conf == Confidence.HIGH else Confidence.LOW)
        reasons.append(f"{share_hs:.0%} of days used temperature-only ET0 (Hargreaves)")
    share_gap = float(table["flags"].str.contains("et0_gap_filled").mean())
    if share_gap > 0.1:
        conf = _cap(conf, Confidence.LOW)
        reasons.append(f"{share_gap:.0%} of days had ET0 gap-filled")
    if weather_data_class in (DataClass.SIMULATED, DataClass.PROJECTED):
        conf = _cap(conf, Confidence.LOW)
        reasons.append(f"weather input is {weather_data_class.value}")

    # --- Derived outputs -------------------------------------------------------------------
    dts = None
    if forecast is not None:
        dts, _ = days_to_stress(setup, float(last["dr_end_mm"]), forecast)
        if dts is not None:
            dts += 1  # forecast starts the day after `as_of`

    rel_yield, ry_reasons = relative_yield_stagewise(setup.crop, table)
    etc_sum, eta_sum = table["etc_mm"].sum(), table["eta_mm"].sum()
    mm = lambda v: Quantity(value=round(float(v), 2), unit="mm")  # noqa: E731

    payload = ZoneWaterAssessment(
        as_of=table.index[-1].date(),
        season_day=int(last["season_day"]),
        stage=str(last["stage"]),
        depletion=Quantity(
            value=round(float(last["dr_end_mm"]), 2),
            unit="mm",
            interval=(
                max(0.0, round(float(last["dr_end_mm"] - last["depletion_std_mm"]), 2)),
                round(float(last["dr_end_mm"] + last["depletion_std_mm"]), 2),
            ),
            interval_kind="plus_minus_1_std",
        ),
        total_available_water=mm(last["taw_mm"]),
        readily_available_water=mm(last["raw_mm"]),
        ks=round(float(last["ks"]), 3),
        stressed=bool(last["dr_end_mm"] > last["raw_mm"]),
        days_to_stress=dts,
        season_totals={
            "et0": mm(table["et0_mm"].sum()),
            "etc": mm(etc_sum),
            "eta": mm(eta_sum),
            "effective_rain": mm(table["peff_mm"].sum()),
            "irrigation_net": mm(table["irrigation_net_mm"].sum()),
            "deep_percolation": mm(table["deep_percolation_mm"].sum()),
        },
        relative_transpiration=round(eta_sum / etc_sum, 3) if etc_sum > 0 else None,
        relative_yield_estimate=None if rel_yield is None else round(rel_yield, 3),
        relative_yield_unavailable_reasons=ry_reasons,
        refill_requirement=irrigation_requirement(
            depletion_mm=float(last["dr_end_mm"]),
            area_ha=setup.area_ha,
            application_efficiency=setup.application_efficiency,
            design_flow_m3h=design_flow_m3h,
        ),
        daily=table.reset_index()
        .assign(date=lambda d: d["date"].dt.date.astype(str))
        .to_dict("records"),
    )

    provenance = Counter({weather_data_class: len(table), setup.soil.data_class: 1})
    if assimilated:
        provenance[DataClass.MEASURED] += int(assimilated)
    if share_hs == 0 and (methods == METHOD_PM).all():
        reasons.append("ET0 computed with full Penman-Monteith on all days")

    return EngineEnvelope[ZoneWaterAssessment](
        **env_common,
        confidence=conf,
        confidence_reasons=reasons,
        limitations=limitations,
        provenance_summary=dict(provenance),
        payload=payload,
    )

"""Contracts for the multi-zone irrigation scheduler (AI_ENGINE_BLUEPRINT section 6.1)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from qatra_ai.contracts import DataClass


class SchedulingZone(BaseModel):
    """One irrigation zone, with per-slot crop demand already computed by the agronomy engine."""

    model_config = ConfigDict(frozen=True)

    zone_id: str
    area_ha: float = Field(gt=0)
    design_flow_m3h: float = Field(gt=0)
    application_efficiency: float = Field(gt=0, le=1)
    initial_depletion_mm: float = Field(ge=0)
    taw_mm: float = Field(gt=0)
    raw_mm: float = Field(gt=0)
    etc_mm: list[float] = Field(description="Crop ET per slot [mm] (no stress reduction)")
    peff_mm: list[float] = Field(description="Effective rain per slot [mm]")
    ky: list[float] = Field(description="Yield-response factor of the growth stage, per slot")
    ky_assumed: bool = Field(False, description="True if Ky was missing and a default was used")
    perennial: bool = False
    max_hours_per_day: float | None = Field(default=None, gt=0, le=24)

    @model_validator(mode="after")
    def _check(self) -> SchedulingZone:
        if self.raw_mm > self.taw_mm:
            raise ValueError(f"{self.zone_id}: RAW must be <= TAW")
        if not (len(self.etc_mm) == len(self.peff_mm) == len(self.ky)):
            raise ValueError(f"{self.zone_id}: etc_mm, peff_mm and ky must have equal length")
        if min(self.etc_mm, default=0) < 0 or min(self.peff_mm, default=0) < 0:
            raise ValueError(f"{self.zone_id}: ET and rain must be >= 0")
        return self


class PumpSystem(BaseModel):
    model_config = ConfigDict(frozen=True)

    max_flow_m3h: float = Field(gt=0, description="Pump / well yield limit")
    max_simultaneous_zones: int = Field(ge=1)
    total_head_m: float = Field(gt=0)
    pump_efficiency: float = Field(gt=0, le=1)
    motor_efficiency: float = Field(default=0.9, gt=0, le=1)


class WaterSource(BaseModel):
    """Well/aquifer limits. Both caps are optional; None means 'not constrained / unknown'."""

    model_config = ConfigDict(frozen=True)

    max_volume_m3: float | None = Field(default=None, ge=0, description="Cap over the horizon")
    max_volume_per_day_m3: float | None = Field(default=None, ge=0)
    note: str | None = None


class BatterySpec(BaseModel):
    model_config = ConfigDict(frozen=True)

    capacity_kwh: float = Field(gt=0)
    soc_initial_kwh: float = Field(ge=0)
    soc_min_kwh: float = Field(ge=0)
    soc_max_kwh: float = Field(gt=0)
    max_charge_kw: float = Field(gt=0)
    max_discharge_kw: float = Field(gt=0)
    charge_efficiency: float = Field(default=0.95, gt=0, le=1)
    discharge_efficiency: float = Field(default=0.95, gt=0, le=1)

    @model_validator(mode="after")
    def _check(self) -> BatterySpec:
        if not (self.soc_min_kwh <= self.soc_initial_kwh <= self.soc_max_kwh <= self.capacity_kwh):
            raise ValueError("battery requires soc_min <= soc_initial <= soc_max <= capacity")
        return self


class EnergySupply(BaseModel):
    model_config = ConfigDict(frozen=True)

    pv_kwh: list[float] = Field(description="Conservative PV energy available per slot [kWh]")
    pv_data_class: DataClass = DataClass.PROJECTED
    grid_available: list[bool]
    grid_max_kw: float = Field(default=0.0, ge=0)
    grid_cost_per_kwh: list[float] | None = None
    battery: BatterySpec | None = None


class PriorityPolicy(BaseModel):
    """How stress is weighted. Every value is reported with the plan; none is hidden."""

    model_config = ConfigDict(frozen=True)

    # Default 2: knee of the full-season trade-off curve (docs/evaluation/
    # scheduler_closed_loop_2025.md). A policy choice, adjustable by the user.
    kappa_perennial: float = Field(
        default=2.0, ge=0, description="Extra weight on severe stress, perennials"
    )
    kappa_annual: float = Field(
        default=1.0, ge=0, description="Extra weight on severe stress, annuals"
    )
    severe_fraction: float = Field(
        default=0.5,
        gt=0,
        lt=1,
        description="Severe tier starts at RAW + severe_fraction * (TAW - RAW)",
    )
    lambda_water_per_m3: float = Field(default=1e-3, ge=0, description="Tie-breaker: save water")
    lambda_energy: float = Field(default=1e-2, ge=0, description="Tie-breaker: avoid grid cost")
    default_ky: float = Field(default=1.0, gt=0)


class ScheduleRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    start: datetime
    slot_hours: float = Field(default=1.0, gt=0, le=6)
    n_slots: int = Field(ge=1, le=24 * 7)
    allowed: list[bool] | None = Field(default=None, description="Operating window per slot")
    zones: list[SchedulingZone] = Field(min_length=1)
    pump: PumpSystem
    water: WaterSource = WaterSource()
    energy: EnergySupply
    policy: PriorityPolicy = PriorityPolicy()
    time_limit_s: float = Field(default=20.0, gt=0, le=300)
    mip_relative_gap: float = Field(default=1e-4, gt=0, le=0.05)

    @model_validator(mode="after")
    def _lengths(self) -> ScheduleRequest:
        n = self.n_slots
        for z in self.zones:
            if len(z.etc_mm) != n:
                raise ValueError(f"zone {z.zone_id}: series length {len(z.etc_mm)} != n_slots {n}")
        if len({z.zone_id for z in self.zones}) != len(self.zones):
            raise ValueError("zone ids must be unique")
        e = self.energy
        if len(e.pv_kwh) != n or len(e.grid_available) != n:
            raise ValueError("energy series must have n_slots entries")
        if e.grid_cost_per_kwh is not None and len(e.grid_cost_per_kwh) != n:
            raise ValueError("grid_cost_per_kwh must have n_slots entries")
        if self.allowed is not None and len(self.allowed) != n:
            raise ValueError("allowed must have n_slots entries")
        return self


# --- Outputs ------------------------------------------------------------------------------

ZoneReason = Literal[
    "NO_STRESS_EXPECTED_IN_HORIZON",
    "IRRIGATED_TO_PREVENT_STRESS",
    "IRRIGATED_STRESS_REDUCED",
    "PUMP_CAPACITY_SHARED",
    "ENERGY_LIMITED",
    "WATER_VOLUME_CAP",
    "DAILY_HOURS_LIMIT",
    "OPERATING_WINDOW_OR_FLOW_LIMIT",
    "PRIORITY_TRADE_OFF",
]


class SlotAction(BaseModel):
    zone_id: str
    slot: int
    start: datetime
    end: datetime
    volume_m3: float
    net_depth_mm: float


class ZonePlan(BaseModel):
    zone_id: str
    volume_m3: float
    irrigation_hours: float
    net_depth_mm: float
    depletion_start_mm: float
    depletion_end_mm: float
    max_depletion_mm: float
    raw_mm: float
    taw_mm: float
    stress_mm_h: float = Field(description="Sum over slots of max(0, Dr - RAW) * slot_hours")
    stress_mm_h_without_irrigation: float
    severe_stress_slots: int
    severe_stress_slots_without_irrigation: int
    perennial: bool
    weight_summary: str
    reasons: list[ZoneReason]
    reason_details: list[str]


class ConstraintReport(BaseModel):
    name: str
    binding_slots: int
    shadow_price: float | None = None
    shadow_price_meaning: str | None = None


class SchedulePlan(BaseModel):
    status: Literal["optimal", "feasible"]
    objective: float
    mip_gap: float | None
    solve_time_s: float
    solver: str
    actions: list[SlotAction]
    zones: list[ZonePlan]
    totals: dict[str, float]
    constraints: list[ConstraintReport]
    unweighted_comparison: dict[str, float] | None = Field(
        None, description="Volume per zone [m3] if every zone's stress counted equally"
    )
    policy: PriorityPolicy
    assumptions: list[str]
    verification_violations: list[str]

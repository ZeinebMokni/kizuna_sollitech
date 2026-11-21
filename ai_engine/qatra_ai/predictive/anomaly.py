"""Water anomaly detection for a pumped irrigation system (rule-based + robust statistics).

No machine learning is trained here: confirmed leak labels are not available. Every detector
is explainable, and every event lists *possible* causes with their evidence. The engine never
concludes misconduct. Words such as "theft" are banned from outputs (enforced by tests).

Input (hourly, DatetimeIndex):
    inlet_m3h            flow at the well/pump meter                          (required)
    zone_<id>_m3h        flow at a zone meter                                  (optional)
    pressure_kpa         mainline pressure                                     (optional)
    pump_on              pump status signal (bool)                             (optional)
schedule: DataFrame of booleans, one column per zone id: which zones SHOULD be irrigating.

Detectors:
    idle_flow        flow while no zone is scheduled
    pump_status      flow while the pump reports OFF, or no flow while it reports ON + scheduled
    flow_excess      flow above expected (sum of calibrated zone flows) beyond tolerance
    flow_deficit     flow below expected beyond tolerance
    zone_mismatch    inlet vs sum of zone meters (water accounting), when zone meters exist
    pressure_drop    pressure far below its history for the same set of active zones
    stuck_meter      inlet flat-lines while the schedule changes
    slow_leak        one-sided CUSUM on the normalised flow residual (small persistent excess)

Baseline calibration: actual zone flows differ from design flows. The expected flow is
calibrated as median(inlet / design-expected) over a training window that the caller asserts
is fault-free (or the first `train_days`). If that window contains faults, detection degrades.
This is a stated assumption.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Literal

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field

AnomalyKind = Literal[
    "idle_flow",
    "pump_status",
    "flow_excess",
    "flow_deficit",
    "zone_mismatch",
    "pressure_drop",
    "stuck_meter",
    "slow_leak",
]
FORBIDDEN_TERMS = ("theft", "steal", "stolen", "fraud", "illegal")


class Hypothesis(BaseModel):
    cause: str
    likelihood: Literal["low", "medium", "high"]
    evidence: list[str]


class AnomalyEvent(BaseModel):
    kind: AnomalyKind
    start: datetime
    end: datetime
    detected_at: datetime = Field(description="First hour at which the detector would alert")
    hours: int
    estimated_volume_m3: float | None = Field(
        description="Water unaccounted for (excess) or not delivered (deficit), if estimable"
    )
    severity: Literal["low", "medium", "high"]
    confidence: Literal["low", "medium", "high"]
    hypotheses: list[Hypothesis]
    recommended_checks: list[str]
    zone_id: str | None = None


@dataclass(frozen=True)
class DetectorConfig:
    design_flow_m3h: dict[str, float]
    train_days: int = 7
    idle_threshold_m3h: float = 0.3
    rel_tolerance: float = 0.12  # flow vs expected
    zone_balance_tolerance: float = 0.08  # inlet vs sum(zone meters), relative (~3 sigma)
    pressure_z: float = 4.0
    stuck_hours: int = 6
    # Two one-sided CUSUMs for small persistent excess flow:
    cusum_idle_k_m3h: float = 0.05  # idle hours: allowance in m3/h (meter noise floor)
    cusum_idle_h_m3: float = 1.0  # idle hours: alarm after ~1 m3 unexplained
    cusum_active_k: float = 0.03  # irrigation hours: allowance, fraction of expected flow
    cusum_active_h: float = 0.6  # irrigation hours: alarm level (sum of relative excess)
    merge_gap_hours: int = 1
    meters_calibrated: bool = False
    # Scale thresholds to the noise observed in the training window (never below defaults).
    adaptive_thresholds: bool = True
    noise_multiplier: float = 4.0
    # Noisy detectors must persist this many consecutive hours before alerting.
    min_hours: tuple[tuple[str, int], ...] = (
        ("zone_mismatch", 2),
        ("flow_excess", 2),
        ("flow_deficit", 2),
        ("pressure_drop", 2),
    )


@dataclass
class DetectionResult:
    events: list[AnomalyEvent]
    calibration_factor: float | None
    zone_calibration: dict[str, float]
    hourly_flags: pd.DataFrame
    assumptions: list[str] = field(default_factory=list)


def _robust_z(x: pd.Series, ref: pd.Series) -> pd.Series:
    med = ref.median()
    mad = (ref - med).abs().median() * 1.4826
    if not np.isfinite(mad) or mad < 1e-9:
        return pd.Series(0.0, index=x.index)
    return (x - med) / mad


def _sigma(x: pd.Series) -> float:
    x = x.dropna()
    if len(x) < 6:
        return 0.0
    return float((x - x.median()).abs().median() * 1.4826)


def _adapt_thresholds(
    cfg: DetectorConfig,
    data: pd.DataFrame,
    inlet: pd.Series,
    expected: pd.Series,
    active: pd.Series,
    train_end: pd.Timestamp,
    zone_meters: list[str],
) -> DetectorConfig:
    m = cfg.noise_multiplier
    train = pd.Series(data.index < train_end, index=data.index)
    tr_act = train & active
    tr_idle = train & ~active
    sig_a = _sigma(((inlet - expected) / expected)[tr_act])
    idle_vals = inlet[tr_idle]
    sig_i = _sigma(idle_vals)
    med_i = float(idle_vals.median()) if len(idle_vals) else 0.0
    sig_z = 0.0
    if zone_meters:
        zsum = data[zone_meters].sum(axis=1)
        flowing = inlet > cfg.idle_threshold_m3h
        sig_z = _sigma(((inlet - zsum) / inlet.where(flowing))[train & flowing])
    return replace(
        cfg,
        rel_tolerance=max(cfg.rel_tolerance, m * sig_a),
        zone_balance_tolerance=max(cfg.zone_balance_tolerance, m * sig_z),
        idle_threshold_m3h=max(cfg.idle_threshold_m3h, med_i + m * sig_i),
        cusum_active_k=max(cfg.cusum_active_k, 1.5 * sig_a),
        cusum_active_h=max(cfg.cusum_active_h, 10 * sig_a),
        cusum_idle_k_m3h=max(cfg.cusum_idle_k_m3h, med_i + 1.5 * sig_i),
        cusum_idle_h_m3=max(cfg.cusum_idle_h_m3, 20 * sig_i),
    )


def _drop_short(mask: pd.Series, n: int) -> pd.Series:
    """Keep only runs of consecutive True values of length >= n."""
    if n <= 1:
        return mask
    run_id = (mask != mask.shift()).cumsum()
    lengths = mask.groupby(run_id).transform("sum")
    return mask & (lengths >= n)


def _events_from_mask(mask: pd.Series, gap: int) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    idx = mask[mask].index
    if len(idx) == 0:
        return []
    spans = []
    start = prev = idx[0]
    for ts in idx[1:]:
        if (ts - prev) > pd.Timedelta(hours=gap + 1):
            spans.append((start, prev))
            start = ts
        prev = ts
    spans.append((start, prev))
    return spans


def detect_anomalies(
    data: pd.DataFrame, schedule: pd.DataFrame, cfg: DetectorConfig
) -> DetectionResult:
    if "inlet_m3h" not in data:
        raise ValueError("inlet_m3h is required")
    data = data.sort_index()
    schedule = schedule.reindex(data.index).fillna(False).astype(bool)
    unknown = set(schedule.columns) - set(cfg.design_flow_m3h)
    if unknown:
        raise ValueError(f"no design flow for scheduled zones {sorted(unknown)}")

    inlet = data["inlet_m3h"].astype(float)
    design_expected = sum(
        schedule[z].astype(float) * cfg.design_flow_m3h[z] for z in schedule.columns
    )
    if not isinstance(design_expected, pd.Series):
        design_expected = pd.Series(0.0, index=data.index)
    active = design_expected > 0
    zone_meters = [c for c in data.columns if c.startswith("zone_") and c.endswith("_m3h")]

    # --- Baseline calibration on the training window ----------------------------------------
    train_end = data.index[0] + pd.Timedelta(days=cfg.train_days)
    train = (data.index < train_end) & active.to_numpy()
    calib = None
    if train.sum() >= 6:
        calib = float((inlet[train] / design_expected[train]).median())
    factor = calib if calib and np.isfinite(calib) and calib > 0 else 1.0
    # Per-zone factors from hours when that zone ran alone (falls back to the global factor).
    alone = schedule.sum(axis=1) == 1
    zone_cal: dict[str, float] = {}
    for zc in schedule.columns:
        m = train & alone.to_numpy() & schedule[zc].to_numpy()
        zone_cal[zc] = (
            float((inlet[m] / cfg.design_flow_m3h[zc]).median()) if m.sum() >= 3 else factor
        )
    expected = sum(
        schedule[zc].astype(float) * cfg.design_flow_m3h[zc] * zone_cal[zc]
        for zc in schedule.columns
    )
    if not isinstance(expected, pd.Series):
        expected = pd.Series(0.0, index=data.index)
    eval_mask = pd.Series(data.index >= train_end, index=data.index)

    if cfg.adaptive_thresholds:
        cfg = _adapt_thresholds(cfg, data, inlet, expected, active, train_end, zone_meters)

    flags = pd.DataFrame(False, index=data.index, columns=list(AnomalyKind.__args__))

    # idle flow
    flags["idle_flow"] = (~active) & (inlet > cfg.idle_threshold_m3h)

    # pump status
    if "pump_on" in data:
        pump = data["pump_on"].astype(bool)
        flags["pump_status"] = ((~pump) & (inlet > cfg.idle_threshold_m3h)) | (
            pump & active & (inlet <= cfg.idle_threshold_m3h)
        )

    # excess / deficit during scheduled irrigation
    ratio = inlet / expected.where(active)
    flags["flow_excess"] = active & (ratio > 1 + cfg.rel_tolerance)
    flags["flow_deficit"] = active & (ratio < 1 - cfg.rel_tolerance)

    # water accounting with zone meters
    if zone_meters:
        zsum = data[zone_meters].sum(axis=1)
        flowing = inlet > cfg.idle_threshold_m3h
        gap = (inlet - zsum) / inlet.where(flowing)
        flags["zone_mismatch"] = flowing & (gap.abs() > cfg.zone_balance_tolerance)

    # pressure drop vs same active-zone configuration in the training window
    if "pressure_kpa" in data:
        pressure = data["pressure_kpa"].astype(float)
        config_key = schedule.apply(lambda r: "|".join(sorted(r.index[r.to_numpy()])), axis=1)
        z = pd.Series(0.0, index=data.index)
        train_s = pd.Series(data.index < train_end, index=data.index)
        for _key, grp in pressure.groupby(config_key):
            ref = grp[train_s[grp.index]]
            if len(ref) >= 6:
                z[grp.index] = _robust_z(grp, ref)
        flags["pressure_drop"] = z < -cfg.pressure_z

    # stuck meter: no variation while the schedule changes
    std = inlet.rolling(cfg.stuck_hours, min_periods=cfg.stuck_hours).std()
    sched_changes = design_expected.diff().abs().rolling(cfg.stuck_hours).sum()
    flags["stuck_meter"] = (std < 1e-6) & (sched_changes > 0) & (inlet > cfg.idle_threshold_m3h)

    # Two one-sided CUSUMs with reset-on-alarm: idle hours in absolute m3/h (small continuous
    # leaks), irrigation hours relative to expected flow. Each statistic only advances on its
    # own hours. The window since the statistic last left zero is flagged; the alarm hour is
    # recorded as the detection time.
    slow = np.zeros(len(data), dtype=bool)
    alarms: list[pd.Timestamp] = []
    act = active.to_numpy()
    inl = inlet.to_numpy()
    exp_arr = expected.to_numpy()
    for channel_active, k, h in (
        (False, cfg.cusum_idle_k_m3h, cfg.cusum_idle_h_m3),
        (True, cfg.cusum_active_k, cfg.cusum_active_h),
    ):
        s_stat, window_start = 0.0, None
        for i in range(len(data)):
            if not eval_mask.iloc[i]:
                s_stat, window_start = 0.0, None
                continue
            if act[i] != channel_active:
                continue
            x = (inl[i] - exp_arr[i]) / exp_arr[i] if channel_active else inl[i]
            s_stat = max(0.0, s_stat + float(x) - k)
            if s_stat == 0.0:
                window_start = None
            else:
                window_start = i if window_start is None else window_start
                if s_stat > h:
                    slow[window_start : i + 1] = True
                    alarms.append(data.index[i])
                    s_stat, window_start = 0.0, None
    alarms.sort()
    flags["slow_leak"] = slow

    flags = flags & eval_mask.to_numpy()[:, None]
    for kind, n in cfg.min_hours:
        flags[kind] = _drop_short(flags[kind], n)
    min_h = dict(cfg.min_hours)

    events: list[AnomalyEvent] = []
    for kind in flags.columns:
        for start, end in _events_from_mask(flags[kind], cfg.merge_gap_hours):
            window = slice(start, end)
            if kind == "slow_leak":
                hits = [a for a in alarms if start <= a <= end]
                detected = hits[0] if hits else end
            else:
                detected = start + pd.Timedelta(hours=min_h.get(kind, 1) - 1)
            events.append(
                _describe(
                    kind,
                    start,
                    end,
                    detected,
                    data.loc[window],
                    expected.loc[window],
                    active.loc[window],
                    schedule.loc[window],
                    zone_meters,
                    cfg,
                )
            )
    events.sort(key=lambda e: e.start)
    assumptions = [
        "Expected flow = design flow x per-zone calibration factor "
        f"{ {k: round(v, 3) for k, v in zone_cal.items()} } (medians over the first "
        f"{cfg.train_days} days, assumed fault-free).",
        "Detectors are rule-based/statistical; thresholds are defaults, raised to "
        f"{cfg.noise_multiplier:g}x the training-window noise when adaptive "
        f"(applied: flow +/-{cfg.rel_tolerance:.1%}, "
        f"zone balance {cfg.zone_balance_tolerance:.1%}, "
        f"idle {cfg.idle_threshold_m3h:.2f} m3/h); not tuned on field data.",
        "Events are hypotheses for inspection, not conclusions about causes or people.",
    ]
    return DetectionResult(events, calib, zone_cal, flags, assumptions)


# --- Event description ------------------------------------------------------------------------


def _severity(volume: float | None, hours: int, rate_share: float | None) -> str:
    if rate_share is not None and rate_share > 0.25:
        return "high"
    if volume is not None and volume > 50:
        return "high"
    if (volume is not None and volume > 10) or hours >= 6:
        return "medium"
    return "low"


def _describe(
    kind: str,
    start: pd.Timestamp,
    end: pd.Timestamp,
    detected: pd.Timestamp,
    d: pd.DataFrame,
    expected: pd.Series,
    active: pd.Series,
    schedule: pd.DataFrame,
    zone_meters: list[str],
    cfg: DetectorConfig,
) -> AnomalyEvent:
    inlet = d["inlet_m3h"]
    hours = len(d)
    H = Hypothesis
    hyp: list[Hypothesis] = []
    checks: list[str] = []
    volume: float | None = None
    rate_share: float | None = None
    zone_id = None
    conf = "medium" if cfg.meters_calibrated else "low"

    if kind == "idle_flow":
        volume = float(inlet.sum())
        ev = [f"{volume:.1f} m3 measured over {hours} h with no zone scheduled"]
        if "pump_on" in d and not d["pump_on"].any():
            ev.append("pump reported OFF during the flow")
            hyp.append(
                H(cause="meter fault or pump status signal fault", likelihood="medium", evidence=ev)
            )
        hyp += [
            H(cause="leak downstream of the inlet meter", likelihood="medium", evidence=ev),
            H(
                cause="valve not fully closed after the last irrigation",
                likelihood="medium",
                evidence=ev,
            ),
            H(cause="irrigation run not recorded in the schedule", likelihood="low", evidence=ev),
        ]
        checks = [
            "Walk the mainline for wet spots",
            "Check that every zone valve closes",
            "Compare with the farm's manual irrigation log",
        ]
        if hours >= 3:
            conf = "medium" if conf == "low" else "high"
    elif kind == "pump_status":
        ev = [f"inlet mean {inlet.mean():.2f} m3/h vs pump status {d['pump_on'].mean():.0%} ON"]
        hyp = [
            H(cause="pump status sensor or wiring fault", likelihood="medium", evidence=ev),
            H(cause="flow meter fault", likelihood="medium", evidence=ev),
            H(cause="pump failed to start or lost prime", likelihood="medium", evidence=ev),
        ]
        checks = ["Check pump contactor and status signal", "Read the meter manually"]
    elif kind in ("flow_excess", "flow_deficit"):
        exp_sum = float(expected[active].sum())
        diff = float((inlet[active] - expected[active]).sum())
        volume = abs(diff)
        rate_share = abs(diff) / exp_sum if exp_sum > 0 else None
        zones_on = sorted({z for z in schedule.columns if schedule[z].any()})
        ev = [
            f"measured {inlet[active].sum():.1f} m3 vs expected {exp_sum:.1f} m3"
            + (f" ({rate_share:.0%} difference)" if rate_share is not None else ""),
            f"scheduled zones: {', '.join(zones_on)}",
        ]
        if kind == "flow_excess":
            hyp = [
                H(
                    cause="pipe or lateral leak / burst in the active zone(s) or mainline",
                    likelihood="high" if (rate_share or 0) > 0.25 else "medium",
                    evidence=ev,
                ),
                H(
                    cause="emitters damaged or missing (higher discharge)",
                    likelihood="medium",
                    evidence=ev,
                ),
                H(
                    cause="additional valve open that is not in the schedule",
                    likelihood="medium",
                    evidence=ev,
                ),
            ]
            checks = [
                "Inspect active zones for wet areas or broken laterals",
                "Confirm which valves are physically open",
            ]
        else:
            hyp = [
                H(cause="clogged filters or emitters", likelihood="medium", evidence=ev),
                H(
                    cause="pump wear, low well level or energy limitation",
                    likelihood="medium",
                    evidence=ev,
                ),
                H(cause="scheduled valve failed to open", likelihood="medium", evidence=ev),
            ]
            checks = [
                "Check filter pressure differential",
                "Check well level and pump current",
                "Confirm each scheduled valve opened",
            ]
        if hours >= 2:
            conf = "medium" if conf == "low" else "high"
        if len(zones_on) == 1:
            zone_id = zones_on[0]
    elif kind == "zone_mismatch":
        zsum = d[zone_meters].sum(axis=1)
        diff = float((inlet - zsum).sum())
        volume = abs(diff)
        ev = [
            f"inlet {inlet.sum():.1f} m3 vs zone meters {zsum.sum():.1f} m3 "
            f"(difference {diff:+.1f} m3)"
        ]
        if diff > 0:
            hyp = [
                H(
                    cause="leak on the mainline between inlet and zone meters",
                    likelihood="medium",
                    evidence=ev,
                ),
                H(
                    cause="unmetered outlet (e.g. tap, livestock trough) in use",
                    likelihood="medium",
                    evidence=ev,
                ),
            ]
        else:
            hyp = []
        hyp.append(H(cause="meter calibration drift", likelihood="medium", evidence=ev))
        checks = [
            "Walk the mainline",
            "List all unmetered outlets",
            "Check meter calibration dates",
        ]
    elif kind == "pressure_drop":
        ev = [
            f"pressure min {d['pressure_kpa'].min():.0f} kPa, far below its history for the "
            f"same active zones; inlet mean {inlet.mean():.2f} m3/h"
        ]
        high_flow = bool((inlet > expected * (1 + cfg.rel_tolerance)).any())
        hyp = [
            H(
                cause="burst or large leak",
                likelihood="high" if high_flow else "low",
                evidence=ev + (["flow simultaneously above expected"] if high_flow else []),
            ),
            H(
                cause="pump or supply problem (low well level, energy)",
                likelihood="low" if high_flow else "medium",
                evidence=ev,
            ),
            H(cause="pressure sensor fault", likelihood="low", evidence=ev),
        ]
        checks = ["Inspect for a burst near the pressure drop", "Check pump and well level"]
        conf = "medium"
    elif kind == "stuck_meter":
        ev = [
            f"inlet constant at {inlet.iloc[0]:.2f} m3/h for {hours} h while the schedule changed"
        ]
        hyp = [H(cause="flow meter stuck or logger frozen", likelihood="high", evidence=ev)]
        checks = ["Read the meter on site", "Check logger power and connectivity"]
        conf = "high"
    elif kind == "slow_leak":
        exp = expected.where(active).fillna(0.0)
        excess = (inlet - exp).clip(lower=0)
        volume = float(excess.sum())
        ev = [
            f"persistent small excess flow (one-sided CUSUM) totalling ~{volume:.1f} m3 "
            f"over {hours} h"
        ]
        hyp = [
            H(
                cause="small leak (drip line, fitting, valve seat)",
                likelihood="medium",
                evidence=ev,
            ),
            H(cause="meter drift", likelihood="medium", evidence=ev),
        ]
        checks = ["Inspect fittings and valve seats", "Compare with a portable meter"]

    sev = _severity(volume, hours, rate_share)
    return AnomalyEvent(
        kind=kind,
        start=start,
        end=end,
        detected_at=detected,
        hours=hours,
        estimated_volume_m3=None if volume is None else round(volume, 2),
        severity=sev,
        confidence=conf,
        hypotheses=hyp,
        recommended_checks=checks,
        zone_id=zone_id,
    )

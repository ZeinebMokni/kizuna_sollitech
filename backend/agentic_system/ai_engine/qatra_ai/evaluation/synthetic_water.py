"""SYNTHETIC water-system data with injected, labelled faults: data_class = simulated.

Purpose: test anomaly detectors when no real labelled incidents exist. Results obtained on
this data are "simulation-tested" only and say nothing about field detection rates.

System: one well pump feeding 3 zones on a daily schedule. Actual zone flows differ from
design flows by unknown factors (the detector must calibrate). Meters have noise.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

DESIGN = {"A": 10.0, "B": 12.0, "C": 8.0}
ACTUAL_FACTOR = {"A": 0.95, "B": 1.03, "C": 0.90}
SCHEDULE_HOURS = {"A": range(6, 9), "B": range(9, 12), "C": range(13, 15)}

FaultKind = str


@dataclass(frozen=True)
class InjectedFault:
    name: str
    start: pd.Timestamp
    end: pd.Timestamp
    detectable_by: tuple[str, ...]


@dataclass
class SyntheticSystem:
    data: pd.DataFrame
    schedule: pd.DataFrame
    faults: list[InjectedFault]
    design_flow_m3h: dict[str, float]
    data_class: str = "simulated"


def generate(
    days: int = 42,
    seed: int = 0,
    faults: tuple[str, ...] = (),
    start: str = "2026-06-01",
    skip_prob: float = 0.15,
    slow_leak_m3h: float = 0.2,
    burst_fraction: float = 0.4,
    meter_noise_rel: float = 0.02,
) -> SyntheticSystem:
    """Generate `days` of hourly data. Faults are injected after a 7-day clean training window."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range(start, periods=days * 24, freq="h")
    sched = pd.DataFrame(False, index=idx, columns=list(DESIGN))
    for d in range(days):
        if rng.random() < skip_prob:
            continue
        for z, hrs in SCHEDULE_HOURS.items():
            for h in hrs:
                sched.iloc[d * 24 + h, sched.columns.get_loc(z)] = True

    valve_open = sched.copy()  # physical state (faults may differ from the schedule)
    zone_extra = pd.DataFrame(0.0, index=idx, columns=list(DESIGN))  # leaks inside a zone
    zone_factor = pd.DataFrame(1.0, index=idx, columns=list(DESIGN))  # clogging etc.
    mainline_leak = pd.Series(0.0, index=idx)  # between inlet and zone meters
    pressure_offset = pd.Series(0.0, index=idx)
    stuck: tuple[int, int] | None = None
    pump_fault = pd.Series(False, index=idx)
    injected: list[InjectedFault] = []

    def day_hour(day: int, hour: int) -> int:
        return day * 24 + hour

    def active_day(after: int) -> int:
        """First day >= after on which every zone is scheduled."""
        for d in range(after, days):
            if sched.iloc[day_hour(d, 0) : day_hour(d + 1, 0)].any().all():
                return d
        raise ValueError("no fully scheduled day available for fault injection")

    t0 = 8  # first day after training
    for f in faults:
        if f == "background_leak":  # 0.8 m3/h on the mainline for 2 days
            a, b = day_hour(t0, 0), day_hour(t0 + 2, 0)
            mainline_leak.iloc[a:b] += 0.8
            injected.append(
                InjectedFault(f, idx[a], idx[b - 1], ("idle_flow", "zone_mismatch", "slow_leak"))
            )
        elif f == "burst_zone_B":  # +40 % flow and -60 kPa in zone B during one irrigation
            d = active_day(t0 + 3)
            hrs = [day_hour(d, h) for h in SCHEDULE_HOURS["B"]]
            for i in hrs:
                zone_extra.iloc[i, zone_extra.columns.get_loc("B")] += burst_fraction * DESIGN["B"]
                pressure_offset.iloc[i] -= 150 * burst_fraction
            injected.append(
                InjectedFault(f, idx[hrs[0]], idx[hrs[-1]], ("flow_excess", "pressure_drop"))
            )
        elif f == "valve_C_stuck_open":  # zone C keeps flowing 3 h after its window
            d = active_day(t0 + 6)
            hrs = [day_hour(d, h) for h in range(15, 18)]
            for i in hrs:
                valve_open.iloc[i, valve_open.columns.get_loc("C")] = True
            injected.append(InjectedFault(f, idx[hrs[0]], idx[hrs[-1]], ("idle_flow",)))
        elif f == "clogging_A":  # zone A delivers 25 % less for 3 days
            d = t0 + 9
            a, b = day_hour(d, 0), day_hour(d + 3, 0)
            zone_factor.iloc[a:b, zone_factor.columns.get_loc("A")] = 0.75
            first = next(i for i in range(a, b) if sched.iloc[i]["A"])
            last = max(i for i in range(a, b) if sched.iloc[i]["A"])
            injected.append(InjectedFault(f, idx[first], idx[last], ("flow_deficit",)))
        elif f == "stuck_meter":  # inlet frozen for 12 h across schedule changes
            d = active_day(t0 + 13)
            stuck = (day_hour(d, 4), day_hour(d, 16))
            # Frozen at an idle reading: also visible as missing flow while pumping is scheduled.
            injected.append(
                InjectedFault(
                    f,
                    idx[stuck[0]],
                    idx[stuck[1] - 1],
                    ("stuck_meter", "flow_deficit", "pump_status"),
                )
            )
        elif f == "pump_status_fault":  # status reads OFF while pumping
            d = active_day(t0 + 16)
            hrs = [day_hour(d, h) for h in SCHEDULE_HOURS["A"]]
            for i in hrs:
                pump_fault.iloc[i] = True
            injected.append(InjectedFault(f, idx[hrs[0]], idx[hrs[-1]], ("pump_status",)))
        elif f == "slow_leak":  # 0.2 m3/h (below the idle threshold) for 5 days
            a, b = day_hour(t0 + 19, 0), day_hour(t0 + 24, 0)
            mainline_leak.iloc[a:b] += slow_leak_m3h
            injected.append(InjectedFault(f, idx[a], idx[b - 1], ("slow_leak", "zone_mismatch")))
        else:
            raise ValueError(f"unknown fault {f}")

    zone_flow = pd.DataFrame(index=idx, columns=list(DESIGN), dtype=float)
    for z in DESIGN:
        base = DESIGN[z] * ACTUAL_FACTOR[z] * zone_factor[z]
        zone_flow[z] = valve_open[z] * base + zone_extra[z]
    true_inlet = zone_flow.sum(axis=1) + mainline_leak
    pumping = true_inlet > 0.05

    def noisy(x: pd.Series, rel: float, abs_: float) -> pd.Series:
        n = rng.normal(0, 1, len(x)) * (rel * x + abs_)
        return (x + n).clip(lower=0.0)

    inlet = noisy(true_inlet, meter_noise_rel, 0.03)
    if stuck is not None:
        inlet.iloc[stuck[0] : stuck[1]] = round(float(inlet.iloc[stuck[0]]), 2)
    data = pd.DataFrame({"inlet_m3h": inlet})
    for z in DESIGN:
        data[f"zone_{z}_m3h"] = noisy(zone_flow[z], meter_noise_rel, 0.03)
    pressure = np.where(pumping, 260 - 2.5 * true_inlet, 15.0) + pressure_offset
    data["pressure_kpa"] = pressure + rng.normal(0, 3, len(idx))
    data["pump_on"] = pumping & ~pump_fault
    return SyntheticSystem(data, sched, injected, dict(DESIGN))


ALL_FAULTS = (
    "background_leak",
    "burst_zone_B",
    "valve_C_stuck_open",
    "clogging_A",
    "stuck_meter",
    "pump_status_fault",
    "slow_leak",
)

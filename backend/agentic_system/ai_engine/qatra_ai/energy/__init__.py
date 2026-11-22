"""Energy models: pump hydraulics, photovoltaic production, battery state of charge.

Pump energy:   E [kWh] = rho g V H / (3.6e6 * eta_pump * eta_motor)
               (rho g / 3.6e6 = 2.725e-3 kWh per m3 per metre of head)
PV power:      P = P_rated * (G_poa / 1000) * (1 + gamma_T (T_cell - 25)) * eta_sys
Cell temp:     T_cell = T_air + (NOCT - 20) / 800 * G_poa      (NOCT model)
Battery:       SOC' = SOC + eta_c * E_ch - E_dis / eta_d
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

RHO_WATER = 1000.0  # kg m-3
G = 9.80665  # m s-2


def pump_energy_kwh(
    volume_m3: float, head_m: float, pump_efficiency: float, motor_efficiency: float = 0.9
) -> float:
    if volume_m3 < 0 or head_m < 0:
        raise ValueError("volume and head must be >= 0")
    if not (0 < pump_efficiency <= 1 and 0 < motor_efficiency <= 1):
        raise ValueError("efficiencies must be in (0, 1]")
    return RHO_WATER * G * volume_m3 * head_m / 3.6e6 / (pump_efficiency * motor_efficiency)


def pump_power_kw(
    flow_m3h: float, head_m: float, pump_efficiency: float, motor_efficiency: float = 0.9
) -> float:
    """Electrical input power for a given flow: energy for one hour of pumping."""
    return pump_energy_kwh(flow_m3h, head_m, pump_efficiency, motor_efficiency)


def cell_temperature(t_air_c: float, g_poa_w_m2: float, noct_c: float = 45.0) -> float:
    return t_air_c + (noct_c - 20.0) / 800.0 * g_poa_w_m2


def pv_power_kw(
    p_rated_kw: float,
    g_poa_w_m2: float,
    t_cell_c: float,
    gamma_per_c: float = -0.004,
    system_efficiency: float = 0.86,
) -> float:
    """DC->AC power of a PV array. Defaults: crystalline Si temperature coefficient,
    14 % system losses (wiring, soiling, inverter). Both are assumptions to override."""
    if g_poa_w_m2 <= 0:
        return 0.0
    p = p_rated_kw * g_poa_w_m2 / 1000.0 * (1 + gamma_per_c * (t_cell_c - 25.0)) * system_efficiency
    return max(p, 0.0)


class Battery(BaseModel):
    model_config = ConfigDict(frozen=True)

    capacity_kwh: float = Field(gt=0)
    soc_min_fraction: float = Field(default=0.2, ge=0, lt=1)
    soc_max_fraction: float = Field(default=1.0, gt=0, le=1)
    charge_efficiency: float = Field(default=0.95, gt=0, le=1)
    discharge_efficiency: float = Field(default=0.95, gt=0, le=1)

    def step(self, soc_kwh: float, charge_kwh: float, discharge_kwh: float) -> float:
        """Next SOC [kWh]. Raises if the request violates SOC limits (no silent clipping)."""
        if charge_kwh < 0 or discharge_kwh < 0:
            raise ValueError("charge and discharge must be >= 0")
        new = (
            soc_kwh
            + self.charge_efficiency * charge_kwh
            - discharge_kwh / self.discharge_efficiency
        )
        lo, hi = (
            self.soc_min_fraction * self.capacity_kwh,
            self.soc_max_fraction * self.capacity_kwh,
        )
        if new < lo - 1e-9 or new > hi + 1e-9:
            raise ValueError(f"SOC {new:.2f} kWh outside [{lo:.2f}, {hi:.2f}]")
        return new

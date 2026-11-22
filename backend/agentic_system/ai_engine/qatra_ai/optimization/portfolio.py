"""Risk-aware crop portfolio for one farm (or a group of identical farms), one season.

AI_ENGINE_BLUEPRINT section 6.3. Linear programme (OR-Tools GLOP):

  variables   x_c >= 0 area of crop c (ha)
  land        sum_c x_c <= A
  water       sum_c x_c * WR_c <= W            (m3; pumped well water)
  energy      sum_c x_c * EN_c <= E            (kWh; optional)
  bounds      min_c <= x_c <= max_c; x_c = 0 for excluded crops (suitability class N)
  objective   max  E_s[pi_s] - beta * CVaR_alpha[-pi_s]
              pi_s = sum_c x_c * m_{c,s}       margin in scenario s
  CVaR (Rockafellar & Uryasev 2000):
              CVaR_alpha[L] = min_eta  eta + 1/((1-alpha) S) * sum_s max(0, L_s - eta)

Margins m_{c,s} (money/ha) are scenario samples supplied by the caller (for example from
qatra_ai.market). Scenarios must be aligned across crops (sample s is one joint state of
weather and prices), otherwise diversification benefits are wrong.

Leaving land fallow is allowed (sum x <= A): if every crop loses money in expectation, the plan
plants nothing rather than forcing a loss.
"""

from __future__ import annotations

import numpy as np
from ortools.linear_solver import pywraplp
from pydantic import BaseModel, Field, model_validator

EPS = 1e-9


class CropOption(BaseModel):
    crop: str
    water_m3_per_ha: float = Field(ge=0)
    energy_kwh_per_ha: float = Field(default=0.0, ge=0)
    min_ha: float = Field(default=0.0, ge=0)
    max_ha: float | None = Field(default=None, ge=0)
    excluded: bool = Field(default=False, description="e.g. suitability class N")
    margin_samples: list[float] = Field(description="margin per ha in each joint scenario")

    @model_validator(mode="after")
    def _bounds(self) -> CropOption:
        if self.max_ha is not None and self.max_ha < self.min_ha:
            raise ValueError(f"{self.crop}: max_ha < min_ha")
        return self


class PortfolioRequest(BaseModel):
    land_ha: float = Field(gt=0)
    water_m3: float = Field(ge=0)
    energy_kwh: float | None = Field(default=None, ge=0)
    options: list[CropOption] = Field(min_length=1)
    beta: float = Field(default=0.5, ge=0, description="weight on CVaR (risk aversion)")
    alpha: float = Field(default=0.9, gt=0, lt=1, description="CVaR level (worst 1-alpha)")
    money_unit: str = "TND"

    @model_validator(mode="after")
    def _aligned(self) -> PortfolioRequest:
        n = {len(o.margin_samples) for o in self.options}
        if len(n) != 1 or 0 in n:
            raise ValueError("every crop needs the same, non-zero number of margin samples")
        if len({o.crop for o in self.options}) != len(self.options):
            raise ValueError("duplicate crop")
        return self


class ConstraintUse(BaseModel):
    name: str
    used: float
    limit: float
    binding: bool
    marginal_value: float | None = Field(
        default=None, description="objective gain per extra unit (LP dual)"
    )


class PortfolioResult(BaseModel):
    feasible: bool
    note: str | None = None
    area_ha: dict[str, float] = Field(default_factory=dict)
    fallow_ha: float = 0.0
    expected_margin: float | None = None
    cvar_margin: float | None = Field(
        default=None, description="mean margin over the worst (1-alpha) share of scenarios"
    )
    prob_loss: float | None = None
    objective: float | None = None
    constraints: list[ConstraintUse] = Field(default_factory=list)
    beta: float
    alpha: float
    money_unit: str


def evaluate_plan(
    area_ha: dict[str, float], margins: dict[str, np.ndarray], alpha: float
) -> tuple[float, float, float]:
    """(expected margin, CVaR margin = mean of the worst 1-alpha share, P(total < 0))."""
    pi = sum(area_ha.get(c, 0.0) * m for c, m in margins.items())
    pi = np.asarray(pi, dtype=float)
    k = max(1, int(np.ceil((1 - alpha) * pi.size)))
    worst = np.sort(pi)[:k]
    return float(pi.mean()), float(worst.mean()), float(np.mean(pi < -EPS))


def solve_portfolio(req: PortfolioRequest) -> PortfolioResult:
    solver = pywraplp.Solver.CreateSolver("GLOP")
    S = len(req.options[0].margin_samples)
    M = {o.crop: np.asarray(o.margin_samples, dtype=float) for o in req.options}
    x = {}
    for o in req.options:
        hi = 0.0 if o.excluded else (o.max_ha if o.max_ha is not None else req.land_ha)
        lo = 0.0 if o.excluded else o.min_ha
        x[o.crop] = solver.NumVar(lo, hi, f"x_{o.crop}")
    excluded_min = [o.crop for o in req.options if o.excluded and o.min_ha > 0]

    land = solver.Add(sum(x.values()) <= req.land_ha)
    water = solver.Add(sum(x[o.crop] * o.water_m3_per_ha for o in req.options) <= req.water_m3)
    energy = None
    if req.energy_kwh is not None:
        energy = solver.Add(
            sum(x[o.crop] * o.energy_kwh_per_ha for o in req.options) <= req.energy_kwh
        )

    eta = solver.NumVar(-solver.infinity(), solver.infinity(), "eta")
    z = [solver.NumVar(0, solver.infinity(), f"z{s}") for s in range(S)]
    for s in range(S):
        pi_s = sum(x[c] * float(M[c][s]) for c in x)
        solver.Add(z[s] >= -pi_s - eta)
    mean = sum(x[c] * float(M[c].mean()) for c in x)
    cvar_loss = eta + (1.0 / ((1 - req.alpha) * S)) * sum(z)
    solver.Maximize(mean - req.beta * cvar_loss)

    status = solver.Solve()
    base = {"beta": req.beta, "alpha": req.alpha, "money_unit": req.money_unit}
    if status != pywraplp.Solver.OPTIMAL:
        need_land = sum(o.min_ha for o in req.options if not o.excluded)
        need_water = sum(o.min_ha * o.water_m3_per_ha for o in req.options if not o.excluded)
        return PortfolioResult(
            feasible=False,
            note=f"infeasible: minimum areas need {need_land:g} ha and {need_water:g} m3 "
            f"(available {req.land_ha:g} ha, {req.water_m3:g} m3)",
            **base,
        )
    area = {c: max(0.0, v.solution_value()) for c, v in x.items()}
    exp, cvar, ploss = evaluate_plan(area, M, req.alpha)
    used_water = sum(area[o.crop] * o.water_m3_per_ha for o in req.options)
    cons = [
        ConstraintUse(
            name="land_ha",
            used=round(sum(area.values()), 3),
            limit=req.land_ha,
            binding=sum(area.values()) >= req.land_ha - 1e-6,
            marginal_value=round(land.dual_value(), 3),
        ),
        ConstraintUse(
            name="water_m3",
            used=round(used_water, 1),
            limit=req.water_m3,
            binding=used_water >= req.water_m3 - 1e-3,
            marginal_value=round(water.dual_value(), 4),
        ),
    ]
    if energy is not None:
        used_e = sum(area[o.crop] * o.energy_kwh_per_ha for o in req.options)
        cons.append(
            ConstraintUse(
                name="energy_kwh",
                used=round(used_e, 1),
                limit=req.energy_kwh,
                binding=used_e >= req.energy_kwh - 1e-3,
                marginal_value=round(energy.dual_value(), 4),
            )
        )
    note = None
    if excluded_min:
        note = f"minimum area ignored for excluded crops: {excluded_min}"
    return PortfolioResult(
        feasible=True,
        note=note,
        area_ha={c: round(a, 3) for c, a in area.items()},
        fallow_ha=round(max(0.0, req.land_ha - sum(area.values())), 3),
        expected_margin=round(exp, 2),
        cvar_margin=round(cvar, 2),
        prob_loss=round(ploss, 3),
        objective=round(solver.Objective().Value(), 2),
        constraints=cons,
        **base,
    )

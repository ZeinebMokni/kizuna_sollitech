"""Regional reflexivity: crop plans and prices solved together (AI_ENGINE_BLUEPRINT 6.4).

The farms that follow QATRA are aggregated into one group (identical farms assumption) with
land, well water and energy limits. For every crop there is a market (reference season,
supply scenario, yield distribution, cost), as in qatra_ai.market.scenarios.

  prices(x)    for each crop: p_c = p0_c ((Q_other_c + x_c Y_c + M_c)/(Q0_c + M0_c))^(1/eps_c)
  margins(x)   m_c = p_c(x) * Y_c - cost_c      (per scenario sample)
  Portfolio(m) risk-aware crop mix (qatra_ai.optimization.portfolio)

1. Naive plan: x_naive = Portfolio(margins(0)), i.e. what the engine would recommend if it
   ignored that its own users move the market. Its "promised" margin uses margins(0); its
   "realised" margin, if all followers adopt it, uses margins(x_naive).
2. Equilibrium: damped fixed point x <- (1-l_k) x + l_k Portfolio(margins(x)), with the method
   of successive averages (l_k = 1/(k+1)) by default. It stops when the plan is (nearly) optimal
   at the prices it creates itself: regret = obj(Portfolio(margins(x))) - obj(x) under
   margins(x) is <= tol * |obj|. Otherwise non-convergence is reported.
3. Undamped behaviour: x_{k+1} = Portfolio(margins(x_k)) for a few rounds, i.e. everyone
   re-plans from last season's prices. A cycle there is a boom-bust risk signal.

Uncertainty: scenarios are joint samples. Each crop's yield and the rest of its region's
production share one weather draw; weather draws of different crops are linked by a Gaussian
copula with correlation `weather_correlation`. Elasticity and trade are independent.
"""

from __future__ import annotations

import math
import uuid
from typing import Literal

import numpy as np
from pydantic import BaseModel, Field, model_validator

from qatra_ai.contracts import (
    Confidence,
    DataClass,
    EngineEnvelope,
    ModelInfo,
    Quantity,
    ValidationStatus,
    inputs_hash,
)
from qatra_ai.market.scenarios import (
    ASSUMPTIONS as MARKET_ASSUMPTIONS,
)
from qatra_ai.market.scenarios import (
    DISCLAIMER,
    MarketReference,
    SupplyScenario,
    YieldDistribution,
    _band,
    _lerp,
    inverse_demand_price,
    yield_quantile,
)
from qatra_ai.optimization.portfolio import (
    CropOption,
    PortfolioRequest,
    PortfolioResult,
    evaluate_plan,
    solve_portfolio,
)

ENGINE = "qatra_ai.market.regional"
MODEL = ModelInfo(
    model_id="regional_reflexivity",
    version="0.1.0",
    validation_status=ValidationStatus.LITERATURE_PARAMETERISED,
    references=[
        "Rockafellar & Uryasev (2000) Optimization of conditional value-at-risk, J. Risk 2(3)",
        "Method of successive averages for equilibrium fixed points (Sheffi 1985)",
        "AI_ENGINE_BLUEPRINT 6.3-6.4",
    ],
)
ASSUMPTIONS = MARKET_ASSUMPTIONS + [
    "Following farms are aggregated into one group with identical per-hectare yields, costs "
    "and water needs; they all receive and adopt the same plan.",
    "Each farm takes prices as given when planning; the loop accounts for the group's "
    "combined effect on prices.",
]


class CropMarket(BaseModel):
    crop: str
    reference: MarketReference
    scenario: SupplyScenario
    yield_t_per_ha: YieldDistribution
    cost_per_ha: float = Field(ge=0)
    water_m3_per_ha: float = Field(ge=0)
    energy_kwh_per_ha: float = Field(default=0.0, ge=0)
    min_ha: float = Field(default=0.0, ge=0)
    max_ha: float | None = Field(default=None, ge=0)
    excluded: bool = False


class RegionalRequest(BaseModel):
    region: str
    price_unit: str = "TND/t"
    followers_land_ha: float = Field(gt=0)
    followers_water_m3: float = Field(ge=0)
    followers_energy_kwh: float | None = Field(default=None, ge=0)
    crops: list[CropMarket] = Field(min_length=1)
    beta: float = Field(default=0.5, ge=0)
    alpha: float = Field(default=0.9, gt=0, lt=1)
    max_share_per_crop: float | None = Field(
        default=None, gt=0, le=1, description="optional regional cap the engine itself applies"
    )
    weather_correlation: float = Field(default=0.5, ge=0, le=1)
    damping: Literal["msa"] | float = "msa"
    tol: float = Field(default=0.01, gt=0)
    max_iter: int = Field(default=150, ge=1, le=2000)
    undamped_rounds: int = Field(default=10, ge=3, le=50)
    n_samples: int = Field(default=800, ge=100, le=20_000)
    seed: int = 0

    @model_validator(mode="after")
    def _check(self) -> RegionalRequest:
        if isinstance(self.damping, float) and not 0 < self.damping <= 1:
            raise ValueError("damping must be 'msa' or in (0, 1]")
        if len({c.crop for c in self.crops}) != len(self.crops):
            raise ValueError("duplicate crop")
        return self


class PlanSummary(BaseModel):
    area_ha: dict[str, float]
    fallow_ha: float
    expected_margin: float
    cvar_margin: float = Field(description="mean margin over the worst (1-alpha) scenarios")
    prob_loss: float
    prices: dict[str, Quantity] = Field(description="price bands if all followers adopt")


class NaiveComparison(BaseModel):
    plan: PlanSummary = Field(description="evaluated at the prices the plan itself creates")
    promised_expected_margin: float = Field(description="at today's prices, ignoring feedback")
    promised_cvar_margin: float
    overstatement_pct: float = Field(description="promised vs realised expected margin")


class IterationTrace(BaseModel):
    iteration: int
    area_ha: dict[str, float]
    median_price: dict[str, float]
    regret: float


class RegionalOutcome(BaseModel):
    region: str
    scenario_kind: Literal["hypothetical"] = "hypothetical"
    price_unit: str
    money_unit: str
    naive: NaiveComparison
    equilibrium: PlanSummary | None
    converged: bool
    iterations: int
    final_regret: float
    trace: list[IterationTrace]
    undamped_behaviour: Literal["settles", "cycles"]
    undamped_areas: list[dict[str, float]]
    signals: list[dict[str, str]]
    assumptions: list[str]
    disclaimer: str = DISCLAIMER
    n_samples: int
    seed: int


def _norm_cdf(z: np.ndarray) -> np.ndarray:
    return 0.5 * (1.0 + np.vectorize(math.erf)(z / math.sqrt(2.0)))


class _RegionDraws:
    def __init__(self, req: RegionalRequest):
        rng = np.random.default_rng(req.seed)
        n, rho = req.n_samples, req.weather_correlation
        common = rng.standard_normal(n)
        self.y, self.other, self.eps, self.m = {}, {}, {}, {}
        for c in req.crops:
            z = math.sqrt(rho) * common + math.sqrt(1 - rho) * rng.standard_normal(n)
            u = np.clip(_norm_cdf(z), 1e-6, 1 - 1e-6)
            self.y[c.crop] = yield_quantile(c.yield_t_per_ha, u)
            self.other[c.crop] = _lerp(c.scenario.other_production_t, u)
            self.eps[c.crop] = _lerp(c.reference.elasticity, rng.random(n))
            self.m[c.crop] = _lerp(c.scenario.imports_t, rng.random(n)) - _lerp(
                c.scenario.exports_t, rng.random(n)
            )


class _Region:
    def __init__(self, req: RegionalRequest):
        self.req = req
        self.d = _RegionDraws(req)
        self.by = {c.crop: c for c in req.crops}

    def prices(self, x: dict[str, float]) -> dict[str, np.ndarray]:
        out = {}
        for c, cm in self.by.items():
            supply = self.d.other[c] + x.get(c, 0.0) * self.d.y[c]
            out[c], _ = inverse_demand_price(cm.reference, supply, self.d.m[c], self.d.eps[c])
        return out

    def margins(self, x: dict[str, float]) -> dict[str, np.ndarray]:
        p = self.prices(x)
        return {c: p[c] * self.d.y[c] - cm.cost_per_ha for c, cm in self.by.items()}

    def portfolio(self, margins: dict[str, np.ndarray]) -> PortfolioResult:
        r = self.req
        cap = r.max_share_per_crop * r.followers_land_ha if r.max_share_per_crop else None
        opts = []
        for c, cm in self.by.items():
            mx = cm.max_ha
            if cap is not None:
                mx = cap if mx is None else min(mx, cap)
            opts.append(
                CropOption(
                    crop=c,
                    water_m3_per_ha=cm.water_m3_per_ha,
                    energy_kwh_per_ha=cm.energy_kwh_per_ha,
                    min_ha=min(cm.min_ha, mx) if mx is not None else cm.min_ha,
                    max_ha=mx,
                    excluded=cm.excluded,
                    margin_samples=margins[c].tolist(),
                )
            )
        return solve_portfolio(
            PortfolioRequest(
                land_ha=r.followers_land_ha,
                water_m3=r.followers_water_m3,
                energy_kwh=r.followers_energy_kwh,
                options=opts,
                beta=r.beta,
                alpha=r.alpha,
                money_unit=r.price_unit.split("/")[0],
            )
        )

    def objective(self, x: dict[str, float], margins: dict[str, np.ndarray]) -> float:
        exp, cvar, _ = evaluate_plan(x, margins, self.req.alpha)
        return exp + self.req.beta * cvar  # = E[pi] - beta * CVaR[-pi]

    def summary(self, x: dict[str, float]) -> PlanSummary:
        margins = self.margins(x)
        exp, cvar, ploss = evaluate_plan(x, margins, self.req.alpha)
        p = self.prices(x)
        return PlanSummary(
            area_ha={c: round(v, 2) for c, v in x.items()},
            fallow_ha=round(max(0.0, self.req.followers_land_ha - sum(x.values())), 2),
            expected_margin=round(exp, 0),
            cvar_margin=round(cvar, 0),
            prob_loss=round(ploss, 3),
            prices={c: _band(v, self.req.price_unit) for c, v in p.items()},
        )


def _median_prices(region: _Region, x: dict[str, float]) -> dict[str, float]:
    return {c: round(float(np.median(v)), 2) for c, v in region.prices(x).items()}


def regional_equilibrium(
    req: RegionalRequest, *, request_id: str | None = None
) -> EngineEnvelope[RegionalOutcome]:
    region = _Region(req)
    crops = list(region.by)
    zero = dict.fromkeys(crops, 0.0)

    first = region.portfolio(region.margins(zero))
    if not first.feasible:
        raise ValueError(first.note or "portfolio infeasible")
    naive_x = dict(first.area_ha)
    naive_sum = region.summary(naive_x)
    promised = first.expected_margin or 0.0
    over = (
        100 * (promised - naive_sum.expected_margin) / abs(promised) if abs(promised) > 1 else 0.0
    )

    # damped fixed point
    x = dict(naive_x)
    trace: list[IterationTrace] = []
    converged = False
    regret = float("inf")
    k = 0
    for k in range(1, req.max_iter + 1):
        m = region.margins(x)
        target = region.portfolio(m)
        obj_t = region.objective(target.area_ha, m)
        regret = obj_t - region.objective(x, m)
        trace.append(
            IterationTrace(
                iteration=k - 1,
                area_ha={c: round(v, 2) for c, v in x.items()},
                median_price=_median_prices(region, x),
                regret=round(regret, 2),
            )
        )
        if regret <= req.tol * max(abs(obj_t), 1.0):
            converged = True
            break
        lam = 1.0 / (k + 1) if req.damping == "msa" else float(req.damping)
        x = {c: (1 - lam) * x[c] + lam * target.area_ha[c] for c in crops}

    # undamped: everyone re-plans from last season's prices
    ux = dict(naive_x)
    rounds = [ux]
    for _ in range(req.undamped_rounds - 1):
        ux = dict(region.portfolio(region.margins(ux)).area_ha)
        rounds.append(ux)

    def same(a, b):
        return all(abs(a[c] - b[c]) <= 1e-3 * max(1.0, req.followers_land_ha) for c in crops)

    settles = same(rounds[-1], rounds[-2])
    eq = region.summary(x) if converged else None

    signals: list[dict[str, str]] = []
    if over >= 10:
        signals.append(
            {
                "code": "NAIVE_PLAN_OVERSTATES",
                "text": f"A plan that ignores its own effect on prices promises about "
                f"{over:.0f}% more margin than it delivers once all followers adopt it.",
            }
        )
    if eq is not None:
        for c in crops:
            a, b = naive_x[c], eq.area_ha[c]
            if a > 1 and b < 0.8 * a:
                signals.append(
                    {
                        "code": "CROWDED_CROP",
                        "text": f"{c}: the equilibrium plan uses {b:g} ha instead of {a:g} ha "
                        "because extra supply from followers lowers its price.",
                    }
                )
    if not converged:
        signals.append(
            {
                "code": "NO_EQUILIBRIUM_FOUND",
                "text": f"Plans and prices did not settle within {req.max_iter} iterations "
                f"(regret {regret:.0f}). Treat every plan here as unstable.",
            }
        )
    if not settles:
        signals.append(
            {
                "code": "BOOM_BUST_RISK",
                "text": "If all followers re-plan each season from last season's prices, the "
                "crop mix keeps switching instead of settling.",
            }
        )

    payload = RegionalOutcome(
        region=req.region,
        price_unit=req.price_unit,
        money_unit=req.price_unit.split("/")[0],
        naive=NaiveComparison(
            plan=naive_sum,
            promised_expected_margin=round(promised, 0),
            promised_cvar_margin=round(first.cvar_margin or 0.0, 0),
            overstatement_pct=round(over, 1),
        ),
        equilibrium=eq,
        converged=converged,
        iterations=k,
        final_regret=round(regret, 2),
        trace=trace,
        undamped_behaviour="settles" if settles else "cycles",
        undamped_areas=[{c: round(v, 2) for c, v in r.items()} for r in rounds],
        signals=signals,
        assumptions=ASSUMPTIONS
        + [
            f"{c.crop}: reference {c.reference.source}; scenario {c.scenario.source}"
            for c in req.crops
        ],  # fmt: skip
        n_samples=req.n_samples,
        seed=req.seed,
    )
    classes = [c.reference.data_class for c in req.crops]
    reasons = ["market and supply parameters are scenario inputs, not observations"]
    if any(dc in (DataClass.SIMULATED, DataClass.PROJECTED) for dc in classes):
        reasons.append("some reference seasons are simulated or projected")
    if not converged:
        reasons.append("no equilibrium found")
    return EngineEnvelope[RegionalOutcome](
        request_id=request_id or str(uuid.uuid4()),
        engine=ENGINE,
        model=MODEL,
        inputs_hash=inputs_hash(req.model_dump(mode="json")),
        provenance_summary={dc: classes.count(dc) for dc in set(classes)},
        confidence=Confidence.LOW,
        confidence_reasons=reasons,
        limitations=ASSUMPTIONS + [DISCLAIMER],
        missing_inputs=[],
        payload=payload,
    )

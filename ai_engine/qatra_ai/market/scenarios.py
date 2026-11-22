"""Market scenarios: supply, demand, price bands and recommendation reflexivity.

AI_ENGINE_BLUEPRINT sections 2.7 and 6.4. Scenario-based, never a price promise.

Model (per crop and market region, one marketing season):
  Supply      Q = Q_other + a * A * Y          a = share of candidate farms following the
                                               recommendation, A = their area (ha),
                                               Y = yield (t/ha) sampled from P10/P50/P90
  Net imports M = imports - exports            scenario ranges, NOT predictions
  Price       p = p0 * ((Q + M) / (Q0 + M0)) ** (1 / eps)     inverse constant-elasticity
                                               demand around a reference season (p0, Q0, M0);
                                               eps < 0 sampled from a range
  Apparent consumption (market demand that clears) = Q + M
  Margin      pi = p * Y - cost_per_ha

Uncertainty: Monte Carlo with common random numbers (the same draws for every adoption
share, so differences between shares are due to adoption only). Yield and the rest of the
region's production share one weather draw (comonotonic: a good year is good for everyone),
which is the conservative choice for price swings. Elasticity and trade are independent.

Reflexivity (the key requirement):
  - adoption table: "if X % of candidate farms follow this", the price band, the margin band
    and the probability of doing worse than the alternative;
  - adoption cap: the largest followed area at which the median margin still beats the
    alternative (bisection; price falls monotonically with area). The engine should not push
    the crop onto more area than this;
  - cobweb check: if everyone sets next season's area from last season's price, does the
    market settle or swing? (undamped iteration; swinging is itself a risk signal).

All parameters are inputs with their source. The module ships no prices or elasticities.
"""

from __future__ import annotations

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
from qatra_ai.market import history as hist

ENGINE = "qatra_ai.market"
MODEL = ModelInfo(
    model_id="market_scenarios",
    version="0.1.0",
    validation_status=ValidationStatus.LITERATURE_PARAMETERISED,
    references=[
        "Constant-elasticity inverse demand (AI_ENGINE_BLUEPRINT 6.4)",
        "Ezekiel (1938) The cobweb theorem, QJE 52(2)",
    ],
)
DISCLAIMER = (
    "Market outputs are scenario ranges built from the stated assumptions. They are not "
    "forecasts of the price any farmer will receive and are never guaranteed."
)
ASSUMPTIONS = [
    "Inverse demand has constant elasticity around the reference season; it is unreliable far "
    "from that season (supply ratios outside 0.5-2 are flagged).",
    "Imports and exports are scenario ranges, not predictions; trade does not react to price.",
    "Yield of the followers and production of the rest of the region share one weather draw.",
    "One marketing season, one price for the whole region; storage, grading, timing of sale "
    "and transport costs are not modelled.",
    "Farms not following the recommendation keep their area (no competitor response).",
]
VALID_SUPPLY_RATIO = (0.5, 2.0)


class Range(BaseModel):
    low: float
    high: float

    @model_validator(mode="after")
    def _ordered(self) -> Range:
        if self.low > self.high:
            raise ValueError("low must be <= high")
        return self


class YieldDistribution(BaseModel):
    p10: float = Field(ge=0)
    p50: float = Field(ge=0)
    p90: float = Field(ge=0)
    source: str

    @model_validator(mode="after")
    def _ordered(self) -> YieldDistribution:
        if not self.p10 <= self.p50 <= self.p90:
            raise ValueError("need p10 <= p50 <= p90")
        return self


class MarketReference(BaseModel):
    """The reference season the demand curve is anchored to."""

    price: float = Field(gt=0, description="p0, mean farm-gate or wholesale price")
    production_t: float = Field(gt=0, description="Q0, production in the market region")
    net_imports_t: float = Field(default=0.0, description="M0 = imports - exports")
    elasticity: Range = Field(description="price elasticity of demand, both bounds < 0")
    source: str
    data_class: DataClass

    @model_validator(mode="after")
    def _check(self) -> MarketReference:
        if self.elasticity.high >= 0:
            raise ValueError("elasticity must be negative")
        if self.production_t + self.net_imports_t <= 0:
            raise ValueError("reference consumption Q0 + M0 must be > 0")
        return self


class SupplyScenario(BaseModel):
    name: str
    other_production_t: Range = Field(
        description="production of everyone NOT counted in candidate_area_ha"
    )
    imports_t: Range = Field(default_factory=lambda: Range(low=0, high=0))
    exports_t: Range = Field(default_factory=lambda: Range(low=0, high=0))
    source: str


class PricePoint(BaseModel):
    date: str
    price: float = Field(gt=0)


class MarketOutlookRequest(BaseModel):
    crop: str
    region: str
    price_unit: str = "TND/t"
    reference: MarketReference
    scenario: SupplyScenario
    candidate_area_ha: float = Field(
        gt=0, description="area of the farms that would receive this crop recommendation"
    )
    yield_t_per_ha: YieldDistribution
    cost_per_ha: float = Field(ge=0, description="variable cost per ha, same currency as price")
    alternative_margin_per_ha: float | None = Field(
        default=None, description="margin per ha of what these farms would grow otherwise"
    )
    adoption_shares: list[float] = Field(default=[0.0, 0.1, 0.25, 0.5, 0.75, 1.0])
    influence_share: float = Field(
        default=0.25, ge=0, le=1, description="adoption share at which drivers are compared"
    )
    price_history: list[PricePoint] | None = None
    n_samples: int = Field(default=4000, ge=200, le=100_000)
    seed: int = 0

    @model_validator(mode="after")
    def _shares(self) -> MarketOutlookRequest:
        if any(not 0 <= s <= 1 for s in self.adoption_shares):
            raise ValueError("adoption shares must be in [0, 1]")
        return self


class AdoptionPoint(BaseModel):
    share: float
    followed_area_ha: float
    total_supply_t: Quantity
    apparent_consumption_t: Quantity
    price: Quantity
    price_change_vs_reference_pct: Quantity
    margin_per_ha: Quantity
    prob_loss: float = Field(description="P(margin < 0)")
    prob_below_alternative: float | None
    outside_validity_share: float


class DriverInfluence(BaseModel):
    driver: str
    low_setting: str
    high_setting: str
    price_at_low: float
    price_at_high: float
    swing: float


class CobwebRound(BaseModel):
    season: int
    followed_area_ha: float
    median_price: float


class Reflexivity(BaseModel):
    adoption_cap_share: float | None = Field(
        description="largest share of candidate area at which the median margin still beats "
        "the alternative; None when no alternative margin is given"
    )
    adoption_cap_area_ha: float | None
    cap_rule: str
    cobweb: list[CobwebRound]
    cobweb_behaviour: Literal["settles", "oscillates", "not_run"]


class MarketSignal(BaseModel):
    code: str
    severity: Literal["info", "warning"]
    text: str


class MarketOutlook(BaseModel):
    crop: str
    region: str
    scenario_kind: Literal["hypothetical"] = "hypothetical"
    scenario_name: str
    price_unit: str
    reference: MarketReference
    history: hist.PriceProfile | None
    forecast: hist.PriceForecast | None
    forecast_status: str
    adoption: list[AdoptionPoint]
    influence_share: float
    influences: list[DriverInfluence]
    reflexivity: Reflexivity
    signals: list[MarketSignal]
    assumptions: list[str]
    disclaimer: str = DISCLAIMER
    n_samples: int
    seed: int


# --- sampling -------------------------------------------------------------------------------


def yield_quantile(d: YieldDistribution, u: np.ndarray) -> np.ndarray:
    """Piecewise-linear quantile function through (0.1, p10), (0.5, p50), (0.9, p90),
    extended linearly into the tails and clipped at 0."""
    s_lo = (d.p50 - d.p10) / 0.4
    s_hi = (d.p90 - d.p50) / 0.4
    y = np.where(u <= 0.5, d.p50 + (u - 0.5) * s_lo, d.p50 + (u - 0.5) * s_hi)
    return np.maximum(y, 0.0)


class _Draws:
    def __init__(self, req: MarketOutlookRequest):
        rng = np.random.default_rng(req.seed)
        n = req.n_samples
        self.u_weather = rng.random(n)
        u_eps, u_imp, u_exp = rng.random(n), rng.random(n), rng.random(n)
        sc, ref = req.scenario, req.reference
        self.yield_ = yield_quantile(req.yield_t_per_ha, self.u_weather)
        self.other = _lerp(sc.other_production_t, self.u_weather)
        self.eps = _lerp(ref.elasticity, u_eps)
        self.net_imports = _lerp(sc.imports_t, u_imp) - _lerp(sc.exports_t, u_exp)


def _lerp(r: Range, u: np.ndarray | float) -> np.ndarray:
    return r.low + (r.high - r.low) * np.asarray(u, dtype=float)


def inverse_demand_price(
    ref: MarketReference, supply_t: np.ndarray, net_imports_t: np.ndarray, eps: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Returns (price, supply_ratio). Consumption is floored at 1 % of the reference."""
    q0 = ref.production_t + ref.net_imports_t
    ratio = np.maximum(supply_t + net_imports_t, 0.01 * q0) / q0
    return ref.price * ratio ** (1.0 / eps), ratio


def _band(x: np.ndarray, unit: str, nd: int = 2) -> Quantity:
    p10, p50, p90 = np.quantile(x, hist.QUANTILES)
    return Quantity(
        value=round(float(p50), nd),
        unit=unit,
        interval=(round(float(p10), nd), round(float(p90), nd)),
        interval_kind="quantile_10_90",
    )


def _simulate(req: MarketOutlookRequest, dr: _Draws, area_ha: float):
    supply = dr.other + area_ha * dr.yield_
    price, ratio = inverse_demand_price(req.reference, supply, dr.net_imports, dr.eps)
    margin = price * dr.yield_ - req.cost_per_ha
    return supply, price, ratio, margin


def adoption_table(req: MarketOutlookRequest, dr: _Draws) -> list[AdoptionPoint]:
    money = req.price_unit.split("/")[0]
    out = []
    for s in sorted(set(req.adoption_shares)):
        area = s * req.candidate_area_ha
        supply, price, ratio, margin = _simulate(req, dr, area)
        lo, hi = VALID_SUPPLY_RATIO
        alt = req.alternative_margin_per_ha
        out.append(
            AdoptionPoint(
                share=s,
                followed_area_ha=round(area, 2),
                total_supply_t=_band(supply, "t", 0),
                apparent_consumption_t=_band(supply + dr.net_imports, "t", 0),
                price=_band(price, req.price_unit),
                price_change_vs_reference_pct=_band(
                    100 * (price / req.reference.price - 1), "%", 1
                ),
                margin_per_ha=_band(margin, f"{money}/ha", 0),
                prob_loss=round(float(np.mean(margin < 0)), 3),
                prob_below_alternative=(
                    round(float(np.mean(margin < alt)), 3) if alt is not None else None
                ),
                outside_validity_share=round(float(np.mean((ratio < lo) | (ratio > hi))), 3),
            )
        )
    return out


def driver_influences(req: MarketOutlookRequest, share: float) -> list[DriverInfluence]:
    """One-at-a-time swings of the price: each driver at its low/high setting while the others
    stay at their middle, at a given adoption share. Sorted by swing (largest first).
    Elasticity has no effect when supply equals the reference season (ratio 1)."""
    sc, ref = req.scenario, req.reference
    area = share * req.candidate_area_ha
    yd = req.yield_t_per_ha
    mid = {
        "weather": 0.5,
        "eps": (ref.elasticity.low + ref.elasticity.high) / 2,
        "imp": (sc.imports_t.low + sc.imports_t.high) / 2,
        "exp": (sc.exports_t.low + sc.exports_t.high) / 2,
    }

    def price(weather=None, eps=None, imp=None, exp=None) -> float:
        u = mid["weather"] if weather is None else weather
        y = float(yield_quantile(yd, np.array([u]))[0])
        q = float(_lerp(sc.other_production_t, u)) + area * y
        m = (mid["imp"] if imp is None else imp) - (mid["exp"] if exp is None else exp)
        p, _ = inverse_demand_price(
            ref, np.array([q]), np.array([m]), np.array([mid["eps"] if eps is None else eps])
        )
        return float(p[0])

    rows = [
        ("regional harvest (weather)", "poor year (P10 yields)", "good year (P90 yields)",
         price(weather=0.1), price(weather=0.9)),
        ("price elasticity of demand", f"{ref.elasticity.low}", f"{ref.elasticity.high}",
         price(eps=ref.elasticity.low), price(eps=ref.elasticity.high)),
        ("imports", f"{sc.imports_t.low:g} t", f"{sc.imports_t.high:g} t",
         price(imp=sc.imports_t.low), price(imp=sc.imports_t.high)),
        ("exports", f"{sc.exports_t.low:g} t", f"{sc.exports_t.high:g} t",
         price(exp=sc.exports_t.low), price(exp=sc.exports_t.high)),
    ]  # fmt: skip
    out = [
        DriverInfluence(
            driver=d,
            low_setting=lo,
            high_setting=hi,
            price_at_low=round(pl, 2),
            price_at_high=round(ph, 2),
            swing=round(abs(ph - pl), 2),
        )
        for d, lo, hi, pl, ph in rows
    ]
    return sorted(out, key=lambda r: -r.swing)


def _median_margin(req: MarketOutlookRequest, dr: _Draws, area: float) -> float:
    return float(np.median(_simulate(req, dr, area)[3]))


def reflexivity(req: MarketOutlookRequest, dr: _Draws, seasons: int = 8) -> Reflexivity:
    A = req.candidate_area_ha
    alt = req.alternative_margin_per_ha
    if alt is None:
        return Reflexivity(
            adoption_cap_share=None,
            adoption_cap_area_ha=None,
            cap_rule="no alternative margin supplied: cap and cobweb not computed",
            cobweb=[],
            cobweb_behaviour="not_run",
        )
    # adoption cap: median margin is non-increasing in followed area (common random numbers)
    if _median_margin(req, dr, A) >= alt:
        cap = 1.0
    elif _median_margin(req, dr, 0.0) < alt:
        cap = 0.0
    else:
        lo, hi = 0.0, 1.0
        for _ in range(40):
            mid = (lo + hi) / 2
            if _median_margin(req, dr, mid * A) >= alt:
                lo = mid
            else:
                hi = mid
        cap = lo

    # cobweb: each season everyone follows if LAST season's median price made the crop pay
    y50 = req.yield_t_per_ha.p50
    area = 0.0
    rounds = []
    for k in range(seasons):
        p = float(np.median(_simulate(req, dr, area)[1]))
        rounds.append(
            CobwebRound(season=k, followed_area_ha=round(area, 2), median_price=round(p, 2))
        )
        area = A if p * y50 - req.cost_per_ha >= alt else 0.0
    tail = [r.followed_area_ha for r in rounds[2:]]
    behaviour: Literal["settles", "oscillates"] = "settles" if len(set(tail)) <= 1 else "oscillates"
    return Reflexivity(
        adoption_cap_share=round(cap, 3),
        adoption_cap_area_ha=round(cap * A, 2),
        cap_rule="largest followed share at which the median margin >= alternative margin",
        cobweb=rounds,
        cobweb_behaviour=behaviour,
    )


def market_signals(
    req: MarketOutlookRequest, table: list[AdoptionPoint], rfx: Reflexivity
) -> list[MarketSignal]:
    sig: list[MarketSignal] = []
    by = {p.share: p for p in table}
    first, last = table[0], table[-1]
    drop = 100 * (1 - last.price.value / first.price.value) if first.price.value else 0.0
    if last.share > first.share and drop >= 15:
        sig.append(
            MarketSignal(
                code="DIVERSIFY_PRICE_PRESSURE",
                severity="warning",
                text=f"If {last.share:.0%} of candidate farms follow this recommendation, the "
                f"median price falls by about {drop:.0f}% compared with {first.share:.0%}. "
                "Spread the recommendation across crops.",
            )
        )
    if rfx.adoption_cap_share is not None and rfx.adoption_cap_share < 1:
        sig.append(
            MarketSignal(
                code="ADOPTION_CAP",
                severity="warning",
                text=f"Beyond about {rfx.adoption_cap_share:.0%} of the candidate area "
                f"({rfx.adoption_cap_area_ha:g} ha), the median margin no longer beats the "
                "alternative. The engine should not push this crop onto more area.",
            )
        )
    if rfx.cobweb_behaviour == "oscillates":
        sig.append(
            MarketSignal(
                code="BOOM_BUST_RISK",
                severity="warning",
                text="If everyone chooses next season's area from last season's price, supply "
                "and price swing between seasons instead of settling (cobweb).",
            )
        )
    risky = [p for p in table if p.prob_loss >= 0.2]
    if risky:
        p = risky[0]
        sig.append(
            MarketSignal(
                code="LOSS_RISK",
                severity="warning",
                text=f"From {p.share:.0%} adoption, at least {p.prob_loss:.0%} of the scenarios "
                "give a negative margin.",
            )
        )
    if any(p.outside_validity_share > 0.1 for p in table):
        sig.append(
            MarketSignal(
                code="EXTRAPOLATION",
                severity="warning",
                text="Some scenarios move supply far from the reference season; the demand "
                "curve is extrapolated there and the price band is less reliable.",
            )
        )
    if 0.0 in by and by[0.0].price.interval:
        lo, hi = by[0.0].price.interval
        sig.append(
            MarketSignal(
                code="PRICE_RANGE",
                severity="info",
                text=f"Even with no extra planting, the price in 8 of 10 scenarios lies between "
                f"{lo:g} and {hi:g} {req.price_unit}.",
            )
        )
    return sig


def market_outlook(
    req: MarketOutlookRequest, *, request_id: str | None = None
) -> EngineEnvelope[MarketOutlook]:
    dr = _Draws(req)
    table = adoption_table(req, dr)
    rfx = reflexivity(req, dr)
    reasons = ["supply, trade and demand parameters are scenario inputs, not observations"]
    limitations = ASSUMPTIONS + [DISCLAIMER]
    missing: list[str] = []

    profile = forecast = None
    status = "no price history supplied"
    if req.price_history:
        import pandas as pd

        series = pd.Series(
            [p.price for p in req.price_history],
            index=pd.to_datetime([p.date for p in req.price_history]),
        )
        profile = hist.price_profile(series, req.price_unit)
        forecast, status = hist.forecast_range(series, req.price_unit)
    else:
        missing.append("price_history")

    conf = Confidence.LOW
    if req.reference.data_class in (DataClass.SIMULATED, DataClass.PROJECTED):
        reasons.append(f"reference season is {req.reference.data_class.value}")
    elif (
        forecast is not None
        and forecast.backtest is not None
        and 0.7 <= forecast.backtest.interval_coverage_p10_p90 <= 0.9
        and req.reference.data_class == DataClass.OFFICIAL
    ):
        conf = Confidence.MEDIUM
        reasons.append("official reference and a backtested price range with sound coverage")
    if forecast is None:
        reasons.append(status)
    if req.alternative_margin_per_ha is None:
        missing.append("alternative_margin_per_ha")

    payload = MarketOutlook(
        crop=req.crop,
        region=req.region,
        scenario_name=req.scenario.name,
        price_unit=req.price_unit,
        reference=req.reference,
        history=profile,
        forecast=forecast,
        forecast_status=status,
        adoption=table,
        influence_share=req.influence_share,
        influences=driver_influences(req, req.influence_share),
        reflexivity=rfx,
        signals=market_signals(req, table, rfx),
        assumptions=ASSUMPTIONS
        + [
            f"reference: {req.reference.source}",
            f"scenario: {req.scenario.source}",
            f"yield: {req.yield_t_per_ha.source}",
        ],
        n_samples=req.n_samples,
        seed=req.seed,
    )
    return EngineEnvelope[MarketOutlook](
        request_id=request_id or str(uuid.uuid4()),
        engine=ENGINE,
        model=MODEL,
        inputs_hash=inputs_hash(req.model_dump(mode="json")),
        provenance_summary={req.reference.data_class: 1},
        confidence=conf,
        confidence_reasons=reasons,
        limitations=limitations,
        missing_inputs=missing,
        payload=payload,
    )

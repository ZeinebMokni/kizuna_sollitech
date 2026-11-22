"""Market intelligence tests on SYNTHETIC inputs (labelled test values, not real markets)."""

import numpy as np
import pandas as pd
import pytest
from pydantic import ValidationError

from qatra_ai.contracts import Confidence, DataClass, Quantity
from qatra_ai.market import history as hist
from qatra_ai.market.scenarios import (
    MarketOutlookRequest,
    MarketReference,
    PricePoint,
    Range,
    SupplyScenario,
    YieldDistribution,
    _Draws,
    _median_margin,
    inverse_demand_price,
    market_outlook,
    yield_quantile,
)


def request(**kw) -> MarketOutlookRequest:
    base = dict(
        crop="tomato",
        region="test-region",
        reference=MarketReference(
            price=1000.0,
            production_t=100_000,
            net_imports_t=0,
            elasticity=Range(low=-0.6, high=-0.3),
            source="synthetic test",
            data_class=DataClass.SIMULATED,
        ),
        scenario=SupplyScenario(
            name="test",
            other_production_t=Range(low=90_000, high=110_000),
            imports_t=Range(low=0, high=5_000),
            exports_t=Range(low=0, high=5_000),
            source="synthetic test",
        ),
        candidate_area_ha=500.0,
        yield_t_per_ha=YieldDistribution(p10=40, p50=55, p90=65, source="synthetic test"),
        cost_per_ha=25_000.0,
        alternative_margin_per_ha=20_000.0,
        n_samples=2000,
    )
    base.update(kw)
    return MarketOutlookRequest(**base)


def test_inverse_demand_reference_and_direction():
    ref = request().reference
    p, r = inverse_demand_price(ref, np.array([100_000.0]), np.array([0.0]), np.array([-0.5]))
    assert p[0] == pytest.approx(1000.0) and r[0] == pytest.approx(1.0)
    # +10 % supply with eps = -0.5 -> price * 1.1**-2
    p, _ = inverse_demand_price(ref, np.array([110_000.0]), np.array([0.0]), np.array([-0.5]))
    assert p[0] == pytest.approx(1000 * 1.1**-2)


def test_yield_quantile_hits_given_quantiles():
    d = YieldDistribution(p10=40, p50=55, p90=65, source="t")
    assert yield_quantile(d, np.array([0.1, 0.5, 0.9])) == pytest.approx([40, 55, 65])
    assert yield_quantile(d, np.array([0.0])).min() >= 0


def test_price_falls_as_adoption_rises():
    env = market_outlook(request())
    prices = [p.price.value for p in env.payload.adoption]
    assert all(a > b for a, b in zip(prices, prices[1:], strict=False))
    supply = [p.total_supply_t.value for p in env.payload.adoption]
    assert all(a < b for a, b in zip(supply, supply[1:], strict=False))


def test_no_price_is_a_point_value():
    """Never present uncertain prices as certain: every price/margin carries a P10-P90 band."""
    env = market_outlook(request())
    for p in env.payload.adoption:
        for q in (p.price, p.margin_per_ha, p.price_change_vs_reference_pct):
            assert isinstance(q, Quantity)
            assert q.interval_kind == "quantile_10_90"
            assert q.interval[0] < q.value < q.interval[1]
    assert "never guaranteed" in env.payload.disclaimer
    assert any("never guaranteed" in x for x in env.limitations)
    assert env.payload.scenario_kind == "hypothetical"


def test_adoption_cap_is_where_median_margin_meets_alternative():
    req = request()
    env = market_outlook(req)
    rfx = env.payload.reflexivity
    assert 0 < rfx.adoption_cap_share < 1
    dr = _Draws(req)
    A = req.candidate_area_ha
    alt = req.alternative_margin_per_ha
    assert _median_margin(req, dr, rfx.adoption_cap_share * A) >= alt - 1e-6
    assert _median_margin(req, dr, (rfx.adoption_cap_share + 0.01) * A) < alt
    assert "ADOPTION_CAP" in {s.code for s in env.payload.signals}


def test_cap_is_full_when_the_crop_pays_even_at_full_adoption():
    env = market_outlook(request(alternative_margin_per_ha=0.0, candidate_area_ha=10))
    assert env.payload.reflexivity.adoption_cap_share == 1.0
    assert "ADOPTION_CAP" not in {s.code for s in env.payload.signals}


def test_cobweb_detects_boom_bust_with_inelastic_demand():
    # very inelastic demand, large candidate area: following last season's price swings
    req = request(
        reference=request().reference.model_copy(update={"elasticity": Range(low=-0.3, high=-0.2)}),
        candidate_area_ha=600,
    )
    env = market_outlook(req)
    assert env.payload.reflexivity.cobweb_behaviour == "oscillates"
    assert "BOOM_BUST_RISK" in {s.code for s in env.payload.signals}


def test_no_alternative_margin_skips_cap_and_lists_missing_input():
    env = market_outlook(request(alternative_margin_per_ha=None))
    assert env.payload.reflexivity.cobweb_behaviour == "not_run"
    assert "alternative_margin_per_ha" in env.missing_inputs
    assert all(p.prob_below_alternative is None for p in env.payload.adoption)


def test_imports_lower_price_and_influences_are_sorted():
    env = market_outlook(request())
    infl = {d.driver: d for d in env.payload.influences}
    assert infl["imports"].price_at_high < infl["imports"].price_at_low
    assert infl["exports"].price_at_high > infl["exports"].price_at_low
    swings = [d.swing for d in env.payload.influences]
    assert swings == sorted(swings, reverse=True)


def test_simulated_reference_keeps_confidence_low_and_is_reproducible():
    a, b = market_outlook(request()), market_outlook(request())
    assert a.confidence == Confidence.LOW
    assert a.inputs_hash == b.inputs_hash
    assert a.payload.adoption == b.payload.adoption


def test_invalid_inputs_rejected():
    with pytest.raises(ValidationError):
        Range(low=2, high=1)
    with pytest.raises(ValidationError):
        request().reference.model_validate(
            {**request().reference.model_dump(), "elasticity": {"low": -0.5, "high": 0.2}}
        )
    with pytest.raises(ValidationError):
        YieldDistribution(p10=60, p50=50, p90=70, source="t")
    with pytest.raises(ValidationError):
        request(adoption_shares=[0.5, 1.5])


# --- price history ------------------------------------------------------------------------


def synthetic_prices(years=7, seed=1) -> pd.Series:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2015-01-01", periods=12 * years, freq="MS")
    season = 1 + 0.3 * np.sin(2 * np.pi * (idx.month - 1) / 12)
    return pd.Series(1000 * season * np.exp(rng.normal(0, 0.08, idx.size)), index=idx)


def test_profile_recovers_seasonality():
    prof = hist.price_profile(synthetic_prices(), "TND/t")
    idx = {b.month: b.seasonal_index for b in prof.by_month}
    assert idx[4] > 1.15 and idx[10] < 0.85  # sin peak in April, trough in October
    assert prof.n_months == 84 and prof.missing_months == 0
    assert 0.05 < prof.yoy_log_change_std < 0.2


def test_forecast_needs_five_years():
    fc, status = hist.forecast_range(synthetic_prices(years=4), "TND/t")
    assert fc is None and "60 needed" in status


def test_forecast_band_and_backtest_coverage():
    fc, status = hist.forecast_range(synthetic_prices(years=8), "TND/t")
    assert status == "ok" and len(fc.points) == 12
    assert all(p.p10 < p.p50 < p.p90 for p in fc.points)
    bt = fc.backtest
    assert bt is not None and bt.n_origins > 0
    assert 0.6 <= bt.interval_coverage_p10_p90 <= 0.97
    assert bt.mape_p50 < 0.2


def test_backtest_has_no_lookahead():
    """Changing a price after the last backtest target must not change the backtest."""
    s = synthetic_prices(years=8)
    m = hist.to_monthly(s)
    bt1 = hist.backtest_seasonal_naive(m, horizon=6, n_origins=6)
    m2 = m.copy()
    m2.iloc[-1] *= 5  # last month is only ever a target, never history for earlier targets
    bt2 = hist.backtest_seasonal_naive(m2[:-1], horizon=6, n_origins=6)
    bt3 = hist.backtest_seasonal_naive(m[:-1], horizon=6, n_origins=6)
    assert bt2 == bt3
    assert bt1 != bt2


def test_outlook_with_history_reports_profile_and_forecast():
    s = synthetic_prices(years=6)
    hist_pts = [PricePoint(date=str(d.date()), price=float(v)) for d, v in s.items()]
    env = market_outlook(request(price_history=hist_pts))
    assert env.payload.history is not None and env.payload.forecast is not None
    assert "price_history" not in env.missing_inputs
    assert env.confidence == Confidence.LOW  # reference is simulated

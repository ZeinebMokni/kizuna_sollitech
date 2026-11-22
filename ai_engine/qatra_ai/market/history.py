"""Descriptive price statistics and baseline forecast ranges from a price history.

AI_ENGINE_BLUEPRINT section 2.7. Nothing here is a price promise:
- Descriptive: per-calendar-month price distribution (P10/P50/P90), a seasonal index
  (month median / overall median; a robust stand-in for STL that needs no extra dependency)
  and volatility (spread of month-to-month and year-over-year log changes).
- Forecast ranges: only with >= MIN_YEARS of monthly data. The baseline is the seasonal naive
  forecast (same month last year); its P10/P90 band comes from the empirical distribution of
  past year-over-year log ratios. A rolling-origin backtest (no look-ahead: each origin only
  uses data before it) reports MAPE, pinball loss and the actual P10-P90 coverage.
  Any richer model (ETS/SARIMAX, gradient boosting) must beat this baseline in the same
  backtest before it may be used; none is implemented yet.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field

MIN_YEARS = 5
QUANTILES = (0.1, 0.5, 0.9)


class MonthBand(BaseModel):
    month: int = Field(ge=1, le=12)
    n_years: int
    p10: float
    p50: float
    p90: float
    seasonal_index: float = Field(description="month median / overall median")


class PriceProfile(BaseModel):
    price_unit: str
    first_month: str
    last_month: str
    n_months: int
    missing_months: int
    by_month: list[MonthBand]
    mom_log_change_std: float | None = Field(
        description="std of month-to-month log price changes (volatility)"
    )
    yoy_log_change_std: float | None = Field(
        description="std of same-month year-over-year log changes"
    )


class ForecastPoint(BaseModel):
    month: str
    p10: float
    p50: float
    p90: float


class Backtest(BaseModel):
    method: str
    n_origins: int
    horizon_months: int
    mape_p50: float
    pinball_loss: dict[str, float]
    interval_coverage_p10_p90: float = Field(description="nominal 0.80")


class PriceForecast(BaseModel):
    method: str
    price_unit: str
    points: list[ForecastPoint]
    backtest: Backtest | None
    note: str


def to_monthly(prices: pd.Series) -> pd.Series:
    """Monthly mean on a complete month index (missing months stay NaN, never filled)."""
    s = pd.Series(prices, dtype=float).dropna()
    if s.empty:
        raise ValueError("empty price series")
    if (s <= 0).any():
        raise ValueError("prices must be > 0")
    s.index = pd.DatetimeIndex(s.index)
    m = s.resample("MS").mean()
    return m


def price_profile(prices: pd.Series, price_unit: str) -> PriceProfile:
    m = to_monthly(prices)
    valid = m.dropna()
    overall = float(valid.median())
    bands = []
    for month in range(1, 13):
        x = valid[valid.index.month == month]
        if x.empty:
            continue
        q = np.quantile(x.to_numpy(), QUANTILES)
        bands.append(
            MonthBand(
                month=month,
                n_years=len(x),
                p10=round(float(q[0]), 4),
                p50=round(float(q[1]), 4),
                p90=round(float(q[2]), 4),
                seasonal_index=round(float(q[1]) / overall, 4),
            )
        )
    logm = np.log(m)
    mom = logm.diff().dropna()
    yoy = (logm - logm.shift(12)).dropna()
    return PriceProfile(
        price_unit=price_unit,
        first_month=str(m.index[0].date()),
        last_month=str(m.index[-1].date()),
        n_months=int(valid.size),
        missing_months=int(m.isna().sum()),
        by_month=bands,
        mom_log_change_std=round(float(mom.std()), 4) if len(mom) > 1 else None,
        yoy_log_change_std=round(float(yoy.std()), 4) if len(yoy) > 1 else None,
    )


def _yoy_log_ratios(m: pd.Series) -> np.ndarray:
    logm = np.log(m)
    return (logm - logm.shift(12)).dropna().to_numpy()


def _pinball(y: float, q: float, tau: float) -> float:
    d = y - q
    return max(tau * d, (tau - 1) * d)


def _snaive_band(m: pd.Series, target: pd.Timestamp) -> tuple[float, float, float] | None:
    """Seasonal-naive P10/P50/P90 for `target` using only `m` (data before the origin).

    Multi-year horizons chain the last observed same-month value; the log-ratio band is
    widened by sqrt(years ahead) (random-walk-in-years assumption)."""
    same = m[(m.index.month == target.month) & (m.index < target)].dropna()
    if same.empty:
        return None
    ratios = _yoy_log_ratios(m)
    if ratios.size < 12:
        return None
    years_ahead = max(1, (target.year - same.index[-1].year))
    base = float(same.iloc[-1])
    lo, mid, hi = np.quantile(ratios, QUANTILES)
    k = np.sqrt(years_ahead)
    # median of ratios is the typical drift; the band is around it
    return (
        base * float(np.exp(mid * years_ahead + (lo - mid) * k)),
        base * float(np.exp(mid * years_ahead)),
        base * float(np.exp(mid * years_ahead + (hi - mid) * k)),
    )


def backtest_seasonal_naive(
    m: pd.Series, horizon: int = 12, n_origins: int = 24
) -> Backtest | None:
    valid_idx = m.dropna().index
    origins = [o for o in valid_idx[-(n_origins + horizon) : -horizon]]
    # each origin needs >= 3 years before it for the ratio distribution
    origins = [o for o in origins if m[:o].dropna().size >= 36]
    if not origins:
        return None
    ape, cover = [], []
    pin = {f"q{int(t * 100)}": [] for t in QUANTILES}
    for o in origins:
        hist = m[m.index <= o]
        for h in range(1, horizon + 1):
            t = o + pd.DateOffset(months=h)
            if t not in m.index or np.isnan(m[t]):
                continue
            band = _snaive_band(hist, t)
            if band is None:
                continue
            y = float(m[t])
            ape.append(abs(band[1] - y) / y)
            cover.append(band[0] <= y <= band[2])
            for tau, q in zip(QUANTILES, band, strict=True):
                pin[f"q{int(tau * 100)}"].append(_pinball(y, q, tau))
    if not ape:
        return None
    return Backtest(
        method="rolling origin, seasonal naive",
        n_origins=len(origins),
        horizon_months=horizon,
        mape_p50=round(float(np.mean(ape)), 4),
        pinball_loss={k: round(float(np.mean(v)), 4) for k, v in pin.items()},
        interval_coverage_p10_p90=round(float(np.mean(cover)), 3),
    )


def forecast_range(
    prices: pd.Series, price_unit: str, horizon: int = 12
) -> tuple[PriceForecast | None, str]:
    """Returns (forecast, status). forecast is None when the history is too short."""
    m = to_monthly(prices)
    n = int(m.dropna().size)
    if n < MIN_YEARS * 12:
        return None, (
            f"no forecast: {n} monthly prices, at least {MIN_YEARS * 12} needed "
            f"({MIN_YEARS} years); descriptive statistics only"
        )
    last = m.dropna().index[-1]
    points = []
    for h in range(1, horizon + 1):
        t = last + pd.DateOffset(months=h)
        band = _snaive_band(m, t)
        if band is None:
            continue
        points.append(
            ForecastPoint(
                month=str(t.date()),
                p10=round(band[0], 4),
                p50=round(band[1], 4),
                p90=round(band[2], 4),
            )
        )
    bt = backtest_seasonal_naive(m, horizon=horizon)
    return (
        PriceForecast(
            method="seasonal naive with empirical year-over-year quantile band",
            price_unit=price_unit,
            points=points,
            backtest=bt,
            note="A range from past price behaviour, not a prediction of the price you will get. "
            "Read it together with the backtest coverage.",
        ),
        "ok",
    )

"""Time-series quality control. Flags values; never deletes or silently alters them.

Each check returns a boolean Series (True = check failed). `apply_qc` combines checks into
one flag per sample (invalid > suspect > valid). Invalid samples are removed from `value`;
if they sit inside a short enough gap they are interpolated and flagged `gap_filled`.
The original reading is always preserved in `raw_value`.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

VALID, SUSPECT, INVALID, GAP_FILLED, MISSING = (
    "valid",
    "suspect",
    "invalid",
    "gap_filled",
    "missing",
)


@dataclass(frozen=True)
class QCRules:
    min_value: float | None = None
    max_value: float | None = None
    max_rate_per_hour: float | None = None  # spike: |dx/dt| above this is suspect
    flatline_window: str | None = None  # e.g. "6h"
    flatline_min_std: float = 1e-6
    max_gap_fill: str | None = None  # e.g. "2h"; longer gaps are never filled


def range_check(s: pd.Series, lo: float | None, hi: float | None) -> pd.Series:
    bad = pd.Series(False, index=s.index)
    if lo is not None:
        bad |= s < lo
    if hi is not None:
        bad |= s > hi
    return bad


def spike_check(s: pd.Series, max_rate_per_hour: float) -> pd.Series:
    dt_h = s.index.to_series().diff().dt.total_seconds() / 3600.0
    rate = s.diff().abs() / dt_h
    return (rate > max_rate_per_hour).fillna(False)


def flatline_check(s: pd.Series, window: str, min_std: float) -> pd.Series:
    rolling_std = s.rolling(window, min_periods=3).std()
    return (rolling_std < min_std).fillna(False)


def timestamp_issues(index: pd.DatetimeIndex, now: pd.Timestamp | None = None) -> pd.Series:
    """Duplicate or future timestamps."""
    now = now or pd.Timestamp.now(tz=index.tz)
    s = pd.Series(index.duplicated(keep="first"), index=index)
    return s | pd.Series(index > now, index=index)


def apply_qc(s: pd.Series, rules: QCRules) -> pd.DataFrame:
    """Return a DataFrame with columns value (possibly gap-filled), raw_value, flag."""
    if not isinstance(s.index, pd.DatetimeIndex):
        raise TypeError("series must have a DatetimeIndex")
    s = s.sort_index()
    invalid = range_check(s, rules.min_value, rules.max_value) | timestamp_issues(s.index)
    suspect = pd.Series(False, index=s.index)
    if rules.max_rate_per_hour is not None:
        suspect |= spike_check(s.where(~invalid), rules.max_rate_per_hour)
    if rules.flatline_window is not None:
        suspect |= flatline_check(s.where(~invalid), rules.flatline_window, rules.flatline_min_std)

    value = s.where(~invalid)
    flag = pd.Series(VALID, index=s.index, dtype="object")
    flag[suspect] = SUSPECT
    flag[invalid] = INVALID
    flag[s.isna()] = MISSING

    if rules.max_gap_fill is not None:
        filled = value.interpolate(method="time", limit_area="inside")
        # Only fill runs of missing values whose total duration is short enough.
        missing = value.isna()
        run_id = (missing != missing.shift()).cumsum()
        limit = pd.Timedelta(rules.max_gap_fill)
        idx = s.index.to_series()
        for _, run in idx[missing].groupby(run_id[missing]):
            pos_start = s.index.get_loc(run.index[0])
            pos_end = s.index.get_loc(run.index[-1])
            if pos_start == 0 or pos_end == len(s) - 1:
                continue  # never extrapolate at the edges
            span = s.index[pos_end + 1] - s.index[pos_start - 1]
            if span <= limit:
                value.loc[run.index] = filled.loc[run.index]
                flag.loc[run.index] = GAP_FILLED  # original kept in raw_value
    return pd.DataFrame({"value": value, "raw_value": s, "flag": flag})

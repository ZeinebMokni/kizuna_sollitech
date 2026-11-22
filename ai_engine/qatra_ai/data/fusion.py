"""Combine weather and station data without replacing measurements with estimates."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

from qatra_ai.contracts import DataClass
from qatra_ai.data.station_selection import VariableSelection


@dataclass(frozen=True)
class FusedVariable:
    variable: str
    value: float | None
    unit: str | None
    data_class: DataClass
    source: str
    observed_at: datetime | None
    qc_flag: str | None
    fallback_used: bool
    reason: str


class DataFusionEngine:
    def __init__(self, fallback_observations: Iterable[dict] | None = None):
        self.fallback_observations = list(fallback_observations or [])

    def fuse(
        self,
        variable: str,
        measurement: VariableSelection | None,
        model_value: float | None,
        model_unit: str,
        model_source: str,
        model_class: DataClass = DataClass.INFERRED,
    ) -> FusedVariable:
        if measurement is not None and measurement.value is not None:
            return FusedVariable(
                variable=variable,
                value=measurement.value,
                unit=measurement.unit,
                data_class=DataClass.MEASURED,
                source=f"{measurement.source}:{measurement.station_id}",
                observed_at=measurement.observed_at,
                qc_flag=measurement.qc_flag,
                fallback_used=False,
                reason=measurement.reason,
            )
        if model_value is None:
            return FusedVariable(
                variable, None, model_unit, model_class, model_source, None, "missing",
                True, "missing observation and no usable model estimate",
            )
        return FusedVariable(
            variable, model_value, model_unit, model_class, model_source, None, "model",
            True, "physical observation missing; model estimate used explicitly",
        )

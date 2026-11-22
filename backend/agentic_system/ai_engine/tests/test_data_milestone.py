from datetime import UTC, datetime, timedelta

import pandas as pd
import pytest

from qatra_ai.data.fusion import DataFusionEngine
from qatra_ai.data.ingestion import (
    ImportValidationError,
    import_irrigation_csv,
    import_sensor_csv,
)
from qatra_ai.data.station_selection import VariableSelection, haversine_km, select_variable


def observation(station, variable="air_temperature", value=25.0, flag="valid", age_hours=1):
    timestamp = pd.Timestamp(datetime.now(UTC) - timedelta(hours=age_hours))
    return {
        "timestamp_utc": timestamp,
        "site_id": station,
        "variable": variable,
        "value": value,
        "unit": "degC",
        "source": "dgacta_sidi_bouzid",
        "data_class": "measured",
        "qc_flag": flag,
        "qc_note": "",
        "raw_file_sha256": "a" * 64,
    }


def test_station_selection_rejects_faults_and_uses_nearest_valid_station():
    df = pd.DataFrame([
        observation("sb_crra", value=0.0, flag="invalid"),
        observation("sb_el_ayoun", value=26.0, age_hours=2),
        observation("sb_rayhana", value=27.0, age_hours=1),
    ])
    at = datetime.now(UTC)
    selected = select_variable(df, "air_temperature", 35.60, 9.50, at)
    assert selected.station_id == "sb_el_ayoun"
    assert selected.value == 26.0 and selected.distance_km is not None


def test_station_selection_reports_missing_fresh_valid_data():
    df = pd.DataFrame([observation("sb_crra", flag="suspect", age_hours=200)])
    selected = select_variable(
        df, "air_temperature", 35.60, 9.50, datetime.now(UTC), max_age=timedelta(days=30)
    )
    assert selected.value is None and "no fresh" in selected.reason


def test_haversine_is_finite_and_nonnegative():
    d = haversine_km(35.684, 9.479, 35.552, 9.664)
    assert d > 0


def test_fusion_never_silently_replaces_measurement():
    engine = DataFusionEngine()
    measurement = VariableSelection(
        "air_temperature", "dgacta", "sb_rayhana", 24.0, "degC",
        datetime.now(UTC), "valid", 10.0, "fresh valid reading",
    )
    measured = engine.fuse("air_temperature", measurement, 30.0, "degC", "nasa")
    assert measured.value == 24.0 and not measured.fallback_used

    fallback = engine.fuse("air_temperature", None, 30.0, "degC", "nasa")
    assert fallback.value == 30.0 and fallback.fallback_used
    assert fallback.data_class.value == "inferred"


def test_csv_sensor_import_validation_and_duplicates(tmp_path):
    csv = (
        b"timestamp_utc,zone_id,variable,value,unit\n"
        b"2026-06-01T10:00:00Z,zone-a,soil_moisture,20.5,%\n"
    )
    _, first, duplicates = import_sensor_csv(csv, farm_id="test-farm", root=tmp_path)
    assert len(first) == 1 and duplicates == 0
    _, repeated, duplicates = import_sensor_csv(csv, farm_id="test-farm", root=tmp_path)
    assert len(repeated) == 1 and duplicates == 1

    with pytest.raises(ImportValidationError, match="missing columns"):
        import_sensor_csv(b"zone_id,value\nzone-a,1\n", farm_id="test-farm", root=tmp_path)


def test_irrigation_import_requires_known_zone_and_valid_timestamp(tmp_path):
    with pytest.raises(ImportValidationError, match="unknown zones"):
        import_irrigation_csv(
            b"timestamp_utc,zone_id,volume_m3\n2026-06-01T10:00:00Z,other,12\n",
            farm_id="test-farm",
            known_zones={"zone-a"},
            root=tmp_path,
        )
    _, table, duplicates = import_irrigation_csv(
        b"timestamp_utc,zone_id,volume_m3\n2026-06-01T10:00:00Z,zone-a,12.5\n",
        farm_id="test-farm",
        known_zones={"zone-a"},
        root=tmp_path,
    )
    assert table.iloc[0]["data_class"] == "farmer_reported"
    assert duplicates == 0

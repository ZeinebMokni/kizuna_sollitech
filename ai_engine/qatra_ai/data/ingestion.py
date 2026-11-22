"""Validated CSV imports for irrigation logs and farm sensor measurements."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd

from qatra_ai.contracts import DataClass
from qatra_ai.data.store import Zone, data_root, write_observations


class ImportValidationError(ValueError):
    pass


def _utc(value: str) -> pd.Timestamp:
    try:
        ts = pd.to_datetime(value, utc=True, format="ISO8601")
    except (TypeError, ValueError) as exc:
        raise ImportValidationError(f"invalid timestamp: {value!r}") from exc
    if pd.isna(ts):
        raise ImportValidationError(f"invalid timestamp: {value!r}")
    if ts.tzinfo is None:
        raise ImportValidationError(f"timestamp lacks timezone: {value!r}")
    return ts


def import_sensor_csv(
    content: bytes,
    *,
    farm_id: str,
    root: Path | None = None,
) -> tuple[Path, pd.DataFrame, int]:
    try:
        df = pd.read_csv(
            pd.io.common.BytesIO(content),
            dtype={"site_id": str, "zone_id": str, "variable": str, "unit": str},
        )
    except (pd.errors.ParserError, UnicodeDecodeError) as exc:
        raise ImportValidationError(f"unreadable CSV: {exc}") from exc
    required = {"timestamp_utc", "zone_id", "variable", "value", "unit"}
    missing = required - set(df.columns)
    if missing:
        raise ImportValidationError(f"missing columns: {sorted(missing)}")

    timestamps = [_utc(str(v)) for v in df["timestamp_utc"]]
    try:
        values = pd.to_numeric(df["value"], errors="raise").astype("float64")
    except (TypeError, ValueError) as exc:
        raise ImportValidationError(f"value must be numeric: {exc}") from exc
    if df["zone_id"].isna().any() or df["variable"].isna().any() or df["unit"].isna().any():
        raise ImportValidationError("zone_id, variable and unit are required")

    digest = hashlib.sha256(content).hexdigest()
    out = pd.DataFrame(
        {
            "timestamp_utc": timestamps,
            "site_id": [f"{farm_id}:{z}" for z in df["zone_id"]],
            "variable": df["variable"].str.strip(),
            "value": values,
            "unit": df["unit"].str.strip(),
            "source": [f"sensor_import:{farm_id}" for _ in range(len(df))],
            "data_class": [DataClass.MEASURED.value for _ in range(len(df))],
            "qc_flag": ["valid" for _ in range(len(df))],
            "qc_note": [f"import_sha256={digest}" for _ in range(len(df))],
            "raw_file_sha256": [digest for _ in range(len(df))],
        }
    )
    key = ["timestamp_utc", "site_id", "variable", "source"]
    folder = (root or data_root()) / "sensors" / farm_id
    existing_path = folder / "sensor_measurements.csv"
    existing = pd.DataFrame()
    if existing_path.exists():
        existing = pd.read_csv(existing_path)
        existing["timestamp_utc"] = pd.to_datetime(existing["timestamp_utc"], utc=True)
        existing["value"] = pd.to_numeric(existing["value"], errors="coerce")
    combined = pd.concat([existing, out], ignore_index=True)
    duplicate_count = int(combined.duplicated(subset=key, keep="first").sum())
    combined = combined.drop_duplicates(subset=key, keep="first")
    out = combined.reset_index(drop=True)
    path = write_observations(out, Zone.SENSORS, farm_id, "sensor_measurements", root=root)
    return path, out, duplicate_count


def import_irrigation_csv(
    content: bytes,
    *,
    farm_id: str,
    known_zones: set[str] | None = None,
    root: Path | None = None,
) -> tuple[Path, pd.DataFrame, int]:
    try:
        df = pd.read_csv(pd.io.common.BytesIO(content))
    except (pd.errors.ParserError, UnicodeDecodeError) as exc:
        raise ImportValidationError(f"unreadable CSV: {exc}") from exc
    required = {"timestamp_utc", "zone_id", "volume_m3"}
    missing = required - set(df.columns)
    if missing:
        raise ImportValidationError(f"missing columns: {sorted(missing)}")
    timestamps = [_utc(str(v)) for v in df["timestamp_utc"]]
    try:
        volumes = pd.to_numeric(df["volume_m3"], errors="raise").astype("float64")
    except (TypeError, ValueError) as exc:
        raise ImportValidationError(f"volume_m3 must be numeric: {exc}") from exc
    if (volumes < 0).any():
        raise ImportValidationError("irrigation volumes must be >= 0")
    if known_zones is not None:
        unknown = sorted(set(df["zone_id"].astype(str)) - known_zones)
        if unknown:
            raise ImportValidationError(f"unknown zones: {unknown}")

    digest = hashlib.sha256(content).hexdigest()
    out = pd.DataFrame(
        {
            "timestamp_utc": timestamps,
            "site_id": [f"{farm_id}:{z}" for z in df["zone_id"]],
            "variable": ["irrigation_volume" for _ in range(len(df))],
            "value": volumes,
            "unit": ["m3" for _ in range(len(df))],
            "source": [f"irrigation_log_import:{farm_id}" for _ in range(len(df))],
            "data_class": [DataClass.FARMER_REPORTED.value for _ in range(len(df))],
            "qc_flag": ["valid" for _ in range(len(df))],
            "qc_note": [f"import_sha256={digest}" for _ in range(len(df))],
            "raw_file_sha256": [digest for _ in range(len(df))],
        }
    )
    key = ["timestamp_utc", "site_id", "variable", "source"]
    folder = (root or data_root()) / "sensors" / farm_id
    existing_path = folder / "irrigation_logs.csv"
    existing = pd.DataFrame()
    if existing_path.exists():
        existing = pd.read_csv(existing_path)
        existing["timestamp_utc"] = pd.to_datetime(existing["timestamp_utc"], utc=True)
        existing["value"] = pd.to_numeric(existing["value"], errors="coerce")
    combined = pd.concat([existing, out], ignore_index=True)
    duplicates = int(combined.duplicated(subset=key, keep="first").sum())
    out = combined.drop_duplicates(subset=key, keep="first").reset_index(drop=True)
    path = write_observations(out, Zone.SENSORS, farm_id, "irrigation_logs", root=root)
    return path, out, duplicates

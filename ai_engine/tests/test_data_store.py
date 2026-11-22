"""Data store rules: schema, real/synthetic separation, write-once raw files, manifests.

All tables here are tiny hand-written fixtures to exercise the rules; none is presented as data.
"""

from datetime import UTC, datetime

import pandas as pd
import pytest

from qatra_ai.contracts import DataClass
from qatra_ai.data.store import (
    OBSERVATION_COLUMNS,
    DataStoreError,
    Zone,
    data_root,
    file_meta,
    list_raw,
    read_observations,
    sha256_bytes,
    validate_observations,
    verify_raw,
    write_observations,
    write_raw,
)

SHA = "a" * 64


def table(data_class=DataClass.MEASURED, n=3, sha=SHA, **over):
    df = pd.DataFrame(
        {
            "timestamp_utc": pd.date_range("2026-10-23 10:00", periods=n, freq="h", tz="UTC"),
            "site_id": "site-1",
            "variable": "air_temperature",
            "value": [20.0 + i for i in range(n)],
            "unit": "degC",
            "source": "test_source",
            "data_class": str(data_class),
            "qc_flag": "unchecked",
            "qc_note": "",
            "raw_file_sha256": sha,
        }
    )
    for k, v in over.items():
        df[k] = v
    return df


def raw_kwargs(**over):
    kw = dict(
        source="test_source",
        file_name="station.csv",
        publisher="test publisher",
        url="https://example.org/station.csv",
        licence="test licence",
        data_class=DataClass.MEASURED,
    )
    kw.update(over)
    return kw


# --- separation of real and simulated data ------------------------------------------------------


@pytest.mark.parametrize("zone", [Zone.PROCESSED, Zone.SENSORS, Zone.EXTERNAL])
def test_simulated_rows_rejected_outside_synthetic(zone):
    with pytest.raises(DataStoreError, match="not allowed"):
        validate_observations(table(DataClass.SIMULATED), zone)


@pytest.mark.parametrize("cls", [DataClass.MEASURED, DataClass.OFFICIAL, DataClass.INFERRED])
def test_synthetic_zone_accepts_only_simulated(cls):
    with pytest.raises(DataStoreError, match="not allowed"):
        validate_observations(table(cls), Zone.SYNTHETIC)
    ok = validate_observations(table(DataClass.SIMULATED, sha=None), Zone.SYNTHETIC)
    assert len(ok) == 3


def test_one_simulated_row_poisons_a_real_table():
    df = table()
    df.loc[1, "data_class"] = "simulated"
    with pytest.raises(DataStoreError, match="simulated"):
        validate_observations(df, Zone.PROCESSED)


def test_sensors_zone_rejects_official_statistics():
    with pytest.raises(DataStoreError, match="not allowed"):
        validate_observations(table(DataClass.OFFICIAL), Zone.SENSORS)


def test_simulated_never_written_to_raw(tmp_path):
    with pytest.raises(DataStoreError, match="synthetic"):
        write_raw(b"x", root=tmp_path, **raw_kwargs(data_class=DataClass.SIMULATED))


# --- schema --------------------------------------------------------------------------------------


def test_real_rows_must_reference_raw_file():
    with pytest.raises(DataStoreError, match="SHA-256"):
        validate_observations(table(sha=None), Zone.PROCESSED)
    with pytest.raises(DataStoreError, match="SHA-256"):
        validate_observations(table(sha="not-a-hash"), Zone.PROCESSED)


def test_naive_timestamps_rejected_and_other_zones_converted_to_utc():
    df = table()
    df["timestamp_utc"] = df["timestamp_utc"].dt.tz_localize(None)
    with pytest.raises(DataStoreError, match="timezone-aware"):
        validate_observations(df, Zone.PROCESSED)
    df = table()
    df["timestamp_utc"] = df["timestamp_utc"].dt.tz_convert("Africa/Tunis")
    out = validate_observations(df, Zone.PROCESSED)
    assert str(out["timestamp_utc"].dt.tz) == "UTC"
    assert out["timestamp_utc"].iloc[0] == pd.Timestamp("2026-10-23 10:00", tz="UTC")


def test_missing_extra_and_blank_columns():
    with pytest.raises(DataStoreError, match="missing columns"):
        validate_observations(table().drop(columns="unit"), Zone.PROCESSED)
    with pytest.raises(DataStoreError, match="unexpected columns"):
        validate_observations(table(extra=1), Zone.PROCESSED)
    with pytest.raises(DataStoreError, match="unit must be set"):
        validate_observations(table(unit=" "), Zone.PROCESSED)


def test_qc_flags_and_missing_values():
    with pytest.raises(DataStoreError, match="qc_flag"):
        validate_observations(table(qc_flag="fixed"), Zone.PROCESSED)
    df = table()
    df.loc[0, "value"] = float("nan")
    with pytest.raises(DataStoreError, match="missing"):
        validate_observations(df, Zone.PROCESSED)
    df.loc[0, "qc_flag"] = "missing"
    assert validate_observations(df, Zone.PROCESSED)["value"].isna().sum() == 1


def test_invalid_values_are_kept_not_altered():
    """A physically impossible reading stays as published, flagged invalid."""
    df = table(variable="soil_vwc_10cm", unit="%", qc_flag="invalid", qc_note="below 0 %")
    df["value"] = -2.0
    out = validate_observations(df, Zone.PROCESSED)
    assert (out["value"] == -2.0).all() and (out["qc_flag"] == "invalid").all()
    assert (out["qc_note"] == "below 0 %").all()


def test_duplicate_keys_rejected():
    df = pd.concat([table(), table()])
    with pytest.raises(DataStoreError, match="share the same"):
        validate_observations(df, Zone.PROCESSED)


# --- write / read round trip ---------------------------------------------------------------------


def test_observation_round_trip_and_meta(tmp_path):
    df = table()
    df.loc[2, "value"] = float("nan")
    df.loc[2, "qc_flag"] = "missing"
    path = write_observations(df, Zone.PROCESSED, "test_source", "obs_2026-10", root=tmp_path)
    assert path == tmp_path / "processed" / "test_source" / "obs_2026-10.csv"
    assert path.read_text().splitlines()[0] == ",".join(OBSERVATION_COLUMNS)
    assert "2026-10-23T10:00:00Z" in path.read_text()
    back = read_observations(path, Zone.PROCESSED)
    pd.testing.assert_frame_equal(back, validate_observations(df, Zone.PROCESSED))
    meta = file_meta(path)
    assert meta["rows"] == 3 and meta["data_classes"] == ["measured"]
    assert meta["qc_counts"] == {"unchecked": 2, "missing": 1}
    assert meta["raw_files_sha256"] == [SHA]
    with pytest.raises(DataStoreError, match="not allowed"):
        read_observations(path, Zone.SYNTHETIC)  # a real file can't be re-read as synthetic


def test_synthetic_round_trip_without_hash(tmp_path):
    path = write_observations(
        table(DataClass.SIMULATED, sha=None), Zone.SYNTHETIC, "bench", "leak", root=tmp_path
    )
    assert read_observations(path, Zone.SYNTHETIC)["raw_file_sha256"].isna().all()


def test_unsafe_names_rejected(tmp_path):
    with pytest.raises(DataStoreError, match="unsafe"):
        write_observations(table(), Zone.PROCESSED, "../etc", "x", root=tmp_path)
    with pytest.raises(DataStoreError, match="unsafe"):
        write_raw(b"x", root=tmp_path, **raw_kwargs(file_name="a/b.csv"))


# --- raw files and manifests ---------------------------------------------------------------------


def test_raw_is_content_addressed_idempotent_and_versioned(tmp_path):
    t = datetime(2026, 1, 2, 6, 0, tzinfo=UTC)
    p1, m1, created1 = write_raw(b"snapshot-1", root=tmp_path, retrieved_at_utc=t, **raw_kwargs())
    assert created1 and p1.name == f"{sha256_bytes(b'snapshot-1')[:12]}_station.csv"
    assert p1.read_bytes() == b"snapshot-1"
    assert m1.sha256 == sha256_bytes(b"snapshot-1") and m1.size_bytes == 10
    assert m1.retrieved_at_utc == t and m1.data_class == DataClass.MEASURED

    p2, m2, created2 = write_raw(b"snapshot-1", root=tmp_path, **raw_kwargs())
    assert not created2 and p2 == p1 and m2 == m1  # same bytes: nothing rewritten

    p3, _, created3 = write_raw(
        b"snapshot-2", root=tmp_path, extra={"resource_id": "r1"}, **raw_kwargs()
    )
    assert created3 and p3 != p1 and p1.read_bytes() == b"snapshot-1"  # new version kept beside
    assert verify_raw(p1) == m1
    listed = list_raw("test_source", root=tmp_path)
    assert [p for p, _ in listed] == [p1, p3]  # oldest retrieval first
    assert listed[1][1].extra == {"resource_id": "r1"}


def test_tampered_raw_file_detected(tmp_path):
    path, _, _ = write_raw(b"original", root=tmp_path, **raw_kwargs())
    path.write_bytes(b"edited")
    with pytest.raises(DataStoreError, match="no longer matches"):
        verify_raw(path)
    with pytest.raises(DataStoreError, match="write-once"):
        write_raw(b"original", root=tmp_path, **raw_kwargs())


def test_data_root_env_override(tmp_path, monkeypatch):
    monkeypatch.setenv("QATRA_DATA_DIR", str(tmp_path))
    assert data_root() == tmp_path
    monkeypatch.delenv("QATRA_DATA_DIR")
    assert data_root().name == "data" and (data_root().parent / "ai_engine").is_dir()

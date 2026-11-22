"""DGACTA station archiver: parsing, QC, snapshot merging, archiving (mock HTTP, no network).

The CSVs below are small hand-written TEST INPUTS in the publisher's format, written to
exercise each rule (e.g. a humidity sensor stuck at 100 %). They are not station data.
"""

import json

import httpx
import pandas as pd
import pytest

from qatra_ai.data.sources import dgacta
from qatra_ai.data.sources.dgacta import (
    StationParseError,
    apply_station_qc,
    archive,
    merge_snapshots,
    node_of,
    parse_station_csv,
)
from qatra_ai.data.store import Zone, list_raw, read_observations, verify_raw

SHA1, SHA2 = "1" * 64, "2" * 64
HEADER = "﻿Date,nom_ar,nom_fr,unite,valeur\n"


def csv(rows):
    return (HEADER + "\n".join(",".join(map(str, r)) for r in rows) + "\n").encode("utf-8")


def env_rows(hours=range(0, 24, 2), rh=100.0, pressure=0.0):
    rows = []
    for h in hours:
        t = f"2026-10-23 {h:02d}:00:00"
        sun = max(0.0, 600 - 80 * abs(h - 12))
        rows += [
            (t, "x", "Température", "°c", 15.0 + h / 2),
            (t, "x", "Humidité relative", "%", rh),
            (t, "x", "Point de Rosée", "°c", 15.0 + h / 2),
            (t, "x", "Pression atmosphérique", "hPa", pressure),
            (t, "x", "Rayonnement solaire", "W/m²", sun),
            (t, "x", "Évapotranspiration Horaire", "mm/h", 0.0),
            (t, "x", "Évapotranspiration journalière", "mm/j", 1.5),
        ]
    return rows


def parse(rows, node="environment", depth=None, sha=SHA1):
    return parse_station_csv(csv(rows), station="sb_t", node=node, depth=depth, raw_sha256=sha)


# --- parsing -------------------------------------------------------------------------------------


def test_node_of_catalogue_names():
    assert node_of("Capteur d'humidité du sol à 20 cm de la station climatique") == ("soil", 20)
    assert node_of("Capteur de pluviométrie dans la station climatique") == ("rain", None)
    assert node_of("Capteur d'environnement de la station climatique") == ("environment", None)


def test_local_time_converted_to_utc_and_units_standardised():
    df = parse([("2026-07-01 12:00:00", "x", "Température", "°c", 30.5)])
    row = df.iloc[0]
    assert row["timestamp_utc"] == pd.Timestamp("2026-07-01 11:00", tz="UTC")  # UTC+1
    assert (row["variable"], row["unit"], row["value"]) == ("air_temperature", "degC", 30.5)
    assert row["data_class"] == "measured" and row["qc_flag"] == "unchecked"
    assert row["raw_file_sha256"] == SHA1


def test_soil_node_variables_carry_depth():
    rows = [
        ("2026-06-24 06:00:00", "x", "Température", "°c", 30.5),
        ("2026-06-24 06:00:00", "x", "Contenu volumétrique d'eau", "%", -2.0),
        ("2026-06-24 06:00:00", "x", "L'humidité du sol", "mV", 324.8),
    ]
    df = parse(rows, node="soil", depth=10)
    assert set(df["variable"]) == {
        "soil_temperature_10cm",
        "soil_vwc_10cm",
        "soil_moisture_signal_10cm",
    }


def test_wrong_unit_label_kept_and_flagged():
    df = parse([("2026-06-13 09:00:00", "x", "Pression atmosphérique", "mm/j", 988.4)])
    row = df.iloc[0]
    assert row["value"] == 988.4 and row["unit"] == "mm/day"  # as published, not corrected
    assert row["qc_flag"] == "suspect" and "unexpected" in row["qc_note"]


def test_non_numeric_and_unknown_variables_kept():
    df = parse(
        [
            ("2026-06-13 09:00:00", "x", "Vitesse du vent", "m/s", "n/a"),
            ("2026-06-13 09:00:00", "x", "Niveau batterie", "V", 12.6),
        ]
    )
    wind = df[df["variable"] == "wind_speed"].iloc[0]
    assert pd.isna(wind["value"]) and wind["qc_flag"] == "missing"
    other = df[df["variable"].str.startswith("unmapped_")].iloc[0]
    assert other["variable"] == "unmapped_niveau_batterie" and other["value"] == 12.6


def test_bad_files_rejected():
    with pytest.raises(StationParseError, match="expected columns"):
        parse_station_csv(b"a,b\n1,2\n", station="s", node="rain", depth=None, raw_sha256=SHA1)
    with pytest.raises(StationParseError, match="unreadable Date"):
        parse([("23/10/2026 10:00", "x", "Température", "°c", 20)])


# --- quality control -----------------------------------------------------------------------------


def test_qc_flags_failed_sensors_without_changing_values():
    raw = parse(env_rows())
    qc = apply_station_qc(raw)
    by = {v: g for v, g in qc.groupby("variable")}
    # values untouched
    merged = raw.merge(qc, on=["timestamp_utc", "variable"], suffixes=("_raw", "_qc"))
    assert (merged["value_raw"] == merged["value_qc"]).all()
    assert (by["air_pressure"]["qc_flag"] == "invalid").all()  # 0 hPa
    assert (by["relative_humidity"]["qc_flag"] == "suspect").all()  # stuck at 100 %
    assert by["relative_humidity"]["qc_note"].str.contains("stuck").all()
    assert (by["solar_radiation"]["qc_flag"] == "valid").all()  # zero at night is normal
    assert by["dew_point_temperature"]["qc_note"].str.contains("humidity flagged").all()
    et0 = by["et0_daily_station"]
    assert (et0["qc_flag"] == "suspect").all()
    assert et0["qc_note"].str.contains("relative_humidity, air_pressure").all()
    noon = by["et0_hourly_station"].set_index("timestamp_utc")["qc_note"]
    assert "zero ET0" in noon[pd.Timestamp("2026-10-23 11:00", tz="UTC")]
    assert (by["air_temperature"]["qc_flag"] == "valid").all()  # varying, in range


def test_healthy_humidity_passes():
    rows = [r for r in env_rows(pressure=965.0) if r[2] != "Humidité relative"]
    rows += [
        (f"2026-10-23 {h:02d}:00:00", "x", "Humidité relative", "%", 40 + h)
        for h in range(0, 24, 2)
    ]  # noqa: E501
    by = {v: g for v, g in apply_station_qc(parse(rows)).groupby("variable")}
    assert (by["relative_humidity"]["qc_flag"] == "valid").all()
    assert (by["air_pressure"]["qc_flag"] == "suspect").all()  # constant 965 for 24 h
    assert (by["et0_daily_station"]["qc_note"].str.contains("air_pressure")).all()


def test_impossible_soil_moisture_invalid():
    rows = [
        (f"2026-06-24 {h:02d}:00:00", "x", "Contenu volumétrique d'eau", "%", -2.0 + h / 100)
        for h in range(6)
    ]  # noqa: E501
    qc = apply_station_qc(parse(rows, node="soil", depth=10))
    assert (qc["qc_flag"] == "invalid").all() and qc["qc_note"].str.contains("below").all()
    assert qc["value"].iloc[0] == -2.0


def test_short_constant_run_not_flagged_as_stuck():
    rows = [(f"2026-10-23 {h:02d}:00:00", "x", "Vitesse du vent", "m/s", 2.0) for h in (0, 1, 2)]
    qc = apply_station_qc(parse(rows))
    assert (qc["qc_flag"] == "valid").all()


# --- merging snapshots ---------------------------------------------------------------------------


def test_overlapping_snapshots_keep_first_source_and_flag_revisions():
    t = "2026-10-23 10:00:00"
    a = parse(
        [(t, "x", "Température", "°c", 20.0), (t, "x", "Vitesse du vent", "m/s", 2.0)], sha=SHA1
    )  # noqa: E501
    b = parse(
        [
            (t, "x", "Température", "°c", 20.0),
            (t, "x", "Vitesse du vent", "m/s", 2.5),
            ("2026-10-23 12:00:00", "x", "Température", "°c", 22.0),
        ],
        sha=SHA2,
    )
    m = merge_snapshots([a, b]).set_index("variable")
    assert len(m) == 3
    temp = merge_snapshots([a, b])
    first_t = temp[(temp.variable == "air_temperature") & (temp.value == 20.0)].iloc[0]
    assert first_t["raw_file_sha256"] == SHA1  # unchanged reading credited to first snapshot
    wind = m.loc["wind_speed"]
    assert wind["value"] == 2.5 and wind["raw_file_sha256"] == SHA2
    assert wind["qc_flag"] == "suspect" and "revised by publisher" in wind["qc_note"]


# --- archive (mock catalogue) --------------------------------------------------------------------


def catalogue(files, fail=()):
    pkg = {
        "license_title": "Licence Nationale de Données Publiques Ouvertes",
        "resources": [
            {
                "id": f"{name}-0000-0000",
                "name": label,
                "format": "CSV",
                "url": f"https://catalog.agridata.tn/files/{name}.csv",
                "last_modified": "2026-11-22T00:01:04",
            }
            for name, (label, _) in files.items()
        ],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("package_show"):
            return httpx.Response(200, json={"success": True, "result": pkg})
        name = request.url.path.rsplit("/", 1)[-1].removesuffix(".csv")
        if name in fail:
            return httpx.Response(500)
        return httpx.Response(200, content=files[name][1], headers={"content-type": "text/csv"})

    return httpx.Client(transport=httpx.MockTransport(handler))


ENV = "Capteur d'environnement de la station climatique"
SOIL10 = "Capteur d'humidité du sol à 10 cm de la station climatique"


def test_archive_stores_raw_dedupes_and_builds_processed(tmp_path):
    soil = csv([("2026-10-23 10:00:00", "x", "Contenu volumétrique d'eau", "%", 5.4)])
    files = {"envaaaa1": (ENV, csv(env_rows())), "soilbbb2": (SOIL10, soil)}
    run = archive(["sb_crra"], root=tmp_path, client=catalogue(files))[0]
    assert (run.files_seen, run.files_new, run.errors) == (2, 2, [])
    raws = list_raw(dgacta.SOURCE, tmp_path)
    assert len(raws) == 2
    for path, manifest in raws:
        assert verify_raw(path) == manifest and manifest.data_class == "measured"
        assert manifest.extra["station"] == "sb_crra" and manifest.licence.startswith("Licence")
    assert {m.extra["node"] for _, m in raws} == {"environment", "soil"}

    table = read_observations(
        tmp_path / "processed" / dgacta.SOURCE / "sb_crra.csv", Zone.PROCESSED
    )
    assert run.processed_rows == len(table) == 12 * 7 + 1
    assert "soil_vwc_10cm" in set(table["variable"])
    assert set(table["raw_file_sha256"]) == {m.sha256 for _, m in raws}

    again = archive(["sb_crra"], root=tmp_path, client=catalogue(files))[0]
    assert again.files_new == 0 and len(list_raw(dgacta.SOURCE, tmp_path)) == 2  # re-upload
    log = (tmp_path / "raw" / dgacta.SOURCE / "runs.jsonl").read_text("utf-8").splitlines()
    assert len(log) == 2 and json.loads(log[1])["files_new"] == 0


def test_archive_reports_download_failures(tmp_path):
    files = {"envaaaa1": (ENV, csv(env_rows())), "soilbbb2": (SOIL10, b"")}
    run = archive(["sb_crra"], root=tmp_path, client=catalogue(files, fail={"soilbbb2"}))[0]
    assert run.files_new == 1 and any("download failed" in e for e in run.errors)
    assert dgacta.main is not None


def test_soil_values_need_three_days_unchanged_before_stuck():
    def rows(hours):
        return [
            (str(pd.Timestamp("2026-06-01") + pd.Timedelta(hours=h)), "x",
             "Contenu volumétrique d'eau", "%", 6.6)
            for h in hours
        ]  # fmt: skip

    day = apply_station_qc(parse(rows(range(0, 24, 2)), node="soil", depth=20))
    assert (day["qc_flag"] == "valid").all()  # one steady day in dry soil is normal
    week = apply_station_qc(parse(rows(range(0, 96, 2)), node="soil", depth=20))
    assert (week["qc_flag"] == "suspect").all() and week["qc_note"].str.contains("72h").all()


def test_night_et0_flagged():
    t = "2026-06-13 02:00:00"
    rows = [
        (t, "x", "Rayonnement solaire", "W/m²", 0.0),
        (t, "x", "Évapotranspiration Horaire", "mm/h", 1.0),
    ]
    qc = apply_station_qc(parse(rows)).set_index("variable")
    assert qc.loc["et0_hourly_station", "qc_flag"] == "suspect"
    assert "no sunlight" in qc.loc["et0_hourly_station", "qc_note"]

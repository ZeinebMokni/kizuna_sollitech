"""DGACTA agro-weather stations, Sidi Bouzid (Tunisia), from the open-data catalogue
catalog.agridata.tn (CKAN). Licence: Licence Nationale de Données Publiques Ouvertes.

What the catalogue publishes (inspected 2026-11-22):
- one dataset per station; one CSV resource per sensor node: the environment sensor, soil
  probes at 10/20/30 cm and a rain gauge. Resource ids change when the publisher re-uploads,
  so resources are discovered through `package_show` on every run, never hard-coded;
- each CSV is a short rolling window (days to weeks), long format:
  `Date, nom_ar, nom_fr, unite, valeur`, with `Date` as `YYYY-MM-DD HH:MM:SS`;
- the files can be re-uploaded with identical content (same bytes, new timestamp).

So history only exists if QATRA keeps every snapshot: `archive()` stores each file unchanged in
raw/ (content-addressed, so identical re-uploads are not duplicated), then rebuilds
processed/dgacta_sidi_bouzid/<station>.csv from ALL stored snapshots.

Timestamps: the files carry no time zone. They are read as Tunisian local time (Africa/Tunis,
UTC+1, no DST since 2009), because the solar-radiation profile of the CRRA station centres on
about 12:10 clock time, which is local solar noon in UTC+1 at 9.3 E, about 11:10 UTC. Whether a
time stamp labels the start or end of its averaging period is not documented (+/- 1 h).

QC flags values; it never changes or removes them (see qatra_ai.data.store).
"""

from __future__ import annotations

import argparse
import io
import json
import re
import ssl
import unicodedata
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import httpx
import numpy as np
import pandas as pd

from qatra_ai.contracts import DataClass
from qatra_ai.data.qc import INVALID, MISSING, SUSPECT, VALID
from qatra_ai.data.store import (
    OBSERVATION_COLUMNS,
    UNCHECKED,
    Zone,
    data_root,
    list_raw,
    write_observations,
    write_raw,
)

SOURCE = "dgacta_sidi_bouzid"
CKAN_PACKAGE_SHOW = "https://catalog.agridata.tn/api/3/action/package_show"
PUBLISHER = "DGACTA (Ministère de l'Agriculture, Tunisie), via catalog.agridata.tn"
LICENCE = "Licence Nationale de Données Publiques Ouvertes (Tunisie)"
STATION_TZ = "Africa/Tunis"
USER_AGENT = "qatra-ai/0.1 (agricultural research prototype)"

STATIONS: dict[str, str] = {
    "sb_crra": "station-climatique-sidi-bouzid-crra-dgacta",
    "sb_el_ayoun": "station-climatique-sidi-bouzid-el-ayoun-dgacta",
    "sb_rayhana": "station-climatique-sidi-bouzid-rayhana-dgacta",
}

# Published unit label -> standard unit
UNIT_ALIASES = {
    "°c": "degC",
    "%": "%",
    "hpa": "hPa",
    "w/m²": "W/m2",
    "w/m2": "W/m2",
    "deg": "deg",
    "m/s": "m/s",
    "mm/h": "mm/h",
    "mm/j": "mm/day",
    "mm": "mm",
    "mv": "mV",
}


@dataclass(frozen=True)
class VarSpec:
    name: str  # may contain {depth}
    unit: str
    lo: float | None = None
    hi: float | None = None
    # A value that does not change at all for this many hours is suspect (stuck sensor). None
    # where long constant runs are normal (rain at 0, radiation at 0 overnight, daily totals).
    # Soil variables change slowly, so they get a longer window.
    flatline_h: float | None = 12


# Keyed by the accent-free, lower-case `nom_fr`. Ranges are physical/plausibility limits for
# central Tunisia; outside them a value is flagged invalid.
VARIABLES: dict[str, VarSpec] = {
    "temperature": VarSpec("air_temperature", "degC", -15, 55),
    "humidite relative": VarSpec("relative_humidity", "%", 1, 100),
    "point de rosee": VarSpec("dew_point_temperature", "degC", -40, 40),
    "pression atmospherique": VarSpec("air_pressure", "hPa", 850, 1060),
    "rayonnement solaire": VarSpec("solar_radiation", "W/m2", 0, 1400, flatline_h=None),
    "vitesse du vent": VarSpec("wind_speed", "m/s", 0, 60),
    "direction du vent": VarSpec("wind_direction", "deg", 0, 360),
    "evapotranspiration horaire": VarSpec("et0_hourly_station", "mm/h", 0, 2, flatline_h=None),
    "evapotranspiration journaliere": VarSpec(
        "et0_daily_station", "mm/day", 0, 15, flatline_h=None
    ),
    "contenu volumetrique d'eau": VarSpec("soil_vwc_{depth}cm", "%", 0, 60, flatline_h=72),
    "l'humidite du sol": VarSpec("soil_moisture_signal_{depth}cm", "mV", 0, 5000, flatline_h=72),
    "pluie quotidienne": VarSpec("precipitation_daily", "mm", 0, 300, flatline_h=None),
    "pluie totale": VarSpec("precipitation_counter", "mm", 0, None, flatline_h=None),
    "intensite de pluie": VarSpec("precipitation_intensity", "mm/h", 0, 300, flatline_h=None),
}
SOIL_TEMPERATURE = VarSpec("soil_temperature_{depth}cm", "degC", -10, 70, flatline_h=72)

ET0_INPUTS = (
    "relative_humidity",
    "air_pressure",
    "air_temperature",
    "solar_radiation",
    "wind_speed",
)
FLATLINE_MIN_READINGS = 4
NIGHT_ET0_MAX_MM_H = 0.2  # hourly reference ET0 above this with no sunlight is implausible

_SEVERITY = {UNCHECKED: 0, VALID: 1, SUSPECT: 2, INVALID: 3, MISSING: 4}


class StationParseError(ValueError):
    pass


def _key(text: str) -> str:
    t = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", t.replace("’", "'")).strip().lower()


def node_of(resource_name: str) -> tuple[str, int | None]:
    """Sensor node kind and depth from the catalogue resource name."""
    k = _key(resource_name)
    if "sol" in k:
        m = re.search(r"(\d+)\s*cm", k)
        return "soil", int(m.group(1)) if m else None
    if "pluvio" in k:
        return "rain", None
    if "environnement" in k:
        return "environment", None
    return "other", None


# --- Parsing -------------------------------------------------------------------------------------


def parse_station_csv(
    content: bytes, *, station: str, node: str, depth: int | None, raw_sha256: str
) -> pd.DataFrame:
    """One published CSV -> rows in the observation schema, qc_flag 'unchecked'.

    Values are kept exactly as published. Unknown variables are kept as `unmapped_<name>`.
    """
    try:
        df = pd.read_csv(io.BytesIO(content), encoding="utf-8-sig", dtype=str)
    except (pd.errors.ParserError, UnicodeDecodeError) as exc:
        raise StationParseError(f"unreadable CSV: {exc}") from exc
    need = {"Date", "nom_fr", "unite", "valeur"}
    if not need <= set(df.columns):
        raise StationParseError(f"expected columns {sorted(need)}, got {list(df.columns)}")

    local = pd.to_datetime(df["Date"].str.strip(), format="%Y-%m-%d %H:%M:%S", errors="coerce")
    if local.isna().any():
        raise StationParseError(f"{int(local.isna().sum())} rows with an unreadable Date")
    ts = local.dt.tz_localize(STATION_TZ).dt.tz_convert("UTC")

    names, units, flags, notes = [], [], [], []
    for nom, unite in zip(df["nom_fr"], df["unite"], strict=True):
        key = _key(nom)
        spec = VARIABLES.get(key)
        if key == "temperature" and node == "soil":
            spec = SOIL_TEMPERATURE
        raw_unit = unicodedata.normalize("NFC", str(unite)).strip()
        published = UNIT_ALIASES.get(raw_unit.lower(), raw_unit)
        if spec is None:
            names.append("unmapped_" + re.sub(r"[^a-z0-9]+", "_", key).strip("_"))
            units.append(published or "unknown")
            flags.append(UNCHECKED)
            notes.append(f"variable '{nom}' not in QATRA's mapping")
            continue
        name = spec.name.format(depth=depth if depth is not None else "unknown")
        names.append(name)
        units.append(published)
        if published != spec.unit:
            flags.append(SUSPECT)
            notes.append(f"published unit '{unite}' unexpected for {name} (expected {spec.unit})")
        else:
            flags.append(UNCHECKED)
            notes.append("")

    value = pd.to_numeric(df["valeur"].str.replace(",", ".", regex=False), errors="coerce")
    out = pd.DataFrame(
        {
            "timestamp_utc": ts,
            "site_id": station,
            "variable": names,
            "value": value.astype("float64"),
            "unit": units,
            "source": SOURCE,
            "data_class": DataClass.MEASURED.value,
            "qc_flag": flags,
            "qc_note": notes,
            "raw_file_sha256": raw_sha256,
        }
    )
    nonnum = out["value"].isna()
    out.loc[nonnum, "qc_flag"] = MISSING
    out.loc[nonnum, "qc_note"] = [f"non-numeric value '{v}'" for v in df.loc[nonnum, "valeur"]]

    key_cols = ["timestamp_utc", "variable"]
    out = out.drop_duplicates(subset=[*key_cols, "value"], keep="first")
    clash = out.duplicated(subset=key_cols, keep=False)
    if clash.any():
        out.loc[clash, "qc_flag"] = SUSPECT
        out.loc[clash, "qc_note"] = "several different values for this time in one file"
        out = out.drop_duplicates(subset=key_cols, keep="first")
    return out[OBSERVATION_COLUMNS].reset_index(drop=True)


def merge_snapshots(frames: list[pd.DataFrame]) -> pd.DataFrame:
    """Combine parsed snapshots, oldest first. A reading seen in several snapshots keeps the hash
    of the first snapshot that published it; if a later snapshot published a different value,
    the latest value is kept and flagged as revised."""
    if not frames:
        return pd.DataFrame(columns=OBSERVATION_COLUMNS)
    key = ["timestamp_utc", "site_id", "variable", "source"]
    allrows = pd.concat(frames, ignore_index=True)
    first = allrows.drop_duplicates(subset=key, keep="first").set_index(key)
    last = allrows.drop_duplicates(subset=key, keep="last").set_index(key)
    first = first.loc[last.index]
    a, b = first["value"], last["value"]
    same = (a == b) | (a.isna() & b.isna())
    out = last.copy()
    out.loc[same, "raw_file_sha256"] = first.loc[same, "raw_file_sha256"]
    out.loc[same, ["qc_flag", "qc_note"]] = first.loc[same, ["qc_flag", "qc_note"]].values
    revised = ~same
    if revised.any():
        out.loc[revised, "qc_flag"] = SUSPECT
        out.loc[revised, "qc_note"] = [
            f"revised by publisher (earlier snapshot {s[:12]} had {v})"
            for s, v in zip(
                first.loc[revised, "raw_file_sha256"], first.loc[revised, "value"], strict=True
            )
        ]
    return out.reset_index()[OBSERVATION_COLUMNS]


# --- Quality control -----------------------------------------------------------------------------


def _flag(df: pd.DataFrame, mask: pd.Series, flag: str, note: str) -> None:
    """Raise rows in `mask` to at least `flag` and append `note`. Never touches `value`."""
    mask = mask.fillna(False) & (df["qc_flag"] != MISSING)
    if not mask.any():
        return
    df.loc[mask & (df["qc_flag"].map(_SEVERITY) < _SEVERITY[flag]), "qc_flag"] = flag
    old = df.loc[mask, "qc_note"]
    df.loc[mask, "qc_note"] = np.where(old == "", note, old + "; " + note)


def _spec_for(variable: str) -> VarSpec | None:
    for spec in [*VARIABLES.values(), SOIL_TEMPERATURE]:
        pattern = "^" + re.escape(spec.name).replace(r"\{depth\}", r"(\d+|unknown)") + "$"
        if re.match(pattern, variable):
            return spec
    return None


def apply_station_qc(obs: pd.DataFrame) -> pd.DataFrame:
    """Range, stuck-sensor and cross-variable checks. Returns a copy with qc_flag/qc_note set;
    rows that pass every check become 'valid'."""
    df = obs.sort_values(["site_id", "variable", "timestamp_utc"]).reset_index(drop=True)
    df["qc_note"] = df["qc_note"].fillna("")

    for variable, idx in df.groupby("variable").groups.items():
        spec = _spec_for(str(variable))
        if spec is None:
            continue
        if spec.lo is not None:
            _flag(df, df.index.isin(idx) & (df["value"] < spec.lo), INVALID,
                  f"below plausible minimum {spec.lo:g} {spec.unit}")  # fmt: skip
        if spec.hi is not None:
            _flag(df, df.index.isin(idx) & (df["value"] > spec.hi), INVALID,
                  f"above plausible maximum {spec.hi:g} {spec.unit}")  # fmt: skip
        if spec.flatline_h is not None:
            window = f"{spec.flatline_h:g}h"
            for _, g in df.loc[idx].groupby("site_id"):
                s = pd.Series(g["value"].values, index=pd.DatetimeIndex(g["timestamp_utc"]))
                roll = s.rolling(window, min_periods=FLATLINE_MIN_READINGS)
                stuck = (roll.max() - roll.min()).eq(0) & roll.count().ge(FLATLINE_MIN_READINGS)
                secs = pd.Series((s.index - s.index[0]).total_seconds(), index=s.index)
                span_h = (secs - secs.rolling(window).min()) / 3600.0
                stuck &= span_h.ge(spec.flatline_h / 2)  # readings must span half the window
                if stuck.any():
                    # mark the whole constant run, not only the window ends
                    run = (s != s.shift()).cumsum()
                    stuck_runs = set(run[stuck.values])
                    m = pd.Series(run.isin(stuck_runs).values, index=g.index)
                    _flag(df, pd.Series(df.index.isin(m[m].index), index=df.index), SUSPECT,
                          f"unchanged over {window} (stuck sensor?)")  # fmt: skip

    # cross-variable checks, per station and time
    wide = df.pivot_table(
        index=["site_id", "timestamp_utc"], columns="variable", values="value", aggfunc="first"
    )
    flags = df.pivot_table(
        index=["site_id", "timestamp_utc"], columns="variable", values="qc_flag", aggfunc="first"
    )
    at = pd.MultiIndex.from_frame(df[["site_id", "timestamp_utc"]])

    def at_rows(cond: pd.Series, variable: str) -> pd.Series:
        hit = cond.reindex(at).fillna(False).to_numpy(dtype=bool)
        return pd.Series(hit & (df["variable"] == variable).to_numpy(), index=df.index)

    if {"dew_point_temperature", "air_temperature"} <= set(wide.columns):
        over = wide["dew_point_temperature"] > wide["air_temperature"] + 0.5
        _flag(
            df, at_rows(over, "dew_point_temperature"), INVALID, "dew point above air temperature"
        )
    if "relative_humidity" in flags.columns and "dew_point_temperature" in wide.columns:
        bad_rh = flags["relative_humidity"].isin([SUSPECT, INVALID])
        _flag(df, at_rows(bad_rh, "dew_point_temperature"), SUSPECT,
              "humidity flagged at this time; dew point is derived from it")  # fmt: skip
    if {"et0_hourly_station", "solar_radiation"} <= set(wide.columns):
        zero_sun = (wide["et0_hourly_station"] == 0) & (wide["solar_radiation"] >= 200)
        _flag(df, at_rows(zero_sun, "et0_hourly_station"), SUSPECT,
              "zero ET0 with solar radiation >= 200 W/m2")  # fmt: skip
        night = (wide["et0_hourly_station"] > NIGHT_ET0_MAX_MM_H) & (wide["solar_radiation"] == 0)
        _flag(df, at_rows(night, "et0_hourly_station"), SUSPECT,
              f"hourly ET0 above {NIGHT_ET0_MAX_MM_H} mm/h with no sunlight")  # fmt: skip
    present = [c for c in ET0_INPUTS if c in flags.columns]
    if present:
        bad_inputs = flags[present].isin([SUSPECT, INVALID])
        names = bad_inputs.apply(lambda r: ", ".join(c for c in present if r[c]), axis=1)
        any_bad = names != ""
        for et0 in ("et0_hourly_station", "et0_daily_station"):
            if et0 in wide.columns:
                for label in names[any_bad].unique():
                    cond = names == label
                    _flag(df, at_rows(cond, et0), SUSPECT,
                          f"station ET0 inputs flagged at this time: {label}")  # fmt: skip

    df.loc[df["qc_flag"] == UNCHECKED, "qc_flag"] = VALID
    return df[OBSERVATION_COLUMNS]


# --- Download and archive ------------------------------------------------------------------------


def make_client(timeout_s: float = 120.0) -> httpx.Client:
    """HTTPS client using the operating system's trust store (the catalogue's certificate chain
    is issued by TunTrust, which certifi does not carry). Certificate verification stays ON."""
    import truststore

    ctx = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    return httpx.Client(
        verify=ctx, timeout=timeout_s, follow_redirects=True, headers={"User-Agent": USER_AGENT}
    )


@dataclass
class StationRun:
    station: str
    dataset: str
    files_seen: int = 0
    files_new: int = 0
    errors: list[str] = field(default_factory=list)
    processed_rows: int = 0
    processed_path: str | None = None
    time_min_utc: str | None = None
    time_max_utc: str | None = None
    qc_counts: dict[str, int] = field(default_factory=dict)


def fetch_station(client: httpx.Client, station: str, root: Path | None = None) -> StationRun:
    dataset = STATIONS[station]
    run = StationRun(station=station, dataset=dataset)
    try:
        r = client.get(CKAN_PACKAGE_SHOW, params={"id": dataset})
        r.raise_for_status()
        pkg = r.json()["result"]
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        run.errors.append(f"catalogue lookup failed: {type(exc).__name__}: {str(exc)[:200]}")
        return run
    for res in pkg.get("resources", []):
        if (res.get("format") or "").upper() != "CSV":
            continue
        node, depth = node_of(res.get("name") or "")
        run.files_seen += 1
        try:
            resp = client.get(res["url"])
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            run.errors.append(f"{res['id'][:8]} download failed: {type(exc).__name__}: {exc}"[:240])
            continue
        tag = f"{node}{depth}" if depth is not None else node
        _, _, created = write_raw(
            resp.content,
            source=SOURCE,
            file_name=f"{station}_{tag}_{res['id'][:8]}.csv",
            publisher=PUBLISHER,
            url=res["url"],
            licence=pkg.get("license_title") or LICENCE,
            data_class=DataClass.MEASURED,
            content_type=resp.headers.get("content-type"),
            notes="Time stamps are local time (Africa/Tunis); see qatra_ai.data.sources.dgacta",
            extra={
                "station": station,
                "dataset": dataset,
                "resource_id": res["id"],
                "resource_name": res.get("name") or "",
                "resource_last_modified": res.get("last_modified") or "",
                "http_last_modified": resp.headers.get("last-modified", ""),
                "node": node,
                "depth_cm": "" if depth is None else str(depth),
            },
            root=root,
        )
        run.files_new += int(created)
    return run


def rebuild_processed(station: str, root: Path | None = None) -> tuple[pd.DataFrame, list[str]]:
    """Parse every stored snapshot of a station, merge, QC. Returns (table, parse errors)."""
    frames, errors = [], []
    for path, manifest in list_raw(SOURCE, root):
        if manifest.extra.get("station") != station:
            continue
        depth = manifest.extra.get("depth_cm") or None
        try:
            frames.append(
                parse_station_csv(
                    path.read_bytes(),
                    station=station,
                    node=manifest.extra.get("node", "other"),
                    depth=int(depth) if depth else None,
                    raw_sha256=manifest.sha256,
                )
            )
        except StationParseError as exc:
            errors.append(f"{path.name}: {exc}")
    merged = merge_snapshots(frames)
    return (apply_station_qc(merged) if len(merged) else merged), errors


def archive(
    stations: list[str] | None = None, root: Path | None = None, client: httpx.Client | None = None
) -> list[StationRun]:
    """Download the current snapshot of each station, then rebuild its processed table."""
    own = client is None
    client = client or make_client()
    runs = []
    try:
        for station in stations or list(STATIONS):
            run = fetch_station(client, station, root)
            table, errors = rebuild_processed(station, root)
            run.errors += errors
            if len(table):
                path = write_observations(table, Zone.PROCESSED, SOURCE, station, root=root)
                run.processed_path = str(path)
                run.processed_rows = len(table)
                run.time_min_utc = table["timestamp_utc"].min().isoformat()
                run.time_max_utc = table["timestamp_utc"].max().isoformat()
                run.qc_counts = {k: int(v) for k, v in table["qc_flag"].value_counts().items()}
            runs.append(run)
    finally:
        if own:
            client.close()
    log = (root or data_root()) / Zone.RAW.value / SOURCE / "runs.jsonl"
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a", encoding="utf-8") as fh:
        stamp = datetime.now(UTC).isoformat()
        for run in runs:
            fh.write(json.dumps({"run_at_utc": stamp, **run.__dict__}, ensure_ascii=False) + "\n")
    return runs


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Archive DGACTA Sidi Bouzid station snapshots")
    ap.add_argument("--station", action="append", choices=list(STATIONS))
    args = ap.parse_args(argv)
    runs = archive(args.station)
    for r in runs:
        span = f"{r.time_min_utc} .. {r.time_max_utc}" if r.time_min_utc else "no data"
        print(
            f"{r.station:12} files {r.files_seen} (new {r.files_new}) | rows {r.processed_rows} "
            f"| {span} | qc {r.qc_counts}"
        )
        for e in r.errors:
            print(f"   ! {e}")
    return 1 if any(r.errors for r in runs) else 0


if __name__ == "__main__":
    raise SystemExit(main())

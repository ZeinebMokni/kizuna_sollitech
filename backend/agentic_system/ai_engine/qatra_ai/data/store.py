"""QATRA data store: the folder layout, the observation schema and the provenance manifests.

Layout (root = $QATRA_DATA_DIR, default <repo>/data):

  raw/<source>/        downloaded files, byte-for-byte, never edited; one manifest per file
  external/<source>/   reference data from third parties (statistics, soil maps, projections)
  processed/<source>/  real observations parsed to the long-format schema below
  sensors/<site>/      measurements received from farm sensors and farmer logs
  synthetic/<name>/    simulated data ONLY (benchmarks, tests); never mixed with the others

Rules enforced here, not left to convention:
- Every observation row carries its data class. `synthetic/` accepts only SIMULATED rows and
  every other zone rejects them, so simulated values cannot be filed as real ones.
- Raw files are write-once and content-addressed (SHA-256). Writing different bytes under an
  existing name fails; writing the same bytes again is a no-op.
- QC flags values; it never deletes or changes them. `value` is always what the source said.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from qatra_ai.contracts import DataClass
from qatra_ai.data.qc import GAP_FILLED, INVALID, MISSING, SUSPECT, VALID

SCHEMA_VERSION = "1.0"


class Zone(StrEnum):
    RAW = "raw"
    EXTERNAL = "external"
    PROCESSED = "processed"
    SENSORS = "sensors"
    SYNTHETIC = "synthetic"


UNCHECKED = "unchecked"  # parsed but QC not yet applied
QC_FLAGS = frozenset({UNCHECKED, VALID, SUSPECT, INVALID, MISSING, GAP_FILLED})

ZONE_DATA_CLASSES: dict[Zone, frozenset[DataClass]] = {
    Zone.RAW: frozenset(DataClass) - {DataClass.SIMULATED},
    Zone.EXTERNAL: frozenset(
        {
            DataClass.OFFICIAL,
            DataClass.INFERRED,
            DataClass.REMOTE_SENSED,
            DataClass.PROJECTED,
            DataClass.MEASURED,
        }
    ),
    Zone.PROCESSED: frozenset(
        {
            DataClass.MEASURED,
            DataClass.OFFICIAL,
            DataClass.FARMER_REPORTED,
            DataClass.REMOTE_SENSED,
            DataClass.INFERRED,
        }
    ),
    Zone.SENSORS: frozenset({DataClass.MEASURED, DataClass.FARMER_REPORTED}),
    Zone.SYNTHETIC: frozenset({DataClass.SIMULATED}),
}

OBSERVATION_COLUMNS = [
    "timestamp_utc",
    "site_id",
    "variable",
    "value",
    "unit",
    "source",
    "data_class",
    "qc_flag",
    "qc_note",
    "raw_file_sha256",
]

_SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,120}$")


class DataStoreError(ValueError):
    """Data that would break the store's rules (schema, provenance or separation)."""


def data_root() -> Path:
    env = os.environ.get("QATRA_DATA_DIR")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[3] / "data"


def _safe(name: str, what: str) -> str:
    if not _SAFE_NAME.match(name) or ".." in name:
        raise DataStoreError(f"unsafe {what} {name!r}: use letters, digits, '.', '_', '-'")
    return name


def zone_dir(zone: Zone, key: str, root: Path | None = None) -> Path:
    return (root or data_root()) / zone.value / _safe(key, "source/site name")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# --- Manifests ----------------------------------------------------------------------------------


class SourceManifest(BaseModel):
    """Where a raw file came from. Stored next to it as <file>.manifest.json."""

    model_config = ConfigDict(frozen=True)

    file_name: str
    sha256: str
    size_bytes: int
    source: str  # short id, e.g. "dgacta_sidi_bouzid"
    publisher: str  # who published it, e.g. "DGACTA, Ministry of Agriculture, Tunisia"
    url: str
    retrieved_at_utc: datetime
    licence: str
    data_class: DataClass
    content_type: str | None = None
    notes: str | None = None
    extra: dict[str, str] = Field(default_factory=dict)  # e.g. catalogue resource ids
    schema_version: str = SCHEMA_VERSION


def manifest_path(file_path: Path) -> Path:
    return file_path.with_name(file_path.name + ".manifest.json")


def write_raw(
    content: bytes,
    *,
    source: str,
    file_name: str,
    publisher: str,
    url: str,
    licence: str,
    data_class: DataClass,
    retrieved_at_utc: datetime | None = None,
    content_type: str | None = None,
    notes: str | None = None,
    extra: dict[str, str] | None = None,
    root: Path | None = None,
) -> tuple[Path, SourceManifest, bool]:
    """Store a downloaded file unchanged in raw/<source>/ with its manifest.

    The stored name is prefixed with the first 12 hex digits of its SHA-256, so successive
    snapshots of the same URL never overwrite each other. Returns (path, manifest, created);
    `created` is False when identical bytes were already stored.
    """
    if data_class == DataClass.SIMULATED:
        raise DataStoreError("simulated data never goes into raw/; use the synthetic zone")
    digest = sha256_bytes(content)
    folder = zone_dir(Zone.RAW, source, root)
    path = folder / f"{digest[:12]}_{_safe(file_name, 'file name')}"
    mpath = manifest_path(path)
    if path.exists():
        if sha256_bytes(path.read_bytes()) != digest:
            raise DataStoreError(f"{path} exists with different content; raw files are write-once")
        return path, SourceManifest.model_validate_json(mpath.read_text("utf-8")), False
    manifest = SourceManifest(
        file_name=path.name,
        sha256=digest,
        size_bytes=len(content),
        source=source,
        publisher=publisher,
        url=url,
        retrieved_at_utc=retrieved_at_utc or datetime.now(UTC),
        licence=licence,
        data_class=data_class,
        content_type=content_type,
        notes=notes,
        extra=extra or {},
    )
    folder.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".part")
    tmp.write_bytes(content)
    tmp.replace(path)
    mpath.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    return path, manifest, True


def list_raw(source: str, root: Path | None = None) -> list[tuple[Path, SourceManifest]]:
    """All raw files of a source with their manifests, oldest retrieval first."""
    folder = zone_dir(Zone.RAW, source, root)
    items = [
        (m.with_name(m.name.removesuffix(".manifest.json")), m)
        for m in sorted(folder.glob("*.manifest.json"))
    ]
    out = [(p, SourceManifest.model_validate_json(m.read_text("utf-8"))) for p, m in items]
    return sorted(out, key=lambda pm: (pm[1].retrieved_at_utc, pm[0].name))


def verify_raw(path: Path) -> SourceManifest:
    """Check a raw file against its manifest; raises if the bytes changed."""
    manifest = SourceManifest.model_validate_json(manifest_path(path).read_text("utf-8"))
    if sha256_bytes(path.read_bytes()) != manifest.sha256:
        raise DataStoreError(f"{path} no longer matches its manifest hash")
    return manifest


# --- Observations (long format) -----------------------------------------------------------------


class ObservationSetInfo(BaseModel):
    """Sidecar describing a processed observation file (<file>.meta.json)."""

    model_config = ConfigDict(frozen=True)

    zone: Zone
    rows: int
    data_classes: list[DataClass]
    sources: list[str]
    sites: list[str]
    variables: list[str]
    time_min_utc: datetime | None
    time_max_utc: datetime | None
    qc_counts: dict[str, int] = Field(default_factory=dict)
    raw_files_sha256: list[str] = Field(default_factory=list)
    written_at_utc: datetime
    schema_version: str = SCHEMA_VERSION


def validate_observations(df: pd.DataFrame, zone: Zone) -> pd.DataFrame:
    """Check the long-format schema and the zone's data-class rule. Returns a normalised copy
    (columns in schema order, timestamps tz-aware UTC). Raises DataStoreError on any breach."""
    if zone == Zone.RAW:
        raise DataStoreError("raw/ holds files, not observation tables")
    missing = [c for c in OBSERVATION_COLUMNS if c not in df.columns]
    if missing:
        raise DataStoreError(f"missing columns: {missing}")
    extra = [c for c in df.columns if c not in OBSERVATION_COLUMNS]
    if extra:
        raise DataStoreError(f"unexpected columns: {extra} (keep extras in the raw file)")
    out = df[OBSERVATION_COLUMNS].copy()

    ts = out["timestamp_utc"]
    if not isinstance(ts.dtype, pd.DatetimeTZDtype):
        raise DataStoreError("timestamp_utc must be timezone-aware (UTC)")
    out["timestamp_utc"] = ts.dt.tz_convert("UTC")
    if out["timestamp_utc"].isna().any():
        raise DataStoreError("timestamp_utc has missing values")

    for col in ("site_id", "variable", "unit", "source"):
        s = out[col]
        if s.isna().any() or (s.astype(str).str.strip() == "").any():
            raise DataStoreError(f"{col} must be set on every row")

    try:
        out["value"] = pd.to_numeric(out["value"], errors="raise").astype("float64")
    except (ValueError, TypeError) as exc:
        raise DataStoreError(f"value must be numeric: {exc}") from exc

    classes = set(out["data_class"].astype(str))
    unknown = classes - {c.value for c in DataClass}
    if unknown:
        raise DataStoreError(f"unknown data_class values: {sorted(unknown)}")
    allowed = {c.value for c in ZONE_DATA_CLASSES[zone]}
    wrong = classes - allowed
    if wrong:
        raise DataStoreError(
            f"data_class {sorted(wrong)} not allowed in {zone.value}/ (allowed: {sorted(allowed)})"
        )

    flags = set(out["qc_flag"].astype(str))
    if flags - QC_FLAGS:
        raise DataStoreError(f"unknown qc_flag values: {sorted(flags - QC_FLAGS)}")
    out["qc_note"] = out["qc_note"].fillna("").astype(str)
    nan_not_missing = out["value"].isna() & (out["qc_flag"] != MISSING)
    if nan_not_missing.any():
        raise DataStoreError("rows with no value must be flagged 'missing'")

    if zone != Zone.SYNTHETIC:
        sha = out["raw_file_sha256"].astype(str)
        if out["raw_file_sha256"].isna().any() or not sha.str.fullmatch(r"[0-9a-f]{64}").all():
            raise DataStoreError("real observations must reference their raw file's SHA-256")

    key = ["timestamp_utc", "site_id", "variable", "source"]
    dup = out.duplicated(subset=key, keep=False)
    if dup.any():
        raise DataStoreError(f"{int(dup.sum())} rows share the same {key}")
    return out.sort_values(key).reset_index(drop=True)


def write_observations(
    df: pd.DataFrame, zone: Zone, key: str, name: str, root: Path | None = None
) -> Path:
    """Validate and write an observation table as CSV (ISO-8601 UTC) plus a .meta.json."""
    out = validate_observations(df, zone)
    folder = zone_dir(zone, key, root)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{_safe(name, 'file name')}.csv"
    csv = out.copy()
    csv["timestamp_utc"] = csv["timestamp_utc"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    tmp = path.with_name(path.name + ".part")
    csv.to_csv(tmp, index=False, lineterminator="\n")
    tmp.replace(path)
    info = ObservationSetInfo(
        zone=zone,
        rows=len(out),
        data_classes=sorted({DataClass(c) for c in out["data_class"]}),
        sources=sorted(out["source"].unique()),
        sites=sorted(out["site_id"].unique()),
        variables=sorted(out["variable"].unique()),
        time_min_utc=out["timestamp_utc"].min().to_pydatetime() if len(out) else None,
        time_max_utc=out["timestamp_utc"].max().to_pydatetime() if len(out) else None,
        qc_counts={k: int(v) for k, v in out["qc_flag"].value_counts().items()},
        raw_files_sha256=sorted(out["raw_file_sha256"].dropna().astype(str).unique()),
        written_at_utc=datetime.now(UTC),
    )
    path.with_name(path.stem + ".meta.json").write_text(
        info.model_dump_json(indent=2), encoding="utf-8"
    )
    return path


def read_observations(path: Path, zone: Zone) -> pd.DataFrame:
    """Read a CSV written by write_observations and re-check it against the zone's rules."""
    df = pd.read_csv(
        path,
        dtype={c: str for c in OBSERVATION_COLUMNS if c not in ("timestamp_utc", "value")},
        keep_default_na=False,
        na_values={"value": [""], "raw_file_sha256": [""]},
    )
    df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True, format="ISO8601")
    return validate_observations(df, zone)


def file_meta(path: Path) -> dict:
    return json.loads(path.with_name(path.stem + ".meta.json").read_text("utf-8"))

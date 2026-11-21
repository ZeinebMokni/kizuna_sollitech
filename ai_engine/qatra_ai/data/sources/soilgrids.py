"""ISRIC SoilGrids 2.0 point query -> texture -> FC/WP via Saxton & Rawls.

API: https://rest.isric.org/soilgrids/v2.0/properties/query  (free; CC-BY 4.0; ~250 m)
SoilGrids values are *machine-learning predictions*, not measurements -> data_class `inferred`.
They are a prior to be replaced by laboratory analyses when available.

Conversions (SoilGrids "mapped units", divide by `d_factor` to get "target units"):
    sand, clay: g/kg (d_factor 10) -> %;  soc: dg/kg (d_factor 10) -> g/kg
Organic matter [%] = SOC [g/kg] / 10 * 1.724   (van Bemmelen factor; a convention, not exact)

The root-zone value is the thickness-weighted mean over the standard depth intervals
down to `max_depth_cm`.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from qatra_ai.agronomy.soil import SoilWaterProperties, soil_from_texture
from qatra_ai.data.sources.open_meteo import USER_AGENT

URL = "https://rest.isric.org/soilgrids/v2.0/properties/query"
DEPTHS = ["0-5cm", "5-15cm", "15-30cm", "30-60cm", "60-100cm", "100-200cm"]
VAN_BEMMELEN = 1.724


class SoilGridsError(RuntimeError):
    pass


@dataclass
class SoilGridsProfile:
    sand_pct: float
    clay_pct: float
    soc_g_kg: float
    organic_matter_pct: float
    depth_cm: int
    by_depth: dict[str, dict[str, float]]

    def to_soil_properties(self) -> SoilWaterProperties:
        om = min(self.organic_matter_pct, 8.0)  # Saxton-Rawls validity limit
        return soil_from_texture(
            self.sand_pct / 100,
            self.clay_pct / 100,
            om,
            source=f"soilgrids_v2:0-{self.depth_cm}cm",
        )


def _depth_bounds(label: str) -> tuple[int, int]:
    top, bottom = label.removesuffix("cm").split("-")
    return int(top), int(bottom)


def parse_soilgrids(payload: dict, max_depth_cm: int = 60) -> SoilGridsProfile:
    try:
        layers = payload["properties"]["layers"]
    except KeyError as exc:
        raise SoilGridsError("unexpected response shape") from exc

    by_depth: dict[str, dict[str, float]] = {}
    for layer in layers:
        name = layer["name"]
        d_factor = float(layer["unit_measure"]["d_factor"])
        for d in layer["depths"]:
            mean = d["values"].get("mean")
            if mean is None:
                continue
            by_depth.setdefault(d["label"], {})[name] = mean / d_factor

    weighted = {"sand": 0.0, "clay": 0.0, "soc": 0.0}
    total = 0
    for label in DEPTHS:
        top, bottom = _depth_bounds(label)
        if top >= max_depth_cm:
            break
        vals = by_depth.get(label, {})
        if not all(k in vals for k in weighted):
            raise SoilGridsError(f"no SoilGrids prediction at {label} (water, urban or no-data?)")
        thick = min(bottom, max_depth_cm) - top
        for k in weighted:
            weighted[k] += vals[k] * thick
        total += thick
    if total == 0:
        raise SoilGridsError("no depth intervals selected")
    # Values are already in target units after dividing by d_factor: sand/clay %, soc g/kg.
    sand_pct, clay_pct, soc = (weighted[k] / total for k in ("sand", "clay", "soc"))
    return SoilGridsProfile(
        sand_pct=sand_pct,
        clay_pct=clay_pct,
        soc_g_kg=soc,
        organic_matter_pct=soc / 10 * VAN_BEMMELEN,
        depth_cm=max_depth_cm,
        by_depth=by_depth,
    )


def fetch_soilgrids(
    latitude: float, longitude: float, max_depth_cm: int = 60, client: httpx.Client | None = None
) -> SoilGridsProfile:
    params: list[tuple[str, str | float]] = [("lon", longitude), ("lat", latitude)]
    params += [("property", p) for p in ("sand", "clay", "soc")]
    params += [("depth", d) for d in DEPTHS]
    params += [("value", "mean")]
    own = client is None
    client = client or httpx.Client(headers={"User-Agent": USER_AGENT})
    try:
        resp = client.get(URL, params=params, timeout=60.0)
    finally:
        if own:
            client.close()
    if resp.status_code != 200:
        raise SoilGridsError(f"HTTP {resp.status_code}: {resp.text[:200]}")
    return parse_soilgrids(resp.json(), max_depth_cm)

"""NASA NEX-GDDP-CMIP6 point reader (THREDDS NetCDF Subset Service, CSV output).

Dataset: NASA Earth Exchange Global Daily Downscaled Projections (CMIP6), 0.25 deg, daily,
bias-corrected and statistically downscaled (BCSD). Scenarios: historical (to 2014), ssp245,
ssp585 (others exist). data_class: projected (historical runs are model output too, not
observations). Licence: per CMIP6 model terms (mostly CC BY 4.0); check each model before reuse.

One request = one model x scenario x variable x year at one point. Results are cached on disk.
"""

from __future__ import annotations

import io
import json
import threading
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
import pandas as pd

from qatra_ai.data.sources.open_meteo import USER_AGENT

BASE = "https://ds.nccs.nasa.gov/thredds/ncss/grid/AMES/NEX/GDDP-CMIP6"
VERSION_SUFFIXES = ("_v2.0", "_v1.1", "")
# variable -> (column name, conversion from native units)
VARIABLES = {
    "tasmax": ("tmax", lambda k: k - 273.15),  # K -> degC
    "tasmin": ("tmin", lambda k: k - 273.15),
    "pr": ("precip", lambda x: x * 86400.0),  # kg m-2 s-1 -> mm/day
    "rsds": ("rs", lambda w: w * 0.0864),  # W m-2 (daily mean) -> MJ m-2 day-1
}
DEFAULT_MEMBERS = {"CNRM-CM6-1": "r1i1p1f2", "CNRM-ESM2-1": "r1i1p1f2", "UKESM1-0-LL": "r1i1p1f2"}


class NexGddpError(RuntimeError):
    pass


class NexGddpClient:
    def __init__(self, cache_dir: Path | str, timeout: float = 90.0, max_workers: int = 4):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.timeout = timeout
        self.max_workers = max_workers
        self._suffix: dict[tuple[str, str, str], str] = {}
        self._lock = threading.Lock()
        self._client = httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=timeout)

    def close(self) -> None:
        self._client.close()

    def _cache_path(self, model, scenario, var, year, lat, lon) -> Path:
        return self.cache_dir / f"{model}_{scenario}_{var}_{year}_{lat:.3f}_{lon:.3f}.json"

    def _url(self, model, scenario, member, var, year, suffix) -> str:
        fn = f"{var}_day_{model}_{scenario}_{member}_gn_{year}{suffix}.nc"
        return f"{BASE}/{model}/{scenario}/{member}/{var}/{fn}"

    def fetch_year(
        self, model: str, scenario: str, var: str, year: int, lat: float, lon: float
    ) -> pd.Series:
        if var not in VARIABLES:
            raise ValueError(f"unsupported variable {var}")
        cpath = self._cache_path(model, scenario, var, year, lat, lon)
        if cpath.exists():
            d = json.loads(cpath.read_text())
            return pd.Series(d["values"], index=pd.to_datetime(d["dates"]), name=var)
        member = DEFAULT_MEMBERS.get(model, "r1i1p1f1")
        params = {
            "var": var,
            "latitude": lat,
            "longitude": lon,
            "time_start": f"{year}-01-01T00:00:00Z",
            "time_end": f"{year}-12-31T23:59:59Z",
            "accept": "csv",
        }
        key = (model, scenario, var)
        suffixes = [self._suffix[key]] if key in self._suffix else list(VERSION_SUFFIXES)
        last = None
        for sfx in suffixes:
            r = self._client.get(self._url(model, scenario, member, var, year, sfx), params=params)
            if r.status_code == 200:
                with self._lock:
                    self._suffix[key] = sfx
                s = parse_ncss_csv(r.text, var)
                cpath.write_text(
                    json.dumps({"dates": [str(i.date()) for i in s.index], "values": s.tolist()})
                )
                return s
            last = f"HTTP {r.status_code}"
        raise NexGddpError(f"{model}/{scenario}/{var}/{year}: not found ({last})")

    def fetch(
        self,
        model: str,
        scenario: str,
        years: Iterable[int],
        lat: float,
        lon: float,
        variables: Iterable[str] = tuple(VARIABLES),
    ) -> pd.DataFrame:
        """Daily DataFrame with columns tmax, tmin, precip, rs (converted units)."""
        jobs = [(v, y) for v in variables for y in years]
        with ThreadPoolExecutor(self.max_workers) as ex:
            parts = list(
                ex.map(
                    lambda j: (j[0], self.fetch_year(model, scenario, j[0], j[1], lat, lon)), jobs
                )
            )
        cols: dict[str, list[pd.Series]] = {}
        for var, s in parts:
            cols.setdefault(var, []).append(s)
        out = pd.DataFrame(
            {VARIABLES[v][0]: VARIABLES[v][1](pd.concat(ss).sort_index()) for v, ss in cols.items()}
        )
        out.index = pd.DatetimeIndex(out.index.normalize(), name="date")
        return out[~out.index.duplicated()]


def parse_ncss_csv(text: str, var: str) -> pd.Series:
    df = pd.read_csv(io.StringIO(text))
    vcol = next((c for c in df.columns if c.split("[")[0] == var), None)
    if vcol is None or "time" not in df.columns:
        raise NexGddpError(f"unexpected NCSS CSV columns: {list(df.columns)}")
    s = pd.Series(
        df[vcol].astype(float).to_numpy(),
        index=pd.to_datetime(df["time"]).dt.tz_localize(None),
        name=var,
    )
    return s

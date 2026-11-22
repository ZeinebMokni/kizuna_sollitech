"""The HYPOTHETICAL demo farm shown in the dashboard.

Location (farmland west of Sidi Bouzid) and the weather/soil fetched for it are real; every
farm attribute below (zones, crops, dates, flows, pump, PV, battery, well cap, quota, past
irrigation practice) is invented for demonstration. Not a real farm; not advice.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from qatra_ai.optimization.schedule_models import BatterySpec, PumpSystem

FARM_ID = "demo-farm"
FARM_NAME = "Demo farm (hypothetical)"
LATITUDE, LONGITUDE = 35.10, 9.30
TIMEZONE = "Africa/Tunis"
SEASON_YEAR = 2025
DEFAULT_DAY = date(2025, 6, 15)
WEATHER_START, WEATHER_END = date(2025, 3, 1), date(2025, 9, 10)
CLIMATE_YEARS = (2015, 2024)  # multi-year weather for suitability


@dataclass(frozen=True)
class DemoZone:
    zone_id: str
    name: str
    crop: str
    season_start: date
    area_ha: float
    design_flow_m3h: float
    # Polygon offsets (deg) around the farm point, for the map only (hypothetical layout).
    polygon: tuple[tuple[float, float], ...]


ZONES = [
    DemoZone(
        "olive-north",
        "Olive grove (north)",
        "olive",
        date(2025, 3, 1),
        2.0,
        12.0,
        ((0.0018, -0.0030), (0.0018, 0.0010), (0.0003, 0.0010), (0.0003, -0.0030)),
    ),
    DemoZone(
        "tomato-east",
        "Tomato (east)",
        "tomato",
        date(2025, 4, 1),
        1.0,
        10.0,
        ((0.0000, 0.0012), (0.0000, 0.0030), (-0.0009, 0.0030), (-0.0009, 0.0012)),
    ),
    DemoZone(
        "potato-south",
        "Potato (south)",
        "potato",
        date(2025, 3, 1),
        1.0,
        10.0,
        ((-0.0011, -0.0030), (-0.0011, 0.0008), (-0.0020, 0.0008), (-0.0020, -0.0030)),
    ),
]

PUMP = PumpSystem(max_flow_m3h=15, max_simultaneous_zones=1, total_head_m=60, pump_efficiency=0.55)
PV_RATED_KW = 12.0
BATTERY = BatterySpec(
    capacity_kwh=20,
    soc_initial_kwh=10,
    soc_min_kwh=4,
    soc_max_kwh=20,
    max_charge_kw=5,
    max_discharge_kw=5,
)
MAX_VOLUME_PER_DAY_M3 = 120.0
PAST_IRRIGATION_MM = 12.0  # hypothetical past practice: 12 mm gross every 4 days
PAST_IRRIGATION_EVERY_DAYS = 4
APPLICATION_EFFICIENCY = 0.9

# Suitability site settings (hypothetical)
SITE_WATER_M3_PER_HA = 6000
SITE_ENERGY_KWH_PER_HA = 3000
SITE_IRRIGATION_EC_DS_M = 1.5
SITE_SOIL_DEPTH_M = 1.5
SUITABILITY_CROPS = {
    "tomato": (4, 1),
    "potato": (2, 1),
    "durum_wheat": (11, 15),
    "olive": (3, 1),
    "citrus": (3, 1),
    "date_palm": (3, 1),
}

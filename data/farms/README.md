# farms/

One file per farm, named `<farm_id>.yaml`. QATRA loads every profile here plus the shipped demo farm (`ai_engine/qatra_ai/reference_data/farms/demo-farm.yaml`).

**Profiles stay out of git**, because a farm's location and setup are private. Only this README is tracked.

## Add a farm

1. Copy the template below into `data/farms/<farm_id>.yaml`. The `farm_id` must match the file name and use lower-case letters, digits and `-`.
2. Fill in what you know.
   - **Required:** location, at least one zone, the pump, and a power source.
   - **Optional, leave out if unknown:** soil analysis, water limits, salinity, sensors, map polygons. QATRA treats a missing limit as "not known"; it never invents one.
3. Check it:
   ```bash
   cd ai_engine && uv run python -m qatra_ai.farms.check
   ```
   Every problem is listed with the field it concerns.

**Soil:** without a `soil:` section QATRA uses the SoilGrids map (250 m, modelled). The map has no value in towns or over water; there, add your soil analysis.

**Crops:** QATRA only accepts crops it has parameters for (`ai_engine/qatra_ai/reference_data/crops/`). A crop that isn't there needs a reviewed crop file first. QATRA won't borrow another crop's values.

## Template

```yaml
schema_version: "1.0"
farm_id: my-farm
name: My farm
kind: real                    # real = an actual farm; demo = hypothetical
location:
  latitude: 36.80             # decimal degrees, north positive
  longitude: 10.10            # decimal degrees, east positive
  timezone: Africa/Tunis
  elevation_m: 120            # optional
  region: Manouba             # optional, free text
soil_depth_m: 1.2             # optional: rootable soil depth
soil:                         # optional: your own soil data (else the SoilGrids map is used)
  sand_pct: 45                #   EITHER a lab texture analysis ...
  clay_pct: 20
  organic_matter_pct: 1.2
  # theta_fc: 0.28            #   ... OR measured field capacity / wilting point (m3/m3)
  # theta_wp: 0.14
  source: CRDA soil lab, 2025
zones:
  - zone_id: zone-1
    name: Olive grove
    crop: olive               # one of the crop files QATRA has
    season_start: 2026-03-01  # planting date, or season start for trees
    area_ha: 3.0
    design_flow_m3h: 12.0     # flow when this zone's valve is open
    application_efficiency: 0.9   # drip ~0.9, sprinkler ~0.75
    polygon: [[36.8010, 10.0990], [36.8010, 10.1010], [36.7995, 10.1010], [36.7995, 10.0990]]  # optional
pump:
  max_flow_m3h: 15            # well / pump yield limit
  max_simultaneous_zones: 1
  total_head_m: 60
  pump_efficiency: 0.55
water:                        # all optional
  max_volume_per_day_m3: 150
  seasonal_m3_per_ha: 5000
  irrigation_ec_ds_m: 1.2     # irrigation water salinity
energy:                       # at least solar (pv_rated_kw) or grid hours
  pv_rated_kw: 10
  grid_hours: [0, 1, 2, 3, 4, 5, 22, 23]   # optional; needs grid_max_kw
  grid_max_kw: 15
sensors:                      # optional; what is installed
  - {sensor_id: sm-1-30, kind: soil_moisture, zone_id: zone-1, depth_cm: 30}
  - {sensor_id: flow-main, kind: flow_meter}
```

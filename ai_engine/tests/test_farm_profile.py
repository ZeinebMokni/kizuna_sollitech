"""Farm profiles: validation rules, registry loading, the README template, the demo profile."""

import copy
import re
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from qatra_ai.farms.profile import FarmProfile
from qatra_ai.farms.registry import (
    PACKAGE_FARMS_DIR,
    FarmProfileError,
    load_profile,
    load_registry,
)

README = Path(__file__).resolve().parents[2] / "data" / "farms" / "README.md"


def template() -> dict:
    text = README.read_text(encoding="utf-8")
    block = re.search(r"```yaml\n(.*?)```", text, re.S)
    assert block, "README must contain the YAML template"
    return yaml.safe_load(block.group(1))


def make(**changes) -> dict:
    d = copy.deepcopy(template())
    for dotted, value in changes.items():
        node = d
        *path, last = dotted.split("__")
        for k in path:
            node = node[int(k)] if isinstance(node, list) else node[k]
        if value is DELETE:
            del node[last]
        else:
            node[last] = value
    return d


DELETE = object()


def reject(data: dict, match: str):
    with pytest.raises(ValidationError, match=match):
        FarmProfile.model_validate(data)


# --- the template and the demo -------------------------------------------------------------------


def test_readme_template_is_a_valid_real_farm():
    p = FarmProfile.model_validate(template())
    assert p.kind == "real" and p.zones[0].crop == "olive" and len(p.sensors) == 2


def test_demo_profile_is_labelled_hypothetical():
    p = load_profile(PACKAGE_FARMS_DIR / "demo-farm.yaml")
    assert p.kind == "demo" and "hypothetical" in p.name.lower()
    assert p.replay is not None and p.assumed_past_irrigation is not None
    assert p.sensors == []  # nothing measured on a hypothetical farm


# --- validation ----------------------------------------------------------------------------------


def test_unknown_crop_rejected_with_known_list():
    reject(make(zones__0__crop="pepper"), "no parameters for crop 'pepper'.*known: citrus")


def test_location_and_timezone_checked():
    reject(make(location__latitude=95), "less than or equal to 90")
    reject(make(location__timezone="Tunisia/Tunis"), "unknown time zone")
    reject(make(location=DELETE), "location")


def test_zone_rules():
    reject(make(zones__0__area_ha=0), "greater than 0")
    reject(make(zones__0__zone_id="Zone 1"), "lower-case")
    two = make()
    two["zones"].append(copy.deepcopy(two["zones"][0]))
    reject(two, "duplicate zone_id")
    reject(make(zones=[]), "at least 1")


def test_polygon_far_from_farm_rejected():
    swapped = [[10.0990, 36.8010], [10.1010, 36.8010], [10.1010, 36.7995]]  # lat/lon swapped
    reject(make(zones__0__polygon=swapped), "more than 10 km")


def test_sensor_rules():
    reject(make(sensors=[{"sensor_id": "sm", "kind": "soil_moisture", "zone_id": "zone-1"}]),
           "needs zone_id and depth_cm")  # fmt: skip
    reject(make(sensors=[{"sensor_id": "f1", "kind": "flow_meter", "zone_id": "nope"}]),
           "unknown zone 'nope'")  # fmt: skip
    reject(make(sensors=[{"sensor_id": "x1", "kind": "camera"}]), "kind")


def test_energy_needs_a_power_source():
    reject(make(energy={"pv_rated_kw": 0}), "needs power")
    reject(make(energy={"grid_hours": [1, 2]}), "without grid_max_kw")
    reject(make(energy={"grid_hours": [24], "grid_max_kw": 5}), "between 0 and 23")


def test_typos_are_errors_not_silently_ignored():
    reject(make(zones__0__area_hectares=3), "Extra inputs")
    reject(make(water__max_volume_m3=100), "Extra inputs")


def test_unknown_limits_stay_unknown():
    p = FarmProfile.model_validate(make(water=DELETE))
    assert p.water.max_volume_per_day_m3 is None and p.water.irrigation_ec_ds_m is None


def test_demo_kind_requires_replay_window():
    reject(make(kind="demo"), "replay window")


# --- registry ------------------------------------------------------------------------------------


def write(folder: Path, name: str, data) -> Path:
    path = folder / name
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return path


def test_registry_loads_good_files_and_reports_bad_ones(tmp_path):
    write(tmp_path, "my-farm.yaml", template())
    write(tmp_path, "broken.yaml", make(farm_id="broken", zones__0__crop="pepper"))
    write(tmp_path, "wrong-name.yaml", make(farm_id="other-id"))
    (tmp_path / "junk.yaml").write_text("- just\n- a list\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("ignored", encoding="utf-8")
    reg = load_registry([PACKAGE_FARMS_DIR, tmp_path])
    assert set(reg.profiles) == {"demo-farm", "my-farm"}
    reasons = " | ".join(reg.errors.values())
    assert "pepper" in reasons and "must be other-id.yaml" in reasons and "mapping" in reasons
    assert len(reg.errors) == 3
    assert reg.get("my-farm").location.latitude == 36.80
    with pytest.raises(KeyError, match="known: demo-farm, my-farm"):
        reg.get("nope")


def test_duplicate_farm_id_across_folders(tmp_path):
    write(tmp_path, "demo-farm.yaml", make(farm_id="demo-farm"))
    reg = load_registry([PACKAGE_FARMS_DIR, tmp_path])
    assert reg.get("demo-farm").kind == "demo"  # the first definition wins
    assert any("already defined" in e for e in reg.errors.values())


def test_load_profile_error_names_the_field(tmp_path):
    path = write(tmp_path, "my-farm.yaml", make(pump__pump_efficiency=1.5))
    with pytest.raises(FarmProfileError, match=r"my-farm.yaml: pump.pump_efficiency"):
        load_profile(path)


def test_registry_missing_folder_is_fine(tmp_path):
    assert load_registry([tmp_path / "absent"]).profiles == {}


def test_soil_input_takes_exactly_one_form():
    texture = {"sand_pct": 45, "clay_pct": 20, "organic_matter_pct": 1.2, "source": "lab"}
    water = {"theta_fc": 0.28, "theta_wp": 0.14, "source": "lab"}
    assert FarmProfile.model_validate(make(soil=texture)).soil.sand_pct == 45
    assert FarmProfile.model_validate(make(soil=water)).soil.theta_fc == 0.28
    reject(make(soil={**texture, **water}), "either")
    reject(make(soil={"source": "lab"}), "either")
    reject(make(soil={"sand_pct": 45, "clay_pct": 20, "source": "lab"}), "needs sand_pct")
    reject(make(soil={"sand_pct": 80, "clay_pct": 30, "organic_matter_pct": 1, "source": "lab"}),
           "exceeds 100")  # fmt: skip
    reject(make(soil={"theta_fc": 0.1, "theta_wp": 0.2, "source": "lab"}), "greater than")
    reject(make(soil={**water, "source": ""}), "at least 1")

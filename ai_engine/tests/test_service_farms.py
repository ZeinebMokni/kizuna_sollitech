"""The API runs on any farm profile: listing, per-farm routes, live mode, missing inputs.

Weather and soil come from the OFFLINE synthetic provider in test_service.py; the extra farms
are test profiles built from the README template (not real farms).
"""

import copy
from datetime import date

import pytest
import yaml
from fastapi.testclient import TestClient

import qatra_ai.service.app as service
from qatra_ai.farms.registry import PACKAGE_FARMS_DIR, load_registry
from tests.test_farm_profile import template
from tests.test_service import OfflineProvider

TODAY = date(2026, 6, 15)


def profile(farm_id, **changes):
    d = copy.deepcopy(template())
    d["farm_id"] = farm_id
    d.update(changes)
    return d


def build(tmp_path, *profiles, provider=None):
    for p in profiles:
        (tmp_path / f"{p['farm_id']}.yaml").write_text(yaml.safe_dump(p), encoding="utf-8")
    reg = load_registry([PACKAGE_FARMS_DIR, tmp_path])
    prov = provider or OfflineProvider()
    app = service.create_app(prov, registry=reg, today=lambda: TODAY)
    return TestClient(app), prov, reg


ASSUMED = {"mm_per_event": 10, "every_days": 3}


@pytest.fixture
def farms(tmp_path):
    later = copy.deepcopy(template()["zones"][0])
    later.update(zone_id="zone-late", name="Late tomato", crop="tomato", season_start="2026-08-01")
    north = profile(
        "north-farm",
        name="North farm",
        assumed_past_irrigation=ASSUMED,
        zones=[template()["zones"][0], later],
    )
    bare = profile("bare-farm", name="Farm without history")
    bad = profile("bad-farm", zones=[{**template()["zones"][0], "crop": "pepper"}])
    return build(tmp_path, north, bare, bad)


def test_farm_list_includes_real_farms_and_reports_invalid_ones(farms):
    client, _, _ = farms
    body = client.get("/api/farms").json()
    ids = [f["farm_id"] for f in body["data"]]
    assert ids[-1] == "demo-farm" and {"north-farm", "bare-farm"} <= set(ids)
    north = next(f for f in body["data"] if f["farm_id"] == "north-farm")
    assert (
        north["mode"] == "live"
        and north["kind"] == "real"
        and north["crops"]
        == [
            "olive",
            "tomato",
        ]
    )
    bad = body["meta"]["invalid_profiles"]
    assert len(bad) == 1 and "pepper" in bad[0]["reason"]


def test_live_farm_uses_its_own_location_and_today(farms):
    client, prov, _ = farms
    info = client.get("/api/farms/north-farm").json()
    assert info["meta"]["demo"] is False and "Real farm" in info["meta"]["note"]
    assert info["data"]["day_range"] == [str(TODAY), str(TODAY)]
    assert info["data"]["grid_hours"] == [0, 1, 2, 3, 4, 5, 22, 23]
    body = client.get("/api/farms/north-farm/decision").json()
    assert body["meta"]["day"] == str(TODAY) and body["meta"]["mode"] == "live"
    assert "Open-Meteo" in body["meta"]["forecast_note"]
    assert "ASSUMED" in body["meta"]["irrigation_note"]
    assert body["meta"]["inactive_zones"] == ["zone-late: season starts 2026-08-01, not yet active"]
    zones = {p["target"] for p in body["data"]["payload"]["packages"] if p["target"]}
    assert "zone-late" not in zones
    live = [c for c in prov.calls if c[0] == "live"]
    assert live and live[0][1:3] == (36.8, 10.1) and live[0][4] == TODAY


def test_live_farm_rejects_other_days(farms):
    client, _, _ = farms
    r = client.get("/api/farms/north-farm/decision", params={"day": "2026-06-10"})
    assert r.status_code == 422 and "only today" in r.json()["detail"]


def test_missing_irrigation_history_is_a_clear_409(farms):
    client, _, _ = farms
    for path in ("decision", "water-balance"):
        r = client.get(f"/api/farms/bare-farm/{path}")
        assert r.status_code == 409 and "irrigation history" in r.json()["detail"]


def test_real_farm_without_meter_has_no_anomaly_data(farms):
    client, _, _ = farms
    body = client.get("/api/farms/north-farm/anomalies").json()
    assert body["meta"]["status"] == "no_meter_data" and body["data"]["events"] == []


def test_climate_and_suitability_per_farm(farms, tmp_path, monkeypatch):
    client, prov, _ = farms
    monkeypatch.setattr(service, "RESULTS_DIR", tmp_path)
    r = client.get("/api/farms/north-farm/climate")
    assert r.status_code == 404 and "--farm north-farm" in r.json()["detail"]
    r = client.get("/api/farms/north-farm/suitability")
    assert r.status_code == 409 and "suitability_candidates" in r.json()["detail"]
    demo = client.get("/api/farms/demo-farm/suitability").json()
    assert demo["meta"]["years"] == [2015, 2024]


def test_unknown_farm_is_404(farms):
    client, _, _ = farms
    r = client.get("/api/farms/nowhere/decision")
    assert r.status_code == 404 and "demo-farm" in r.json()["detail"]


def test_weather_outage_is_503_not_invented(tmp_path):
    p = profile("north-farm", assumed_past_irrigation=ASSUMED)
    client, _, _ = build(tmp_path, p, provider=OfflineProvider(fail_live=True))
    r = client.get("/api/farms/north-farm/decision")
    assert r.status_code == 503 and "forecast service down" in r.json()["detail"]


def test_demo_routes_unchanged_and_legacy_routes_follow_default(farms, monkeypatch):
    client, _, _ = farms
    a = client.get("/api/farms/demo-farm/decision", params={"day": "2025-06-15"}).json()
    b = client.get("/api/decision", params={"day": "2025-06-15"}).json()
    assert a["data"]["payload"] == b["data"]["payload"] and a["meta"]["demo"] is True
    monkeypatch.setenv("QATRA_DEFAULT_FARM", "north-farm")
    assert client.get("/api/farm").json()["data"]["farm_id"] == "north-farm"


def test_assistant_per_farm(farms, monkeypatch):
    from types import SimpleNamespace

    from qatra_ai.assistant.assistant import QatraAssistant

    client, _, _ = farms
    refusal = SimpleNamespace(content=[], stop_reason="refusal", model="x")
    fake = SimpleNamespace(
        beta=SimpleNamespace(messages=SimpleNamespace(create=lambda **kw: refusal))
    )
    monkeypatch.setattr(service, "QatraAssistant", lambda ctx: QatraAssistant(ctx, client=fake))
    body = client.post("/api/farms/north-farm/assistant", json={"question": "What first?"}).json()
    assert body["meta"]["farm_id"] == "north-farm" and body["data"]["used_fallback"]


def test_harvested_annual_zone_is_left_out_not_a_crash(farms):
    """Regression: on 2025-08-01 the demo potato season is over; the old API raised a 500."""
    client, _, _ = farms
    body = client.get("/api/farms/demo-farm/decision", params={"day": "2025-08-01"}).json()
    assert any("potato-south: potato season ends" in n for n in body["meta"]["inactive_zones"])
    targets = {p["target"] for p in body["data"]["payload"]["packages"] if p["target"]}
    assert "potato-south" not in targets
    wb = client.get("/api/farms/demo-farm/water-balance", params={"day": "2025-08-01"}).json()
    assert set(wb["data"]) == {"olive-north", "tomato-east"}


class NoSoilMapProvider(OfflineProvider):
    def soil(self, lat, lon):
        from qatra_ai.service.data import SoilUnavailableError

        raise SoilUnavailableError("no SoilGrids prediction at 0-5cm", no_data_here=True)


def test_farm_soil_from_profile_is_used_and_labelled(tmp_path):
    measured = profile(
        "lab-farm",
        assumed_past_irrigation=ASSUMED,
        soil={"theta_fc": 0.31, "theta_wp": 0.16, "source": "test lab"},
    )
    texture = profile("tex-farm", assumed_past_irrigation=ASSUMED)  # template: texture analysis
    client, _, _ = build(tmp_path, measured, texture, provider=NoSoilMapProvider())
    soil = client.get("/api/farms/lab-farm").json()["data"]["soil"]
    assert (soil["theta_fc"], soil["data_class"], soil["source"]) == (0.31, "measured", "test lab")
    soil = client.get("/api/farms/tex-farm").json()["data"]["soil"]
    assert soil["data_class"] == "inferred" and soil["method"] == "saxton_rawls_2006"
    assert soil["source"].startswith("farm texture analysis")
    assert client.get("/api/farms/lab-farm/decision").status_code == 200


def test_no_soil_anywhere_is_a_clear_409(tmp_path):
    p = profile("town-farm", assumed_past_irrigation=ASSUMED)
    del p["soil"]
    client, _, _ = build(tmp_path, p, provider=NoSoilMapProvider())
    r = client.get("/api/farms/town-farm/decision")
    assert r.status_code == 409 and "Add `soil:`" in r.json()["detail"]

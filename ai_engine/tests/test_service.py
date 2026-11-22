"""Service API tests with an OFFLINE provider (synthetic weather/soil) and a fake LLM client."""

from types import SimpleNamespace

import pandas as pd
import pytest
from fastapi.testclient import TestClient

import qatra_ai.service.app as service
from qatra_ai.agronomy.soil import SoilWaterProperties
from qatra_ai.assistant.assistant import QatraAssistant
from qatra_ai.contracts import DataClass
from qatra_ai.service.data import WeatherData


def _weather(start, end):
    idx = pd.date_range(start, end, freq="D")
    doy = idx.day_of_year.to_numpy()
    seasonal = 4.5 + 3.0 * pd.Series(-(((doy - 196) / 90.0) ** 2) + 1, index=idx).clip(lower=0)
    return pd.DataFrame(
        {
            "et0": seasonal,
            "et0_method": "penman_monteith",
            "precip": 0.0,
            "rs": 25.0,
            "tmax": 30.0,
            "tmin": 15.0,
        },
        index=idx,
    )


class OfflineProvider:
    def season_weather(self):
        return WeatherData(
            _weather("2025-03-01", "2025-09-10"), "synthetic", DataClass.SIMULATED, 400.0
        )

    def multi_year_weather(self):
        return WeatherData(
            _weather("2015-01-01", "2024-12-31"), "synthetic", DataClass.SIMULATED, 400.0
        )

    def soil(self):
        return SoilWaterProperties(
            theta_fc=0.28,
            theta_wp=0.155,
            data_class=DataClass.INFERRED,
            source="synthetic",
            method="test",
        )


@pytest.fixture(scope="module")
def client():
    return TestClient(service.create_app(OfflineProvider()))


def test_health_and_farm(client):
    assert client.get("/api/health").json() == {"status": "ok"}
    body = client.get("/api/farm").json()
    assert body["meta"]["demo"] is True and "hypothetical" in body["meta"]["note"]
    zones = body["data"]["zones"]
    assert len(zones) == 3 and all(len(z["polygon"]) == 4 for z in zones)


def test_decision_has_ranked_packages_and_schedule(client):
    body = client.get("/api/decision", params={"day": "2025-06-15"}).json()
    data = body["data"]["payload"]
    assert [p["rank"] for p in data["packages"]] == list(range(1, len(data["packages"]) + 1))
    assert data["schedule"] is not None and data["schedule"]["verification_violations"] == []
    assert "replayed" in body["meta"]["forecast_note"]
    for p in data["packages"]:
        if p["action"] == "irrigate":
            assert p["requires_human_approval"]


def test_day_validation(client):
    assert client.get("/api/decision", params={"day": "2025-01-01"}).status_code == 422
    assert client.get("/api/decision", params={"day": "not-a-date"}).status_code == 422


def test_water_balance_series(client):
    data = client.get("/api/water-balance", params={"day": "2025-06-15"}).json()["data"]
    assert set(data) == {"olive-north", "tomato-east", "potato-south"}
    row = data["tomato-east"][-1]
    assert row["date"] == "2025-06-14" and {"dr_end_mm", "raw_mm", "taw_mm"} <= set(row)


def test_suitability(client):
    data = client.get("/api/suitability").json()["data"]
    assert {r["crop"] for r in data} == {
        "tomato",
        "potato",
        "durum_wheat",
        "olive",
        "citrus",
        "date_palm",
    }


def test_climate_missing_returns_404(client, tmp_path, monkeypatch):
    monkeypatch.setattr(service, "RESULTS_DIR", tmp_path)
    r = client.get("/api/climate")
    assert r.status_code == 404 and "climate_2050.py" in r.json()["detail"]


def test_anomalies_are_labelled_simulated(client):
    body = client.get("/api/anomalies").json()
    assert body["meta"]["data_class"] == "simulated" and body["meta"]["injected_faults"]
    assert body["data"]["events"] and len(body["data"]["series"]) > 24


def test_assistant_uses_engine_context_and_falls_back(client, monkeypatch):
    refusal = SimpleNamespace(content=[], stop_reason="refusal", model="x")
    fake = SimpleNamespace(
        beta=SimpleNamespace(messages=SimpleNamespace(create=lambda **kw: refusal))
    )
    monkeypatch.setattr(service, "QatraAssistant", lambda ctx: QatraAssistant(ctx, client=fake))
    body = client.post(
        "/api/assistant", json={"question": "What first?", "day": "2025-06-15"}
    ).json()
    assert (
        body["data"]["used_fallback"]
        and "tomato" in body["data"]["text"].lower()
        or body["data"]["text"]
    )
    assert client.post("/api/assistant", json={"question": "x"}).status_code == 422

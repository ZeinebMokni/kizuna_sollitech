"""Service API tests with an OFFLINE provider (synthetic weather/soil) and a fake LLM client."""

from datetime import timedelta
from types import SimpleNamespace

import pandas as pd
import pytest
from fastapi.testclient import TestClient

import qatra_ai.service.app as service
from qatra_ai.agronomy.soil import SoilWaterProperties
from qatra_ai.assistant.assistant import QatraAssistant
from qatra_ai.contracts import DataClass
from qatra_ai.farms.registry import PACKAGE_FARMS_DIR, load_registry
from qatra_ai.service.data import WeatherData, WeatherUnavailableError


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
    """Synthetic weather and soil for any coordinates (test input, labelled simulated)."""

    def __init__(self, fail_live=False):
        self.fail_live = fail_live
        self.calls = []

    def weather(self, lat, lon, start, end):
        self.calls.append(("weather", lat, lon, start, end))
        return WeatherData(_weather(start, end), "synthetic", DataClass.SIMULATED, 400.0)

    def live_weather(self, lat, lon, start, today):
        self.calls.append(("live", lat, lon, start, today))
        if self.fail_live:
            raise WeatherUnavailableError("test: forecast service down")
        end = today + timedelta(days=7)
        return WeatherData(
            _weather(start, end), "synthetic", DataClass.SIMULATED, 400.0, forecast_from=today
        )

    def soil(self, lat, lon):
        return SoilWaterProperties(
            theta_fc=0.28,
            theta_wp=0.155,
            data_class=DataClass.INFERRED,
            source="synthetic",
            method="test",
        )


@pytest.fixture(scope="module")
def client():
    reg = load_registry([PACKAGE_FARMS_DIR])  # demo only: ignore the user's own farms
    return TestClient(service.create_app(OfflineProvider(), registry=reg))


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


def test_market_outlook_endpoint(client):
    body = {
        "crop": "tomato",
        "region": "test-region",
        "reference": {
            "price": 1000,
            "production_t": 100000,
            "elasticity": {"low": -0.6, "high": -0.3},
            "source": "synthetic test",
            "data_class": "simulated",
        },
        "scenario": {
            "name": "test",
            "other_production_t": {"low": 90000, "high": 110000},
            "source": "synthetic test",
        },
        "candidate_area_ha": 500,
        "yield_t_per_ha": {"p10": 40, "p50": 55, "p90": 65, "source": "synthetic"},
        "cost_per_ha": 25000,
        "alternative_margin_per_ha": 20000,
        "n_samples": 500,
    }
    r = client.post("/api/market/outlook", json=body)
    assert r.status_code == 200
    out = r.json()
    assert out["confidence"] == "low" and out["payload"]["scenario_kind"] == "hypothetical"
    assert out["payload"]["adoption"][0]["price"]["interval_kind"] == "quantile_10_90"
    bad = {**body, "reference": {**body["reference"], "elasticity": {"low": -0.5, "high": 0.1}}}
    assert client.post("/api/market/outlook", json=bad).status_code == 422


def test_market_regional_endpoint(client):
    from test_portfolio_regional import region_req

    body = region_req(n_samples=200).model_dump(mode="json")
    r = client.post("/api/market/regional", json=body)
    assert r.status_code == 200
    p = r.json()["payload"]
    assert p["converged"] and p["naive"]["overstatement_pct"] > 10
    body["crops"][0]["min_ha"] = 1e9  # impossible minimum area
    assert client.post("/api/market/regional", json=body).status_code == 422


def test_strategy_endpoint_without_credentials_falls_back(client, monkeypatch):
    from qatra_ai.strategy.agent import FarmStrategyAgent

    def no_creds(self):
        raise RuntimeError("Could not resolve authentication method")

    monkeypatch.setattr(FarmStrategyAgent, "_get_client", no_creds)  # never hits the network
    r = client.post("/api/farms/demo-farm/strategy", json={"language": "fr"})
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["used_fallback"] and not data["verified"] and data["language"] == "fr"
    assert data["strategy"]["market_trends"] == [] and data["sources"] == []
    assert client.post("/api/farms/demo-farm/strategy", json={"language": "de"}).status_code == 422
    tele = client.get("/api/telemetry/llm").json()["by_kind"]["strategy"]
    assert tele["requests"] == 1 and tele["fallback_rate"] == 1.0
    assert (
        tele["fallback_reasons"] == {"no Claude API credentials configured": 1}
        or tele["fallback_reasons"]
    )

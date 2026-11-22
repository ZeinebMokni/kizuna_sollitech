import uuid

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_register_login_and_farm_crud():
    suffix = uuid.uuid4().hex
    email = f"farmer-{suffix}@example.com"

    registration = client.post(
        "/auth/register",
        json={
            "email": email,
            "password": "A-strong-password-2026",
            "full_name": "Foundation Farmer",
            "locale": "fr",
        },
    )
    assert registration.status_code == 201, registration.text

    login = client.post(
        "/auth/login",
        json={"email": email, "password": "A-strong-password-2026"},
    )
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    me = client.get("/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["email"] == email
    assert "farmer" in me.json()["roles"]

    farm = client.post(
        "/farms",
        headers=headers,
        json={
            "name": f"Test Farm {suffix}",
            "code": f"TF-{suffix[:8]}",
            "country_code": "TN",
            "governorate": "sidi_bouzid",
            "timezone": "Africa/Tunis",
        },
    )
    assert farm.status_code == 201, farm.text
    farm_id = farm.json()["id"]

    parcel = client.post(
        f"/farms/{farm_id}/parcels",
        headers=headers,
        json={
            "name": "North parcel",
            "boundary": {
                "type": "Polygon",
                "coordinates": [
                    [
                        [9.47, 35.68],
                        [9.48, 35.68],
                        [9.48, 35.69],
                        [9.47, 35.69],
                        [9.47, 35.68],
                    ]
                ],
            },
        },
    )
    assert parcel.status_code == 201, parcel.text
    parcel_id = parcel.json()["id"]

    zone = client.post(
        f"/farms/{farm_id}/parcels/{parcel_id}/zones",
        headers=headers,
        json={
            "name": "Zone A",
            "irrigation_method": "drip",
            "area_ha": 1.25,
            "emitter_flow_lph": 2.0,
            "application_efficiency": 0.90,
            "design_flow_m3h": 5.0,
        },
    )
    assert zone.status_code == 201, zone.text

    listing = client.get("/farms", headers=headers)
    assert listing.status_code == 200
    assert any(item["id"] == farm_id for item in listing.json())


def test_weather_provenance_and_duplicate_rejection():
    suffix = uuid.uuid4().hex
    email = f"weather-{suffix}@example.com"
    registration = client.post(
        "/auth/register",
        json={
            "email": email,
            "password": "A-strong-password-2026",
            "full_name": "Weather Farmer",
        },
    )
    assert registration.status_code == 201
    login = client.post(
        "/auth/login",
        json={"email": email, "password": "A-strong-password-2026"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    sources = client.get("/data/sources", headers=headers)
    assert sources.status_code == 200
    assert "nasa_power" in {s["code"] for s in sources.json()}

    payload = {
        "observation_date": "2026-11-22",
        "latitude": "35.10000",
        "longitude": "9.30000",
        "tmin_c": "12.5",
        "tmax_c": "24.0",
        "precipitation_mm": "0",
        "solar_radiation_mj_m2_day": "18.25",
        "wind_m_s": "2.4",
        "et0_mm": "3.1",
        "source_code": "nasa_power",
        "data_class": "inferred",
        "retrieved_at": "2026-11-22T05:00:00Z",
        "method": "NASA POWER daily point retrieval",
    }
    first = client.post("/data/weather", headers=headers, json=payload)
    assert first.status_code == 201, first.text
    assert first.json()["source_code"] == "nasa_power"

    duplicate = client.post("/data/weather", headers=headers, json=payload)
    assert duplicate.status_code == 409

    listing = client.get(
        "/data/weather",
        headers=headers,
        params={
            "start": "2026-11-22",
            "end": "2026-11-22",
            "latitude": "35.10000",
            "longitude": "9.30000",
        },
    )
    assert listing.status_code == 200
    assert len(listing.json()) == 1

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
    latitude = f"35.{int(suffix[:2], 16):05d}"
    longitude = f"9.{int(suffix[2:4], 16):05d}"
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
        "latitude": latitude,
        "longitude": longitude,
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
            "latitude": latitude,
            "longitude": longitude,
        },
    )
    assert listing.status_code == 200
    assert len(listing.json()) == 1


def test_device_sensor_measurement_and_irrigation_ingestion():
    suffix = uuid.uuid4().hex
    email = f"field-{suffix}@example.com"
    registration = client.post(
        "/auth/register",
        json={
            "email": email,
            "password": "A-strong-password-2026",
            "full_name": "Field Farmer",
        },
    )
    assert registration.status_code == 201
    login = client.post(
        "/auth/login",
        json={"email": email, "password": "A-strong-password-2026"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    farm = client.post(
        "/farms",
        headers=headers,
        json={
            "name": f"Field Farm {suffix}",
            "code": f"FF-{suffix[:8]}",
            "timezone": "Africa/Tunis",
        },
    )
    assert farm.status_code == 201, farm.text
    farm_id = farm.json()["id"]

    parcel = client.post(
        f"/farms/{farm_id}/parcels",
        headers=headers,
        json={
            "name": "Field Parcel",
            "boundary": {
                "type": "Polygon",
                "coordinates": [[
                    [9.40, 35.60],
                    [9.41, 35.60],
                    [9.41, 35.61],
                    [9.40, 35.61],
                    [9.40, 35.60],
                ]],
            },
        },
    )
    assert parcel.status_code == 201, parcel.text
    parcel_id = parcel.json()["id"]

    zone = client.post(
        f"/farms/{farm_id}/parcels/{parcel_id}/zones",
        headers=headers,
        json={
            "name": "South Zone",
            "irrigation_method": "drip",
            "area_ha": "0.8000",
            "design_flow_m3h": "2.500",
        },
    )
    assert zone.status_code == 201, zone.text
    zone_id = zone.json()["id"]

    device = client.post(
        f"/farms/{farm_id}/devices",
        headers=headers,
        json={
            "external_id": f"esp32-{suffix}",
            "name": "ESP32 test controller",
            "firmware_version": "1.0.0",
        },
    )
    assert device.status_code == 201, device.text
    device_id = device.json()["id"]
    api_key = device.json()["api_key"]

    sensor = client.post(
        f"/farms/{farm_id}/devices/{device_id}/sensors",
        headers=headers,
        json={
            "external_id": "probe-1",
            "zone_id": zone_id,
            "kind": "soil_moisture",
            "unit": "%",
            "calibration_status": "calibrated",
            "calibration_metadata": "Test probe calibration",
        },
    )
    assert sensor.status_code == 201, sensor.text

    measurement_payload = {
        "sensor_external_id": "probe-1",
        "observed_at": "2026-11-22T04:00:00Z",
        "value": "21.5",
        "unit": "%",
        "quality": "valid",
        "quality_note": "within range",
    }
    measurement = client.post(
        f"/farms/{farm_id}/devices/{device_id}/measurements",
        headers={"X-Device-Key": api_key},
        json=measurement_payload,
    )
    assert measurement.status_code == 200, measurement.text
    assert measurement.json()["zone_id"] == zone_id

    duplicate = client.post(
        f"/farms/{farm_id}/devices/{device_id}/measurements",
        headers={"X-Device-Key": api_key},
        json=measurement_payload,
    )
    assert duplicate.status_code == 200
    assert duplicate.json()["id"] == measurement.json()["id"]

    event_payload = {
        "zone_id": zone_id,
        "started_at": "2026-11-22T05:00:00Z",
        "ended_at": "2026-11-22T05:30:00Z",
        "volume_m3": "12.500",
        "source": "meter",
    }
    event = client.post(
        f"/farms/{farm_id}/irrigation-events",
        headers=headers,
        json=event_payload,
    )
    assert event.status_code == 201, event.text

    duplicate_event = client.post(
        f"/farms/{farm_id}/irrigation-events",
        headers=headers,
        json=event_payload,
    )
    assert duplicate_event.status_code == 409


def test_decision_recommendation_requires_evidence_and_records_approval():
    suffix = uuid.uuid4().hex
    email = f"decision-{suffix}@example.com"
    registration = client.post(
        "/auth/register",
        json={
            "email": email,
            "password": "A-strong-password-2026",
            "full_name": "Decision Farmer",
        },
    )
    assert registration.status_code == 201
    login = client.post(
        "/auth/login",
        json={"email": email, "password": "A-strong-password-2026"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    farm = client.post(
        "/farms",
        headers=headers,
        json={
            "name": f"Decision Farm {suffix}",
            "code": f"DF-{suffix[:8]}",
            "timezone": "Africa/Tunis",
        },
    )
    assert farm.status_code == 201, farm.text
    farm_id = farm.json()["id"]

    parcel = client.post(
        f"/farms/{farm_id}/parcels",
        headers=headers,
        json={
            "name": "Decision Parcel",
            "boundary": {
                "type": "Polygon",
                "coordinates": [[
                    [9.40, 35.60],
                    [9.41, 35.60],
                    [9.41, 35.61],
                    [9.40, 35.61],
                    [9.40, 35.60],
                ]],
            },
        },
    )
    assert parcel.status_code == 201, parcel.text
    parcel_id = parcel.json()["id"]
    zone = client.post(
        f"/farms/{farm_id}/parcels/{parcel_id}/zones",
        headers=headers,
        json={
            "name": "Decision Zone",
            "irrigation_method": "drip",
            "area_ha": "1.0000",
        },
    )
    assert zone.status_code == 201, zone.text
    zone_id = zone.json()["id"]

    generated = client.post(
        f"/farms/{farm_id}/recommendations/run",
        headers=headers,
        json={"zone_id": zone_id, "include_model_fallback": False},
    )
    assert generated.status_code == 200, generated.text
    recommendation = generated.json()
    assert recommendation["confidence"] == "insufficient_evidence"
    assert recommendation["payload"]["action"] == "insufficient_evidence"
    assert len(recommendation["inputs_hash"]) == 64
    assert recommendation["payload"]["requires_human_approval"] is False

    listing = client.get(f"/farms/{farm_id}/recommendations", headers=headers)
    assert listing.status_code == 200
    assert listing.json()[0]["id"] == recommendation["id"]

    approval = client.post(
        f"/farms/{farm_id}/recommendations/{recommendation['id']}/approval",
        headers=headers,
        json={"decision": "rejected", "note": "More field evidence is required"},
    )
    assert approval.status_code == 200, approval.text
    assert approval.json()["decision"] == "rejected"

    resolved = client.post(
        f"/farms/{farm_id}/recommendations/{recommendation['id']}/approval",
        headers=headers,
        json={"decision": "approved"},
    )
    assert resolved.status_code == 409

import uuid

from fastapi.testclient import TestClient

from app.main import app
from app.modules.devices.mqtt import MqttTelemetryError, parse_payload, parse_topic
from app.modules.devices.routes import canonical_command_payload, sign_command_payload

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
    listed_devices = client.get(f"/farms/{farm_id}/devices", headers=headers)
    assert listed_devices.status_code == 200
    assert listed_devices.json()[0]["external_id"] == f"esp32-{suffix}"
    listed_measurements = client.get(
        f"/farms/{farm_id}/measurements",
        headers=headers,
    )
    assert listed_measurements.status_code == 200
    assert listed_measurements.json()[0]["sensor_external_id"] == "probe-1"


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


def test_advanced_satellite_climate_and_incident_evidence(monkeypatch):
    suffix = uuid.uuid4().hex
    email = f"advanced-{suffix}@example.com"
    assert client.post(
        "/auth/register",
        json={
            "email": email,
            "password": "A-strong-password-2026",
            "full_name": "Advanced Farmer",
        },
    ).status_code == 201
    login = client.post(
        "/auth/login",
        json={"email": email, "password": "A-strong-password-2026"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    farm = client.post(
        "/farms",
        headers=headers,
        json={"name": f"Advanced Farm {suffix}", "code": f"AF-{suffix[:8]}"},
    )
    assert farm.status_code == 201, farm.text
    farm_id = farm.json()["id"]

    parcel = client.post(
        f"/farms/{farm_id}/parcels",
        headers=headers,
        json={
            "name": "Advanced Parcel",
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

    satellite = client.post(
        f"/farms/{farm_id}/satellite-observations",
        headers=headers,
        json={
            "parcel_id": parcel_id,
            "observed_at": "2026-11-22T10:00:00Z",
            "acquisition_date": "2026-11-22",
            "provider": "Copernicus",
            "product": "Sentinel-2",
            "ndvi": "0.62",
            "cloud_pct": "4.5",
            "resolution_m": "10",
            "scene_id": "S2-test-001",
        },
    )
    assert satellite.status_code == 200, satellite.text
    assert satellite.json()["data_class"] == "remote_sensed"

    climate = client.post(
        f"/farms/{farm_id}/climate-scenarios",
        headers=headers,
        json={
            "name": "Drier hot test",
            "kind": "hypothetical",
            "temperature_delta_c": 2.0,
            "precipitation_pct": -20,
            "radiation_pct": 5,
        },
    )
    assert climate.status_code == 200, climate.text
    assert climate.json()["kind"] == "hypothetical"
    assert climate.json()["limitations"][0].startswith("Scenario")

    incident = client.post(
        f"/farms/{farm_id}/incidents",
        headers=headers,
        json={
            "incident_type": "pump_downtime",
            "occurred_at": "2026-11-22T08:00:00Z",
            "description": "Pump stopped after a maintenance alarm and no output was measured.",
        },
    )
    assert incident.status_code == 200, incident.text
    incident_id = incident.json()["id"]
    assert incident.json()["verification_status"] == "unverified"

    evidence = client.post(
        f"/farms/{farm_id}/incidents/{incident_id}/evidence",
        headers=headers,
        json={
            "evidence_type": "photo",
            "description": "Photo of the pump controller error screen",
            "source": "farmer report",
            "observed_at": "2026-11-22T08:10:00Z",
        },
    )
    assert evidence.status_code == 200, evidence.text
    assert evidence.json()["verification"] == "unverified"
    listed_incidents = client.get(f"/farms/{farm_id}/incidents", headers=headers)
    assert listed_incidents.status_code == 200
    assert listed_incidents.json()[0]["id"] == incident_id

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "model": {
                    "model_id": "lp_aquifer_allocation",
                    "version": "0.1.0",
                },
                "payload": {"strategies": []},
            }

    monkeypatch.setattr(
        "app.modules.advanced.routes.httpx.post",
        lambda *args, **kwargs: FakeResponse(),
    )
    allocation = client.post(
        f"/farms/{farm_id}/optimization-runs",
        headers=headers,
        json={
            "period_label": "2026-Q4-test",
            "farms": [
                {
                    "farm_id": "farm-a",
                    "aquifer_id": "aquifer-a",
                    "blocks": [{
                        "block_id": "block-a",
                        "crop": "olive",
                        "area_ha": 2,
                        "demand_m3": 100,
                    }],
                    "pump_capacity_m3": 100,
                }
            ],
            "aquifers": [
                {
                    "aquifer_id": "aquifer-a",
                    "sustainable_yield_m3": 200,
                    "source_note": "test policy input",
                }
            ],
        },
    )
    assert allocation.status_code == 200, allocation.text
    assert len(allocation.json()["inputs_hash"]) == 64
    assert "not an allocation order" in allocation.json()["disclaimer"]


def test_actuation_command_requires_human_approval_and_expires():
    suffix = uuid.uuid4().hex
    email = f"actuation-{suffix}@example.com"
    assert client.post(
        "/auth/register",
        json={
            "email": email,
            "password": "A-strong-password-2026",
            "full_name": "Actuation Farmer",
        },
    ).status_code == 201
    login = client.post(
        "/auth/login",
        json={"email": email, "password": "A-strong-password-2026"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    farm = client.post(
        "/farms",
        headers=headers,
        json={"name": f"Actuation Farm {suffix}", "code": f"AF-{suffix[:8]}"},
    )
    farm_id = farm.json()["id"]
    parcel = client.post(
        f"/farms/{farm_id}/parcels",
        headers=headers,
        json={
            "name": "Actuation Parcel",
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
    parcel_id = parcel.json()["id"]
    zone = client.post(
        f"/farms/{farm_id}/parcels/{parcel_id}/zones",
        headers=headers,
        json={
            "name": "Actuation Zone",
            "irrigation_method": "drip",
            "area_ha": "1.0000",
        },
    )
    zone_id = zone.json()["id"]
    device = client.post(
        f"/farms/{farm_id}/devices",
        headers=headers,
        json={"external_id": f"actuator-{suffix}", "name": "Test actuator"},
    )
    device_id = device.json()["id"]

    oversize = client.post(
        f"/farms/{farm_id}/devices/{device_id}/commands",
        headers=headers,
        json={
            "zone_id": zone_id,
            "action": "open_valve",
            "duration_s": 999999,
        },
    )
    assert oversize.status_code == 422

    created = client.post(
        f"/farms/{farm_id}/devices/{device_id}/commands",
        headers=headers,
        json={
            "zone_id": zone_id,
            "action": "open_valve",
            "duration_s": 300,
            "max_volume_m3": "12.500",
        },
    )
    assert created.status_code == 201, created.text
    command = created.json()
    assert command["status"] == "pending"
    assert command["mqtt_topic"].endswith(f"/commands/{zone_id}")

    class FakeMqttPublisher:
        published = []

        def publish(self, topic, payload):
            self.published.append((topic, payload))

    publisher = FakeMqttPublisher()
    app.state.mqtt_service = publisher
    approved = client.post(
        f"/farms/{farm_id}/devices/{device_id}/commands/{command['id']}/approve",
        headers=headers,
        json={},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "sent"
    assert len(publisher.published) == 1

    verification = client.post(
        f"/farms/{farm_id}/devices/{device_id}/commands/{command['id']}/verify",
        headers=headers,
        json={
            "actual_started_at": "2026-11-22T05:00:00Z",
            "actual_ended_at": "2026-11-22T05:05:00Z",
            "actual_volume_m3": "12.000",
            "actual_flow_m3h": "144.000",
            "actual_pressure_kpa": "310.000",
        },
    )
    assert verification.status_code == 200, verification.text
    assert verification.json()["status"] == "completed"
    assert verification.json()["data_class"] == "measured"

    operating = client.post(
        f"/farms/{farm_id}/irrigation-operating-window",
        headers=headers,
        json={
            "zone_id": zone_id,
            "pv_kwh_available": "1.500",
            "battery_kwh_available": "5.000",
            "grid_available": True,
            "required_volume_m3": "12.000",
        },
    )
    assert operating.status_code == 200, operating.text
    assert operating.json()["allowed"] is False
    assert operating.json()["status"] == "blocked"
    assert operating.json()["actuation_note"] == "No command is sent by this endpoint"

    rejected = client.post(
        f"/farms/{farm_id}/devices/{device_id}/commands/{command['id']}/reject",
        headers=headers,
        json={"reason": "too soon"},
    )
    assert rejected.status_code == 409


def test_signed_command_canonical_payload():
    payload = {
        "action": "open_valve",
        "command_id": "11111111-1111-4111-8111-111111111111",
        "device_id": "22222222-2222-4222-8222-222222222222",
        "duration_s": 300,
        "expires_at": "2026-11-22T05:10:00+00:00",
        "farm_id": "33333333-3333-4333-8333-333333333333",
        "max_volume_m3": 12.5,
        "zone_id": "44444444-4444-4444-8444-444444444444",
    }
    canonical = canonical_command_payload(payload)
    assert canonical.startswith('{"action":"open_valve"')
    assert canonical.index('"command_id"') < canonical.index('"device_id"')
    assert len(sign_command_payload(payload, "test-secret")) == 64


def test_mqtt_topic_and_payload_validation():
    farm_id = uuid.uuid4()
    device_id = uuid.uuid4()
    topic = f"qatra/{farm_id}/{device_id}/measurements/probe-1"
    parsed = parse_topic(topic)
    assert parsed == (farm_id, device_id, "probe-1")

    payload = parse_payload(
        b'{"api_key":"test-key","observed_at":"2026-11-22T04:00:00Z",'
        b'"value":21.5,"unit":"%","quality":"valid","idempotency_key":"evt-1"}'
    )
    assert payload["_value"] == 21.5
    assert len(payload["_sha256"]) == 64

    try:
        parse_topic("qatra/not-a-uuid/device/measurements/probe")
    except MqttTelemetryError:
        pass
    else:
        raise AssertionError("invalid MQTT topic UUID must be rejected")

    try:
        parse_payload(b'{"api_key":"x","observed_at":"2026-11-22T04:00:00Z","value":"n/a","unit":"%"}')
    except MqttTelemetryError:
        pass
    else:
        raise AssertionError("non-numeric MQTT value must be rejected")

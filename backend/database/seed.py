"""Insert the minimum QATRA demo graph into PostgreSQL."""

from datetime import datetime, timezone

from .models import Alert, Agent, Decision, Device, Farm, FarmMembership, FarmZone, ImpactMeasurement, MarketplaceListing, TelemetryReading, User
from .session import SessionLocal, create_schema


def seed_demo() -> None:
    create_schema()
    with SessionLocal.begin() as session:
        farm = session.get(Farm, "farm-sbz-01")
        if farm is None:
            farm = Farm(
                id="farm-sbz-01",
                name="Domaine El-Baraka",
                governorate="Bizerte",
                delegation="Mateur",
                area_ha=15.3,
                center_geojson={"type": "Point", "coordinates": [9.665, 37.04]},
                privacy_mode="private",
            )
            session.add(farm)

        owner = session.query(User).filter_by(external_id="demo-farmer").one_or_none()
        if owner is None:
            owner = User(external_id="demo-farmer", display_name="Demo farmer", role="farmer", privacy_scope="private")
            session.add(owner)
            session.flush()
            session.add(FarmMembership(farm_id=farm.id, user_id=owner.id, role="owner"))

        agents = [
            ("water-agriculture", "Water and irrigation agent"),
            ("energy-optimizer", "Solar, battery and pump agent"),
            ("safety-guard", "Safety and human approval agent"),
            ("orchestrator", "Decision coordination agent"),
        ]
        for agent_id, focus in agents:
            if session.get(Agent, agent_id) is None:
                session.add(Agent(id=agent_id, name=agent_id, focus=focus, version="1.0"))

        zones = [
            ("zone-1", "Zone A - Oliviers Chemlali", "olive"),
            ("zone-2", "Zone B - Serres Tomates", "tomato"),
            ("zone-3", "Zone C - Grenadiers Gabsi", "pomegranate"),
            ("zone-4", "Zone D - Piments Baklouti", "pepper"),
            ("zone-5", "Zone E - Luzerne", "alfalfa"),
        ]
        for zone_id, name, crop in zones:
            if session.get(FarmZone, zone_id) is None:
                session.add(FarmZone(id=zone_id, farm_id=farm.id, name=name, crop_type=crop, status="healthy"))

        devices = [
            ("esp32-gateway-01", None, "gateway", "LoRa/Wi-Fi", "online"),
            ("soil-sensor-zone-1", "zone-1", "soil_sensor", "LoRa", "online"),
            ("soil-sensor-zone-2", "zone-2", "soil_sensor", "LoRa", "warning"),
            ("soil-sensor-zone-4", "zone-4", "soil_sensor", "LoRa", "alert"),
            ("solar-inverter-01", None, "solar_inverter", "Modbus", "online"),
            ("pump-01", None, "irrigation_pump", "Modbus", "online"),
            ("battery-bms-01", None, "battery_bms", "CAN", "online"),
        ]
        for device_id, zone_id, kind, protocol, status in devices:
            if session.get(Device, device_id) is None:
                session.add(Device(id=device_id, farm_id=farm.id, zone_id=zone_id, kind=kind, protocol=protocol, status=status))

        now = datetime.now(timezone.utc)
        readings = [
            ("soil-sensor-zone-1", "zone-1", {"soil_moisture_percent": 38, "temperature_c": 28.4, "battery_percent": 92}),
            ("soil-sensor-zone-2", "zone-2", {"soil_moisture_percent": 22, "temperature_c": 32.1, "battery_percent": 78}),
            ("soil-sensor-zone-4", "zone-4", {"soil_moisture_percent": 14, "temperature_c": 36.4, "battery_percent": 88}),
            ("solar-inverter-01", None, {"solar_production_kw": 14.8, "efficiency_percent": 97.4}),
            ("pump-01", None, {"pump_consumption_kw": 6.8, "flow_rate_m3h": 26.4}),
            ("battery-bms-01", None, {"battery_soc_percent": 89, "battery_power_kw": 4.5}),
        ]
        for device_id, zone_id, measurements in readings:
            exists = session.query(TelemetryReading).filter(TelemetryReading.device_id == device_id).first()
            if exists is None:
                session.add(TelemetryReading(device_id=device_id, zone_id=zone_id, recorded_at=now, measurements=measurements))

        alerts = [
            ("zone-2", "critical", "water", "Stress hydrique à confirmer", "Humidité du sol à 22 %, sous le seuil de 35 %.", "open"),
            ("zone-4", "critical", "water", "Stress hydrique critique", "Humidité du sol à 14 %, inspection et validation humaine requises.", "open"),
        ]
        for zone_id, severity, category, title, message, status in alerts:
            exists = session.query(Alert).filter(Alert.farm_id == farm.id, Alert.zone_id == zone_id, Alert.title == title, Alert.status == status).first()
            if exists is None:
                session.add(Alert(farm_id=farm.id, zone_id=zone_id, severity=severity, category=category, title=title, message=message, status=status))

        if session.query(Decision).filter(Decision.farm_id == farm.id, Decision.zone_id == "zone-4").first() is None:
            decision = Decision(
                farm_id=farm.id,
                zone_id="zone-4",
                agent_id="water-agriculture",
                decision_type="targeted_irrigation",
                status="approved",
                recommendation="Cycle goutte-à-goutte de 45 minutes après confirmation du capteur.",
                confidence=92,
                predicted_impact={"water_saved_liters_day": 1200, "yield_risk": "reduced"},
            )
            session.add(decision)
            session.flush()
            session.add(ImpactMeasurement(
                farm_id=farm.id,
                zone_id="zone-4",
                decision_id=decision.id,
                metric="water_consumption",
                baseline_value=5100,
                observed_value=3900,
                unit="L/day",
                source="irrigation meter + zone history",
            ))

        if session.get(MarketplaceListing, "listing-demo-olive") is None:
            session.add(MarketplaceListing(
                id="listing-demo-olive", farm_id=farm.id, zone_id="zone-1", crop_type="Huile d'olive vierge extra",
                quantity_kg=8500, asking_price_tnd_kg=24.5, cost_per_m2_tnd=1.82,
                expected_revenue_tnd=208250, expected_profit_tnd=112400,
            ))


if __name__ == "__main__":
    seed_demo()
    print("QATRA demo graph seeded")

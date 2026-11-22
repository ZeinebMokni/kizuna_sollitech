"""Platform-wide enumerations. Values are persisted as PostgreSQL enum types."""

from enum import StrEnum


class DataClass(StrEnum):
    """Provenance class of a piece of information (see docs/BLUEPRINT.md section 7)."""

    MEASURED = "measured"
    OFFICIAL = "official"
    FARMER_REPORTED = "farmer_reported"
    REMOTE_SENSED = "remote_sensed"
    INFERRED = "inferred"
    SIMULATED = "simulated"
    PROJECTED = "projected"


class RoleName(StrEnum):
    ADMIN = "admin"
    FARMER = "farmer"
    OPERATOR = "operator"
    ANALYST = "analyst"


class FarmRole(StrEnum):
    """Role of a user on one specific farm, from least to most privileged."""

    VIEWER = "viewer"
    OPERATOR = "operator"
    OWNER = "owner"

    @property
    def rank(self) -> int:
        return {"viewer": 0, "operator": 1, "owner": 2}[self.value]


class IrrigationMethod(StrEnum):
    DRIP = "drip"
    SPRINKLER = "sprinkler"
    SURFACE = "surface"
    PIVOT = "pivot"
    NONE = "none"


class DataSourceKind(StrEnum):
    API = "api"
    DEVICE = "device"
    MANUAL = "manual"
    MODEL = "model"
    SIMULATOR = "simulator"


class DeviceStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    MAINTENANCE = "maintenance"


class SensorKind(StrEnum):
    SOIL_MOISTURE = "soil_moisture"
    SOIL_TEMPERATURE = "soil_temperature"
    AIR_TEMPERATURE = "air_temperature"
    HUMIDITY = "humidity"
    WATER_FLOW = "water_flow"
    WATER_PRESSURE = "water_pressure"
    TANK_LEVEL = "tank_level"
    SOLAR_PRODUCTION = "solar_production"
    BATTERY_LEVEL = "battery_level"
    PUMP_STATUS = "pump_status"


class MeasurementQuality(StrEnum):
    VALID = "valid"
    SUSPECT = "suspect"
    INVALID = "invalid"
    MISSING = "missing"

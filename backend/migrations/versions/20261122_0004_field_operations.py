"""Add devices, sensors, measurements and irrigation event storage."""

import sqlalchemy as sa
from alembic import op

revision = "20261122_0004"
down_revision = "20261122_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text(
        "DO $$ BEGIN "
        "IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'device_status') THEN "
        "CREATE TYPE device_status AS ENUM ('active','inactive','maintenance'); "
        "END IF; END $$"
    ))
    op.execute(sa.text(
        "DO $$ BEGIN "
        "IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'sensor_kind') THEN "
        "CREATE TYPE sensor_kind AS ENUM "
        "('soil_moisture','soil_temperature','air_temperature','humidity','water_flow',"
        "'water_pressure','tank_level','solar_production','battery_level','pump_status'); "
        "END IF; END $$"
    ))
    op.execute(sa.text(
        "DO $$ BEGIN "
        "IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'measurement_quality') THEN "
        "CREATE TYPE measurement_quality AS ENUM ('valid','suspect','invalid','missing'); "
        "END IF; END $$"
    ))

    from app.core.db import Base
    from app.modules.devices import models as device_models  # noqa: F401

    tables = [
        device_models.Device.__table__,
        device_models.Sensor.__table__,
        device_models.SensorMeasurement.__table__,
        device_models.IrrigationEvent.__table__,
    ]
    Base.metadata.create_all(op.get_bind(), tables=tables)

    op.execute(
        sa.text(
            "SELECT create_hypertable("
            "'sensor_measurements', 'observed_at', "
            "if_not_exists => TRUE, migrate_data => TRUE)"
        )
    )
    op.execute(
        sa.text(
            "SELECT create_hypertable("
            "'irrigation_events', 'started_at', "
            "if_not_exists => TRUE, migrate_data => TRUE)"
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DROP TABLE IF EXISTS irrigation_events"))
    op.execute(sa.text("DROP TABLE IF EXISTS sensor_measurements"))
    op.execute(sa.text("DROP TABLE IF EXISTS sensors"))
    op.execute(sa.text("DROP TABLE IF EXISTS devices"))
    for type_name in ("measurement_quality", "sensor_kind", "device_status"):
        op.execute(sa.text(f"DROP TYPE IF EXISTS {type_name}"))

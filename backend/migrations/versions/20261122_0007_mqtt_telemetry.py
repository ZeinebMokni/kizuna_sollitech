"""Add MQTT communication logs and measurement idempotency support."""

import sqlalchemy as sa
from alembic import op

revision = "20261122_0007"
down_revision = "20261122_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app.core.db import Base
    from app.modules.devices import models as device_models  # noqa: F401

    Base.metadata.create_all(
        op.get_bind(),
        tables=[
            device_models.DeviceCommunication.__table__,
        ],
    )
    op.execute(
        sa.text(
            "ALTER TABLE sensor_measurements "
            "ADD COLUMN IF NOT EXISTS ingestion_idempotency_key VARCHAR(128)"
        )
    )
    op.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_sensor_measurements_ingestion_key "
            "ON sensor_measurements (ingestion_idempotency_key)"
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DROP TABLE IF EXISTS device_communications"))

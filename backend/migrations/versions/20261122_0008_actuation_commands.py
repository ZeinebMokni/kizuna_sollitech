"""Add approved, expiring, signed actuation commands."""

import sqlalchemy as sa
from alembic import op

revision = "20261122_0008"
down_revision = "20261122_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app.core.db import Base
    from app.modules.devices import models as device_models  # noqa: F401

    Base.metadata.create_all(
        op.get_bind(),
        tables=[device_models.ActuationCommand.__table__],
    )


def downgrade() -> None:
    op.execute(sa.text("DROP TABLE IF EXISTS actuation_commands"))

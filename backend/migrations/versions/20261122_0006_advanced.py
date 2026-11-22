"""Create satellite, allocation, climate and incident evidence tables."""

import sqlalchemy as sa
from alembic import op

revision = "20261122_0006"
down_revision = "20261122_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app.core.db import Base
    from app.modules.advanced import models as advanced_models  # noqa: F401

    Base.metadata.create_all(
        op.get_bind(),
        tables=[
            advanced_models.SatelliteObservation.__table__,
            advanced_models.OptimizationRun.__table__,
            advanced_models.ClimateScenario.__table__,
            advanced_models.Incident.__table__,
            advanced_models.EvidenceRecord.__table__,
        ],
    )


def downgrade() -> None:
    op.execute(sa.text("DROP TABLE IF EXISTS evidence_records"))
    op.execute(sa.text("DROP TABLE IF EXISTS incidents"))
    op.execute(sa.text("DROP TABLE IF EXISTS climate_scenarios"))
    op.execute(sa.text("DROP TABLE IF EXISTS optimization_runs"))
    op.execute(sa.text("DROP TABLE IF EXISTS satellite_observations"))

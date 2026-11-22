"""Add explainable recommendation and human approval records."""

import sqlalchemy as sa
from alembic import op

revision = "20261122_0005"
down_revision = "20261122_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app.core.db import Base
    from app.modules.recommendations import models as recommendation_models  # noqa: F401

    Base.metadata.create_all(
        op.get_bind(),
        tables=[
            recommendation_models.Recommendation.__table__,
            recommendation_models.RecommendationApproval.__table__,
        ],
    )


def downgrade() -> None:
    op.execute(sa.text("DROP TABLE IF EXISTS recommendation_approvals"))
    op.execute(sa.text("DROP TABLE IF EXISTS ai_recommendations"))

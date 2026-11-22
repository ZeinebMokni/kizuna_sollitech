"""Create the append-only audit log table."""

import sqlalchemy as sa
from alembic import op

revision = "20261122_0002"
down_revision = "20261122_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app.core.audit import AuditLog

    AuditLog.__table__.create(op.get_bind(), checkfirst=True)


def downgrade() -> None:
    op.execute(sa.text("DROP TABLE IF EXISTS audit_logs"))

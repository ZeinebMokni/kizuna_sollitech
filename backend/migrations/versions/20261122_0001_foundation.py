"""Create QATRA foundation tables and seed roles."""

import sqlalchemy as sa
from alembic import op

revision = "20261122_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb")
    op.execute(
        sa.text(
            "DO $$ BEGIN "
            "IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'role_name') THEN "
            "CREATE TYPE role_name AS ENUM ('admin','farmer','operator','analyst'); "
            "END IF; END $$"
        )
    )
    op.execute(
        sa.text(
            "DO $$ BEGIN "
            "IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'farm_role') THEN "
            "CREATE TYPE farm_role AS ENUM ('viewer','operator','owner'); "
            "END IF; END $$"
        )
    )
    op.execute(
        sa.text(
            "DO $$ BEGIN "
            "IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'irrigation_method') THEN "
            "CREATE TYPE irrigation_method AS ENUM "
            "('drip','sprinkler','surface','pivot','none'); "
            "END IF; END $$"
        )
    )
    op.execute(
        sa.text(
            "DO $$ BEGIN "
            "IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'data_class') THEN "
            "CREATE TYPE data_class AS ENUM "
            "('measured','official','farmer_reported','remote_sensed','"
            "inferred','simulated','projected'); "
            "END IF; END $$"
        )
    )
    op.execute(
        sa.text(
            "DO $$ BEGIN "
            "IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'data_source_kind') THEN "
            "CREATE TYPE data_source_kind AS ENUM "
            "('api','device','manual','model','simulator'); "
            "END IF; END $$"
        )
    )

    from app.core import audit as audit_models  # noqa: F401
    from app.core.db import Base
    from app.modules.data_sources import models as data_source_models  # noqa: F401
    from app.modules.data_sources import models_observations as observation_models  # noqa: F401
    from app.modules.farms import models as farm_models  # noqa: F401
    from app.modules.identity import models as identity_models  # noqa: F401

    Base.metadata.create_all(op.get_bind())
    op.execute(
        """
        INSERT INTO roles (id, name, description)
        VALUES
          (1, 'admin', 'Platform administrator'),
          (2, 'farmer', 'Farm owner or farmer'),
          (3, 'operator', 'Agricultural operator'),
          (4, 'analyst', 'Read-only analyst')
        ON CONFLICT (name) DO NOTHING
        """
    )


def downgrade() -> None:
    from app.core.db import Base

    Base.metadata.drop_all(op.get_bind())
    for type_name in (
        "data_source_kind",
        "data_class",
        "irrigation_method",
        "farm_role",
        "role_name",
    ):
        op.execute(f"DROP TYPE IF EXISTS {type_name}")

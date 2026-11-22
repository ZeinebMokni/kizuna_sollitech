"""Append-only audit trail.

The table is INSERT-only from the application's point of view (no update/delete code path).
In production, revoke UPDATE/DELETE on audit_logs from the application DB role.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, Identity, Index, String, Uuid, func
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.core.db import Base
from app.core.logging import request_id_var


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)  # no FK
    actor_type: Mapped[str] = mapped_column(String(16))
    action: Mapped[str] = mapped_column(String(64))
    entity_type: Mapped[str] = mapped_column(String(64))
    entity_id: Mapped[str | None] = mapped_column(String(64))
    farm_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)  # no FK
    before: Mapped[dict | None] = mapped_column(JSONB)
    after: Mapped[dict | None] = mapped_column(JSONB)
    ip: Mapped[str | None] = mapped_column(INET)
    request_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        Index("ix_audit_logs_entity", "entity_type", "entity_id"),
        Index("ix_audit_logs_farm_created", "farm_id", "created_at"),
        Index("ix_audit_logs_actor_created", "actor_user_id", "created_at"),
    )


def record_audit(
    db: Session,
    *,
    action: str,
    entity_type: str,
    entity_id: Any = None,
    actor_user_id: uuid.UUID | None = None,
    actor_type: str = "user",
    farm_id: uuid.UUID | None = None,
    before: dict | None = None,
    after: dict | None = None,
    ip: str | None = None,
) -> None:
    """Add an audit row to the current transaction (committed with the business change)."""
    db.add(
        AuditLog(
            actor_user_id=actor_user_id,
            actor_type=actor_type,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id is not None else None,
            farm_id=farm_id,
            before=before,
            after=after,
            ip=ip,
            request_id=request_id_var.get(),
        )
    )

import uuid

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TimestampMixin, pg_enum
from app.core.enums import DataSourceKind
from app.core.ids import uuid7


class DataSource(Base, TimestampMixin):
    """Registry of every origin of data in QATRA (APIs, devices, people, simulators)."""

    __tablename__ = "data_sources"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    code: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    provider: Mapped[str | None] = mapped_column(String(200))
    kind: Mapped[DataSourceKind] = mapped_column(pg_enum(DataSourceKind, "data_source_kind"))
    license: Mapped[str | None] = mapped_column(Text)
    terms_url: Mapped[str | None] = mapped_column(Text)
    spatial_resolution: Mapped[str | None] = mapped_column(String(100))
    temporal_resolution: Mapped[str | None] = mapped_column(String(100))
    methodology_url: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)

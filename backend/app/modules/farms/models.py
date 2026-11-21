import uuid
from datetime import datetime
from decimal import Decimal

from geoalchemy2 import Geometry, WKBElement
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base, TimestampMixin, pg_enum
from app.core.enums import DataClass, FarmRole, IrrigationMethod
from app.core.ids import uuid7


def _geom(kind: str, nullable: bool = False) -> Mapped:
    # spatial_index=False: GiST indexes are declared explicitly in __table_args__/migrations.
    return mapped_column(Geometry(kind, srid=4326, spatial_index=False), nullable=nullable)


class Farm(Base, TimestampMixin):
    __tablename__ = "farms"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    name: Mapped[str] = mapped_column(String(200))
    code: Mapped[str] = mapped_column(String(32), unique=True)
    country_code: Mapped[str] = mapped_column(String(2), server_default="TN")
    governorate: Mapped[str | None] = mapped_column(String(64))
    delegation: Mapped[str | None] = mapped_column(String(120))
    timezone: Mapped[str] = mapped_column(String(64), server_default="Africa/Tunis")
    currency: Mapped[str] = mapped_column(String(3), server_default="TND")
    centroid: Mapped[WKBElement | None] = _geom("POINT", nullable=True)
    elevation_m: Mapped[Decimal | None] = mapped_column(Numeric(7, 1))
    irrigation_scheme: Mapped[str | None] = mapped_column(String(200))
    notes: Mapped[str | None] = mapped_column(Text)
    data_class: Mapped[DataClass] = mapped_column(
        pg_enum(DataClass, "data_class"), server_default=DataClass.FARMER_REPORTED.value
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

    members: Mapped[list["FarmMember"]] = relationship(
        back_populates="farm", cascade="all, delete-orphan", passive_deletes=True
    )
    parcels: Mapped[list["Parcel"]] = relationship(
        back_populates="farm", cascade="all, delete-orphan", passive_deletes=True
    )

    __table_args__ = (Index("ix_farms_centroid", "centroid", postgresql_using="gist"),)


class FarmMember(Base):
    __tablename__ = "farm_members"

    farm_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("farms.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    farm_role: Mapped[FarmRole] = mapped_column(pg_enum(FarmRole, "farm_role"))
    granted_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    farm: Mapped[Farm] = relationship(back_populates="members")

    __table_args__ = (Index("ix_farm_members_user_id", "user_id"),)


class FarmBoundary(Base):
    """Versioned farm boundary. Exactly one row per farm has valid_to IS NULL (current)."""

    __tablename__ = "farm_boundaries"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    farm_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("farms.id", ondelete="CASCADE"))
    geom: Mapped[WKBElement] = _geom("MULTIPOLYGON")
    area_ha: Mapped[Decimal] = mapped_column(Numeric(12, 4))
    valid_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    data_class: Mapped[DataClass] = mapped_column(pg_enum(DataClass, "data_class"))
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("data_sources.id", ondelete="SET NULL")
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        Index("ix_farm_boundaries_geom", "geom", postgresql_using="gist"),
        Index("ix_farm_boundaries_farm_id", "farm_id"),
        Index(
            "uq_farm_boundaries_current",
            "farm_id",
            unique=True,
            postgresql_where=text("valid_to IS NULL"),
        ),
    )


class Parcel(Base, TimestampMixin):
    __tablename__ = "parcels"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    farm_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("farms.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(120))
    geom: Mapped[WKBElement] = _geom("MULTIPOLYGON")
    area_ha: Mapped[Decimal] = mapped_column(Numeric(12, 4))
    slope_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    land_tenure: Mapped[str | None] = mapped_column(String(64))
    notes: Mapped[str | None] = mapped_column(Text)
    data_class: Mapped[DataClass] = mapped_column(pg_enum(DataClass, "data_class"))

    farm: Mapped[Farm] = relationship(back_populates="parcels")
    zones: Mapped[list["IrrigationZone"]] = relationship(
        back_populates="parcel", cascade="all, delete-orphan", passive_deletes=True
    )

    __table_args__ = (
        UniqueConstraint("farm_id", "name", name="uq_parcels_farm_id_name"),
        Index("ix_parcels_geom", "geom", postgresql_using="gist"),
        Index("ix_parcels_farm_id", "farm_id"),
    )


class IrrigationZone(Base, TimestampMixin):
    __tablename__ = "irrigation_zones"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    parcel_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("parcels.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(120))
    geom: Mapped[WKBElement | None] = _geom("MULTIPOLYGON", nullable=True)
    area_ha: Mapped[Decimal] = mapped_column(Numeric(12, 4))
    irrigation_method: Mapped[IrrigationMethod] = mapped_column(
        pg_enum(IrrigationMethod, "irrigation_method")
    )
    emitter_flow_lph: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    emitters_per_m2: Mapped[Decimal | None] = mapped_column(Numeric(8, 3))
    application_efficiency: Mapped[Decimal | None] = mapped_column(Numeric(3, 2))
    design_flow_m3h: Mapped[Decimal | None] = mapped_column(Numeric(10, 3))
    notes: Mapped[str | None] = mapped_column(Text)
    data_class: Mapped[DataClass] = mapped_column(pg_enum(DataClass, "data_class"))

    parcel: Mapped[Parcel] = relationship(back_populates="zones")

    __table_args__ = (
        UniqueConstraint("parcel_id", "name", name="uq_irrigation_zones_parcel_id_name"),
        CheckConstraint(
            "application_efficiency IS NULL OR "
            "(application_efficiency > 0 AND application_efficiency <= 1)",
            name="efficiency_range",
        ),
        CheckConstraint("area_ha > 0", name="area_positive"),
        Index("ix_irrigation_zones_geom", "geom", postgresql_using="gist"),
        Index("ix_irrigation_zones_parcel_id", "parcel_id"),
    )

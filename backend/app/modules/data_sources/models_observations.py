import uuid
from datetime import date, datetime
from decimal import Decimal

from geoalchemy2 import Geometry, WKBElement
from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    SmallInteger,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TimestampMixin, pg_enum
from app.core.enums import DataClass
from app.core.ids import uuid7


class WeatherObservation(Base, TimestampMixin):
    __tablename__ = "weather_observations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    observation_date: Mapped[date] = mapped_column(Date)
    location: Mapped[WKBElement] = mapped_column(
        Geometry("POINT", srid=4326, spatial_index=False)
    )
    latitude: Mapped[Decimal] = mapped_column(Numeric(8, 5))
    longitude: Mapped[Decimal] = mapped_column(Numeric(9, 5))
    tmin_c: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    tmax_c: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    precipitation_mm: Mapped[Decimal | None] = mapped_column(Numeric(7, 2))
    solar_radiation_mj_m2_day: Mapped[Decimal | None] = mapped_column(Numeric(7, 3))
    wind_m_s: Mapped[Decimal | None] = mapped_column(Numeric(6, 3))
    et0_mm: Mapped[Decimal | None] = mapped_column(Numeric(7, 3))
    source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("data_sources.id", ondelete="RESTRICT")
    )
    data_class: Mapped[DataClass] = mapped_column(pg_enum(DataClass, "data_class"))
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    method: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        UniqueConstraint(
            "observation_date",
            "latitude",
            "longitude",
            "source_id",
            name="uq_weather_observation_point_day_source",
        ),
        Index(
            "ix_weather_observations_location",
            "location",
            postgresql_using="gist",
        ),
        Index(
            "ix_weather_observations_date_source",
            "observation_date",
            "source_id",
        ),
    )


class SoilProfileObservation(Base, TimestampMixin):
    __tablename__ = "soil_profile_observations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    farm_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("farms.id", ondelete="CASCADE")
    )
    location: Mapped[WKBElement] = mapped_column(
        Geometry("POINT", srid=4326, spatial_index=False)
    )
    latitude: Mapped[Decimal] = mapped_column(Numeric(8, 5))
    longitude: Mapped[Decimal] = mapped_column(Numeric(9, 5))
    depth_top_cm: Mapped[int] = mapped_column(SmallInteger)
    depth_bottom_cm: Mapped[int] = mapped_column(SmallInteger)
    sand_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    clay_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    soc_g_kg: Mapped[Decimal | None] = mapped_column(Numeric(6, 3))
    theta_fc: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    theta_wp: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("data_sources.id", ondelete="RESTRICT")
    )
    data_class: Mapped[DataClass] = mapped_column(pg_enum(DataClass, "data_class"))
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    method: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        Index("ix_soil_profile_location", "location", postgresql_using="gist"),
        Index("ix_soil_profile_farm_depth", "farm_id", "depth_top_cm", "depth_bottom_cm"),
    )

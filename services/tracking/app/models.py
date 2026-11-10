import enum
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    String,
    func,
    text,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base, TimestampMixin


class TripStatus(str, enum.Enum):
    planned = "planned"
    en_route = "en_route"
    arrived = "arrived"
    cancelled = "cancelled"


class Vehicle(TimestampMixin, Base):
    __tablename__ = "vehicles"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    license_plate: Mapped[str | None] = mapped_column(String(20), unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=true(), default=True)

    trips: Mapped[list["Trip"]] = relationship(back_populates="vehicle")


class Trip(TimestampMixin, Base):
    """A vehicle's drive to the job site of one CRM quote."""

    __tablename__ = "trips"
    __table_args__ = (
        # A vehicle can only be en route to one job at a time.
        Index(
            "uq_trips_vehicle_en_route",
            "vehicle_id",
            unique=True,
            postgresql_where=text("status = 'en_route'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    vehicle_id: Mapped[int] = mapped_column(
        ForeignKey("vehicles.id", ondelete="RESTRICT"), index=True
    )
    # IDs from the CRM service. Not foreign keys: the CRM lives in a separate database.
    quote_id: Mapped[int] = mapped_column(index=True)
    customer_id: Mapped[int] = mapped_column(index=True)
    # Job site address copied from the CRM quote when the trip is created.
    dest_street: Mapped[str | None] = mapped_column(String(255))
    dest_street2: Mapped[str | None] = mapped_column(String(255))
    dest_city: Mapped[str | None] = mapped_column(String(100))
    dest_state: Mapped[str | None] = mapped_column(String(100))
    dest_postal_code: Mapped[str | None] = mapped_column(String(20))
    status: Mapped[TripStatus] = mapped_column(
        Enum(
            TripStatus,
            name="trip_status",
            native_enum=False,
            create_constraint=True,
            length=20,
            values_callable=lambda e: [m.value for m in e],
        ),
        default=TripStatus.planned,
        server_default=TripStatus.planned.value,
        index=True,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    arrived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    vehicle: Mapped[Vehicle] = relationship(back_populates="trips")


class LocationPing(Base):
    """One GPS position report from a vehicle."""

    __tablename__ = "location_pings"
    __table_args__ = (
        CheckConstraint("latitude BETWEEN -90 AND 90", name="latitude_range"),
        CheckConstraint("longitude BETWEEN -180 AND 180", name="longitude_range"),
        CheckConstraint("speed_kph IS NULL OR speed_kph >= 0", name="speed_not_negative"),
        CheckConstraint(
            "heading_deg IS NULL OR (heading_deg >= 0 AND heading_deg < 360)",
            name="heading_range",
        ),
        Index("ix_location_pings_vehicle_recorded", "vehicle_id", "recorded_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id", ondelete="CASCADE"))
    trip_id: Mapped[int | None] = mapped_column(
        ForeignKey("trips.id", ondelete="SET NULL"), index=True
    )
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    speed_kph: Mapped[float | None] = mapped_column(Float)
    heading_deg: Mapped[float | None] = mapped_column(Float)
    # Time on the device when the position was taken.
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

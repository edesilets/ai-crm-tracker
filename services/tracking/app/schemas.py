from datetime import UTC, datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .models import TripStatus


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------- vehicles ----------


class VehicleCreate(BaseModel):
    name: Annotated[str, Field(min_length=1, max_length=100)]
    license_plate: Annotated[str | None, Field(default=None, max_length=20)]
    is_active: bool = True


class VehicleUpdate(BaseModel):
    name: Annotated[str | None, Field(default=None, min_length=1, max_length=100)]
    license_plate: Annotated[str | None, Field(default=None, max_length=20)]
    is_active: bool | None = None

    @model_validator(mode="after")
    def _reject_nulls(self):
        for f in ("name", "is_active"):
            if f in self.model_fields_set and getattr(self, f) is None:
                raise ValueError(f"{f} cannot be null")
        return self


class VehicleOut(ORMModel):
    id: int
    name: str
    license_plate: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


# ---------- location pings ----------


class PingIn(BaseModel):
    latitude: Annotated[float, Field(ge=-90, le=90)]
    longitude: Annotated[float, Field(ge=-180, le=180)]
    speed_kph: Annotated[float | None, Field(default=None, ge=0)]
    heading_deg: Annotated[float | None, Field(default=None, ge=0, lt=360)]
    recorded_at: datetime | None = Field(
        default=None, description="Device time (ISO 8601 with timezone). Defaults to now."
    )

    @field_validator("recorded_at")
    @classmethod
    def _to_utc(cls, v: datetime | None) -> datetime | None:
        if v is None:
            return None
        if v.tzinfo is None:
            raise ValueError("recorded_at must include a timezone, e.g. 2026-01-01T12:00:00Z")
        return v.astimezone(UTC)


class PingOut(ORMModel):
    id: int
    vehicle_id: int
    trip_id: int | None
    latitude: float
    longitude: float
    speed_kph: float | None
    heading_deg: float | None
    recorded_at: datetime


# ---------- trips ----------


class TripCreate(BaseModel):
    vehicle_id: int
    quote_id: int


class TripOut(ORMModel):
    id: int
    vehicle_id: int
    quote_id: int
    customer_id: int
    dest_street: str | None
    dest_street2: str | None
    dest_city: str | None
    dest_state: str | None
    dest_postal_code: str | None
    status: TripStatus
    started_at: datetime | None
    arrived_at: datetime | None
    created_at: datetime
    updated_at: datetime

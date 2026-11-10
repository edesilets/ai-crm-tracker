from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import cache
from ..db import get_db
from ..models import LocationPing, Trip, TripStatus, Vehicle
from ..schemas import PingIn, PingOut, VehicleCreate, VehicleOut, VehicleUpdate

router = APIRouter(prefix="/vehicles", tags=["vehicles"])


def get_vehicle(db: Session, vehicle_id: int) -> Vehicle:
    vehicle = db.get(Vehicle, vehicle_id)
    if vehicle is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Vehicle not found")
    return vehicle


def _commit_vehicle(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "License plate already in use")


@router.get("", response_model=list[VehicleOut])
def list_vehicles(active: bool | None = None, db: Session = Depends(get_db)):
    stmt = select(Vehicle).order_by(Vehicle.name, Vehicle.id)
    if active is not None:
        stmt = stmt.where(Vehicle.is_active.is_(active))
    return db.scalars(stmt).all()


@router.post("", response_model=VehicleOut, status_code=status.HTTP_201_CREATED)
def create_vehicle(data: VehicleCreate, db: Session = Depends(get_db)):
    vehicle = Vehicle(**data.model_dump())
    db.add(vehicle)
    _commit_vehicle(db)
    db.refresh(vehicle)
    return vehicle


@router.get("/{vehicle_id}", response_model=VehicleOut)
def read_vehicle(vehicle_id: int, db: Session = Depends(get_db)):
    return get_vehicle(db, vehicle_id)


@router.patch("/{vehicle_id}", response_model=VehicleOut)
def update_vehicle(vehicle_id: int, data: VehicleUpdate, db: Session = Depends(get_db)):
    vehicle = get_vehicle(db, vehicle_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(vehicle, field, value)
    _commit_vehicle(db)
    db.refresh(vehicle)
    return vehicle


@router.post(
    "/{vehicle_id}/locations", response_model=PingOut, status_code=status.HTTP_201_CREATED
)
def report_location(vehicle_id: int, data: PingIn, db: Session = Depends(get_db)):
    """Record a GPS position. It is attached to the vehicle's en-route trip, if any."""
    vehicle = get_vehicle(db, vehicle_id)
    if not vehicle.is_active:
        raise HTTPException(status.HTTP_409_CONFLICT, "Vehicle is inactive")

    trip_id = db.scalar(
        select(Trip.id).where(Trip.vehicle_id == vehicle_id, Trip.status == TripStatus.en_route)
    )
    ping = LocationPing(
        vehicle_id=vehicle_id,
        trip_id=trip_id,
        **data.model_dump(exclude={"recorded_at"}),
        recorded_at=data.recorded_at or datetime.now(UTC),
    )
    db.add(ping)
    db.commit()
    db.refresh(ping)

    out = PingOut.model_validate(ping)
    cache.set_latest(vehicle_id, out.model_dump(mode="json"), ping.recorded_at)
    return out


@router.get("/{vehicle_id}/location", response_model=PingOut)
def latest_location(vehicle_id: int, db: Session = Depends(get_db)):
    """Most recent known position (from Redis, falling back to Postgres)."""
    get_vehicle(db, vehicle_id)
    cached = cache.get_latest(vehicle_id)
    if cached:
        return cached
    ping = db.scalar(
        select(LocationPing)
        .where(LocationPing.vehicle_id == vehicle_id)
        .order_by(LocationPing.recorded_at.desc(), LocationPing.id.desc())
        .limit(1)
    )
    if ping is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No location reported yet")
    return ping


@router.get("/{vehicle_id}/locations", response_model=list[PingOut])
def location_history(
    vehicle_id: int,
    since: datetime | None = None,
    limit: int = Query(500, ge=1, le=5000),
    db: Session = Depends(get_db),
):
    get_vehicle(db, vehicle_id)
    stmt = select(LocationPing).where(LocationPing.vehicle_id == vehicle_id)
    if since is not None:
        stmt = stmt.where(LocationPing.recorded_at >= since)
    return db.scalars(stmt.order_by(LocationPing.recorded_at.desc()).limit(limit)).all()

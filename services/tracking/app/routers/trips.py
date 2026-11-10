from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import crm_client
from ..db import get_db
from ..models import LocationPing, Trip, TripStatus
from ..schemas import PingOut, TripCreate, TripOut
from .vehicles import get_vehicle

router = APIRouter(prefix="/trips", tags=["trips"])

ADDRESS_FIELDS = ("street", "street2", "city", "state", "postal_code")


def _get_trip(db: Session, trip_id: int) -> Trip:
    trip = db.get(Trip, trip_id)
    if trip is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Trip not found")
    return trip


def _require_status(trip: Trip, *allowed: TripStatus) -> None:
    if trip.status not in allowed:
        names = " or ".join(s.value for s in allowed)
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"Trip is {trip.status.value}; must be {names}"
        )


@router.post("", response_model=TripOut, status_code=status.HTTP_201_CREATED)
def create_trip(data: TripCreate, db: Session = Depends(get_db)):
    """Plan a trip for a vehicle to the job site of an accepted CRM quote."""
    vehicle = get_vehicle(db, data.vehicle_id)
    if not vehicle.is_active:
        raise HTTPException(status.HTTP_409_CONFLICT, "Vehicle is inactive")

    try:
        quote = crm_client.get_quote(data.quote_id)
    except crm_client.CRMUnavailable as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc))
    if quote is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Quote not found in CRM")
    if quote["status"] != "accepted":
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Quote is {quote['status']}; only accepted quotes can be scheduled",
        )

    trip = Trip(
        vehicle_id=vehicle.id,
        quote_id=quote["id"],
        customer_id=quote["customer_id"],
        **{f"dest_{f}": quote.get(f"site_{f}") for f in ADDRESS_FIELDS},
    )
    db.add(trip)
    db.commit()
    db.refresh(trip)
    return trip


@router.get("", response_model=list[TripOut])
def list_trips(
    vehicle_id: int | None = None,
    quote_id: int | None = None,
    status_: TripStatus | None = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    stmt = select(Trip).order_by(Trip.id.desc())
    if vehicle_id is not None:
        stmt = stmt.where(Trip.vehicle_id == vehicle_id)
    if quote_id is not None:
        stmt = stmt.where(Trip.quote_id == quote_id)
    if status_ is not None:
        stmt = stmt.where(Trip.status == status_)
    return db.scalars(stmt.limit(limit).offset(offset)).all()


@router.get("/{trip_id}", response_model=TripOut)
def read_trip(trip_id: int, db: Session = Depends(get_db)):
    return _get_trip(db, trip_id)


@router.post("/{trip_id}/start", response_model=TripOut)
def start_trip(trip_id: int, db: Session = Depends(get_db)):
    trip = _get_trip(db, trip_id)
    _require_status(trip, TripStatus.planned)
    trip.status = TripStatus.en_route
    trip.started_at = datetime.now(UTC)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Vehicle is already en route on another trip"
        )
    db.refresh(trip)
    return trip


@router.post("/{trip_id}/arrive", response_model=TripOut)
def arrive_trip(trip_id: int, db: Session = Depends(get_db)):
    trip = _get_trip(db, trip_id)
    _require_status(trip, TripStatus.en_route)
    trip.status = TripStatus.arrived
    trip.arrived_at = datetime.now(UTC)
    db.commit()
    db.refresh(trip)
    return trip


@router.post("/{trip_id}/cancel", response_model=TripOut)
def cancel_trip(trip_id: int, db: Session = Depends(get_db)):
    trip = _get_trip(db, trip_id)
    _require_status(trip, TripStatus.planned, TripStatus.en_route)
    trip.status = TripStatus.cancelled
    db.commit()
    db.refresh(trip)
    return trip


@router.get("/{trip_id}/route", response_model=list[PingOut])
def trip_route(trip_id: int, db: Session = Depends(get_db)):
    """All positions recorded during the trip, oldest first."""
    _get_trip(db, trip_id)
    return db.scalars(
        select(LocationPing)
        .where(LocationPing.trip_id == trip_id)
        .order_by(LocationPing.recorded_at, LocationPing.id)
    ).all()

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import exists, or_, select, update
from sqlalchemy.orm import Session, selectinload

from ..db import get_db
from ..models import ContactKind, Customer, CustomerContact, Quote
from ..schemas import (
    ContactCreate,
    ContactOut,
    ContactUpdate,
    CustomerCreate,
    CustomerOut,
    CustomerUpdate,
)

router = APIRouter(tags=["customers"])


def _load_customer(db: Session, customer_id: int) -> Customer:
    customer = db.scalar(
        select(Customer)
        .where(Customer.id == customer_id)
        .options(selectinload(Customer.contacts))
    )
    if customer is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Customer not found")
    return customer


def _get_contact(db: Session, contact_id: int) -> CustomerContact:
    contact = db.get(CustomerContact, contact_id)
    if contact is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Contact not found")
    return contact


def _clear_primary(
    db: Session, customer_id: int, kind: ContactKind, except_id: int | None = None
) -> None:
    stmt = (
        update(CustomerContact)
        .where(
            CustomerContact.customer_id == customer_id,
            CustomerContact.kind == kind,
            CustomerContact.is_primary.is_(True),
        )
        .values(is_primary=False)
    )
    if except_id is not None:
        stmt = stmt.where(CustomerContact.id != except_id)
    db.execute(stmt)


# ---------- customers ----------


@router.get("/customers", response_model=list[CustomerOut])
def list_customers(
    q: str | None = Query(None, description="Search first or last name"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    stmt = (
        select(Customer)
        .options(selectinload(Customer.contacts))
        .order_by(Customer.last_name, Customer.first_name, Customer.id)
    )
    if q:
        pattern = f"%{q}%"
        stmt = stmt.where(or_(Customer.first_name.ilike(pattern), Customer.last_name.ilike(pattern)))
    return db.scalars(stmt.limit(limit).offset(offset)).all()


@router.post("/customers", response_model=CustomerOut, status_code=status.HTTP_201_CREATED)
def create_customer(data: CustomerCreate, db: Session = Depends(get_db)):
    customer = Customer(
        **data.model_dump(exclude={"contacts"}),
        contacts=[CustomerContact(**c.model_dump()) for c in data.contacts],
    )
    db.add(customer)
    db.commit()
    return _load_customer(db, customer.id)


@router.get("/customers/{customer_id}", response_model=CustomerOut)
def get_customer(customer_id: int, db: Session = Depends(get_db)):
    return _load_customer(db, customer_id)


@router.patch("/customers/{customer_id}", response_model=CustomerOut)
def update_customer(customer_id: int, data: CustomerUpdate, db: Session = Depends(get_db)):
    customer = _load_customer(db, customer_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(customer, field, value)
    db.commit()
    db.expire_all()
    return _load_customer(db, customer_id)


@router.delete("/customers/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_customer(customer_id: int, db: Session = Depends(get_db)):
    customer = _load_customer(db, customer_id)
    if db.scalar(select(exists().where(Quote.customer_id == customer_id))):
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Customer has quotes; delete or reassign them first"
        )
    db.delete(customer)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------- contacts ----------


@router.get("/customers/{customer_id}/contacts", response_model=list[ContactOut])
def list_contacts(customer_id: int, db: Session = Depends(get_db)):
    return _load_customer(db, customer_id).contacts


@router.post(
    "/customers/{customer_id}/contacts",
    response_model=ContactOut,
    status_code=status.HTTP_201_CREATED,
)
def create_contact(customer_id: int, data: ContactCreate, db: Session = Depends(get_db)):
    _load_customer(db, customer_id)
    if data.is_primary:
        _clear_primary(db, customer_id, data.kind)
    contact = CustomerContact(customer_id=customer_id, **data.model_dump())
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return contact


@router.patch("/contacts/{contact_id}", response_model=ContactOut, tags=["contacts"])
def update_contact(contact_id: int, data: ContactUpdate, db: Session = Depends(get_db)):
    contact = _get_contact(db, contact_id)
    changes = data.model_dump(exclude_unset=True)
    if changes.get("is_primary", contact.is_primary):
        _clear_primary(
            db, contact.customer_id, changes.get("kind", contact.kind), except_id=contact.id
        )
    for field, value in changes.items():
        setattr(contact, field, value)
    db.commit()
    db.refresh(contact)
    return contact


@router.delete(
    "/contacts/{contact_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["contacts"]
)
def delete_contact(contact_id: int, db: Session = Depends(get_db)):
    db.delete(_get_contact(db, contact_id))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

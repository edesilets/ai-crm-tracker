from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..db import get_db
from ..models import Customer, Quote, QuoteLineItem, QuoteStatus
from ..schemas import LineItemIn, QuoteCreate, QuoteOut, QuoteUpdate

router = APIRouter(prefix="/quotes", tags=["quotes"])

SITE_FIELDS = ("street", "street2", "city", "state", "postal_code")


def _load_quote(db: Session, quote_id: int) -> Quote:
    quote = db.scalar(
        select(Quote).where(Quote.id == quote_id).options(selectinload(Quote.line_items))
    )
    if quote is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Quote not found")
    return quote


def _build_line_items(items: list[LineItemIn]) -> list[QuoteLineItem]:
    return [QuoteLineItem(position=i, **item.model_dump()) for i, item in enumerate(items, 1)]


@router.get("", response_model=list[QuoteOut])
def list_quotes(
    customer_id: int | None = None,
    status_: QuoteStatus | None = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    stmt = select(Quote).options(selectinload(Quote.line_items)).order_by(Quote.id.desc())
    if customer_id is not None:
        stmt = stmt.where(Quote.customer_id == customer_id)
    if status_ is not None:
        stmt = stmt.where(Quote.status == status_)
    return db.scalars(stmt.limit(limit).offset(offset)).all()


@router.post("", response_model=QuoteOut, status_code=status.HTTP_201_CREATED)
def create_quote(data: QuoteCreate, db: Session = Depends(get_db)):
    customer = db.get(Customer, data.customer_id)
    if customer is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Customer not found")

    fields = data.model_dump(exclude={"line_items"})
    # No job site given: use the customer's address.
    if all(fields[f"site_{f}"] is None for f in SITE_FIELDS):
        for f in SITE_FIELDS:
            fields[f"site_{f}"] = getattr(customer, f)

    quote = Quote(**fields, line_items=_build_line_items(data.line_items))
    db.add(quote)
    db.commit()
    return _load_quote(db, quote.id)


@router.get("/{quote_id}", response_model=QuoteOut)
def get_quote(quote_id: int, db: Session = Depends(get_db)):
    return _load_quote(db, quote_id)


@router.patch("/{quote_id}", response_model=QuoteOut)
def update_quote(quote_id: int, data: QuoteUpdate, db: Session = Depends(get_db)):
    quote = _load_quote(db, quote_id)
    changes = data.model_dump(exclude_unset=True, exclude={"line_items"})
    for field, value in changes.items():
        setattr(quote, field, value)
    if data.line_items is not None:
        quote.line_items = _build_line_items(data.line_items)
    db.commit()
    db.expire_all()
    return _load_quote(db, quote_id)


@router.delete("/{quote_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_quote(quote_id: int, db: Session = Depends(get_db)):
    quote = _load_quote(db, quote_id)
    if quote.status != QuoteStatus.draft:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Only draft quotes can be deleted; set the status to declined or expired instead",
        )
    db.delete(quote)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

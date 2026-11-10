from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, ClassVar

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .models import ContactKind, QuoteStatus

Name = Annotated[str, Field(min_length=1, max_length=100)]
OptStr100 = Annotated[str | None, Field(default=None, max_length=100)]
OptStr255 = Annotated[str | None, Field(default=None, max_length=255)]
OptPostal = Annotated[str | None, Field(default=None, max_length=20)]
Country = Annotated[str, Field(min_length=2, max_length=2, pattern="^[A-Z]{2}$")]


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class PatchModel(BaseModel):
    """Partial update. Fields listed in NOT_NULL may be omitted but not set to null."""

    NOT_NULL: ClassVar[tuple[str, ...]] = ()

    @model_validator(mode="after")
    def _reject_nulls(self):
        bad = [f for f in self.NOT_NULL if f in self.model_fields_set and getattr(self, f) is None]
        if bad:
            raise ValueError(f"these fields cannot be null: {', '.join(bad)}")
        return self


# ---------- contacts ----------


class ContactCreate(BaseModel):
    kind: ContactKind
    value: Annotated[str, Field(min_length=1, max_length=255)]
    label: Annotated[str | None, Field(default=None, max_length=50)]
    is_primary: bool = False


class ContactUpdate(PatchModel):
    NOT_NULL = ("kind", "value", "is_primary")

    kind: ContactKind | None = None
    value: Annotated[str | None, Field(default=None, min_length=1, max_length=255)]
    label: Annotated[str | None, Field(default=None, max_length=50)]
    is_primary: bool | None = None


class ContactOut(ORMModel):
    id: int
    customer_id: int
    kind: ContactKind
    value: str
    label: str | None
    is_primary: bool
    created_at: datetime
    updated_at: datetime


# ---------- customers ----------


class CustomerFields(BaseModel):
    first_name: Name
    last_name: Name
    street: OptStr255 = None
    street2: OptStr255 = None
    city: OptStr100 = None
    state: OptStr100 = None
    postal_code: OptPostal = None
    country: Country = "US"


class CustomerCreate(CustomerFields):
    contacts: list[ContactCreate] = []

    @model_validator(mode="after")
    def _one_primary_per_kind(self):
        kinds = [c.kind for c in self.contacts if c.is_primary]
        if len(kinds) != len(set(kinds)):
            raise ValueError("only one primary contact allowed per kind")
        return self


class CustomerUpdate(PatchModel):
    NOT_NULL = ("first_name", "last_name", "country")

    first_name: Name | None = None
    last_name: Name | None = None
    street: OptStr255 = None
    street2: OptStr255 = None
    city: OptStr100 = None
    state: OptStr100 = None
    postal_code: OptPostal = None
    country: Country | None = None


class CustomerOut(ORMModel, CustomerFields):
    id: int
    contacts: list[ContactOut]
    created_at: datetime
    updated_at: datetime


# ---------- quotes ----------


class LineItemIn(BaseModel):
    description: Annotated[str, Field(min_length=1, max_length=500)]
    quantity: Annotated[Decimal, Field(gt=0, max_digits=10, decimal_places=2)]
    unit_price: Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)]


class LineItemOut(ORMModel):
    id: int
    position: int
    description: str
    quantity: Decimal
    unit_price: Decimal
    line_total: Decimal


class QuoteSiteFields(BaseModel):
    site_street: OptStr255 = None
    site_street2: OptStr255 = None
    site_city: OptStr100 = None
    site_state: OptStr100 = None
    site_postal_code: OptPostal = None


class QuoteCreate(QuoteSiteFields):
    customer_id: int
    title: Annotated[str, Field(min_length=1, max_length=200)]
    status: QuoteStatus = QuoteStatus.draft
    valid_until: date | None = None
    notes: str | None = None
    line_items: list[LineItemIn] = []


class QuoteUpdate(PatchModel, QuoteSiteFields):
    NOT_NULL = ("title", "status", "line_items")

    title: Annotated[str | None, Field(default=None, min_length=1, max_length=200)]
    status: QuoteStatus | None = None
    valid_until: date | None = None
    notes: str | None = None
    # When given, replaces all existing line items.
    line_items: list[LineItemIn] | None = None


class QuoteOut(ORMModel, QuoteSiteFields):
    id: int
    customer_id: int
    title: str
    status: QuoteStatus
    valid_until: date | None
    notes: str | None
    line_items: list[LineItemOut]
    total: Decimal
    created_at: datetime
    updated_at: datetime

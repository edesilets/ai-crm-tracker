import enum
from datetime import date
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    false,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base, TimestampMixin

CENTS = Decimal("0.01")


class ContactKind(str, enum.Enum):
    phone = "phone"
    email = "email"
    other = "other"


class QuoteStatus(str, enum.Enum):
    draft = "draft"
    sent = "sent"
    accepted = "accepted"
    declined = "declined"
    expired = "expired"


def _enum_column(enum_cls: type[enum.Enum], name: str) -> Enum:
    # Stored as VARCHAR + CHECK constraint, which is easier to migrate than a native PG enum.
    return Enum(
        enum_cls,
        name=name,
        native_enum=False,
        create_constraint=True,
        length=20,
        values_callable=lambda e: [m.value for m in e],
    )


class Customer(TimestampMixin, Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(primary_key=True)
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100), index=True)
    street: Mapped[str | None] = mapped_column(String(255))
    street2: Mapped[str | None] = mapped_column(String(255))
    city: Mapped[str | None] = mapped_column(String(100))
    state: Mapped[str | None] = mapped_column(String(100))
    postal_code: Mapped[str | None] = mapped_column(String(20))
    country: Mapped[str] = mapped_column(String(2), server_default="US")

    contacts: Mapped[list["CustomerContact"]] = relationship(
        back_populates="customer",
        cascade="all, delete-orphan",
        order_by="CustomerContact.id",
    )
    quotes: Mapped[list["Quote"]] = relationship(back_populates="customer")


class CustomerContact(TimestampMixin, Base):
    __tablename__ = "customer_contacts"
    __table_args__ = (
        # At most one primary phone / email / other per customer.
        Index(
            "uq_customer_contacts_primary_per_kind",
            "customer_id",
            "kind",
            unique=True,
            postgresql_where=text("is_primary"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[ContactKind] = mapped_column(_enum_column(ContactKind, "contact_kind"))
    value: Mapped[str] = mapped_column(String(255))
    label: Mapped[str | None] = mapped_column(String(50))
    is_primary: Mapped[bool] = mapped_column(Boolean, server_default=false(), default=False)

    customer: Mapped[Customer] = relationship(back_populates="contacts")


class Quote(TimestampMixin, Base):
    __tablename__ = "quotes"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"), index=True
    )
    title: Mapped[str] = mapped_column(String(200))
    status: Mapped[QuoteStatus] = mapped_column(
        _enum_column(QuoteStatus, "quote_status"),
        default=QuoteStatus.draft,
        server_default=QuoteStatus.draft.value,
        index=True,
    )
    # Job site address. Defaults to the customer's address when not given.
    site_street: Mapped[str | None] = mapped_column(String(255))
    site_street2: Mapped[str | None] = mapped_column(String(255))
    site_city: Mapped[str | None] = mapped_column(String(100))
    site_state: Mapped[str | None] = mapped_column(String(100))
    site_postal_code: Mapped[str | None] = mapped_column(String(20))
    valid_until: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)

    customer: Mapped[Customer] = relationship(back_populates="quotes")
    line_items: Mapped[list["QuoteLineItem"]] = relationship(
        back_populates="quote",
        cascade="all, delete-orphan",
        order_by="QuoteLineItem.position",
    )

    @property
    def total(self) -> Decimal:
        return sum((item.line_total for item in self.line_items), Decimal("0.00"))


class QuoteLineItem(Base):
    __tablename__ = "quote_line_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint("unit_price >= 0", name="unit_price_not_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    quote_id: Mapped[int] = mapped_column(
        ForeignKey("quotes.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int]
    description: Mapped[str] = mapped_column(String(500))
    quantity: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))

    quote: Mapped[Quote] = relationship(back_populates="line_items")

    @property
    def line_total(self) -> Decimal:
        return (self.quantity * self.unit_price).quantize(CENTS)

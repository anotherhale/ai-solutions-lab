"""Invoice read model for the laboratory slice."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class Money:
    amount: Decimal
    currency: str


@dataclass(frozen=True, slots=True)
class Invoice:
    """Persisted invoice reference row."""

    id: str
    customer_id: str
    status: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class InvoiceLine:
    """Persisted invoice line. Reference data only; no posting."""

    id: str
    invoice_id: str
    description: str
    quantity: Decimal
    unit_price: Money
    line_total: Money
    line_type: str
    created_at: datetime
    updated_at: datetime
    work_order_id: str | None = None


@dataclass(frozen=True, slots=True)
class Payment:
    """Persisted payment reference row. Read-only; no posting command."""

    id: str
    invoice_id: str
    amount: Money
    method: str
    status: str
    received_on: date
    created_at: datetime
    updated_at: datetime
    reference: str | None = None
    received_by_employee_id: str | None = None
    notes: str | None = None

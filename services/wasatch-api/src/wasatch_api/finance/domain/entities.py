"""Read models for synthetic invoices. A read does not post money."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal


@dataclass(frozen=True)
class Money:
    amount: str
    currency: str


@dataclass(frozen=True)
class InvoiceLine:
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


@dataclass(frozen=True)
class Payment:
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


@dataclass
class Invoice:
    id: str
    customer_id: str
    status: str
    subtotal: Money
    tax: Money
    adjustments: Money
    total: Money
    amount_paid: Money
    balance: Money
    created_at: datetime
    updated_at: datetime
    work_order_id: str | None = None
    issued_on: date | None = None
    due_on: date | None = None
    voided_on: date | None = None
    void_reason: str | None = None
    notes: str | None = None
    lines: list[InvoiceLine] = field(default_factory=list)
    payments: list[Payment] = field(default_factory=list)

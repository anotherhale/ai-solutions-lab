"""Read routes for synthetic invoices, lines, and payments.

These routes do not post a payment, change a total, or mark an invoice posted.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from wasatch_api.api.dependencies import db_session, require_laboratory_actor
from wasatch_api.api.schemas import (
    InvoiceDetailOut,
    InvoiceLineOut,
    InvoiceListItemOut,
    PageOut,
    PaymentOut,
)
from wasatch_api.finance.application.queries import FinanceQueries
from wasatch_api.finance.infrastructure.repository import FinanceRepository

router = APIRouter(
    prefix="/api/v1",
    tags=["finance"],
    dependencies=[Depends(require_laboratory_actor)],
)

SessionDep = Annotated[Session, Depends(db_session)]


def queries(session: SessionDep) -> FinanceQueries:
    return FinanceQueries(FinanceRepository(session))


QueriesDep = Annotated[FinanceQueries, Depends(queries)]


@router.get("/invoices", response_model=PageOut[InvoiceListItemOut])
def list_invoices(
    service: QueriesDep,
    status: str | None = None,
    customer_id: str | None = None,
    page: int | None = Query(default=None, ge=1),
    page_size: int | None = Query(default=None, ge=1, le=100),
) -> PageOut[InvoiceListItemOut]:
    items, total, request = service.list_invoices(
        page=page,
        page_size=page_size,
        status=status,
        customer_id=customer_id,
    )
    return PageOut(
        items=[InvoiceListItemOut.from_domain(item) for item in items],
        page=request.page,
        page_size=request.page_size,
        total=total,
    )


@router.get("/invoices/{invoice_id}", response_model=InvoiceDetailOut)
def get_invoice(invoice_id: str, service: QueriesDep) -> InvoiceDetailOut:
    return InvoiceDetailOut.from_domain(service.get_invoice(invoice_id))


@router.get("/invoice-lines", response_model=PageOut[InvoiceLineOut])
def list_invoice_lines(
    service: QueriesDep,
    invoice_id: str | None = None,
    line_type: str | None = None,
    page: int | None = Query(default=None, ge=1),
    page_size: int | None = Query(default=None, ge=1, le=100),
) -> PageOut[InvoiceLineOut]:
    items, total, request = service.list_invoice_lines(
        page=page,
        page_size=page_size,
        invoice_id=invoice_id,
        line_type=line_type,
    )
    return PageOut(
        items=[InvoiceLineOut.from_domain(item) for item in items],
        page=request.page,
        page_size=request.page_size,
        total=total,
    )


@router.get("/invoice-lines/{line_id}", response_model=InvoiceLineOut)
def get_invoice_line(line_id: str, service: QueriesDep) -> InvoiceLineOut:
    return InvoiceLineOut.from_domain(service.get_invoice_line(line_id))


@router.get("/payments", response_model=PageOut[PaymentOut])
def list_payments(
    service: QueriesDep,
    status: str | None = None,
    invoice_id: str | None = None,
    page: int | None = Query(default=None, ge=1),
    page_size: int | None = Query(default=None, ge=1, le=100),
) -> PageOut[PaymentOut]:
    items, total, request = service.list_payments(
        page=page,
        page_size=page_size,
        status=status,
        invoice_id=invoice_id,
    )
    return PageOut(
        items=[PaymentOut.from_domain(item) for item in items],
        page=request.page,
        page_size=request.page_size,
        total=total,
    )


@router.get("/payments/{payment_id}", response_model=PaymentOut)
def get_payment(payment_id: str, service: QueriesDep) -> PaymentOut:
    return PaymentOut.from_domain(service.get_payment(payment_id))

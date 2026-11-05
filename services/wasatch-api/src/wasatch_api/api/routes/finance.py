"""Read-only invoice routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from wasatch_api.api.dependencies import (
    db_session,
    finance_queries,
    require_laboratory_actor,
)
from wasatch_api.api.schemas import (
    InvoiceDetailOut,
    InvoiceLineOut,
    InvoiceListItemOut,
    PageOut,
)
from wasatch_api.finance.application.queries import InvoiceQueries

router = APIRouter(
    prefix="/api/v1",
    tags=["finance"],
    dependencies=[Depends(require_laboratory_actor)],
)

SessionDep = Annotated[Session, Depends(db_session)]


def queries(session: SessionDep) -> InvoiceQueries:
    return finance_queries(session)


QueriesDep = Annotated[InvoiceQueries, Depends(queries)]


@router.get("/invoices", response_model=PageOut[InvoiceListItemOut])
def list_invoices(
    service: QueriesDep,
    customer_id: str | None = None,
    status: str | None = None,
    page: int | None = Query(default=None, ge=1),
    page_size: int | None = Query(default=None, ge=1, le=100),
) -> PageOut[InvoiceListItemOut]:
    items, total, request = service.list_invoices(
        page=page,
        page_size=page_size,
        customer_id=customer_id,
        status=status,
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


@router.get(
    "/invoices/{invoice_id}/lines",
    response_model=PageOut[InvoiceLineOut],
)
def list_invoice_lines(
    invoice_id: str,
    service: QueriesDep,
    line_type: str | None = None,
    page: int | None = Query(default=None, ge=1),
    page_size: int | None = Query(default=None, ge=1, le=100),
) -> PageOut[InvoiceLineOut]:
    items, total, request = service.list_invoice_lines(
        invoice_id,
        page=page,
        page_size=page_size,
        line_type=line_type,
    )
    return PageOut(
        items=[InvoiceLineOut.from_domain(item) for item in items],
        page=request.page,
        page_size=request.page_size,
        total=total,
    )


@router.get("/invoice-lines/{invoice_line_id}", response_model=InvoiceLineOut)
def get_invoice_line(invoice_line_id: str, service: QueriesDep) -> InvoiceLineOut:
    return InvoiceLineOut.from_domain(service.get_invoice_line(invoice_line_id))

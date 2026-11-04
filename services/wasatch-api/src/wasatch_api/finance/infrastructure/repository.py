"""PostgreSQL adapter for invoice, line, and payment reads.

These queries do not insert, update, or delete finance rows.
"""

from __future__ import annotations

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, selectinload

from wasatch_api.finance.domain.entities import Invoice, InvoiceLine, Payment
from wasatch_api.finance.infrastructure.mapping import (
    invoice_from_orm,
    invoice_line_from_orm,
    payment_from_orm,
)
from wasatch_api.shared.database.models import InvoiceLineORM, InvoiceORM, PaymentORM
from wasatch_api.shared.pagination import PageRequest


def _restrict(stmt, count_stmt, criteria: list):
    if not criteria:
        return stmt, count_stmt
    return stmt.where(*criteria), count_stmt.where(*criteria)


class FinanceRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_invoice(self, business_id: str) -> Invoice | None:
        stmt = (
            select(InvoiceORM)
            .options(*_invoice_detail_options())
            .where(InvoiceORM.business_id == business_id)
        )
        row = self.session.scalar(stmt)
        if row is None:
            return None
        return invoice_from_orm(row, detail=True)

    def list_invoices(
        self,
        page: PageRequest,
        *,
        status: str | None = None,
        customer_id: str | None = None,
    ) -> tuple[list[Invoice], int]:
        stmt: Select[tuple[InvoiceORM]] = select(InvoiceORM).options(
            *_invoice_summary_options()
        )
        count_stmt = select(func.count()).select_from(InvoiceORM)
        criteria = []
        if status:
            criteria.append(InvoiceORM.status == status)
        if customer_id:
            criteria.append(InvoiceORM.customer.has(business_id=customer_id))
        stmt, count_stmt = _restrict(stmt, count_stmt, criteria)
        return _page(
            self.session,
            stmt.order_by(InvoiceORM.business_id),
            count_stmt,
            page,
            lambda row: invoice_from_orm(row, detail=False),
        )

    def get_invoice_line(self, business_id: str) -> InvoiceLine | None:
        stmt = (
            select(InvoiceLineORM)
            .options(*_line_options())
            .where(InvoiceLineORM.business_id == business_id)
        )
        row = self.session.scalar(stmt)
        if row is None:
            return None
        return invoice_line_from_orm(row)

    def list_invoice_lines(
        self,
        page: PageRequest,
        *,
        invoice_id: str | None = None,
        line_type: str | None = None,
    ) -> tuple[list[InvoiceLine], int]:
        stmt: Select[tuple[InvoiceLineORM]] = select(InvoiceLineORM).options(
            *_line_options()
        )
        count_stmt = select(func.count()).select_from(InvoiceLineORM)
        criteria = []
        if invoice_id:
            criteria.append(InvoiceLineORM.invoice.has(business_id=invoice_id))
        if line_type:
            criteria.append(InvoiceLineORM.line_type == line_type)
        stmt, count_stmt = _restrict(stmt, count_stmt, criteria)
        return _page(
            self.session,
            stmt.order_by(InvoiceLineORM.business_id),
            count_stmt,
            page,
            invoice_line_from_orm,
        )

    def get_payment(self, business_id: str) -> Payment | None:
        stmt = (
            select(PaymentORM)
            .options(*_payment_options())
            .where(PaymentORM.business_id == business_id)
        )
        row = self.session.scalar(stmt)
        if row is None:
            return None
        return payment_from_orm(row)

    def list_payments(
        self,
        page: PageRequest,
        *,
        status: str | None = None,
        invoice_id: str | None = None,
    ) -> tuple[list[Payment], int]:
        stmt: Select[tuple[PaymentORM]] = select(PaymentORM).options(
            *_payment_options()
        )
        count_stmt = select(func.count()).select_from(PaymentORM)
        criteria = []
        if status:
            criteria.append(PaymentORM.status == status)
        if invoice_id:
            criteria.append(PaymentORM.invoice.has(business_id=invoice_id))
        stmt, count_stmt = _restrict(stmt, count_stmt, criteria)
        return _page(
            self.session,
            stmt.order_by(PaymentORM.business_id),
            count_stmt,
            page,
            payment_from_orm,
        )


def _invoice_summary_options():
    return (
        selectinload(InvoiceORM.customer),
        selectinload(InvoiceORM.work_order),
    )


def _invoice_detail_options():
    return (
        selectinload(InvoiceORM.customer),
        selectinload(InvoiceORM.work_order),
        selectinload(InvoiceORM.lines).selectinload(InvoiceLineORM.invoice),
        selectinload(InvoiceORM.lines).selectinload(InvoiceLineORM.work_order),
        selectinload(InvoiceORM.payments).selectinload(PaymentORM.invoice),
        selectinload(InvoiceORM.payments).selectinload(PaymentORM.received_by),
    )


def _line_options():
    return (
        selectinload(InvoiceLineORM.invoice),
        selectinload(InvoiceLineORM.work_order),
    )


def _payment_options():
    return (
        selectinload(PaymentORM.invoice),
        selectinload(PaymentORM.received_by),
    )


def _page(session: Session, stmt, count_stmt, page: PageRequest, mapper):
    total = int(session.scalar(count_stmt) or 0)
    rows = session.scalars(stmt.offset(page.offset).limit(page.page_size)).all()
    return [mapper(row) for row in rows], total

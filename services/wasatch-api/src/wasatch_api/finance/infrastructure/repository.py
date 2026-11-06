"""PostgreSQL adapter for invoice read models."""

from __future__ import annotations

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, selectinload

from wasatch_api.finance.domain.entities import Invoice, InvoiceLine, Payment
from wasatch_api.finance.infrastructure.mapping import (
    invoice_from_orm,
    invoice_line_from_orm,
    payment_from_orm,
)
from wasatch_api.shared.database.models import (
    CustomerORM,
    InvoiceLineORM,
    InvoiceORM,
    PaymentORM,
)
from wasatch_api.shared.pagination import PageRequest


def _page(
    session: Session,
    stmt: Select,
    count_stmt,
    page: PageRequest,
    mapper,
) -> tuple[list[Invoice], int]:
    total = session.scalar(count_stmt) or 0
    rows = session.scalars(stmt.offset(page.offset).limit(page.page_size)).all()
    return [mapper(row) for row in rows], total


class InvoiceRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_business_id(self, business_id: str) -> Invoice | None:
        stmt = (
            select(InvoiceORM)
            .options(selectinload(InvoiceORM.customer))
            .where(InvoiceORM.business_id == business_id)
        )
        row = self.session.scalar(stmt)
        if row is None:
            return None
        return invoice_from_orm(row)

    def list_invoices(
        self,
        page: PageRequest,
        *,
        customer_id: str | None = None,
        status: str | None = None,
    ) -> tuple[list[Invoice], int]:
        stmt: Select[tuple[InvoiceORM]] = select(InvoiceORM).options(
            selectinload(InvoiceORM.customer)
        )
        count_stmt = select(func.count()).select_from(InvoiceORM)
        criteria = []
        if status:
            criteria.append(InvoiceORM.status == status)
        if customer_id:
            stmt = stmt.join(CustomerORM)
            count_stmt = count_stmt.join(CustomerORM)
            criteria.append(CustomerORM.business_id == customer_id)
        if criteria:
            stmt = stmt.where(*criteria)
            count_stmt = count_stmt.where(*criteria)
        return _page(
            self.session,
            stmt.order_by(InvoiceORM.business_id),
            count_stmt,
            page,
            invoice_from_orm,
        )

    def get_line_by_business_id(self, business_id: str) -> InvoiceLine | None:
        stmt = (
            select(InvoiceLineORM)
            .options(
                selectinload(InvoiceLineORM.invoice),
                selectinload(InvoiceLineORM.work_order),
            )
            .where(InvoiceLineORM.business_id == business_id)
        )
        row = self.session.scalar(stmt)
        if row is None:
            return None
        return invoice_line_from_orm(row)

    def list_lines_for_invoice(
        self,
        invoice_business_id: str,
        page: PageRequest,
        *,
        line_type: str | None = None,
    ) -> tuple[list[InvoiceLine], int] | None:
        invoice_row = self.session.scalar(
            select(InvoiceORM).where(InvoiceORM.business_id == invoice_business_id)
        )
        if invoice_row is None:
            return None
        stmt: Select[tuple[InvoiceLineORM]] = (
            select(InvoiceLineORM)
            .options(
                selectinload(InvoiceLineORM.invoice),
                selectinload(InvoiceLineORM.work_order),
            )
            .where(InvoiceLineORM.invoice_id == invoice_row.id)
        )
        count_stmt = (
            select(func.count())
            .select_from(InvoiceLineORM)
            .where(InvoiceLineORM.invoice_id == invoice_row.id)
        )
        if line_type:
            stmt = stmt.where(InvoiceLineORM.line_type == line_type)
            count_stmt = count_stmt.where(InvoiceLineORM.line_type == line_type)
        return _page(
            self.session,
            stmt.order_by(InvoiceLineORM.business_id),
            count_stmt,
            page,
            invoice_line_from_orm,
        )

    def get_payment_by_business_id(self, business_id: str) -> Payment | None:
        stmt = (
            select(PaymentORM)
            .options(
                selectinload(PaymentORM.invoice),
                selectinload(PaymentORM.received_by),
            )
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
        invoice_id: str | None = None,
        status: str | None = None,
        method: str | None = None,
    ) -> tuple[list[Payment], int]:
        stmt: Select[tuple[PaymentORM]] = select(PaymentORM).options(
            selectinload(PaymentORM.invoice),
            selectinload(PaymentORM.received_by),
        )
        count_stmt = select(func.count()).select_from(PaymentORM)
        if invoice_id:
            stmt = stmt.join(InvoiceORM)
            count_stmt = count_stmt.join(InvoiceORM)
            stmt = stmt.where(InvoiceORM.business_id == invoice_id)
            count_stmt = count_stmt.where(InvoiceORM.business_id == invoice_id)
        if status:
            stmt = stmt.where(PaymentORM.status == status)
            count_stmt = count_stmt.where(PaymentORM.status == status)
        if method:
            stmt = stmt.where(PaymentORM.method == method)
            count_stmt = count_stmt.where(PaymentORM.method == method)
        return _page(
            self.session,
            stmt.order_by(PaymentORM.business_id),
            count_stmt,
            page,
            payment_from_orm,
        )

"""PostgreSQL adapter for invoice read models."""

from __future__ import annotations

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, selectinload

from wasatch_api.finance.domain.entities import Invoice
from wasatch_api.finance.infrastructure.mapping import invoice_from_orm
from wasatch_api.shared.database.models import CustomerORM, InvoiceORM
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

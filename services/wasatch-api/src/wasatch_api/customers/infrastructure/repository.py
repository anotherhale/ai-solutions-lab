"""PostgreSQL adapter for customer queries."""

from __future__ import annotations

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session, selectinload

from wasatch_api.customers.domain.entities import (
    Customer,
    ServiceLocationDetail,
)
from wasatch_api.customers.infrastructure.mapping import (
    customer_from_orm,
    customer_summary_from_orm,
    location_from_orm,
)
from wasatch_api.shared.database.models import CustomerORM, ServiceLocationORM
from wasatch_api.shared.pagination import PageRequest, escape_like


class CustomerRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_business_id(self, business_id: str) -> Customer | None:
        stmt = (
            select(CustomerORM)
            .options(
                selectinload(CustomerORM.contacts),
                selectinload(CustomerORM.service_locations),
            )
            .where(CustomerORM.business_id == business_id)
        )
        row = self.session.scalar(stmt)
        if row is None:
            return None
        return customer_from_orm(row, include_children=True)

    def list_customers(
        self,
        page: PageRequest,
        *,
        query: str | None = None,
        status: str | None = None,
    ) -> tuple[list[Customer], int]:
        filters = []
        if status:
            filters.append(CustomerORM.status == status)
        if query:
            pattern = f"%{escape_like(query)}%"
            filters.append(
                or_(
                    CustomerORM.legal_name.ilike(pattern, escape="\\"),
                    CustomerORM.trade_name.ilike(pattern, escape="\\"),
                )
            )
        count_stmt = select(func.count()).select_from(CustomerORM)
        stmt: Select[tuple[CustomerORM]] = select(CustomerORM).order_by(
            CustomerORM.business_id
        )
        if filters:
            count_stmt = count_stmt.where(*filters)
            stmt = stmt.where(*filters)
        total = int(self.session.scalar(count_stmt) or 0)
        rows = self.session.scalars(
            stmt.offset(page.offset).limit(page.page_size)
        ).all()
        return [customer_from_orm(row, include_children=False) for row in rows], total

    def get_location(self, business_id: str) -> ServiceLocationDetail | None:
        stmt = (
            select(ServiceLocationORM)
            .options(selectinload(ServiceLocationORM.customer))
            .where(ServiceLocationORM.business_id == business_id)
        )
        row = self.session.scalar(stmt)
        if row is None:
            return None
        return ServiceLocationDetail(
            location=location_from_orm(row, row.customer.business_id),
            customer=customer_summary_from_orm(row.customer),
        )

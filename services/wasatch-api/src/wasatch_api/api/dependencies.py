"""FastAPI dependencies."""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy.orm import Session

from wasatch_api.customers.application.queries import CustomerQueries
from wasatch_api.customers.infrastructure.repository import CustomerRepository
from wasatch_api.shared.database.session import get_session_factory
from wasatch_api.work_orders.application.queries import WorkOrderQueries
from wasatch_api.work_orders.infrastructure.repository import WorkOrderRepository


def db_session() -> Iterator[Session]:
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


def customer_queries(session: Session) -> CustomerQueries:
    return CustomerQueries(CustomerRepository(session))


def work_order_queries(session: Session) -> WorkOrderQueries:
    return WorkOrderQueries(WorkOrderRepository(session))

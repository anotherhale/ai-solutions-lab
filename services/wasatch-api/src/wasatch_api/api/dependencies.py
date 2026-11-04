"""FastAPI dependencies."""

from __future__ import annotations

from collections.abc import Iterator

from fastapi import Request
from sqlalchemy.orm import Session

from wasatch_api.customer_service.application.queries import CustomerServiceQueries
from wasatch_api.customer_service.infrastructure.repository import (
    CustomerServiceRepository,
)
from wasatch_api.customers.application.queries import CustomerQueries
from wasatch_api.customers.infrastructure.repository import CustomerRepository
from wasatch_api.governance.application.queries import GovernanceQueries
from wasatch_api.governance.infrastructure.repository import GovernanceRepository
from wasatch_api.shared.database.session import get_session_factory
from wasatch_api.shared.errors import UnauthenticatedError
from wasatch_api.work_orders.application.queries import WorkOrderQueries
from wasatch_api.work_orders.infrastructure.repository import WorkOrderRepository
from wasatch_api.workforce.application.access import UNAUTHENTICATED_MESSAGE
from wasatch_api.workforce.domain.entities import LaboratoryActor


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


def customer_service_queries(session: Session) -> CustomerServiceQueries:
    return CustomerServiceQueries(CustomerServiceRepository(session))


def governance_queries(session: Session) -> GovernanceQueries:
    return GovernanceQueries(GovernanceRepository(session))


def require_laboratory_actor(request: Request) -> LaboratoryActor:
    """Return the synthetic employee the local adapter already resolved.

    Later write commands in this slice take this actor as the person acting.
    """

    actor = getattr(request.state, "laboratory_actor", None)
    if not isinstance(actor, LaboratoryActor):
        raise UnauthenticatedError(UNAUTHENTICATED_MESSAGE)
    return actor

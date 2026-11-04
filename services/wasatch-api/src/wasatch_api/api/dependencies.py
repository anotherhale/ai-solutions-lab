"""FastAPI dependencies."""

from __future__ import annotations

from collections.abc import Iterator

from fastapi import Request
from sqlalchemy.orm import Session

from wasatch_api.customer_service.application.queries import CustomerServiceQueries
from wasatch_api.customer_service.application.retrieval import RetrievalQueries
from wasatch_api.customer_service.infrastructure.procedure_corpus import (
    ProcedureCorpus,
)
from wasatch_api.customer_service.infrastructure.relational_retrieval import (
    RelationalTextRetrieval,
)
from wasatch_api.customer_service.infrastructure.repository import (
    CustomerServiceRepository,
)
from wasatch_api.customers.application.queries import CustomerQueries
from wasatch_api.customers.infrastructure.repository import CustomerRepository
from wasatch_api.governance.application.queries import GovernanceQueries
from wasatch_api.governance.infrastructure.repository import GovernanceRepository
from wasatch_api.shared.database.session import get_session_factory
from wasatch_api.work_orders.application.queries import WorkOrderQueries
from wasatch_api.work_orders.infrastructure.repository import WorkOrderRepository
from wasatch_api.workforce.application.access import require_authenticated_reader
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


def retrieval_queries(session: Session) -> RetrievalQueries:
    return RetrievalQueries(
        RelationalTextRetrieval(session, ProcedureCorpus.load_default())
    )


def governance_queries(session: Session) -> GovernanceQueries:
    return GovernanceQueries(GovernanceRepository(session))


def require_laboratory_actor(request: Request) -> LaboratoryActor:
    """Return the active synthetic employee required for a business read.

    The application service enforces that rule. Later write commands in this
    slice take this actor as the person acting. The header adapter does not
    grant a role by itself.
    """

    actor = getattr(request.state, "laboratory_actor", None)
    if not isinstance(actor, LaboratoryActor):
        actor = None
    return require_authenticated_reader(actor)

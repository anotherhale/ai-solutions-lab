"""FastAPI dependencies."""

from __future__ import annotations

from collections.abc import Iterator

from fastapi import Request
from sqlalchemy.orm import Session

from wasatch_api.ai.infrastructure.provider import build_model_provider
from wasatch_api.config import get_settings
from wasatch_api.customer_service.application.draft_reply import DraftSuggestedReply
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
from wasatch_api.documents.application.queries import DocumentQueries
from wasatch_api.documents.infrastructure.repository import DocumentRepository
from wasatch_api.governance.application.decisions import CustomerMessageDecisions
from wasatch_api.governance.application.queries import GovernanceQueries
from wasatch_api.governance.infrastructure.repository import GovernanceRepository
from wasatch_api.shared.database.session import get_session_factory
from wasatch_api.work_orders.application.queries import WorkOrderQueries
from wasatch_api.work_orders.infrastructure.repository import WorkOrderRepository
from wasatch_api.workforce.application.access import (
    LaboratoryAccessService,
    require_authenticated_reader,
)
from wasatch_api.workforce.domain.entities import LaboratoryActor
from wasatch_api.workforce.infrastructure.local_authenticator import (
    LocalEmployeeAuthenticator,
)
from wasatch_api.workforce.infrastructure.repository import EmployeeDirectory


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


def draft_suggested_replies(session: Session) -> DraftSuggestedReply:
    settings = get_settings()
    return DraftSuggestedReply(
        RelationalTextRetrieval(session, ProcedureCorpus.load_default()),
        build_model_provider(settings),
        CustomerServiceRepository(session),
    )


def governance_queries(session: Session) -> GovernanceQueries:
    return GovernanceQueries(GovernanceRepository(session))


def document_queries(session: Session) -> DocumentQueries:
    return DocumentQueries(DocumentRepository(session))


def customer_message_decisions(session: Session) -> CustomerMessageDecisions:
    settings = get_settings()
    access = LaboratoryAccessService(
        LocalEmployeeAuthenticator(EmployeeDirectory(session), app_env=settings.app_env)
    )
    return CustomerMessageDecisions(GovernanceRepository(session), access)


def require_laboratory_actor(request: Request) -> LaboratoryActor:
    """Return the active synthetic employee for this request.

    The application service enforces that rule. The customer-message decision
    takes this actor as the person acting. The header adapter does not grant
    a role by itself.
    """

    actor = getattr(request.state, "laboratory_actor", None)
    if not isinstance(actor, LaboratoryActor):
        actor = None
    return require_authenticated_reader(actor)

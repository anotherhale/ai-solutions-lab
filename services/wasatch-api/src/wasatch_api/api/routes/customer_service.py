"""Support-ticket, message, and interaction routes.

The draft command creates an unsent suggested reply. It does not deliver it.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from wasatch_api.api.dependencies import (
    customer_service_queries,
    db_session,
    draft_suggested_replies,
    require_laboratory_actor,
    retrieval_queries,
)
from wasatch_api.api.schemas import (
    InteractionOut,
    MessageOut,
    PageOut,
    SupportTicketDetailOut,
    SupportTicketListItemOut,
    TicketRetrievalOut,
)
from wasatch_api.customer_service.application.draft_reply import DraftSuggestedReply
from wasatch_api.customer_service.application.queries import CustomerServiceQueries
from wasatch_api.customer_service.application.retrieval import RetrievalQueries
from wasatch_api.workforce.domain.entities import LaboratoryActor

router = APIRouter(
    prefix="/api/v1",
    tags=["customer-service"],
    dependencies=[Depends(require_laboratory_actor)],
)

SessionDep = Annotated[Session, Depends(db_session)]


def queries(session: SessionDep) -> CustomerServiceQueries:
    return customer_service_queries(session)


QueriesDep = Annotated[CustomerServiceQueries, Depends(queries)]


def retrieval(session: SessionDep) -> RetrievalQueries:
    return retrieval_queries(session)


RetrievalDep = Annotated[RetrievalQueries, Depends(retrieval)]
ActorDep = Annotated[LaboratoryActor, Depends(require_laboratory_actor)]


def drafts(session: SessionDep) -> DraftSuggestedReply:
    return draft_suggested_replies(session)


DraftDep = Annotated[DraftSuggestedReply, Depends(drafts)]


@router.get("/support-tickets", response_model=PageOut[SupportTicketListItemOut])
def list_support_tickets(
    service: QueriesDep,
    customer_id: str | None = None,
    status: str | None = None,
    service_location_id: str | None = None,
    assigned_employee_id: str | None = None,
    page: int | None = Query(default=None, ge=1),
    page_size: int | None = Query(default=None, ge=1, le=100),
) -> PageOut[SupportTicketListItemOut]:
    items, total, request = service.list_support_tickets(
        page=page,
        page_size=page_size,
        customer_id=customer_id,
        status=status,
        service_location_id=service_location_id,
        assigned_employee_id=assigned_employee_id,
    )
    return PageOut(
        items=[SupportTicketListItemOut.from_domain(item) for item in items],
        page=request.page,
        page_size=request.page_size,
        total=total,
    )


@router.get("/support-tickets/{ticket_id}", response_model=SupportTicketDetailOut)
def get_support_ticket(ticket_id: str, service: QueriesDep) -> SupportTicketDetailOut:
    return SupportTicketDetailOut.from_domain(service.get_support_ticket(ticket_id))


@router.get("/messages", response_model=PageOut[MessageOut])
def list_messages(
    service: QueriesDep,
    support_ticket_id: str | None = None,
    status: str | None = None,
    page: int | None = Query(default=None, ge=1),
    page_size: int | None = Query(default=None, ge=1, le=100),
) -> PageOut[MessageOut]:
    items, total, request = service.list_messages(
        page=page,
        page_size=page_size,
        support_ticket_id=support_ticket_id,
        status=status,
    )
    return PageOut(
        items=[MessageOut.from_domain(item) for item in items],
        page=request.page,
        page_size=request.page_size,
        total=total,
    )


@router.get("/messages/{message_id}", response_model=MessageOut)
def get_message(message_id: str, service: QueriesDep) -> MessageOut:
    return MessageOut.from_domain(service.get_message(message_id))


@router.get("/interactions", response_model=PageOut[InteractionOut])
def list_interactions(
    service: QueriesDep,
    customer_id: str | None = None,
    support_ticket_id: str | None = None,
    page: int | None = Query(default=None, ge=1),
    page_size: int | None = Query(default=None, ge=1, le=100),
) -> PageOut[InteractionOut]:
    items, total, request = service.list_interactions(
        page=page,
        page_size=page_size,
        customer_id=customer_id,
        support_ticket_id=support_ticket_id,
    )
    return PageOut(
        items=[InteractionOut.from_domain(item) for item in items],
        page=request.page,
        page_size=request.page_size,
        total=total,
    )


@router.get("/interactions/{interaction_id}", response_model=InteractionOut)
def get_interaction(interaction_id: str, service: QueriesDep) -> InteractionOut:
    return InteractionOut.from_domain(service.get_interaction(interaction_id))


@router.get(
    "/support-tickets/{ticket_id}/retrieval",
    response_model=TicketRetrievalOut,
)
def retrieve_for_ticket(ticket_id: str, service: RetrievalDep) -> TicketRetrievalOut:
    return TicketRetrievalOut.from_domain(service.for_ticket(ticket_id))


@router.post(
    "/support-tickets/{ticket_id}/draft-replies",
    response_model=MessageOut,
)
def draft_suggested_reply(
    ticket_id: str, actor: ActorDep, service: DraftDep
) -> MessageOut:
    """Create an unsent suggested reply grounded in retrieval for this ticket."""

    return MessageOut.from_domain(service.draft(actor, ticket_id))

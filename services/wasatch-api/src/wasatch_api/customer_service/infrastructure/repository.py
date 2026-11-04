"""PostgreSQL adapter for customer-service queries."""

from __future__ import annotations

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, selectinload

from wasatch_api.customer_service.domain.entities import (
    Interaction,
    Message,
    SupportTicket,
)
from wasatch_api.customer_service.infrastructure.mapping import (
    interaction_from_orm,
    message_from_orm,
    support_ticket_from_orm,
)
from wasatch_api.shared.database.models import (
    InteractionORM,
    MessageORM,
    SupportTicketORM,
)
from wasatch_api.shared.pagination import PageRequest


def _restrict(stmt, count_stmt, criteria: list):
    if not criteria:
        return stmt, count_stmt
    return stmt.where(*criteria), count_stmt.where(*criteria)


class CustomerServiceRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_support_ticket(self, business_id: str) -> SupportTicket | None:
        stmt = (
            select(SupportTicketORM)
            .options(*_ticket_detail_options())
            .where(SupportTicketORM.business_id == business_id)
        )
        row = self.session.scalar(stmt)
        if row is None:
            return None
        return support_ticket_from_orm(row, detail=True)

    def list_support_tickets(
        self,
        page: PageRequest,
        *,
        customer_id: str | None = None,
        status: str | None = None,
        service_location_id: str | None = None,
        assigned_employee_id: str | None = None,
    ) -> tuple[list[SupportTicket], int]:
        stmt: Select[tuple[SupportTicketORM]] = select(SupportTicketORM).options(
            *_ticket_summary_options()
        )
        count_stmt = select(func.count()).select_from(SupportTicketORM)
        criteria = []
        if customer_id:
            criteria.append(SupportTicketORM.customer.has(business_id=customer_id))
        if status:
            criteria.append(SupportTicketORM.status == status)
        if service_location_id:
            criteria.append(
                SupportTicketORM.service_location.has(business_id=service_location_id)
            )
        if assigned_employee_id:
            criteria.append(
                SupportTicketORM.assigned_employee.has(business_id=assigned_employee_id)
            )
        stmt, count_stmt = _restrict(stmt, count_stmt, criteria)
        return _page(
            self.session,
            stmt.order_by(SupportTicketORM.business_id),
            count_stmt,
            page,
            lambda row: support_ticket_from_orm(row, detail=False),
        )

    def get_message(self, business_id: str) -> Message | None:
        stmt = (
            select(MessageORM)
            .options(*_message_options())
            .where(MessageORM.business_id == business_id)
        )
        row = self.session.scalar(stmt)
        if row is None:
            return None
        return message_from_orm(row)

    def list_messages(
        self,
        page: PageRequest,
        *,
        support_ticket_id: str | None = None,
        status: str | None = None,
    ) -> tuple[list[Message], int]:
        stmt: Select[tuple[MessageORM]] = select(MessageORM).options(
            *_message_options()
        )
        count_stmt = select(func.count()).select_from(MessageORM)
        criteria = []
        if support_ticket_id:
            criteria.append(
                MessageORM.support_ticket.has(business_id=support_ticket_id)
            )
        if status:
            criteria.append(MessageORM.status == status)
        stmt, count_stmt = _restrict(stmt, count_stmt, criteria)
        return _page(
            self.session,
            stmt.order_by(MessageORM.business_id),
            count_stmt,
            page,
            message_from_orm,
        )

    def get_interaction(self, business_id: str) -> Interaction | None:
        stmt = (
            select(InteractionORM)
            .options(*_interaction_options())
            .where(InteractionORM.business_id == business_id)
        )
        row = self.session.scalar(stmt)
        if row is None:
            return None
        return interaction_from_orm(row)

    def list_interactions(
        self,
        page: PageRequest,
        *,
        customer_id: str | None = None,
        support_ticket_id: str | None = None,
    ) -> tuple[list[Interaction], int]:
        stmt: Select[tuple[InteractionORM]] = select(InteractionORM).options(
            *_interaction_options()
        )
        count_stmt = select(func.count()).select_from(InteractionORM)
        criteria = []
        if customer_id:
            criteria.append(InteractionORM.customer.has(business_id=customer_id))
        if support_ticket_id:
            criteria.append(
                InteractionORM.support_ticket.has(business_id=support_ticket_id)
            )
        stmt, count_stmt = _restrict(stmt, count_stmt, criteria)
        return _page(
            self.session,
            stmt.order_by(InteractionORM.business_id),
            count_stmt,
            page,
            interaction_from_orm,
        )


def _ticket_summary_options():
    return (
        selectinload(SupportTicketORM.customer),
        selectinload(SupportTicketORM.contact),
        selectinload(SupportTicketORM.service_location),
        selectinload(SupportTicketORM.work_order),
        selectinload(SupportTicketORM.assigned_employee),
    )


def _ticket_detail_options():
    return (
        *_ticket_summary_options(),
        selectinload(SupportTicketORM.messages).selectinload(
            MessageORM.author_employee
        ),
        selectinload(SupportTicketORM.messages).selectinload(MessageORM.author_contact),
        selectinload(SupportTicketORM.messages).selectinload(MessageORM.support_ticket),
    )


def _message_options():
    return (
        selectinload(MessageORM.support_ticket),
        selectinload(MessageORM.author_employee),
        selectinload(MessageORM.author_contact),
    )


def _interaction_options():
    return (
        selectinload(InteractionORM.customer),
        selectinload(InteractionORM.contact),
        selectinload(InteractionORM.support_ticket),
        selectinload(InteractionORM.work_order),
        selectinload(InteractionORM.employee),
    )


def _page(session: Session, stmt, count_stmt, page: PageRequest, mapper):
    total = int(session.scalar(count_stmt) or 0)
    rows = session.scalars(stmt.offset(page.offset).limit(page.page_size)).all()
    return [mapper(row) for row in rows], total

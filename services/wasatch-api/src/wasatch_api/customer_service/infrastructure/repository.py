"""PostgreSQL adapter for customer-service queries and suggested replies."""

from __future__ import annotations

import uuid
from datetime import datetime

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
    ApprovalDecisionORM,
    ApprovalRequestORM,
    AuditEventORM,
    EmployeeORM,
    InteractionORM,
    MessageORM,
    SupportTicketORM,
)
from wasatch_api.shared.errors import InvalidParameterError, NotFoundError
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

    def save_suggested_reply(
        self,
        *,
        ticket_id: str,
        author_employee_id: str,
        body: str,
        requires_approval: bool,
        drafted_at: datetime,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> Message:
        """Insert an unsent reply. A commitment also opens an approval.

        ``sent`` is not a status this method writes. No delivery adapter is
        called. Audit details record the provider model and token counts, not
        the message body.
        """

        cleaned = body.strip()
        if not cleaned:
            raise InvalidParameterError("suggested reply was empty")
        ticket = self.session.scalar(
            select(SupportTicketORM).where(SupportTicketORM.business_id == ticket_id)
        )
        if ticket is None:
            raise NotFoundError(f"support ticket {ticket_id} was not found")
        employee = self.session.scalar(
            select(EmployeeORM).where(EmployeeORM.business_id == author_employee_id)
        )
        if employee is None:
            raise NotFoundError(f"employee {author_employee_id} was not found")

        status = "pending_approval" if requires_approval else "draft"
        message_business_id = _next_business_id(self.session, MessageORM, "msg_")
        approval = None
        if requires_approval:
            approval = ApprovalRequestORM(
                id=uuid.uuid4(),
                business_id=_next_business_id(self.session, ApprovalRequestORM, "apr_"),
                action_type="send_customer_message",
                status="pending",
                requested_by_employee_id=employee.id,
                subject_type="message",
                subject_id=message_business_id,
                rationale=(
                    "Outbound reply would commit Wasatch and needs approval "
                    "before it can be sent."
                ),
                requested_at=drafted_at,
                created_at=drafted_at,
                updated_at=drafted_at,
                requested_by=employee,
            )
            self.session.add(approval)
            self.session.flush()

        message = MessageORM(
            id=uuid.uuid4(),
            business_id=message_business_id,
            support_ticket_id=ticket.id,
            direction="outbound",
            channel=ticket.channel,
            body=cleaned,
            status=status,
            author_employee_id=employee.id,
            requires_approval=requires_approval,
            approval_request_id=approval.id if approval is not None else None,
            sent_at=drafted_at,
            created_at=drafted_at,
            updated_at=drafted_at,
            support_ticket=ticket,
            author_employee=employee,
            approval_request=approval,
        )
        audit = AuditEventORM(
            id=uuid.uuid4(),
            business_id=_next_business_id(self.session, AuditEventORM, "aud_"),
            occurred_at=drafted_at,
            actor_type="employee",
            actor_employee_id=employee.id,
            action="message.drafted",
            subject_type="message",
            subject_id=message_business_id,
            outcome="pending" if requires_approval else "succeeded",
            approval_request_id=approval.id if approval is not None else None,
            details={
                "status": status,
                "requires_approval": requires_approval,
                "model": model,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
            },
            actor_employee=employee,
            approval_request=approval,
        )
        self.session.add(message)
        self.session.add(audit)
        try:
            self.session.flush()
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        stored = self.get_message(message_business_id)
        if stored is None:
            raise NotFoundError(f"message {message_business_id} was not found")
        if stored.status == "sent":
            raise InvalidParameterError("a suggested reply is not sent")
        return stored


def _next_business_id(session: Session, model, prefix: str) -> str:
    business_ids = session.scalars(select(model.business_id)).all()
    highest = 0
    for business_id in business_ids:
        suffix = business_id.removeprefix(prefix)
        if business_id.startswith(prefix) and suffix.isdigit():
            highest = max(highest, int(suffix))
    nxt = highest + 1
    if nxt > 9999:
        raise InvalidParameterError(f"{prefix} identifiers are exhausted")
    return f"{prefix}{nxt:04d}"


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
        selectinload(SupportTicketORM.messages)
        .selectinload(MessageORM.approval_request)
        .selectinload(ApprovalRequestORM.requested_by),
        selectinload(SupportTicketORM.messages)
        .selectinload(MessageORM.approval_request)
        .selectinload(ApprovalRequestORM.reviewer),
        selectinload(SupportTicketORM.messages)
        .selectinload(MessageORM.approval_request)
        .selectinload(ApprovalRequestORM.decision_history)
        .selectinload(ApprovalDecisionORM.actor),
    )


def _message_options():
    return (
        selectinload(MessageORM.support_ticket),
        selectinload(MessageORM.author_employee),
        selectinload(MessageORM.author_contact),
        selectinload(MessageORM.approval_request).selectinload(
            ApprovalRequestORM.requested_by
        ),
        selectinload(MessageORM.approval_request).selectinload(
            ApprovalRequestORM.reviewer
        ),
        selectinload(MessageORM.approval_request)
        .selectinload(ApprovalRequestORM.decision_history)
        .selectinload(ApprovalDecisionORM.actor),
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

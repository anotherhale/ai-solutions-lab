"""ORM to domain mapping for customer service."""

from __future__ import annotations

from wasatch_api.customer_service.domain.entities import (
    Interaction,
    Message,
    SupportTicket,
)
from wasatch_api.governance.infrastructure.mapping import approval_from_orm
from wasatch_api.shared.database.models import (
    InteractionORM,
    MessageORM,
    SupportTicketORM,
)


def message_from_orm(row: MessageORM) -> Message:
    approval = approval_from_orm(row.approval_request) if row.approval_request else None
    return Message(
        id=row.business_id,
        support_ticket_id=row.support_ticket.business_id,
        direction=row.direction,
        channel=row.channel,
        body=row.body,
        status=row.status,
        author_employee_id=(
            row.author_employee.business_id if row.author_employee else None
        ),
        author_contact_id=(
            row.author_contact.business_id if row.author_contact else None
        ),
        requires_approval=row.requires_approval,
        approval_request_id=approval.id if approval else None,
        approval_request=approval,
        sent_at=row.sent_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def support_ticket_from_orm(row: SupportTicketORM, *, detail: bool) -> SupportTicket:
    ticket = SupportTicket(
        id=row.business_id,
        customer_id=row.customer.business_id,
        contact_id=row.contact.business_id if row.contact else None,
        service_location_id=(
            row.service_location.business_id if row.service_location else None
        ),
        work_order_id=row.work_order.business_id if row.work_order else None,
        status=row.status,
        priority=row.priority,
        channel=row.channel,
        subject=row.subject,
        assigned_employee_id=(
            row.assigned_employee.business_id if row.assigned_employee else None
        ),
        opened_at=row.opened_at,
        resolved_at=row.resolved_at,
        closed_at=row.closed_at,
        related_document_ids=list(row.related_document_ids or []),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )
    if detail:
        ticket.messages = [message_from_orm(item) for item in row.messages]
    return ticket


def interaction_from_orm(row: InteractionORM) -> Interaction:
    return Interaction(
        id=row.business_id,
        customer_id=row.customer.business_id,
        contact_id=row.contact.business_id if row.contact else None,
        support_ticket_id=(
            row.support_ticket.business_id if row.support_ticket else None
        ),
        work_order_id=row.work_order.business_id if row.work_order else None,
        channel=row.channel,
        occurred_at=row.occurred_at,
        summary=row.summary,
        employee_id=row.employee.business_id,
        outcome=row.outcome,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )

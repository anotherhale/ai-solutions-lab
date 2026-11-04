"""ORM to domain mapping for follow-up visits."""

from __future__ import annotations

from wasatch_api.shared.database.models import FollowUpVisitORM
from wasatch_api.workflows.domain.entities import FollowUpVisit


def follow_up_from_orm(row: FollowUpVisitORM) -> FollowUpVisit:
    decided_by = row.decided_by.business_id if row.decided_by is not None else None
    return FollowUpVisit(
        id=row.business_id,
        approval_request_id=row.approval_request.business_id,
        message_id=row.message.business_id,
        support_ticket_id=row.support_ticket.business_id,
        status=row.status,
        opened_by_employee_id=row.opened_by.business_id,
        opened_at=row.opened_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
        decided_by_employee_id=decided_by,
        decided_at=row.decided_at,
        note=row.decision_note,
    )

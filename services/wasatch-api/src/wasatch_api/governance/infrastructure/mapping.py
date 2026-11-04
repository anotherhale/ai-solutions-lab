"""ORM to domain mapping for approvals and audit events."""

from __future__ import annotations

from wasatch_api.governance.domain.entities import (
    ApprovalDecision,
    ApprovalRequest,
    AuditEvent,
)
from wasatch_api.shared.database.models import (
    ApprovalRequestORM,
    AuditEventORM,
)


def approval_from_orm(row: ApprovalRequestORM) -> ApprovalRequest:
    history = tuple(
        ApprovalDecision(
            at=item.at,
            actor_employee_id=item.actor.business_id,
            from_status=item.from_status,
            to_status=item.to_status,
            note=item.note,
        )
        for item in row.decision_history
    )
    return ApprovalRequest(
        id=row.business_id,
        action_type=row.action_type,
        status=row.status,
        requested_by_employee_id=row.requested_by.business_id,
        reviewer_employee_id=row.reviewer.business_id if row.reviewer else None,
        subject_type=row.subject_type,
        subject_id=row.subject_id,
        rationale=row.rationale,
        decision_notes=row.decision_notes,
        requested_at=row.requested_at,
        decided_at=row.decided_at,
        executed_at=row.executed_at,
        decision_history=history,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def audit_event_from_orm(row: AuditEventORM) -> AuditEvent:
    return AuditEvent(
        id=row.business_id,
        occurred_at=row.occurred_at,
        actor_type=row.actor_type,
        actor_employee_id=(
            row.actor_employee.business_id if row.actor_employee else None
        ),
        action=row.action,
        subject_type=row.subject_type,
        subject_id=row.subject_id,
        outcome=row.outcome,
        approval_request_id=(
            row.approval_request.business_id if row.approval_request else None
        ),
        details=dict(row.details) if row.details else None,
    )

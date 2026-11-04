"""PostgreSQL adapter for follow-up visits.

Audit events are insert-only. This repository inserts one audit row per
transition. It exposes no update or delete of audit events. It does not
change the message, the approval's executed time, a work order, an
appointment, or an invoice.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from wasatch_api.shared.database.models import (
    ApprovalRequestORM,
    AuditEventORM,
    EmployeeORM,
    FollowUpVisitORM,
    MessageORM,
)
from wasatch_api.shared.errors import InvalidParameterError, NotFoundError
from wasatch_api.workflows.domain.entities import CustomerMessageApproval, FollowUpVisit
from wasatch_api.workflows.domain.follow_up import (
    UNSCHEDULED,
    audit_action,
    opened_status,
)
from wasatch_api.workflows.infrastructure.mapping import follow_up_from_orm


class FollowUpVisitRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_approval(self, business_id: str) -> CustomerMessageApproval | None:
        row = self.session.scalar(
            select(ApprovalRequestORM).where(
                ApprovalRequestORM.business_id == business_id
            )
        )
        if row is None:
            return None
        return CustomerMessageApproval(
            id=row.business_id,
            action_type=row.action_type,
            subject_type=row.subject_type,
            status=row.status,
        )

    def get(self, business_id: str) -> FollowUpVisit | None:
        row = self.session.scalar(
            self._by_id(FollowUpVisitORM.business_id == business_id)
        )
        if row is None:
            return None
        return follow_up_from_orm(row)

    def get_for_approval(self, approval_id: str) -> FollowUpVisit | None:
        row = self.session.scalar(
            self._by_id(FollowUpVisitORM.approval_request.has(business_id=approval_id))
        )
        if row is None:
            return None
        return follow_up_from_orm(row)

    def open_follow_up(
        self,
        approval_id: str,
        *,
        actor_employee_id: str,
        opened_at: datetime,
    ) -> FollowUpVisit:
        """Insert one unscheduled visit and one audit row.

        The message row and the approval row are read and not updated.
        ``executed_at`` stays unset. No work order or appointment is created.
        """

        approval = self._lock_approval(approval_id)
        opened_status(approval.action_type, approval.subject_type, approval.status)
        existing = self.session.scalar(
            select(FollowUpVisitORM.id).where(
                FollowUpVisitORM.approval_request_id == approval.id
            )
        )
        if existing is not None:
            raise InvalidParameterError("follow-up visit is already open")
        message = self.session.scalar(
            select(MessageORM).where(MessageORM.business_id == approval.subject_id)
        )
        if message is None:
            raise NotFoundError(f"message {approval.subject_id} was not found")
        employee = self._employee(actor_employee_id)
        visit = FollowUpVisitORM(
            id=uuid.uuid4(),
            business_id=self._next_business_id(FollowUpVisitORM, "fuv_"),
            approval_request_id=approval.id,
            message_id=message.id,
            support_ticket_id=message.support_ticket_id,
            status=UNSCHEDULED,
            opened_by_employee_id=employee.id,
            opened_at=opened_at,
            created_at=opened_at,
            updated_at=opened_at,
        )
        self.session.add(visit)
        self._insert_audit(
            employee=employee,
            approval=approval,
            action=audit_action(UNSCHEDULED),
            subject_id=visit.business_id,
            occurred_at=opened_at,
            details={"to_status": UNSCHEDULED},
        )
        return self._commit(visit.id)

    def record_decision(
        self,
        approval_id: str,
        *,
        actor_employee_id: str,
        to_status: str,
        decided_at: datetime,
        note: str | None,
    ) -> FollowUpVisit:
        """Move an unscheduled visit to confirmed or cancelled.

        Inserts one audit row. Does not update the message, set
        ``executed_at``, assign a technician, or create an appointment.
        """

        approval = self._lock_approval(approval_id)
        visit = self.session.scalar(
            select(FollowUpVisitORM)
            .where(FollowUpVisitORM.approval_request_id == approval.id)
            .with_for_update()
        )
        if visit is None:
            raise InvalidParameterError("no follow-up visit is open")
        if visit.status != UNSCHEDULED:
            raise InvalidParameterError(f"follow-up visit is {visit.status}")
        employee = self._employee(actor_employee_id)
        from_status = visit.status
        visit.status = to_status
        visit.decided_by_employee_id = employee.id
        visit.decided_at = decided_at
        visit.decision_note = note
        visit.updated_at = decided_at
        self._insert_audit(
            employee=employee,
            approval=approval,
            action=audit_action(to_status),
            subject_id=visit.business_id,
            occurred_at=decided_at,
            details={"from_status": from_status, "to_status": to_status},
        )
        return self._commit(visit.id)

    def _lock_approval(self, approval_id: str) -> ApprovalRequestORM:
        row = self.session.scalar(
            select(ApprovalRequestORM)
            .where(ApprovalRequestORM.business_id == approval_id)
            .with_for_update()
        )
        if row is None:
            raise NotFoundError(f"approval request {approval_id} was not found")
        return row

    def _employee(self, business_id: str) -> EmployeeORM:
        row = self.session.scalar(
            select(EmployeeORM).where(EmployeeORM.business_id == business_id)
        )
        if row is None:
            raise NotFoundError(f"employee {business_id} was not found")
        return row

    def _insert_audit(
        self,
        *,
        employee: EmployeeORM,
        approval: ApprovalRequestORM,
        action: str,
        subject_id: str,
        occurred_at: datetime,
        details: dict[str, str],
    ) -> None:
        audit = AuditEventORM(
            id=uuid.uuid4(),
            business_id=self._next_business_id(AuditEventORM, "aud_"),
            occurred_at=occurred_at,
            actor_type="employee",
            actor_employee_id=employee.id,
            action=action,
            subject_type="follow_up_visit",
            subject_id=subject_id,
            outcome="succeeded",
            approval_request_id=approval.id,
            details=details,
        )
        self.session.add(audit)

    def _commit(self, visit_id: uuid.UUID) -> FollowUpVisit:
        try:
            self.session.flush()
            row = self.session.scalar(self._by_id(FollowUpVisitORM.id == visit_id))
            if row is None:
                raise NotFoundError("follow-up visit was not found")
            recorded = follow_up_from_orm(row)
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        return recorded

    def _by_id(self, criterion):
        return select(FollowUpVisitORM).where(criterion).options(*_visit_options())

    def _next_business_id(self, model, prefix: str) -> str:
        business_ids = self.session.scalars(select(model.business_id)).all()
        highest = 0
        for business_id in business_ids:
            suffix = business_id.removeprefix(prefix)
            if business_id.startswith(prefix) and suffix.isdigit():
                highest = max(highest, int(suffix))
        nxt = highest + 1
        if nxt > 9999:
            raise InvalidParameterError(f"{prefix} identifiers are exhausted")
        return f"{prefix}{nxt:04d}"


def _visit_options():
    return (
        selectinload(FollowUpVisitORM.approval_request),
        selectinload(FollowUpVisitORM.message),
        selectinload(FollowUpVisitORM.support_ticket),
        selectinload(FollowUpVisitORM.opened_by),
        selectinload(FollowUpVisitORM.decided_by),
    )

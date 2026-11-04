"""PostgreSQL adapter for approval and audit records.

Audit events are insert-only. This repository may insert one audit row for a
customer-message decision. It exposes no update or delete of audit events,
and it does not change the message.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, selectinload

from wasatch_api.governance.domain.entities import ApprovalRequest, AuditEvent
from wasatch_api.governance.infrastructure.mapping import (
    approval_from_orm,
    audit_event_from_orm,
)
from wasatch_api.shared.database.models import (
    ApprovalDecisionORM,
    ApprovalRequestORM,
    AuditEventORM,
    EmployeeORM,
)
from wasatch_api.shared.errors import InvalidParameterError, NotFoundError
from wasatch_api.shared.pagination import PageRequest


def _restrict(stmt, count_stmt, criteria: list):
    if not criteria:
        return stmt, count_stmt
    return stmt.where(*criteria), count_stmt.where(*criteria)


class GovernanceRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_approval_request(self, business_id: str) -> ApprovalRequest | None:
        stmt = (
            select(ApprovalRequestORM)
            .options(*_approval_options())
            .where(ApprovalRequestORM.business_id == business_id)
        )
        row = self.session.scalar(stmt)
        if row is None:
            return None
        return approval_from_orm(row)

    def list_approval_requests(
        self,
        page: PageRequest,
        *,
        status: str | None = None,
        action_type: str | None = None,
    ) -> tuple[list[ApprovalRequest], int]:
        stmt: Select[tuple[ApprovalRequestORM]] = select(ApprovalRequestORM).options(
            *_approval_options()
        )
        count_stmt = select(func.count()).select_from(ApprovalRequestORM)
        criteria = []
        if status:
            criteria.append(ApprovalRequestORM.status == status)
        if action_type:
            criteria.append(ApprovalRequestORM.action_type == action_type)
        stmt, count_stmt = _restrict(stmt, count_stmt, criteria)
        return _page(
            self.session,
            stmt.order_by(ApprovalRequestORM.business_id),
            count_stmt,
            page,
            approval_from_orm,
        )

    def get_audit_event(self, business_id: str) -> AuditEvent | None:
        stmt = (
            select(AuditEventORM)
            .options(*_audit_options())
            .where(AuditEventORM.business_id == business_id)
        )
        row = self.session.scalar(stmt)
        if row is None:
            return None
        return audit_event_from_orm(row)

    def list_audit_events(
        self,
        page: PageRequest,
        *,
        outcome: str | None = None,
        approval_request_id: str | None = None,
    ) -> tuple[list[AuditEvent], int]:
        stmt: Select[tuple[AuditEventORM]] = select(AuditEventORM).options(
            *_audit_options()
        )
        count_stmt = select(func.count()).select_from(AuditEventORM)
        criteria = []
        if outcome:
            criteria.append(AuditEventORM.outcome == outcome)
        if approval_request_id:
            criteria.append(
                AuditEventORM.approval_request.has(business_id=approval_request_id)
            )
        stmt, count_stmt = _restrict(stmt, count_stmt, criteria)
        return _page(
            self.session,
            stmt.order_by(AuditEventORM.business_id),
            count_stmt,
            page,
            audit_event_from_orm,
        )

    def record_customer_message_decision(
        self,
        approval_id: str,
        *,
        actor_employee_id: str,
        to_status: str,
        decided_at: datetime,
        note: str | None,
    ) -> ApprovalRequest:
        """Append one decision and insert one audit row.

        The message row is not loaded. ``executed_at`` stays unset, so this
        write cannot record delivery.
        """

        row = self.session.scalar(
            select(ApprovalRequestORM)
            .options(*_approval_options())
            .where(ApprovalRequestORM.business_id == approval_id)
        )
        if row is None:
            raise NotFoundError(f"approval request {approval_id} was not found")
        if row.action_type != "send_customer_message" or row.subject_type != "message":
            raise InvalidParameterError(
                f"approval request {approval_id} is not a customer message decision"
            )
        if row.status != "pending":
            raise InvalidParameterError(
                f"approval request {approval_id} is {row.status}"
            )
        employee = self.session.scalar(
            select(EmployeeORM).where(EmployeeORM.business_id == actor_employee_id)
        )
        if employee is None:
            raise NotFoundError(f"employee {actor_employee_id} was not found")

        from_status = row.status
        entry = ApprovalDecisionORM(
            id=uuid.uuid4(),
            approval_request_id=row.id,
            position=len(row.decision_history),
            at=decided_at,
            actor_employee_id=employee.id,
            from_status=from_status,
            to_status=to_status,
            note=note,
            actor=employee,
        )
        row.decision_history.append(entry)
        row.status = to_status
        row.reviewer = employee
        row.reviewer_employee_id = employee.id
        row.decided_at = decided_at
        row.decision_notes = note
        row.updated_at = decided_at
        audit = AuditEventORM(
            id=uuid.uuid4(),
            business_id=self._next_audit_business_id(),
            occurred_at=decided_at,
            actor_type="employee",
            actor_employee_id=employee.id,
            action="approval.decided",
            subject_type="approval_request",
            subject_id=row.business_id,
            outcome="succeeded",
            approval_request_id=row.id,
            details={"from_status": from_status, "to_status": to_status},
            actor_employee=employee,
            approval_request=row,
        )
        self.session.add(audit)
        try:
            self.session.flush()
            recorded = approval_from_orm(row)
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        return recorded

    def _next_audit_business_id(self) -> str:
        business_ids = self.session.scalars(select(AuditEventORM.business_id)).all()
        highest = 0
        for business_id in business_ids:
            suffix = business_id.removeprefix("aud_")
            if business_id.startswith("aud_") and suffix.isdigit():
                highest = max(highest, int(suffix))
        nxt = highest + 1
        if nxt > 9999:
            raise InvalidParameterError("audit event identifiers are exhausted")
        return f"aud_{nxt:04d}"


def _approval_options():
    return (
        selectinload(ApprovalRequestORM.requested_by),
        selectinload(ApprovalRequestORM.reviewer),
        selectinload(ApprovalRequestORM.decision_history).selectinload(
            ApprovalDecisionORM.actor
        ),
    )


def _audit_options():
    return (
        selectinload(AuditEventORM.actor_employee),
        selectinload(AuditEventORM.approval_request),
    )


def _page(session: Session, stmt, count_stmt, page: PageRequest, mapper):
    total = int(session.scalar(count_stmt) or 0)
    rows = session.scalars(stmt.offset(page.offset).limit(page.page_size)).all()
    return [mapper(row) for row in rows], total

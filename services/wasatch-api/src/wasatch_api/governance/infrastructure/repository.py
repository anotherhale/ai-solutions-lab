"""PostgreSQL adapter for approval and audit queries.

Audit events are insert-only. This repository exposes no update or delete.
"""

from __future__ import annotations

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
)
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

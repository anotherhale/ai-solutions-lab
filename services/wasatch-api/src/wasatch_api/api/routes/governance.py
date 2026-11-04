"""Read-only approval-request and audit-event routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from wasatch_api.api.dependencies import db_session, governance_queries
from wasatch_api.api.schemas import (
    ApprovalRequestOut,
    AuditEventOut,
    PageOut,
)
from wasatch_api.governance.application.queries import GovernanceQueries

router = APIRouter(prefix="/api/v1", tags=["governance"])

SessionDep = Annotated[Session, Depends(db_session)]


def queries(session: SessionDep) -> GovernanceQueries:
    return governance_queries(session)


QueriesDep = Annotated[GovernanceQueries, Depends(queries)]


@router.get("/approval-requests", response_model=PageOut[ApprovalRequestOut])
def list_approval_requests(
    service: QueriesDep,
    status: str | None = None,
    action_type: str | None = None,
    page: int | None = Query(default=None, ge=1),
    page_size: int | None = Query(default=None, ge=1, le=100),
) -> PageOut[ApprovalRequestOut]:
    items, total, request = service.list_approval_requests(
        page=page,
        page_size=page_size,
        status=status,
        action_type=action_type,
    )
    return PageOut(
        items=[ApprovalRequestOut.from_domain(item) for item in items],
        page=request.page,
        page_size=request.page_size,
        total=total,
    )


@router.get("/approval-requests/{approval_id}", response_model=ApprovalRequestOut)
def get_approval_request(approval_id: str, service: QueriesDep) -> ApprovalRequestOut:
    return ApprovalRequestOut.from_domain(service.get_approval_request(approval_id))


@router.get("/audit-events", response_model=PageOut[AuditEventOut])
def list_audit_events(
    service: QueriesDep,
    outcome: str | None = None,
    approval_request_id: str | None = None,
    page: int | None = Query(default=None, ge=1),
    page_size: int | None = Query(default=None, ge=1, le=100),
) -> PageOut[AuditEventOut]:
    items, total, request = service.list_audit_events(
        page=page,
        page_size=page_size,
        outcome=outcome,
        approval_request_id=approval_request_id,
    )
    return PageOut(
        items=[AuditEventOut.from_domain(item) for item in items],
        page=request.page,
        page_size=request.page_size,
        total=total,
    )


@router.get("/audit-events/{audit_event_id}", response_model=AuditEventOut)
def get_audit_event(audit_event_id: str, service: QueriesDep) -> AuditEventOut:
    return AuditEventOut.from_domain(service.get_audit_event(audit_event_id))

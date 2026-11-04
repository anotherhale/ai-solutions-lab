"""Read use cases for approval requests and audit events."""

from __future__ import annotations

from wasatch_api.governance.domain.entities import ApprovalRequest, AuditEvent
from wasatch_api.governance.infrastructure.repository import GovernanceRepository
from wasatch_api.shared.errors import NotFoundError
from wasatch_api.shared.pagination import (
    PageRequest,
    parse_page,
    validate_approval_action_type,
    validate_approval_status,
    validate_audit_outcome,
)


class GovernanceQueries:
    def __init__(self, repository: GovernanceRepository) -> None:
        self.repository = repository

    def list_approval_requests(
        self,
        *,
        page: int | None,
        page_size: int | None,
        status: str | None,
        action_type: str | None,
    ) -> tuple[list[ApprovalRequest], int, PageRequest]:
        request = parse_page(page, page_size)
        items, total = self.repository.list_approval_requests(
            request,
            status=validate_approval_status(status),
            action_type=validate_approval_action_type(action_type),
        )
        return items, total, request

    def get_approval_request(self, approval_id: str) -> ApprovalRequest:
        approval = self.repository.get_approval_request(approval_id)
        if approval is None:
            raise NotFoundError(f"approval request {approval_id} was not found")
        return approval

    def list_audit_events(
        self,
        *,
        page: int | None,
        page_size: int | None,
        outcome: str | None,
        approval_request_id: str | None,
    ) -> tuple[list[AuditEvent], int, PageRequest]:
        request = parse_page(page, page_size)
        items, total = self.repository.list_audit_events(
            request,
            outcome=validate_audit_outcome(outcome),
            approval_request_id=approval_request_id,
        )
        return items, total, request

    def get_audit_event(self, audit_event_id: str) -> AuditEvent:
        event = self.repository.get_audit_event(audit_event_id)
        if event is None:
            raise NotFoundError(f"audit event {audit_event_id} was not found")
        return event

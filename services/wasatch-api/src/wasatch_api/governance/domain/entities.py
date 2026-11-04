"""Governance domain records used by application services."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ApprovalDecision:
    at: datetime
    actor_employee_id: str
    from_status: str
    to_status: str
    note: str | None = None


@dataclass(frozen=True)
class ApprovalRequest:
    id: str
    action_type: str
    status: str
    requested_by_employee_id: str
    subject_type: str
    subject_id: str
    rationale: str
    requested_at: datetime
    created_at: datetime
    updated_at: datetime
    decision_history: tuple[ApprovalDecision, ...] = ()
    reviewer_employee_id: str | None = None
    decision_notes: str | None = None
    decided_at: datetime | None = None
    executed_at: datetime | None = None


@dataclass(frozen=True)
class AuditEvent:
    id: str
    occurred_at: datetime
    actor_type: str
    action: str
    subject_type: str
    subject_id: str
    outcome: str
    actor_employee_id: str | None = None
    approval_request_id: str | None = None
    details: dict | None = None

"""Follow-up visit records. Synthetic laboratory data only."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class CustomerMessageApproval:
    """The approval facts required to open a follow-up. No message body."""

    id: str
    action_type: str
    subject_type: str
    status: str


@dataclass(frozen=True)
class FollowUpVisit:
    """A visit opened from an approved customer message.

    ``unscheduled`` has no technician and no appointment. Confirm and cancel
    record the dispatcher's decision. They do not book a window.
    """

    id: str
    approval_request_id: str
    message_id: str
    support_ticket_id: str
    status: str
    opened_by_employee_id: str
    opened_at: datetime
    created_at: datetime
    updated_at: datetime
    decided_by_employee_id: str | None = None
    decided_at: datetime | None = None
    note: str | None = None

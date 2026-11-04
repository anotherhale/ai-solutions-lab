"""Human approve or reject for one pending customer message.

The command records the decision and an audit event. It does not send email,
SMS, or any other delivery, and it does not mark the message sent.
"""

from __future__ import annotations

from datetime import UTC, datetime

from wasatch_api.governance.domain.entities import ApprovalRequest
from wasatch_api.governance.infrastructure.repository import GovernanceRepository
from wasatch_api.shared.errors import InvalidParameterError, NotFoundError
from wasatch_api.workforce.application.access import LaboratoryAccessService
from wasatch_api.workforce.domain.entities import LaboratoryActor

CUSTOMER_MESSAGE_DECISIONS = frozenset({"approved", "rejected"})
_CUSTOMER_MESSAGE_ACTION = "send_customer_message"


class CustomerMessageDecisions:
    """Record an approver's decision on a pending ``send_customer_message``."""

    def __init__(
        self, repository: GovernanceRepository, access: LaboratoryAccessService
    ) -> None:
        self._repository = repository
        self._access = access

    def decide(
        self,
        actor: LaboratoryActor,
        approval_id: str,
        *,
        decision: str,
        note: str | None,
    ) -> ApprovalRequest:
        self._access.authorize_approval(actor)
        if decision not in CUSTOMER_MESSAGE_DECISIONS:
            raise InvalidParameterError(
                f"unsupported customer message decision: {decision}"
            )
        approval = self._repository.get_approval_request(approval_id)
        if approval is None:
            raise NotFoundError(f"approval request {approval_id} was not found")
        if (
            approval.action_type != _CUSTOMER_MESSAGE_ACTION
            or approval.subject_type != "message"
        ):
            raise InvalidParameterError(
                f"approval request {approval_id} is not a customer message decision"
            )
        if approval.status != "pending":
            raise InvalidParameterError(
                f"approval request {approval_id} is {approval.status}"
            )
        return self._repository.record_customer_message_decision(
            approval_id,
            actor_employee_id=actor.employee_id,
            to_status=decision,
            decided_at=datetime.now(UTC),
            note=_clean_note(note),
        )


def _clean_note(note: str | None) -> str | None:
    if note is None:
        return None
    cleaned = note.strip()
    return cleaned or None

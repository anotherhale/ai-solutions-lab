"""Rules for opening and deciding a follow-up visit.

The visit can be opened only from a customer-message approval that an
approver has already approved. It stays unscheduled until a dispatcher
confirms or cancels it. These functions do not write, send a message, assign
a technician, or post an invoice.
"""

from __future__ import annotations

from wasatch_api.shared.errors import InvalidParameterError

CUSTOMER_MESSAGE_ACTION = "send_customer_message"
UNSCHEDULED = "unscheduled"
CONFIRMED = "confirmed"
CANCELLED = "cancelled"
OPEN = "open"
CONFIRM = "confirm"
CANCEL = "cancel"
FOLLOW_UP_DECISIONS = frozenset({OPEN, CONFIRM, CANCEL})
AUDIT_OPENED = "follow_up_visit.opened"
AUDIT_CONFIRMED = "follow_up_visit.confirmed"
AUDIT_CANCELLED = "follow_up_visit.cancelled"

_DECISION_STATUS = {CONFIRM: CONFIRMED, CANCEL: CANCELLED}
_AUDIT_ACTION = {
    UNSCHEDULED: AUDIT_OPENED,
    CONFIRMED: AUDIT_CONFIRMED,
    CANCELLED: AUDIT_CANCELLED,
}


def opened_status(action_type: str, subject_type: str, approval_status: str) -> str:
    """Return ``unscheduled`` when the approval can open a visit.

    Any other approval raises. The caller must not insert a row in that case.
    """

    if action_type != CUSTOMER_MESSAGE_ACTION or subject_type != "message":
        raise InvalidParameterError(
            "follow-up visits open only from an approved customer message"
        )
    if approval_status != "approved":
        raise InvalidParameterError(
            "a follow-up visit opens only after an approver has approved the request"
        )
    return UNSCHEDULED


def next_status(current: str, decision: str) -> str:
    """Confirm or cancel an unscheduled visit. Other states stay unchanged."""

    if decision not in _DECISION_STATUS:
        raise InvalidParameterError(f"unsupported follow-up decision: {decision}")
    if current != UNSCHEDULED:
        raise InvalidParameterError(f"follow-up visit is {current}")
    return _DECISION_STATUS[decision]


def audit_action(status: str) -> str:
    try:
        return _AUDIT_ACTION[status]
    except KeyError as exc:
        raise InvalidParameterError(f"follow-up visit is {status}") from exc

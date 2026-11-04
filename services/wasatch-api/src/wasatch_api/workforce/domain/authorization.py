"""Authorization rules for laboratory actors.

Approval decisions are not recorded here. The workforce application service
calls these rules. CS-4 owns the decision command and must authorize through
that service before it writes. Team membership is not an input to either check.
"""

from __future__ import annotations

from wasatch_api.shared.errors import AuthorizationDenied
from wasatch_api.workforce.domain.entities import LaboratoryActor


def authorize_write(actor: LaboratoryActor, action: str) -> None:
    """Deny every write until a later command explicitly allows it."""

    raise AuthorizationDenied(f"{actor.employee_id} cannot perform {action}")


def authorize_approval_decision(actor: LaboratoryActor) -> None:
    """Permit a decision only when the actor's role is an approver.

    This check does not append decision history, set a reviewer, or change a
    message. There is no HTTP route for it in this slice.
    """

    if actor.status != "active":
        raise AuthorizationDenied(f"{actor.employee_id} is not an active employee")
    if not actor.is_approver:
        raise AuthorizationDenied(f"role {actor.role_id} cannot decide approvals")

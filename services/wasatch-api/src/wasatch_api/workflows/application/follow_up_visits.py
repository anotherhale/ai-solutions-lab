"""Open a follow-up visit, then confirm or cancel it.

An approver's customer-message decision does not open the visit and does not
dispatch a technician. A dispatcher opens it only after that approval. The
opened visit stays unscheduled until a dispatcher confirms or cancels it.
Neither transition sends the message, assigns a technician, or posts finance.
"""

from __future__ import annotations

from datetime import UTC, datetime

from wasatch_api.shared.errors import InvalidParameterError, NotFoundError
from wasatch_api.workflows.domain.entities import FollowUpVisit
from wasatch_api.workflows.domain.follow_up import (
    FOLLOW_UP_DECISIONS,
    OPEN,
    next_status,
    opened_status,
)
from wasatch_api.workflows.infrastructure.repository import FollowUpVisitRepository
from wasatch_api.workforce.application.access import LaboratoryAccessService
from wasatch_api.workforce.domain.entities import LaboratoryActor


class FollowUpVisits:
    """Dispatcher command for one follow-up visit."""

    def __init__(
        self, repository: FollowUpVisitRepository, access: LaboratoryAccessService
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
    ) -> FollowUpVisit:
        self._access.authorize_follow_up(actor)
        if decision not in FOLLOW_UP_DECISIONS:
            raise InvalidParameterError(f"unsupported follow-up decision: {decision}")
        if decision == OPEN:
            return self._open(actor, approval_id)
        return self._confirm_or_cancel(
            actor, approval_id, decision=decision, note=_clean_note(note)
        )

    def _open(self, actor: LaboratoryActor, approval_id: str) -> FollowUpVisit:
        approval = self._repository.get_approval(approval_id)
        if approval is None:
            raise NotFoundError(f"approval request {approval_id} was not found")
        opened_status(approval.action_type, approval.subject_type, approval.status)
        if self._repository.get_for_approval(approval_id) is not None:
            raise InvalidParameterError("follow-up visit is already open")
        return self._repository.open_follow_up(
            approval_id,
            actor_employee_id=actor.employee_id,
            opened_at=datetime.now(UTC),
        )

    def _confirm_or_cancel(
        self,
        actor: LaboratoryActor,
        approval_id: str,
        *,
        decision: str,
        note: str | None,
    ) -> FollowUpVisit:
        if self._repository.get_approval(approval_id) is None:
            raise NotFoundError(f"approval request {approval_id} was not found")
        visit = self._repository.get_for_approval(approval_id)
        if visit is None:
            raise InvalidParameterError("no follow-up visit is open")
        return self._repository.record_decision(
            approval_id,
            actor_employee_id=actor.employee_id,
            to_status=next_status(visit.status, decision),
            decided_at=datetime.now(UTC),
            note=note,
        )


class FollowUpVisitQueries:
    """Read a follow-up visit. Reading does not open or decide one."""

    def __init__(self, repository: FollowUpVisitRepository) -> None:
        self._repository = repository

    def get(self, follow_up_id: str) -> FollowUpVisit:
        visit = self._repository.get(follow_up_id)
        if visit is None:
            raise NotFoundError(f"follow-up visit {follow_up_id} was not found")
        return visit

    def get_for_approval(self, approval_id: str) -> FollowUpVisit:
        visit = self._repository.get_for_approval(approval_id)
        if visit is None:
            raise NotFoundError(f"follow-up visit for {approval_id} was not found")
        return visit


def _clean_note(note: str | None) -> str | None:
    if note is None:
        return None
    cleaned = note.strip()
    return cleaned or None

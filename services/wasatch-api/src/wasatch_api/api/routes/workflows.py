"""Follow-up visit routes.

The command opens a visit from an approved customer message, then confirms
or cancels it. The visit stays unscheduled until that second decision. It
does not send the message, assign a technician, or post finance. Audit
events stay insert-only.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from wasatch_api.api.dependencies import (
    db_session,
    follow_up_visit_queries,
    follow_up_visits,
    require_laboratory_actor,
)
from wasatch_api.api.schemas import FollowUpVisitDecisionIn, FollowUpVisitOut
from wasatch_api.workflows.application.follow_up_visits import (
    FollowUpVisitQueries,
    FollowUpVisits,
)
from wasatch_api.workforce.domain.entities import LaboratoryActor

router = APIRouter(
    prefix="/api/v1",
    tags=["workflows"],
    dependencies=[Depends(require_laboratory_actor)],
)

SessionDep = Annotated[Session, Depends(db_session)]
ActorDep = Annotated[LaboratoryActor, Depends(require_laboratory_actor)]


def commands(session: SessionDep) -> FollowUpVisits:
    return follow_up_visits(session)


def queries(session: SessionDep) -> FollowUpVisitQueries:
    return follow_up_visit_queries(session)


CommandsDep = Annotated[FollowUpVisits, Depends(commands)]
QueriesDep = Annotated[FollowUpVisitQueries, Depends(queries)]


@router.post(
    "/approval-requests/{approval_id}/follow-up-visits",
    response_model=FollowUpVisitOut,
)
def decide_follow_up_visit(
    approval_id: str,
    body: FollowUpVisitDecisionIn,
    actor: ActorDep,
    service: CommandsDep,
) -> FollowUpVisitOut:
    """Open, confirm, or cancel. The message stays unsent."""

    recorded = service.decide(
        actor, approval_id, decision=body.decision, note=body.note
    )
    return FollowUpVisitOut.from_domain(recorded)


@router.get(
    "/approval-requests/{approval_id}/follow-up-visits",
    response_model=FollowUpVisitOut,
)
def get_follow_up_for_approval(
    approval_id: str, service: QueriesDep
) -> FollowUpVisitOut:
    return FollowUpVisitOut.from_domain(service.get_for_approval(approval_id))


@router.get("/follow-up-visits/{follow_up_id}", response_model=FollowUpVisitOut)
def get_follow_up_visit(follow_up_id: str, service: QueriesDep) -> FollowUpVisitOut:
    return FollowUpVisitOut.from_domain(service.get(follow_up_id))

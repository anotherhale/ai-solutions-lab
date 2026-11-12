"""Merge Alembic heads for Phase D and AI review gate.

Revision ID: 0016
Revises: 0015, 0015_ai_review_gate
Create Date: 2026-11-12
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0016"
down_revision: str | Sequence[str] | None = ("0015", "0015_ai_review_gate")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Union of Phase D child events and Phase 1A.6.2 gate events on one head.
PRIOR_EVENT_TYPES = (
    "run.started",
    "run.completed",
    "run.failed",
    "task.selected",
    "task.delegated",
    "implementation.milestone",
    "test.started",
    "test.completed",
    "test.failed",
    "review.started",
    "review.completed",
    "pr.opened",
    "pr.updated",
    "pr.merged",
    "progress.report",
    "blocker.reported",
    "milestone.reached",
    "coordinator.recovery",
    "coordinator.scheduled",
    "coordinator.auto_merge",
)
CHILD_EVENT_TYPES = (
    "child.requested",
    "child.claimed",
    "child.worktree_prepared",
    "child.launch_requested",
    "child.launch_succeeded",
    "child.launch_failed",
    "child.progress",
    "child.heartbeat_timeout",
    "child.stalled",
    "child.recovery",
    "child.retry",
    "child.completed",
    "child.pr_open",
    "child.awaiting_merge",
    "child.merged",
    "child.operator_intervention",
    "child.execution_toggled",
)
GATE_EVENT_TYPES = (
    "review.verdict_recorded",
    "gate.published",
    "gate.rejected",
    "gate.publish_failed",
    "gate.stale",
)
EVENT_TYPES = PRIOR_EVENT_TYPES + CHILD_EVENT_TYPES + GATE_EVENT_TYPES


def _in_list(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def upgrade() -> None:
    op.drop_constraint(
        "ck_activity_events_event_type",
        "activity_events",
        schema="development_ops",
        type_="check",
    )
    op.create_check_constraint(
        "ck_activity_events_event_type",
        "activity_events",
        f"event_type IN ({_in_list(EVENT_TYPES)})",
        schema="development_ops",
    )


def downgrade() -> None:
    pass

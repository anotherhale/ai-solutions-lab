"""Extend coordinator task lifecycle statuses.

Revision ID: 0013
Revises: 0012
Create Date: 2026-11-13
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Lifecycle: pending -> assigned -> in_progress -> pr_open -> merge_ready -> merged,
# with blocked as a terminal side state. `merge_ready` records that an open pull
# request is ready to merge even when GitHub refuses to arm auto-merge.
TASK_STATUSES = (
    "pending",
    "assigned",
    "in_progress",
    "pr_open",
    "merge_ready",
    "merged",
    "blocked",
)

PRIOR_TASK_STATUSES = (
    "pending",
    "in_progress",
    "pr_open",
    "merged",
    "blocked",
)


def _status_check(values: tuple[str, ...]) -> str:
    joined = ", ".join(f"'{value}'" for value in values)
    return f"status IN ({joined})"


def upgrade() -> None:
    op.drop_constraint(
        "ck_coordinator_tasks_status",
        "coordinator_tasks",
        schema="development_ops",
        type_="check",
    )
    op.create_check_constraint(
        "ck_coordinator_tasks_status",
        "coordinator_tasks",
        _status_check(TASK_STATUSES),
        schema="development_ops",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_coordinator_tasks_status",
        "coordinator_tasks",
        schema="development_ops",
        type_="check",
    )
    op.create_check_constraint(
        "ck_coordinator_tasks_status",
        "coordinator_tasks",
        _status_check(PRIOR_TASK_STATUSES),
        schema="development_ops",
    )

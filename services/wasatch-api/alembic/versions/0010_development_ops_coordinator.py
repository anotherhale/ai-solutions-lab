"""Coordinator scheduling state and extended activity event types.

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-05
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB(astext_type=sa.Text())

EVENT_TYPES = (
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

TASK_STATUSES = (
    "pending",
    "in_progress",
    "pr_open",
    "merged",
    "blocked",
)


def upgrade() -> None:
    event_type_check = ", ".join(f"'{value}'" for value in EVENT_TYPES)
    op.drop_constraint(
        "ck_activity_events_event_type",
        "activity_events",
        schema="development_ops",
        type_="check",
    )
    op.create_check_constraint(
        "ck_activity_events_event_type",
        "activity_events",
        f"event_type IN ({event_type_check})",
        schema="development_ops",
    )

    status_check = ", ".join(f"'{value}'" for value in TASK_STATUSES)
    op.create_table(
        "coordinator_tasks",
        sa.Column("task_id", sa.String(64), primary_key=True),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column(
            "depends_on",
            JSONB,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("blocked_reason", sa.Text(), nullable=True),
        sa.Column("active_run_id", UUID, nullable=True),
        sa.Column("branch_name", sa.String(255), nullable=True),
        sa.Column("pr_number", sa.Integer(), nullable=True),
        sa.Column("owner_agent", sa.String(128), nullable=True),
        sa.Column("merge_commit_sha", sa.String(64), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            f"status IN ({status_check})",
            name="ck_coordinator_tasks_status",
        ),
        schema="development_ops",
    )
    op.create_index(
        "ix_coordinator_tasks_status",
        "coordinator_tasks",
        ["status"],
        schema="development_ops",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_coordinator_tasks_status",
        table_name="coordinator_tasks",
        schema="development_ops",
    )
    op.drop_table("coordinator_tasks", schema="development_ops")

    prior_event_types = EVENT_TYPES[:16]
    event_type_check = ", ".join(f"'{value}'" for value in prior_event_types)
    op.drop_constraint(
        "ck_activity_events_event_type",
        "activity_events",
        schema="development_ops",
        type_="check",
    )
    op.create_check_constraint(
        "ck_activity_events_event_type",
        "activity_events",
        f"event_type IN ({event_type_check})",
        schema="development_ops",
    )

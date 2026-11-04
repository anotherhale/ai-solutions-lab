"""Development activity log schema (development_ops.activity_events).

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-04
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009"
down_revision: str | None = "0008"
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
)

SEVERITIES = ("debug", "info", "notice", "warning", "error", "critical")

SLACK_STATUSES = ("pending", "delivered", "failed", "skipped", "duplicate")


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS development_ops")

    event_type_check = ", ".join(f"'{value}'" for value in EVENT_TYPES)
    severity_check = ", ".join(f"'{value}'" for value in SEVERITIES)
    slack_status_check = ", ".join(f"'{value}'" for value in SLACK_STATUSES)

    op.create_table(
        "activity_events",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("idempotency_key", sa.String(255), nullable=True, unique=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("run_id", UUID, nullable=False),
        sa.Column("task_id", sa.String(128), nullable=True),
        sa.Column("agent_name", sa.String(128), nullable=True),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column(
            "metadata", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column("github_repository", sa.String(255), nullable=True),
        sa.Column("github_pull_number", sa.Integer(), nullable=True),
        sa.Column("github_commit_sha", sa.String(64), nullable=True),
        sa.Column("github_actions_run_url", sa.String(2048), nullable=True),
        sa.Column("slack_channel_id", sa.String(32), nullable=True),
        sa.Column("slack_message_ts", sa.String(32), nullable=True),
        sa.Column("slack_delivery_status", sa.String(16), nullable=False),
        sa.Column("slack_delivery_error", sa.Text(), nullable=True),
        sa.Column(
            "slack_delivery_attempted_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.CheckConstraint(
            f"event_type IN ({event_type_check})",
            name="ck_activity_events_event_type",
        ),
        sa.CheckConstraint(
            f"severity IN ({severity_check})",
            name="ck_activity_events_severity",
        ),
        sa.CheckConstraint(
            f"slack_delivery_status IN ({slack_status_check})",
            name="ck_activity_events_slack_delivery_status",
        ),
        schema="development_ops",
    )

    op.create_index(
        "ix_activity_events_run_id_occurred_at",
        "activity_events",
        ["run_id", "occurred_at"],
        schema="development_ops",
    )
    op.create_index(
        "ix_activity_events_task_id",
        "activity_events",
        ["task_id"],
        schema="development_ops",
    )
    op.create_index(
        "ix_activity_events_event_type",
        "activity_events",
        ["event_type"],
        schema="development_ops",
    )
    op.create_index(
        "ix_activity_events_severity",
        "activity_events",
        ["severity"],
        schema="development_ops",
    )
    op.create_index(
        "ix_activity_events_occurred_at",
        "activity_events",
        ["occurred_at"],
        schema="development_ops",
    )
    op.create_index(
        "ix_activity_events_slack_delivery_status",
        "activity_events",
        ["slack_delivery_status"],
        schema="development_ops",
        postgresql_where=sa.text("slack_delivery_status = 'pending'"),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_activity_events_slack_delivery_status",
        table_name="activity_events",
        schema="development_ops",
    )
    op.drop_index(
        "ix_activity_events_occurred_at",
        table_name="activity_events",
        schema="development_ops",
    )
    op.drop_index(
        "ix_activity_events_severity",
        table_name="activity_events",
        schema="development_ops",
    )
    op.drop_index(
        "ix_activity_events_event_type",
        table_name="activity_events",
        schema="development_ops",
    )
    op.drop_index(
        "ix_activity_events_task_id",
        table_name="activity_events",
        schema="development_ops",
    )
    op.drop_index(
        "ix_activity_events_run_id_occurred_at",
        table_name="activity_events",
        schema="development_ops",
    )
    op.drop_table("activity_events", schema="development_ops")
    op.execute("DROP SCHEMA IF EXISTS development_ops")

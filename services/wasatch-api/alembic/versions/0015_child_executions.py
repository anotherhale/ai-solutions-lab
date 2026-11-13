"""Child-agent execution registry and durable orchestration settings.

Revision ID: 0015
Revises: 0014
Create Date: 2026-11-08

Phase D introduces bounded, observable, recoverable child-agent orchestration.
This migration adds:

* ``child_executions`` — the durable record of each child-agent execution
  attempt, with a partial unique index enforcing one *active* execution per
  task while preserving historical (failed/completed/merged) attempts.
* ``orchestration_settings`` — a small durable key/value table holding the
  operator's ``child_execution_enabled`` decision so it survives restarts and
  cannot be flipped by an environment variable.
* the extended ``activity_events.event_type`` check constraint for the child
  lifecycle events.

The new tables are additive and the constraint change is reversible.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB(astext_type=sa.Text())

# Prior constraint values (migration 0012) plus the Phase D child events.
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

EVENT_TYPES = PRIOR_EVENT_TYPES + CHILD_EVENT_TYPES

CHILD_STATES = (
    "queued",
    "claimed",
    "launch_pending",
    "running",
    "stalled",
    "failed",
    "completed",
    "pr_open",
    "awaiting_merge",
    "merged",
    "cancelled",
)

# States that hold a concurrency slot. The partial unique index below uses this
# same set, so one task cannot have two active executions at once.
ACTIVE_STATES = ("claimed", "launch_pending", "running", "stalled")


def _in_list(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def upgrade() -> None:
    # 1. Extend the activity event type constraint.
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

    # 2. Child execution registry.
    op.create_table(
        "child_executions",
        sa.Column("execution_id", UUID, primary_key=True),
        sa.Column("task_id", sa.String(64), nullable=False),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("idempotency_key", sa.String(255), nullable=False, unique=True),
        sa.Column("run_id", UUID, nullable=True),
        sa.Column("owner_agent", sa.String(128), nullable=True),
        sa.Column("conversation_id", sa.String(128), nullable=True),
        sa.Column("agent_server_url", sa.String(512), nullable=True),
        sa.Column("worktree_path", sa.String(1024), nullable=True),
        sa.Column("branch_name", sa.String(255), nullable=True),
        sa.Column("pr_number", sa.Integer(), nullable=True),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_progress_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "progress_seq", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column("last_event_count", sa.Integer(), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column(
            "operator_intervention",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "retry_count", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            f"state IN ({_in_list(CHILD_STATES)})",
            name="ck_child_executions_state",
        ),
        schema="development_ops",
    )
    op.create_index(
        "ix_child_executions_task_id",
        "child_executions",
        ["task_id"],
        schema="development_ops",
    )
    op.create_index(
        "ix_child_executions_state",
        "child_executions",
        ["state"],
        schema="development_ops",
    )
    op.create_index(
        "ix_child_executions_conversation_id",
        "child_executions",
        ["conversation_id"],
        schema="development_ops",
    )
    op.create_index(
        "ix_child_executions_lease_expires_at",
        "child_executions",
        ["lease_expires_at"],
        schema="development_ops",
    )
    # One active execution per task. The partial predicate means terminal rows
    # (failed/completed/pr_open/merged/cancelled) do not collide, so history is
    # preserved while a task can never have two live children.
    op.create_index(
        "ux_child_executions_active_task",
        "child_executions",
        ["task_id"],
        unique=True,
        schema="development_ops",
        postgresql_where=sa.text(f"state IN ({_in_list(ACTIVE_STATES)})"),
    )

    # 3. Durable orchestration settings.
    op.create_table(
        "orchestration_settings",
        sa.Column("key", sa.String(128), primary_key=True),
        sa.Column(
            "value",
            JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        schema="development_ops",
    )
    # Disabled by default: seed the flag explicitly rather than relying on an
    # absent row. An absent row is treated as disabled by the repository, but an
    # explicit row makes the operator decision visible and auditable.
    op.execute(
        "INSERT INTO development_ops.orchestration_settings (key, value) "
        "VALUES ('child_execution_enabled', '{\"enabled\": false}'::jsonb) "
        "ON CONFLICT (key) DO NOTHING"
    )


def downgrade() -> None:
    op.drop_table("orchestration_settings", schema="development_ops")
    op.drop_index(
        "ux_child_executions_active_task",
        table_name="child_executions",
        schema="development_ops",
    )
    op.drop_index(
        "ix_child_executions_lease_expires_at",
        table_name="child_executions",
        schema="development_ops",
    )
    op.drop_index(
        "ix_child_executions_conversation_id",
        table_name="child_executions",
        schema="development_ops",
    )
    op.drop_index(
        "ix_child_executions_state",
        table_name="child_executions",
        schema="development_ops",
    )
    op.drop_index(
        "ix_child_executions_task_id",
        table_name="child_executions",
        schema="development_ops",
    )
    op.drop_table("child_executions", schema="development_ops")

    # Restore the prior event-type constraint. Any event type the restored
    # constraint cannot hold must be removed first or the ALTER fails on
    # existing rows. This is not limited to ``CHILD_EVENT_TYPES``: the AI
    # review gate branch (``gate.*``) also merges at 0016 and sits *below*
    # this revision on the merged graph. Alembic runs this branch's downgrade
    # before ``0015_ai_review_gate``'s, so gate rows are still present here and
    # would violate the narrowed constraint. Purging every type outside the
    # restored set keeps the two 0015 downgrades order-independent.
    op.execute(
        "DELETE FROM development_ops.activity_events "
        f"WHERE event_type NOT IN ({_in_list(PRIOR_EVENT_TYPES)})"
    )
    op.drop_constraint(
        "ck_activity_events_event_type",
        "activity_events",
        schema="development_ops",
        type_="check",
    )
    op.create_check_constraint(
        "ck_activity_events_event_type",
        "activity_events",
        f"event_type IN ({_in_list(PRIOR_EVENT_TYPES)})",
        schema="development_ops",
    )

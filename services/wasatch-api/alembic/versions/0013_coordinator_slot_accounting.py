"""Coordinator slot accounting, leases, and awaiting-merge state.

Revision ID: 0013
Revises: 0012
Create Date: 2026-11-06
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Only ``in_progress`` consumes an implementation slot. ``pr_open`` and
# ``awaiting_merge`` describe work already handed to GitHub.
TASK_STATUSES = (
    "pending",
    "in_progress",
    "pr_open",
    "awaiting_merge",
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

    op.add_column(
        "coordinator_tasks",
        sa.Column("base_branch", sa.String(255), nullable=True),
        schema="development_ops",
    )
    op.add_column(
        "coordinator_tasks",
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        schema="development_ops",
    )
    op.add_column(
        "coordinator_tasks",
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        schema="development_ops",
    )
    op.add_column(
        "coordinator_tasks",
        sa.Column(
            "attempt_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        schema="development_ops",
    )
    op.add_column(
        "coordinator_tasks",
        sa.Column("last_error", sa.Text(), nullable=True),
        schema="development_ops",
    )

    # Reclaim scans filter on a live lease, so index the expiry column.
    op.create_index(
        "ix_coordinator_tasks_lease_expires_at",
        "coordinator_tasks",
        ["lease_expires_at"],
        schema="development_ops",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_coordinator_tasks_lease_expires_at",
        table_name="coordinator_tasks",
        schema="development_ops",
    )
    op.drop_column("coordinator_tasks", "last_error", schema="development_ops")
    op.drop_column("coordinator_tasks", "attempt_count", schema="development_ops")
    op.drop_column("coordinator_tasks", "heartbeat_at", schema="development_ops")
    op.drop_column("coordinator_tasks", "lease_expires_at", schema="development_ops")
    op.drop_column("coordinator_tasks", "base_branch", schema="development_ops")

    # ``awaiting_merge`` rows cannot survive the older constraint; fold them
    # back to ``pr_open`` before tightening the check.
    op.execute(
        "UPDATE development_ops.coordinator_tasks "
        "SET status = 'pr_open' WHERE status = 'awaiting_merge'"
    )
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

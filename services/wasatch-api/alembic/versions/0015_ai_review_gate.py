"""AI review gate verdict mirror.

Adds ``development_ops.review_verdicts``: an audit/cache mirror of reviewer
verdicts. The table is never the canonical verdict source (the gate always
re-verifies the GitHub PR review); its uniqueness constraint makes mirroring
idempotent.

Migration-graph note: Phase D (branch ``cursor/phase-d-child-agent-orchestration``)
proposes a separate ``0015_child_executions`` revision. If both land, Alembic will
see two heads at ``down_revision = "0014"`` and a merge migration will be needed.
This branch does not modify Phase D.

Revision ID: 0015_ai_review_gate
Revises: 0014
Create Date: 2026-11-09
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0015_ai_review_gate"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)

# The full accepted event-type set after this migration: the pre-existing values
# (see 0012) plus the AI review gate events added here.
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
    "review.verdict_recorded",
    "gate.published",
    "gate.rejected",
    "gate.publish_failed",
    "gate.stale",
)

# The prior set, used by ``downgrade`` to restore the 0012 constraint.
PRIOR_EVENT_TYPES = EVENT_TYPES[:20]


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

    op.create_table(
        "review_verdicts",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("repository", sa.String(255), nullable=False),
        sa.Column("pull_number", sa.Integer(), nullable=False),
        sa.Column("head_sha", sa.String(64), nullable=False),
        sa.Column("review_id", sa.BigInteger(), nullable=False),
        sa.Column("reviewer_login", sa.String(255), nullable=False),
        sa.Column("reviewer_user_id", sa.BigInteger(), nullable=False),
        sa.Column("verdict", sa.String(32), nullable=False),
        sa.Column("blocking_count", sa.Integer(), nullable=False),
        sa.Column("policy_version", sa.String(32), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "repository",
            "pull_number",
            "head_sha",
            "review_id",
            name="uq_review_verdicts_identity",
        ),
        schema="development_ops",
    )
    op.create_index(
        "ix_review_verdicts_repository",
        "review_verdicts",
        ["repository"],
        schema="development_ops",
    )
    op.create_index(
        "ix_review_verdicts_pull_number",
        "review_verdicts",
        ["pull_number"],
        schema="development_ops",
    )
    op.create_index(
        "ix_review_verdicts_head_sha",
        "review_verdicts",
        ["head_sha"],
        schema="development_ops",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_review_verdicts_head_sha",
        table_name="review_verdicts",
        schema="development_ops",
    )
    op.drop_index(
        "ix_review_verdicts_pull_number",
        table_name="review_verdicts",
        schema="development_ops",
    )
    op.drop_index(
        "ix_review_verdicts_repository",
        table_name="review_verdicts",
        schema="development_ops",
    )
    op.drop_table("review_verdicts", schema="development_ops")

    prior_check = ", ".join(f"'{value}'" for value in PRIOR_EVENT_TYPES)
    # Remove any event type the restored constraint cannot hold before narrowing
    # it. The child branch (``0015``) merges at 0016 as well; when this branch is
    # downgraded first, ``child.*`` rows would otherwise violate the restored
    # constraint. Purging every type outside the restored set makes this
    # downgrade order-independent from ``0015_child_executions``.
    op.execute(
        "DELETE FROM development_ops.activity_events "
        f"WHERE event_type NOT IN ({prior_check})"
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
        f"event_type IN ({prior_check})",
        schema="development_ops",
    )

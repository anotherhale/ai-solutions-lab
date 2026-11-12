"""Agent worktree registry for isolated child agents.

Revision ID: 0014
Revises: 0013
Create Date: 2026-11-06
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)

WORKTREE_STATES = (
    "preparing",
    "launched",
    "pr_open",
    "merged",
    "failed",
)


def upgrade() -> None:
    state_check = ", ".join(f"'{value}'" for value in WORKTREE_STATES)
    op.create_table(
        "agent_worktrees",
        sa.Column("task_id", sa.String(64), primary_key=True),
        sa.Column("branch_name", sa.String(255), nullable=False, unique=True),
        sa.Column("worktree_path", sa.String(1024), nullable=False, unique=True),
        sa.Column("base_ref", sa.String(255), nullable=False),
        sa.Column("base_sha", sa.String(64), nullable=True),
        sa.Column("conversation_id", sa.String(128), nullable=True),
        sa.Column("run_id", UUID, nullable=True),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("pr_number", sa.Integer(), nullable=True),
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
            f"state IN ({state_check})",
            name="ck_agent_worktrees_state",
        ),
        schema="development_ops",
    )
    op.create_index(
        "ix_agent_worktrees_state",
        "agent_worktrees",
        ["state"],
        schema="development_ops",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_agent_worktrees_state",
        table_name="agent_worktrees",
        schema="development_ops",
    )
    op.drop_table("agent_worktrees", schema="development_ops")

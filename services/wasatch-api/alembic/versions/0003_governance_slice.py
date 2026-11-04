"""Approval requests and insert-only audit events.

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-04

Replaces messages.approval_request_id string storage with a foreign key to
approval_requests.id. Existing values are matched to approval_requests.business_id.
A business id with no approval row becomes NULL; seed restores it.

audit_events is insert-only. This revision does not UPDATE or DELETE those rows.
Downgrade drops the audit table, which is safe on the synthetic database, and
reloads come from data/fixtures/valid/.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)

BACKFILL_MESSAGE_APPROVALS = """
UPDATE messages AS msg
SET approval_request_row_id = apr.id
FROM approval_requests AS apr
WHERE msg.approval_request_id = apr.business_id
"""

RESTORE_MESSAGE_APPROVAL_BUSINESS_IDS = """
UPDATE messages AS msg
SET approval_request_business_id = apr.business_id
FROM approval_requests AS apr
WHERE msg.approval_request_id = apr.id
"""

CREATE_AUDIT_INSERT_ONLY = """
CREATE OR REPLACE FUNCTION reject_audit_event_change()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'audit_events are insert-only';
END;
$$
"""

CREATE_AUDIT_TRIGGER = """
CREATE TRIGGER audit_events_insert_only
BEFORE UPDATE OR DELETE ON audit_events
FOR EACH ROW
EXECUTE FUNCTION reject_audit_event_change()
"""

DROP_AUDIT_INSERT_ONLY = """
DROP FUNCTION IF EXISTS reject_audit_event_change()
"""


def upgrade() -> None:
    create_governance_tables()
    replace_message_approval_column()


def create_governance_tables() -> None:
    op.create_table(
        "approval_requests",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("business_id", sa.String(16), nullable=False, unique=True),
        sa.Column("action_type", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column(
            "requested_by_employee_id",
            UUID,
            sa.ForeignKey("employees.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "reviewer_employee_id",
            UUID,
            sa.ForeignKey("employees.id", ondelete="SET NULL"),
        ),
        sa.Column("subject_type", sa.String(32), nullable=False),
        sa.Column("subject_id", sa.String(16), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("decision_notes", sa.Text()),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True)),
        sa.Column("executed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_approval_requests_action_type", "approval_requests", ["action_type"]
    )
    op.create_index("ix_approval_requests_status", "approval_requests", ["status"])
    op.create_index(
        "ix_approval_requests_requested_by_employee_id",
        "approval_requests",
        ["requested_by_employee_id"],
    )
    op.create_index(
        "ix_approval_requests_reviewer_employee_id",
        "approval_requests",
        ["reviewer_employee_id"],
    )

    op.create_table(
        "approval_decision_history",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "approval_request_id",
            UUID,
            sa.ForeignKey("approval_requests.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "actor_employee_id",
            UUID,
            sa.ForeignKey("employees.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("from_status", sa.String(32), nullable=False),
        sa.Column("to_status", sa.String(32), nullable=False),
        sa.Column("note", sa.Text()),
        sa.UniqueConstraint(
            "approval_request_id",
            "position",
            name="uq_approval_decision_position",
        ),
    )
    op.create_index(
        "ix_approval_decision_history_approval_request_id",
        "approval_decision_history",
        ["approval_request_id"],
    )

    op.create_table(
        "audit_events",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("business_id", sa.String(16), nullable=False, unique=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor_type", sa.String(32), nullable=False),
        sa.Column(
            "actor_employee_id",
            UUID,
            sa.ForeignKey("employees.id", ondelete="RESTRICT"),
        ),
        sa.Column("action", sa.String(128), nullable=False),
        sa.Column("subject_type", sa.String(32), nullable=False),
        sa.Column("subject_id", sa.String(16), nullable=False),
        sa.Column("outcome", sa.String(32), nullable=False),
        sa.Column("approval_request_id", UUID),
        sa.Column("details", postgresql.JSONB()),
    )
    op.create_foreign_key(
        "fk_audit_events_approval_request",
        "audit_events",
        "approval_requests",
        ["approval_request_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_audit_events_actor_employee_id",
        "audit_events",
        ["actor_employee_id"],
    )
    op.create_index(
        "ix_audit_events_approval_request_id",
        "audit_events",
        ["approval_request_id"],
    )
    op.create_index("ix_audit_events_outcome", "audit_events", ["outcome"])
    op.execute(CREATE_AUDIT_INSERT_ONLY)
    op.execute(CREATE_AUDIT_TRIGGER)


def replace_message_approval_column() -> None:
    op.add_column("messages", sa.Column("approval_request_row_id", UUID))
    op.execute(BACKFILL_MESSAGE_APPROVALS)
    op.drop_column("messages", "approval_request_id")
    op.alter_column(
        "messages",
        "approval_request_row_id",
        new_column_name="approval_request_id",
        existing_type=UUID,
        existing_nullable=True,
    )
    op.create_foreign_key(
        "fk_messages_approval_request",
        "messages",
        "approval_requests",
        ["approval_request_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_messages_approval_request_id",
        "messages",
        ["approval_request_id"],
    )


def downgrade() -> None:
    restore_message_approval_column()
    drop_governance_tables()


def restore_message_approval_column() -> None:
    op.add_column(
        "messages",
        sa.Column("approval_request_business_id", sa.String(16)),
    )
    op.execute(RESTORE_MESSAGE_APPROVAL_BUSINESS_IDS)
    op.drop_index("ix_messages_approval_request_id", table_name="messages")
    op.drop_constraint("fk_messages_approval_request", "messages", type_="foreignkey")
    op.drop_column("messages", "approval_request_id")
    op.alter_column(
        "messages",
        "approval_request_business_id",
        new_column_name="approval_request_id",
        existing_type=sa.String(16),
        existing_nullable=True,
    )


def drop_governance_tables() -> None:
    op.drop_table("audit_events")
    op.execute(DROP_AUDIT_INSERT_ONLY)
    op.drop_table("approval_decision_history")
    op.drop_table("approval_requests")

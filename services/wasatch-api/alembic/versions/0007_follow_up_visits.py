"""Follow-up visits opened from an approved customer message.

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-04

The visit stays unscheduled until a dispatcher confirms or cancels it.
This revision does not add a vector column, an appointment, or a work order.
It does not change the insert-only audit trigger.

Downgrade drops ``follow_up_visits``. That is safe on the synthetic database.
Audit rows are not updated or deleted.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.create_table(
        "follow_up_visits",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("business_id", sa.String(16), nullable=False, unique=True),
        sa.Column(
            "approval_request_id",
            UUID,
            sa.ForeignKey(
                "approval_requests.id",
                name="fk_follow_up_visits_approval_request",
                ondelete="RESTRICT",
            ),
            nullable=False,
        ),
        sa.Column(
            "message_id",
            UUID,
            sa.ForeignKey(
                "messages.id",
                name="fk_follow_up_visits_message",
                ondelete="RESTRICT",
            ),
            nullable=False,
        ),
        sa.Column(
            "support_ticket_id",
            UUID,
            sa.ForeignKey(
                "support_tickets.id",
                name="fk_follow_up_visits_support_ticket",
                ondelete="RESTRICT",
            ),
            nullable=False,
        ),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column(
            "opened_by_employee_id",
            UUID,
            sa.ForeignKey(
                "employees.id",
                name="fk_follow_up_visits_opened_by",
                ondelete="RESTRICT",
            ),
            nullable=False,
        ),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "decided_by_employee_id",
            UUID,
            sa.ForeignKey(
                "employees.id",
                name="fk_follow_up_visits_decided_by",
                ondelete="RESTRICT",
            ),
        ),
        sa.Column("decided_at", sa.DateTime(timezone=True)),
        sa.Column("decision_note", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "business_id ~ '^fuv_[0-9]{4}$'",
            name="ck_follow_up_visits_business_id",
        ),
        sa.CheckConstraint(
            "status IN ('unscheduled', 'confirmed', 'cancelled')",
            name="ck_follow_up_visits_status",
        ),
        sa.CheckConstraint(
            "("
            "status = 'unscheduled' "
            "AND decided_by_employee_id IS NULL "
            "AND decided_at IS NULL"
            ") OR ("
            "status IN ('confirmed', 'cancelled') "
            "AND decided_by_employee_id IS NOT NULL "
            "AND decided_at IS NOT NULL"
            ")",
            name="ck_follow_up_visits_decision",
        ),
        sa.UniqueConstraint(
            "approval_request_id",
            name="uq_follow_up_visits_approval_request_id",
        ),
    )
    op.create_index(
        "ix_follow_up_visits_status",
        "follow_up_visits",
        ["status"],
    )
    op.create_index(
        "ix_follow_up_visits_message_id",
        "follow_up_visits",
        ["message_id"],
    )
    op.create_index(
        "ix_follow_up_visits_support_ticket_id",
        "follow_up_visits",
        ["support_ticket_id"],
    )
    op.execute(
        """
        COMMENT ON TABLE follow_up_visits IS
        'Synthetic follow-up visit opened from an approved customer message. '
        'Unscheduled until a dispatcher confirms or cancels it. Confirm and '
        'cancel do not assign a technician, book an appointment, send a '
        'message, or post finance.'
        """
    )


def downgrade() -> None:
    op.drop_table("follow_up_visits")

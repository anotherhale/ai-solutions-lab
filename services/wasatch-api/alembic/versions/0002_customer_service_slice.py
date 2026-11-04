"""Customer-service tickets, messages, and interactions.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-04

Replaces work_orders.support_ticket_id string storage with a foreign key to
support_tickets.id. Existing values are matched to support_tickets.business_id.
A business id with no ticket row becomes NULL; seed restores it.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)

BACKFILL_WORK_ORDER_TICKETS = """
UPDATE work_orders AS wo
SET support_ticket_row_id = st.id
FROM support_tickets AS st
WHERE wo.support_ticket_id = st.business_id
"""

RESTORE_WORK_ORDER_TICKET_BUSINESS_IDS = """
UPDATE work_orders AS wo
SET support_ticket_business_id = st.business_id
FROM support_tickets AS st
WHERE wo.support_ticket_id = st.id
"""


def upgrade() -> None:
    create_customer_service_tables()
    replace_work_order_support_ticket_column()


def create_customer_service_tables() -> None:
    op.create_table(
        "support_tickets",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("business_id", sa.String(16), nullable=False, unique=True),
        sa.Column(
            "customer_id",
            UUID,
            sa.ForeignKey("customers.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "contact_id",
            UUID,
            sa.ForeignKey("contacts.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "service_location_id",
            UUID,
            sa.ForeignKey("service_locations.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "work_order_id",
            UUID,
            sa.ForeignKey("work_orders.id", ondelete="SET NULL"),
        ),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("priority", sa.String(32), nullable=False),
        sa.Column("channel", sa.String(32), nullable=False),
        sa.Column("subject", sa.String(255), nullable=False),
        sa.Column(
            "assigned_employee_id",
            UUID,
            sa.ForeignKey("employees.id", ondelete="SET NULL"),
        ),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
        sa.Column(
            "related_document_ids",
            postgresql.ARRAY(sa.String()),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_support_tickets_customer_id", "support_tickets", ["customer_id"]
    )
    op.create_index(
        "ix_support_tickets_service_location_id",
        "support_tickets",
        ["service_location_id"],
    )
    op.create_index(
        "ix_support_tickets_work_order_id", "support_tickets", ["work_order_id"]
    )
    op.create_index("ix_support_tickets_status", "support_tickets", ["status"])
    op.create_index(
        "ix_support_tickets_assigned_employee_id",
        "support_tickets",
        ["assigned_employee_id"],
    )

    op.create_table(
        "messages",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("business_id", sa.String(16), nullable=False, unique=True),
        sa.Column(
            "support_ticket_id",
            UUID,
            sa.ForeignKey("support_tickets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("direction", sa.String(32), nullable=False),
        sa.Column("channel", sa.String(32), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column(
            "author_employee_id",
            UUID,
            sa.ForeignKey("employees.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "author_contact_id",
            UUID,
            sa.ForeignKey("contacts.id", ondelete="SET NULL"),
        ),
        sa.Column("requires_approval", sa.Boolean(), nullable=False),
        sa.Column("approval_request_id", sa.String(16)),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_messages_support_ticket_id", "messages", ["support_ticket_id"])
    op.create_index("ix_messages_status", "messages", ["status"])

    op.create_table(
        "interactions",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("business_id", sa.String(16), nullable=False, unique=True),
        sa.Column(
            "customer_id",
            UUID,
            sa.ForeignKey("customers.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "contact_id",
            UUID,
            sa.ForeignKey("contacts.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "support_ticket_id",
            UUID,
            sa.ForeignKey("support_tickets.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "work_order_id",
            UUID,
            sa.ForeignKey("work_orders.id", ondelete="SET NULL"),
        ),
        sa.Column("channel", sa.String(32), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column(
            "employee_id",
            UUID,
            sa.ForeignKey("employees.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("outcome", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_interactions_customer_id", "interactions", ["customer_id"])
    op.create_index(
        "ix_interactions_support_ticket_id", "interactions", ["support_ticket_id"]
    )
    op.create_index("ix_interactions_work_order_id", "interactions", ["work_order_id"])
    op.create_index("ix_interactions_employee_id", "interactions", ["employee_id"])


def replace_work_order_support_ticket_column() -> None:
    op.add_column("work_orders", sa.Column("support_ticket_row_id", UUID))
    op.execute(BACKFILL_WORK_ORDER_TICKETS)
    op.drop_column("work_orders", "support_ticket_id")
    op.alter_column(
        "work_orders",
        "support_ticket_row_id",
        new_column_name="support_ticket_id",
        existing_type=UUID,
        existing_nullable=True,
    )
    op.create_foreign_key(
        "fk_work_orders_support_ticket",
        "work_orders",
        "support_tickets",
        ["support_ticket_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_work_orders_support_ticket_id",
        "work_orders",
        ["support_ticket_id"],
    )


def downgrade() -> None:
    op.add_column(
        "work_orders",
        sa.Column("support_ticket_business_id", sa.String(16)),
    )
    op.execute(RESTORE_WORK_ORDER_TICKET_BUSINESS_IDS)
    op.drop_index("ix_work_orders_support_ticket_id", table_name="work_orders")
    op.drop_constraint(
        "fk_work_orders_support_ticket", "work_orders", type_="foreignkey"
    )
    op.drop_column("work_orders", "support_ticket_id")
    op.alter_column(
        "work_orders",
        "support_ticket_business_id",
        new_column_name="support_ticket_id",
        existing_type=sa.String(16),
        existing_nullable=True,
    )
    op.drop_table("messages")
    op.drop_table("interactions")
    op.drop_table("support_tickets")

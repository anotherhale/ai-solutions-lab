"""Initial Wasatch customer and work-order slice.

Revision ID: 0001
Revises:
Create Date: 2026-11-03
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "customers",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("business_id", sa.String(16), nullable=False, unique=True),
        sa.Column("legal_name", sa.String(255), nullable=False),
        sa.Column("trade_name", sa.String(255)),
        sa.Column("account_number", sa.String(16), nullable=False, unique=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("customer_type", sa.String(32), nullable=False),
        sa.Column("billing_line1", sa.String(255), nullable=False),
        sa.Column("billing_line2", sa.String(255)),
        sa.Column("billing_city", sa.String(128), nullable=False),
        sa.Column("billing_state", sa.String(8), nullable=False),
        sa.Column("billing_postal_code", sa.String(16), nullable=False),
        sa.Column("billing_country", sa.String(8), nullable=False),
        sa.Column("billing_email", sa.String(255)),
        sa.Column("billing_phone", sa.String(32)),
        sa.Column("payment_terms", sa.String(32), nullable=False),
        sa.Column("service_agreement", sa.String(32), nullable=False),
        sa.Column("agreement_expires_on", sa.Date()),
        sa.Column("primary_contact_id", UUID),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_customers_status", "customers", ["status"])
    op.create_index("ix_customers_legal_name", "customers", ["legal_name"])

    op.create_table(
        "contacts",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("business_id", sa.String(16), nullable=False, unique=True),
        sa.Column(
            "customer_id",
            UUID,
            sa.ForeignKey("customers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("first_name", sa.String(128), nullable=False),
        sa.Column("last_name", sa.String(128), nullable=False),
        sa.Column("title", sa.String(128)),
        sa.Column("email", sa.String(255)),
        sa.Column("phone", sa.String(32)),
        sa.Column("contact_role", sa.String(32), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_contacts_customer_id", "contacts", ["customer_id"])
    op.create_foreign_key(
        "fk_customers_primary_contact",
        "customers",
        "contacts",
        ["primary_contact_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "service_locations",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("business_id", sa.String(16), nullable=False, unique=True),
        sa.Column(
            "customer_id",
            UUID,
            sa.ForeignKey("customers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("line1", sa.String(255), nullable=False),
        sa.Column("line2", sa.String(255)),
        sa.Column("city", sa.String(128), nullable=False),
        sa.Column("state", sa.String(8), nullable=False),
        sa.Column("postal_code", sa.String(16), nullable=False),
        sa.Column("country", sa.String(8), nullable=False),
        sa.Column("site_type", sa.String(32), nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False),
        sa.Column("access_notes", sa.Text()),
        sa.Column("square_footage", sa.Integer()),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_service_locations_customer_id", "service_locations", ["customer_id"]
    )
    op.create_index("ix_service_locations_status", "service_locations", ["status"])

    op.create_table(
        "employees",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("business_id", sa.String(16), nullable=False, unique=True),
        sa.Column("employee_number", sa.String(16), nullable=False, unique=True),
        sa.Column("first_name", sa.String(128), nullable=False),
        sa.Column("last_name", sa.String(128), nullable=False),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("phone", sa.String(32)),
        sa.Column("role_id", sa.String(16)),
        sa.Column("team_id", sa.String(16)),
        sa.Column("department", sa.String(32), nullable=False),
        sa.Column("job_title", sa.String(128), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("hire_date", sa.Date(), nullable=False),
        sa.Column("certifications", postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_employees_department", "employees", ["department"])
    op.create_index("ix_employees_status", "employees", ["status"])

    op.create_table(
        "equipment",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("business_id", sa.String(16), nullable=False, unique=True),
        sa.Column(
            "customer_id",
            UUID,
            sa.ForeignKey("customers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "service_location_id",
            UUID,
            sa.ForeignKey("service_locations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("asset_tag", sa.String(16), nullable=False, unique=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("equipment_type", sa.String(32), nullable=False),
        sa.Column("manufacturer", sa.String(128)),
        sa.Column("model", sa.String(128)),
        sa.Column("serial_number", sa.String(128)),
        sa.Column("installed_on", sa.Date()),
        sa.Column("warranty_expires_on", sa.Date()),
        sa.Column("last_service_on", sa.Date()),
        sa.Column("next_maintenance_on", sa.Date()),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_equipment_customer_id", "equipment", ["customer_id"])
    op.create_index(
        "ix_equipment_service_location_id", "equipment", ["service_location_id"]
    )
    op.create_index("ix_equipment_status", "equipment", ["status"])

    op.create_table(
        "work_orders",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("business_id", sa.String(16), nullable=False, unique=True),
        sa.Column(
            "customer_id",
            UUID,
            sa.ForeignKey("customers.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "service_location_id",
            UUID,
            sa.ForeignKey("service_locations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("support_ticket_id", sa.String(16)),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("priority", sa.String(32), nullable=False),
        sa.Column("work_type", sa.String(32), nullable=False),
        sa.Column("summary", sa.String(255), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column(
            "requested_by_contact_id",
            UUID,
            sa.ForeignKey("contacts.id", ondelete="SET NULL"),
        ),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("scheduled_for", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("completion_notes", sa.Text()),
        sa.Column("invoice_id", sa.String(16)),
        sa.Column("cancelled_reason", sa.Text()),
        sa.Column("reopen_reason", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_work_orders_customer_id", "work_orders", ["customer_id"])
    op.create_index(
        "ix_work_orders_service_location_id", "work_orders", ["service_location_id"]
    )
    op.create_index("ix_work_orders_status", "work_orders", ["status"])
    op.create_index(
        "ix_work_orders_customer_status", "work_orders", ["customer_id", "status"]
    )

    op.create_table(
        "work_order_assignments",
        sa.Column(
            "work_order_id",
            UUID,
            sa.ForeignKey("work_orders.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "employee_id",
            UUID,
            sa.ForeignKey("employees.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )
    op.create_table(
        "work_order_equipment",
        sa.Column(
            "work_order_id",
            UUID,
            sa.ForeignKey("work_orders.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "equipment_id",
            UUID,
            sa.ForeignKey("equipment.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )

    op.create_table(
        "work_order_tasks",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("business_id", sa.String(16), nullable=False, unique=True),
        sa.Column(
            "work_order_id",
            UUID,
            sa.ForeignKey("work_orders.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column(
            "assigned_employee_id",
            UUID,
            sa.ForeignKey("employees.id", ondelete="SET NULL"),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("blocked_reason", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("work_order_id", "sequence", name="uq_work_order_task_seq"),
    )
    op.create_index(
        "ix_work_order_tasks_work_order_id", "work_order_tasks", ["work_order_id"]
    )

    op.create_table(
        "appointments",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("business_id", sa.String(16), nullable=False, unique=True),
        sa.Column(
            "work_order_id",
            UUID,
            sa.ForeignKey("work_orders.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "service_location_id",
            UUID,
            sa.ForeignKey("service_locations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "assigned_employee_id",
            UUID,
            sa.ForeignKey("employees.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.Column("cancellation_reason", sa.Text()),
        sa.Column(
            "replaces_appointment_id",
            UUID,
            sa.ForeignKey("appointments.id", ondelete="SET NULL"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_appointments_work_order_id", "appointments", ["work_order_id"])
    op.create_index(
        "ix_appointments_service_location_id", "appointments", ["service_location_id"]
    )
    op.create_index(
        "ix_appointments_assigned_employee_id", "appointments", ["assigned_employee_id"]
    )
    op.create_index("ix_appointments_status", "appointments", ["status"])


def downgrade() -> None:
    op.drop_table("appointments")
    op.drop_table("work_order_tasks")
    op.drop_table("work_order_equipment")
    op.drop_table("work_order_assignments")
    op.drop_table("work_orders")
    op.drop_table("equipment")
    op.drop_table("employees")
    op.drop_table("service_locations")
    op.drop_constraint("fk_customers_primary_contact", "customers", type_="foreignkey")
    op.drop_table("contacts")
    op.drop_table("customers")
    op.execute("DROP EXTENSION IF EXISTS vector")

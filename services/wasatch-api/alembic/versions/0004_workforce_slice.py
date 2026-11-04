"""Roles, teams, and employee foreign keys.

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-04

Replaces employees.role_id and employees.team_id string storage with foreign
keys. Existing values are matched to roles.business_id and teams.business_id.
A business id with no row becomes NULL; seed restores it.

Downgrade copies those business ids back onto the string columns, then drops
teams and roles. That is safe on the synthetic database. Reload
data/fixtures/valid/ after downgrade.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)

BACKFILL_EMPLOYEE_ROLES = """
UPDATE employees AS emp
SET role_row_id = roles.id
FROM roles
WHERE emp.role_id = roles.business_id
"""

RESTORE_EMPLOYEE_ROLES = """
UPDATE employees AS emp
SET role_business_id = roles.business_id
FROM roles
WHERE emp.role_id = roles.id
"""

BACKFILL_EMPLOYEE_TEAMS = """
UPDATE employees AS emp
SET team_row_id = teams.id
FROM teams
WHERE emp.team_id = teams.business_id
"""

RESTORE_EMPLOYEE_TEAMS = """
UPDATE employees AS emp
SET team_business_id = teams.business_id
FROM teams
WHERE emp.team_id = teams.id
"""


def upgrade() -> None:
    create_role_and_team_tables()
    replace_employee_role_column()
    replace_employee_team_column()


def create_role_and_team_tables() -> None:
    op.create_table(
        "roles",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("business_id", sa.String(16), nullable=False, unique=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("department", sa.String(32), nullable=False),
        sa.Column("is_approver", sa.Boolean(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_roles_department", "roles", ["department"])

    op.create_table(
        "teams",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("business_id", sa.String(16), nullable=False, unique=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("department", sa.String(32), nullable=False),
        sa.Column("service_area", sa.String(255)),
        sa.Column(
            "lead_employee_id",
            UUID,
            sa.ForeignKey(
                "employees.id",
                name="fk_teams_lead_employee",
                ondelete="SET NULL",
            ),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_teams_department", "teams", ["department"])
    op.create_index("ix_teams_lead_employee_id", "teams", ["lead_employee_id"])


def replace_employee_role_column() -> None:
    op.add_column("employees", sa.Column("role_row_id", UUID))
    op.execute(BACKFILL_EMPLOYEE_ROLES)
    op.drop_column("employees", "role_id")
    op.alter_column(
        "employees",
        "role_row_id",
        new_column_name="role_id",
        existing_type=UUID,
        existing_nullable=True,
    )
    op.create_foreign_key(
        "fk_employees_role",
        "employees",
        "roles",
        ["role_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_employees_role_id", "employees", ["role_id"])


def replace_employee_team_column() -> None:
    op.add_column("employees", sa.Column("team_row_id", UUID))
    op.execute(BACKFILL_EMPLOYEE_TEAMS)
    op.drop_column("employees", "team_id")
    op.alter_column(
        "employees",
        "team_row_id",
        new_column_name="team_id",
        existing_type=UUID,
        existing_nullable=True,
    )
    op.create_foreign_key(
        "fk_employees_team",
        "employees",
        "teams",
        ["team_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_employees_team_id", "employees", ["team_id"])


def downgrade() -> None:
    restore_employee_team_column()
    restore_employee_role_column()
    op.drop_index("ix_teams_lead_employee_id", table_name="teams")
    op.drop_index("ix_teams_department", table_name="teams")
    op.drop_table("teams")
    op.drop_index("ix_roles_department", table_name="roles")
    op.drop_table("roles")


def restore_employee_role_column() -> None:
    op.add_column("employees", sa.Column("role_business_id", sa.String(16)))
    op.execute(RESTORE_EMPLOYEE_ROLES)
    op.drop_index("ix_employees_role_id", table_name="employees")
    op.drop_constraint("fk_employees_role", "employees", type_="foreignkey")
    op.drop_column("employees", "role_id")
    op.alter_column(
        "employees",
        "role_business_id",
        new_column_name="role_id",
        existing_type=sa.String(16),
        existing_nullable=True,
    )


def restore_employee_team_column() -> None:
    op.add_column("employees", sa.Column("team_business_id", sa.String(16)))
    op.execute(RESTORE_EMPLOYEE_TEAMS)
    op.drop_index("ix_employees_team_id", table_name="employees")
    op.drop_constraint("fk_employees_team", "employees", type_="foreignkey")
    op.drop_column("employees", "team_id")
    op.alter_column(
        "employees",
        "team_business_id",
        new_column_name="team_id",
        existing_type=sa.String(16),
        existing_nullable=True,
    )

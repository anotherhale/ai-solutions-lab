"""ORM to domain mapping for roles, teams, and laboratory actors."""

from __future__ import annotations

from wasatch_api.shared.database.models import EmployeeORM, RoleORM, TeamORM
from wasatch_api.workforce.domain.entities import LaboratoryActor, Role, Team


def role_from_orm(row: RoleORM) -> Role:
    return Role(
        id=row.business_id,
        name=row.name,
        department=row.department,
        is_approver=row.is_approver,
        description=row.description,
    )


def team_from_orm(row: TeamORM) -> Team:
    lead = row.lead.business_id if row.lead is not None else None
    return Team(
        id=row.business_id,
        name=row.name,
        department=row.department,
        lead_employee_id=lead,
        service_area=row.service_area,
    )


def laboratory_actor_from_employee(row: EmployeeORM) -> LaboratoryActor:
    role = row.role
    if role is None:
        raise ValueError("laboratory actor requires a role")
    return LaboratoryActor(
        employee_id=row.business_id,
        role_id=role.business_id,
        is_approver=role.is_approver,
        status=row.status,
    )

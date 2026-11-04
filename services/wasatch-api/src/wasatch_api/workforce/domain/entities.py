"""Workforce records used by authentication and authorization."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Role:
    id: str
    name: str
    department: str
    is_approver: bool
    description: str | None = None


@dataclass(frozen=True)
class Team:
    id: str
    name: str
    department: str
    lead_employee_id: str | None = None
    service_area: str | None = None


@dataclass(frozen=True)
class LaboratoryActor:
    """Synthetic employee resolved for a laboratory request.

    ``is_approver`` is copied from the employee's role at resolution time.
    Team membership is not part of this record.
    """

    employee_id: str
    role_id: str
    is_approver: bool
    status: str

"""Load synthetic employees and the role that grants approval authority."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from wasatch_api.shared.database.models import EmployeeORM
from wasatch_api.workforce.domain.entities import LaboratoryActor
from wasatch_api.workforce.infrastructure.mapping import laboratory_actor_from_employee


class EmployeeDirectory:
    def __init__(self, session: Session) -> None:
        self._session = session

    def find_actor(self, business_id: str) -> LaboratoryActor | None:
        row = self._session.scalar(
            select(EmployeeORM)
            .where(EmployeeORM.business_id == business_id)
            .options(selectinload(EmployeeORM.role))
        )
        if row is None or row.role is None or row.status != "active":
            return None
        return laboratory_actor_from_employee(row)

"""Local authenticator for synthetic employees.

The caller presents an employee business id in ``X-Laboratory-Actor``. The
adapter loads that employee and the role's ``is_approver`` flag. It stores no
password and is not an identity provider. Only active employees authenticate.
"""

from __future__ import annotations

from wasatch_api.workforce.domain.entities import LaboratoryActor
from wasatch_api.workforce.infrastructure.repository import EmployeeDirectory

LABORATORY_ACTOR_HEADER = "X-Laboratory-Actor"


class LocalEmployeeAuthenticator:
    def __init__(self, directory: EmployeeDirectory) -> None:
        self._directory = directory

    def authenticate(self, presented_employee_id: str | None) -> LaboratoryActor | None:
        if presented_employee_id is None:
            return None
        business_id = presented_employee_id.strip()
        if not business_id:
            return None
        return self._directory.find_actor(business_id)

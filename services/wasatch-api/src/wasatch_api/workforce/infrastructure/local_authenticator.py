"""Development-only identity simulation for synthetic employees.

A local caller presents an employee business id in ``X-Laboratory-Actor``.
``emp_0001`` is an approver. ``emp_0004`` is not. The adapter loads that
employee and the role's ``is_approver`` flag. It stores no password and it
does not call an identity provider.

The adapter refuses to construct outside local synthetic development
(``APP_ENV`` of ``local``, ``development``, or ``test``). A production
configuration cannot activate it.
"""

from __future__ import annotations

from wasatch_api.config import reject_unsafe_production_configuration
from wasatch_api.workforce.application.ports import EmployeeLookup
from wasatch_api.workforce.domain.entities import LaboratoryActor

LABORATORY_ACTOR_HEADER = "X-Laboratory-Actor"


class LocalEmployeeAuthenticator:
    """Resolve a synthetic employee id during local development.

    ``app_env`` is the process configuration, not a request value. Construction
    is the activation check: production configuration raises before any
    employee is loaded.
    """

    def __init__(self, directory: EmployeeLookup, *, app_env: str) -> None:
        reject_unsafe_production_configuration(app_env)
        self._directory = directory

    def authenticate(self, presented_employee_id: str | None) -> LaboratoryActor | None:
        if presented_employee_id is None:
            return None
        business_id = presented_employee_id.strip()
        if not business_id:
            return None
        return self._directory.find_actor(business_id)

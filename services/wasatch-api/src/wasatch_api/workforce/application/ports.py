"""Ports for workforce adapters."""

from __future__ import annotations

from typing import Protocol

from wasatch_api.workforce.domain.entities import LaboratoryActor


class EmployeeLookup(Protocol):
    """Load one synthetic employee by business id."""

    def find_actor(self, business_id: str) -> LaboratoryActor | None:
        """Return the employee record the directory is willing to expose."""


class EmployeeAuthenticator(Protocol):
    """Resolve the synthetic employee presented by a caller.

    The local header adapter is one implementation, and it is limited to
    local synthetic development. A future production authenticator would be
    a different implementation of this port. It is not a password check and
    it is not an identity-provider client in this service.
    """

    def authenticate(self, presented_employee_id: str | None) -> LaboratoryActor | None:
        """Return the actor, or None when the caller is not authenticated."""

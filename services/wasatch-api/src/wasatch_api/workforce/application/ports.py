"""Ports for workforce adapters."""

from __future__ import annotations

from typing import Protocol

from wasatch_api.workforce.domain.entities import LaboratoryActor


class EmployeeAuthenticator(Protocol):
    """Resolve the synthetic employee presented by a caller."""

    def authenticate(self, presented_employee_id: str | None) -> LaboratoryActor | None:
        """Return the actor, or None when the caller is not authenticated."""

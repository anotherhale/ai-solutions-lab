"""Decide whether an HTTP call may proceed.

Reads of laboratory data require an authenticated actor. Writes are denied
for every actor until a command explicitly allows one. Role rules for those
choices live here, not in the header adapter. Query strings are not part of
the logged action.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from wasatch_api.shared.errors import AuthorizationDenied, UnauthenticatedError
from wasatch_api.workforce.application.ports import EmployeeAuthenticator
from wasatch_api.workforce.domain.authorization import (
    authorize_approval_decision,
    authorize_write,
)
from wasatch_api.workforce.domain.entities import LaboratoryActor

READ_METHODS = frozenset({"GET", "HEAD"})
UNAUTHENTICATED_MESSAGE = "a laboratory actor is required"
WRITE_DENIED_MESSAGE = "writes are denied"
_BUSINESS_ID = re.compile(r"[a-z]+_\d+")


@dataclass(frozen=True)
class AccessDecision:
    outcome: str
    action: str
    subject: str | None
    actor: LaboratoryActor | None = None


def subject_from_path(path: str) -> str | None:
    matches = _BUSINESS_ID.findall(path)
    if matches:
        return matches[-1]
    parts = [part for part in path.split("/") if part]
    return parts[-1] if parts else None


def decide_http_access(
    actor: LaboratoryActor | None, method: str, path: str
) -> AccessDecision:
    action = f"{method.upper()} {path}"
    subject = subject_from_path(path)
    if actor is None:
        return AccessDecision("unauthenticated", action, subject)
    if method.upper() not in READ_METHODS:
        try:
            authorize_write(actor, action)
        except AuthorizationDenied:
            return AccessDecision("forbidden", action, subject, actor)
        return AccessDecision("allowed", action, subject, actor)
    return AccessDecision("allowed", action, subject, actor)


class LaboratoryAccessService:
    """Authenticate a caller and enforce laboratory role rules.

    The header adapter only resolves a synthetic employee, and only in local
    development. This service decides anonymous access, default-deny writes,
    and approver authority. ``authorize_approval`` does not record a decision,
    set a reviewer, or change a message.
    """

    def __init__(self, authenticator: EmployeeAuthenticator) -> None:
        self._authenticator = authenticator

    def decide_request(
        self, presented_employee_id: str | None, method: str, path: str
    ) -> AccessDecision:
        actor = self._authenticator.authenticate(presented_employee_id)
        if actor is not None and actor.status != "active":
            actor = None
        return decide_http_access(actor, method, path)

    def authorize_approval(self, actor: LaboratoryActor) -> None:
        authorize_approval_decision(actor)


def require_authenticated_reader(actor: LaboratoryActor | None) -> LaboratoryActor:
    """Business reads require an active laboratory actor."""

    if actor is None or actor.status != "active":
        raise UnauthenticatedError(UNAUTHENTICATED_MESSAGE)
    return actor

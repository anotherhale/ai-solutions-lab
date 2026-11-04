"""Decide whether an HTTP call may proceed.

Reads of laboratory data require an authenticated actor. Writes are denied
for every actor until a command explicitly allows one. Query strings are not
part of the logged action.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from wasatch_api.shared.errors import AuthorizationDenied
from wasatch_api.workforce.domain.authorization import authorize_write
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

"""Authorization and structured logging without a database."""

from __future__ import annotations

import json
import logging
from io import StringIO

import pytest

from wasatch_api.shared.errors import AuthorizationDenied
from wasatch_api.shared.logging import (
    StructuredFormatter,
    configure_logging,
    log_access,
)
from wasatch_api.workforce.application.access import AccessDecision, decide_http_access
from wasatch_api.workforce.domain.authorization import (
    authorize_approval_decision,
    authorize_write,
)
from wasatch_api.workforce.domain.entities import LaboratoryActor

DISPATCHER = LaboratoryActor(
    employee_id="emp_0004",
    role_id="role_0004",
    is_approver=False,
    status="active",
)
MANAGER = LaboratoryActor(
    employee_id="emp_0001",
    role_id="role_0001",
    is_approver=True,
    status="active",
)


def test_non_approver_role_cannot_decide_an_approval() -> None:
    with pytest.raises(AuthorizationDenied, match="role role_0004"):
        authorize_approval_decision(DISPATCHER)


def test_approver_passes_the_decision_check_without_recording_one() -> None:
    authorize_approval_decision(MANAGER)


def test_inactive_approver_cannot_decide_an_approval() -> None:
    inactive = LaboratoryActor(
        employee_id="emp_0001",
        role_id="role_0001",
        is_approver=True,
        status="terminated",
    )
    with pytest.raises(AuthorizationDenied, match="not an active employee"):
        authorize_approval_decision(inactive)


def test_writes_are_denied_for_an_approver() -> None:
    with pytest.raises(AuthorizationDenied):
        authorize_write(MANAGER, "POST /api/v1/approval-requests/apr_0001/decisions")


def test_http_access_rejects_anonymous_writes_and_allows_reads() -> None:
    anonymous = decide_http_access(
        None, "POST", "/api/v1/approval-requests/apr_0001/decisions"
    )
    assert anonymous.outcome == "unauthenticated"
    assert anonymous.subject == "apr_0001"
    assert anonymous.actor is None

    denied = decide_http_access(
        MANAGER, "POST", "/api/v1/approval-requests/apr_0001/decisions"
    )
    assert denied.outcome == "forbidden"
    assert denied.actor == MANAGER

    allowed = decide_http_access(DISPATCHER, "GET", "/api/v1/support-tickets/tkt_0007")
    assert allowed.outcome == "allowed"
    assert allowed.subject == "tkt_0007"
    assert allowed.action == "GET /api/v1/support-tickets/tkt_0007"


def test_access_log_uses_app_log_level_and_omits_bodies() -> None:
    decision = AccessDecision(
        outcome="allowed",
        action="GET /api/v1/messages/msg_0016",
        subject="msg_0016",
        actor=DISPATCHER,
    )
    child = logging.getLogger("wasatch_api.access")
    child.setLevel(logging.NOTSET)
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(StructuredFormatter())
    child.addHandler(handler)
    try:
        configure_logging("ERROR")
        log_access(decision)
        assert stream.getvalue() == ""

        configure_logging("INFO")
        log_access(decision)
        payload = json.loads(stream.getvalue())
    finally:
        child.removeHandler(handler)
        child.setLevel(logging.NOTSET)
        configure_logging("INFO")
    assert payload["actor"] == "emp_0004"
    assert payload["action"] == "GET /api/v1/messages/msg_0016"
    assert payload["subject"] == "msg_0016"
    assert payload["outcome"] == "allowed"
    assert payload["level"] == "INFO"
    assert set(payload) == {
        "timestamp",
        "level",
        "logger",
        "message",
        "actor",
        "action",
        "subject",
        "outcome",
    }
    assert "replace-me" not in stream.getvalue()
    assert "password" not in stream.getvalue()

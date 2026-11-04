"""Local synthetic actor adapter, and the production startup refusal."""

from __future__ import annotations

import pytest

from wasatch_api.config import (
    UnsafeProductionConfiguration,
    get_settings,
    reject_unsafe_production_configuration,
)
from wasatch_api.main import create_app
from wasatch_api.shared.errors import AuthorizationDenied
from wasatch_api.shared.logging import configure_logging
from wasatch_api.workforce.application.access import LaboratoryAccessService
from wasatch_api.workforce.domain.entities import LaboratoryActor
from wasatch_api.workforce.infrastructure.local_authenticator import (
    LocalEmployeeAuthenticator,
)

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
DECISION = "/api/v1/approval-requests/apr_0001/decisions"
TICKET = "/api/v1/support-tickets/tkt_0007"


class _MemoryDirectory:
    def __init__(self, actors: dict[str, LaboratoryActor]) -> None:
        self._actors = actors

    def find_actor(self, business_id: str) -> LaboratoryActor | None:
        return self._actors.get(business_id)


class _BoomDirectory:
    def find_actor(self, business_id: str) -> LaboratoryActor | None:
        raise AssertionError("production configuration consulted the directory")


def _service(
    actors: dict[str, LaboratoryActor], *, app_env: str = "local"
) -> LaboratoryAccessService:
    authenticator = LocalEmployeeAuthenticator(
        _MemoryDirectory(actors), app_env=app_env
    )
    return LaboratoryAccessService(authenticator)


@pytest.mark.parametrize("app_env", ["local", "LOCAL", " development ", "test"])
def test_local_synthetic_environments_allow_the_adapter(app_env: str) -> None:
    authenticator = LocalEmployeeAuthenticator(_MemoryDirectory({}), app_env=app_env)
    assert authenticator.authenticate(None) is None
    assert authenticator.authenticate("  ") is None


@pytest.mark.parametrize("app_env", ["production", "Production", "prod", " prod "])
def test_production_configuration_does_not_activate_the_adapter(app_env: str) -> None:
    with pytest.raises(UnsafeProductionConfiguration, match="production configuration"):
        LocalEmployeeAuthenticator(_BoomDirectory(), app_env=app_env)


def test_environment_outside_local_development_does_not_activate_the_adapter() -> None:
    with pytest.raises(
        UnsafeProductionConfiguration, match="outside local synthetic development"
    ):
        LocalEmployeeAuthenticator(_BoomDirectory(), app_env="staging")


def test_anonymous_access_is_rejected() -> None:
    service = _service({"emp_0001": MANAGER, "emp_0004": DISPATCHER})
    for presented in (None, "", "  ", "emp_9999", "cust_0001"):
        read = service.decide_request(presented, "GET", "/api/v1/customers/cust_0001")
        write = service.decide_request(presented, "POST", DECISION)
        assert read.outcome == "unauthenticated"
        assert read.actor is None
        assert write.outcome == "unauthenticated"
        assert write.actor is None


def test_unauthorized_role_can_read_and_cannot_write_or_approve() -> None:
    service = _service({"emp_0004": DISPATCHER})
    read = service.decide_request("emp_0004", "GET", TICKET)
    assert read.outcome == "allowed"
    assert read.actor == DISPATCHER
    write = service.decide_request("emp_0004", "POST", DECISION)
    assert write.outcome == "forbidden"
    assert write.actor == DISPATCHER
    with pytest.raises(AuthorizationDenied, match="role role_0004"):
        service.authorize_approval(DISPATCHER)


def test_privileged_role_can_decide_a_customer_message_and_nothing_else() -> None:
    service = _service({"emp_0001": MANAGER})
    read = service.decide_request(
        "emp_0001", "GET", "/api/v1/approval-requests/apr_0001"
    )
    assert read.outcome == "allowed"
    assert read.actor == MANAGER
    assert read.actor.is_approver is True
    decision = service.decide_request("emp_0001", "POST", DECISION)
    assert decision.outcome == "allowed"
    assert decision.actor == MANAGER
    assert decision.subject == "apr_0001"
    other = service.decide_request("emp_0001", "POST", "/api/v1/customers")
    assert other.outcome == "forbidden"
    replaced = service.decide_request("emp_0001", "PUT", DECISION)
    assert replaced.outcome == "forbidden"
    deleted = service.decide_request(
        "emp_0001", "DELETE", "/api/v1/audit-events/aud_0001"
    )
    assert deleted.outcome == "forbidden"
    assert service.authorize_approval(MANAGER) is None


def test_inactive_privileged_employee_is_anonymous() -> None:
    inactive = LaboratoryActor(
        employee_id="emp_0001",
        role_id="role_0001",
        is_approver=True,
        status="terminated",
    )
    service = _service({"emp_0001": inactive})
    decision = service.decide_request("emp_0001", "GET", TICKET)
    assert decision.outcome == "unauthenticated"
    assert decision.actor is None


@pytest.mark.parametrize("app_env", ["production", "prod"])
def test_production_configuration_fails_startup(
    monkeypatch: pytest.MonkeyPatch, app_env: str
) -> None:
    monkeypatch.setenv("APP_ENV", app_env)
    get_settings.cache_clear()
    try:
        with pytest.raises(
            UnsafeProductionConfiguration, match="production configuration"
        ):
            create_app()
    finally:
        get_settings.cache_clear()


def test_environment_outside_local_development_fails_startup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "staging")
    get_settings.cache_clear()
    try:
        with pytest.raises(
            UnsafeProductionConfiguration, match="outside local synthetic development"
        ):
            create_app()
        with pytest.raises(UnsafeProductionConfiguration):
            reject_unsafe_production_configuration("staging")
    finally:
        get_settings.cache_clear()


@pytest.mark.parametrize("app_env", ["local", "development", "test"])
def test_local_synthetic_configuration_starts(
    monkeypatch: pytest.MonkeyPatch, app_env: str
) -> None:
    monkeypatch.setenv("APP_ENV", app_env)
    get_settings.cache_clear()
    try:
        app = create_app()
    finally:
        get_settings.cache_clear()
        configure_logging("INFO")
    assert app.title == "Wasatch Business Systems API"

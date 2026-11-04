"""SEC-1 keeps the remediated FastAPI and Starlette pair installed."""

from __future__ import annotations

import fastapi
import starlette
from fastapi.testclient import TestClient
from starlette.datastructures import State

from wasatch_api.api.middleware import _remember_actor
from wasatch_api.main import create_app


def _version_tuple(version: str) -> tuple[int, ...]:
    core = version.split("+", 1)[0].split("rc", 1)[0]
    parts: list[int] = []
    for piece in core.split("."):
        digits = "".join(character for character in piece if character.isdigit())
        parts.append(int(digits or "0"))
    return tuple(parts)


def test_installed_http_stack_matches_adr_0007() -> None:
    fastapi_version = _version_tuple(fastapi.__version__)
    starlette_version = _version_tuple(starlette.__version__)
    assert (0, 162, 0) <= fastapi_version < (0, 163)
    assert (1, 10, 0) <= starlette_version < (1, 11)


def test_remember_actor_writes_dict_and_starlette_state() -> None:
    scope: dict[str, object] = {}
    _remember_actor(scope, "emp_0001")
    assert scope["state"] == {"laboratory_actor": "emp_0001"}

    state = State()
    _remember_actor({"state": state}, "emp_0004")
    assert state.laboratory_actor == "emp_0004"


def test_create_app_lifespan_serves_health() -> None:
    """The default lifespan still starts. create_app does not pass on_startup."""

    with TestClient(create_app()) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "wasatch-api"}

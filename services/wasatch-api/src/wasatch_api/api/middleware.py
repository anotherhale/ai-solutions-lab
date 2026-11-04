"""Require a laboratory actor on /api routes and deny writes."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable, MutableMapping

from wasatch_api.api.errors import error_body
from wasatch_api.config import reject_unsafe_production_configuration
from wasatch_api.shared.database.session import get_session_factory
from wasatch_api.shared.logging import log_access
from wasatch_api.workforce.application.access import (
    UNAUTHENTICATED_MESSAGE,
    WRITE_DENIED_MESSAGE,
    AccessDecision,
    LaboratoryAccessService,
)
from wasatch_api.workforce.infrastructure.local_authenticator import (
    LABORATORY_ACTOR_HEADER,
    LocalEmployeeAuthenticator,
)
from wasatch_api.workforce.infrastructure.repository import EmployeeDirectory

Scope = MutableMapping[str, object]
Message = MutableMapping[str, object]
Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]

_HEADER = LABORATORY_ACTOR_HEADER.lower().encode("latin-1")


class LaboratoryAccessMiddleware:
    def __init__(
        self,
        app: Callable[[Scope, Receive, Send], Awaitable[None]],
        *,
        app_env: str,
    ) -> None:
        reject_unsafe_production_configuration(app_env)
        self.app = app
        self._app_env = app_env

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        path = str(scope.get("path", ""))
        if not path.startswith("/api/"):
            await self.app(scope, receive, send)
            return

        decision = self._decide(scope, path)
        log_access(decision)
        if decision.outcome == "unauthenticated":
            await _drain(receive)
            await _reject(send, 401, "unauthenticated", UNAUTHENTICATED_MESSAGE)
            return
        if decision.outcome == "forbidden":
            await _drain(receive)
            await _reject(send, 403, "forbidden", WRITE_DENIED_MESSAGE)
            return
        state = scope.setdefault("state", {})
        if isinstance(state, dict):
            state["laboratory_actor"] = decision.actor
        await self.app(scope, receive, send)

    def _decide(self, scope: Scope, path: str) -> AccessDecision:
        presented = _header(scope)
        session = get_session_factory()()
        try:
            service = LaboratoryAccessService(
                LocalEmployeeAuthenticator(
                    EmployeeDirectory(session), app_env=self._app_env
                )
            )
            return service.decide_request(
                presented, str(scope.get("method", "GET")), path
            )
        finally:
            session.close()


def _header(scope: Scope) -> str | None:
    headers = scope.get("headers", [])
    if not isinstance(headers, list):
        return None
    for key, value in headers:
        if key.lower() == _HEADER:
            text = value.decode("latin-1").strip()
            return text or None
    return None


async def _drain(receive: Receive) -> None:
    while True:
        message = await receive()
        if message.get("type") != "http.request" or not message.get("more_body", False):
            return


async def _reject(send: Send, status: int, code: str, message: str) -> None:
    payload = json.dumps(error_body(code, message)).encode("utf-8")
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(payload)).encode("ascii")),
            ],
        }
    )
    await send({"type": "http.response.body", "body": payload})

"""Unit tests for the read-only agent-server observer.

The HTTP path runs against a real ``httpx`` client backed by a stub transport, so
the observer's request/response handling executes for real. No network and no
credentials.
"""

from __future__ import annotations

import httpx
from development_ops.agent_server import (
    AgentServerObserver,
    ConversationHealth,
)


def _client(handler: object) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))  # type: ignore[arg-type]


def test_reachable_conversation_reports_event_count() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/events/count"):
            return httpx.Response(200, json={"count": 42})
        return httpx.Response(200, json={"id": "conv-1"})

    observer = AgentServerObserver(base_url="http://x", client=_client(handler))
    observation = observer.observe("conv-1")
    assert observation.health == ConversationHealth.REACHABLE
    assert observation.event_count == 42


def test_missing_conversation_is_distinct_from_unreachable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"detail": "not found"})

    observer = AgentServerObserver(base_url="http://x", client=_client(handler))
    observation = observer.observe("gone")
    assert observation.health == ConversationHealth.MISSING
    assert observation.event_count is None


def test_server_error_is_unreachable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    observer = AgentServerObserver(base_url="http://x", client=_client(handler))
    observation = observer.observe("conv-1")
    assert observation.health == ConversationHealth.UNREACHABLE


def test_transport_failure_is_unreachable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom")

    observer = AgentServerObserver(base_url="http://x", client=_client(handler))
    observation = observer.observe("conv-1")
    assert observation.health == ConversationHealth.UNREACHABLE


def test_event_count_failure_does_not_fail_observation() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/events/count"):
            return httpx.Response(500)
        return httpx.Response(200, json={"id": "conv-1"})

    observer = AgentServerObserver(base_url="http://x", client=_client(handler))
    observation = observer.observe("conv-1")
    assert observation.health == ConversationHealth.REACHABLE
    assert observation.event_count is None


def test_ping_true_when_server_answers() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[])

    observer = AgentServerObserver(base_url="http://x", client=_client(handler))
    assert observer.ping() is True


def test_ping_false_when_server_unreachable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down")

    observer = AgentServerObserver(base_url="http://x", client=_client(handler))
    assert observer.ping() is False


def test_api_key_never_appears_in_observation_detail() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom")

    credential = "super" + "-" + "secret-value"
    observer = AgentServerObserver(
        base_url="http://x", api_key=credential, client=_client(handler)
    )
    observation = observer.observe("conv-1")
    assert credential not in (observation.detail or "")

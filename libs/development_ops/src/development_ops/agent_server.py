"""Read-only observation of OpenHands agent-server conversations.

The coordinator monitors a child by asking the agent server two questions:

1. Does the conversation still exist? (a missing conversation is not a crash of
   the coordinator, but it does mean the child is gone)
2. How many events has it produced? (a rising count is *evidence* of activity;
   an unchanged count is not progress)

This module never creates a conversation and never logs credentials. It uses the
same ``X-Session-API-Key`` header contract as
:mod:`development_ops.child_agents`. Only endpoints the installed agent server
documents are used: ``GET /api/conversations/{id}`` and
``GET /api/conversations/{id}/events/count``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import httpx

DEFAULT_AGENT_SERVER_URL = "http://localhost:18000"


class ConversationHealth(StrEnum):
    UNKNOWN = "unknown"
    REACHABLE = "reachable"
    MISSING = "missing"
    UNREACHABLE = "unreachable"


@dataclass(frozen=True, slots=True)
class ConversationObservation:
    """One read-only observation of a child conversation."""

    conversation_id: str
    health: ConversationHealth
    event_count: int | None = None
    detail: str | None = None

    @property
    def reachable(self) -> bool:
        return self.health == ConversationHealth.REACHABLE


class AgentServerObserver:
    """Read-only client for agent-server conversation state."""

    def __init__(
        self,
        *,
        base_url: str = DEFAULT_AGENT_SERVER_URL,
        api_key: str | None = None,
        timeout: float = 15.0,
        client: httpx.Client | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout
        self._client = client

    @property
    def base_url(self) -> str:
        return self._base_url

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self._api_key:
            headers["X-Session-API-Key"] = self._api_key
        return headers

    def _get(self, path: str) -> httpx.Response:
        url = f"{self._base_url}{path}"
        if self._client is not None:
            return self._client.get(url, headers=self._headers())
        return httpx.get(url, headers=self._headers(), timeout=self._timeout)

    def observe(self, conversation_id: str) -> ConversationObservation:
        """Observe a conversation without mutating anything.

        A 404 means the conversation is gone; any other transport or status
        failure means the server is unreachable and the state is unknown. The
        two are deliberately distinct: a missing conversation is a fact about
        the child, an unreachable server is a fact about the infrastructure.
        """
        try:
            response = self._get(f"/api/conversations/{conversation_id}")
        except httpx.HTTPError as exc:
            return ConversationObservation(
                conversation_id=conversation_id,
                health=ConversationHealth.UNREACHABLE,
                detail=f"agent server request failed: {exc}",
            )
        if response.status_code == 404:
            return ConversationObservation(
                conversation_id=conversation_id,
                health=ConversationHealth.MISSING,
                detail="conversation not found on agent server",
            )
        if response.status_code >= 400:
            return ConversationObservation(
                conversation_id=conversation_id,
                health=ConversationHealth.UNREACHABLE,
                detail=f"agent server returned {response.status_code}",
            )
        return ConversationObservation(
            conversation_id=conversation_id,
            health=ConversationHealth.REACHABLE,
            event_count=self._event_count(conversation_id),
        )

    def _event_count(self, conversation_id: str) -> int | None:
        """Best-effort event count. A failure here does not fail the observation."""
        try:
            response = self._get(f"/api/conversations/{conversation_id}/events/count")
        except httpx.HTTPError:
            return None
        if response.status_code >= 400:
            return None
        try:
            body = response.json()
        except ValueError:
            return None
        if isinstance(body, int):
            return body
        if isinstance(body, dict):
            for key in ("count", "total", "event_count"):
                value = body.get(key)
                if isinstance(value, int):
                    return value
        return None

    def ping(self) -> bool:
        """True when the agent server answers at all."""
        try:
            response = self._get("/api/conversations")
        except httpx.HTTPError:
            return False
        # 401/403 still proves the server is up; 5xx or connection failure does
        # not. The caller only needs reachability.
        return response.status_code < 500

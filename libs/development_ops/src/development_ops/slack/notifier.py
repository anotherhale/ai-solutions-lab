"""Slack delivery ports. Persist events before notifying."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import httpx

from development_ops.models import DEFAULT_SLACK_CHANNEL_ID, ActivityEvent
from development_ops.slack.formatting import format_slack_message


@dataclass(frozen=True, slots=True)
class SlackDeliveryResult:
    channel_id: str
    message_ts: str
    duplicate: bool = False


class SlackNotifier(Protocol):
    def deliver(self, event: ActivityEvent) -> SlackDeliveryResult: ...


class NoOpSlackNotifier:
    """Skip Slack delivery (telemetry missing, not success)."""

    def deliver(self, event: ActivityEvent) -> SlackDeliveryResult:
        raise RuntimeError(
            "Slack delivery is not configured; event was persisted only."
        )


class SlackWebApiNotifier:
    """Post to Slack when a bot token is available (local automation or CI)."""

    def __init__(
        self,
        bot_token: str,
        *,
        default_channel_id: str = DEFAULT_SLACK_CHANNEL_ID,
        timeout_seconds: float = 15.0,
    ) -> None:
        self._token = bot_token
        self._default_channel_id = default_channel_id
        self._timeout = timeout_seconds

    def deliver(self, event: ActivityEvent) -> SlackDeliveryResult:
        channel = event.slack.channel_id or self._default_channel_id
        body = format_slack_message(event)
        response = httpx.post(
            "https://slack.com/api/chat.postMessage",
            headers={"Authorization": f"Bearer {self._token}"},
            json={"channel": channel, "text": body, "unfurl_links": False},
            timeout=self._timeout,
        )
        response.raise_for_status()
        payload = response.json()
        if not payload.get("ok"):
            error = str(payload.get("error", "unknown_error"))
            raise RuntimeError(f"Slack chat.postMessage failed: {error}")
        message_ts = str(payload["ts"])
        return SlackDeliveryResult(
            channel_id=str(payload.get("channel", channel)),
            message_ts=message_ts,
            duplicate=False,
        )


class CursorSlackConfirmationNotifier:
    """Record delivery after an external Cursor Slack MCP post."""

    def __init__(
        self,
        *,
        channel_id: str,
        message_ts: str,
    ) -> None:
        self._channel_id = channel_id
        self._message_ts = message_ts

    def deliver(self, event: ActivityEvent) -> SlackDeliveryResult:
        return SlackDeliveryResult(
            channel_id=self._channel_id,
            message_ts=self._message_ts,
        )

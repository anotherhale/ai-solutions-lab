"""High-level API: persist first, then optional Slack delivery."""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from development_ops.models import (
    ActivityEvent,
    ActivityEventCreate,
    SlackDeliveryStatus,
    SlackReference,
)
from development_ops.persistence.repository import ActivityEventRepository
from development_ops.slack.notifier import (
    NoOpSlackNotifier,
    SlackDeliveryResult,
    SlackNotifier,
    SlackWebApiNotifier,
)


@dataclass(frozen=True, slots=True)
class RecordResult:
    event: ActivityEvent
    created: bool
    slack_attempted: bool
    slack_delivered: bool
    slack_error: str | None = None


def slack_notifier_from_env() -> SlackNotifier | None:
    token = os.environ.get("DEVELOPMENT_OPS_SLACK_BOT_TOKEN", "").strip()
    if not token:
        return None
    channel = os.environ.get("DEVELOPMENT_OPS_SLACK_CHANNEL_ID", "C0CFJDH7PTJ").strip()
    return SlackWebApiNotifier(bot_token=token, default_channel_id=channel)


class ActivityRecorder:
    """Append activity events and optionally notify Slack."""

    def __init__(
        self,
        session: Session,
        *,
        notifier: SlackNotifier | None = None,
        notify_slack: bool = True,
    ) -> None:
        self._session = session
        self._repo = ActivityEventRepository(session)
        self._notify_slack = notify_slack
        if notifier is not None:
            self._notifier: SlackNotifier | None = notifier
        elif notify_slack:
            self._notifier = slack_notifier_from_env()
        else:
            self._notifier = None

    def record(
        self,
        payload: ActivityEventCreate,
        *,
        attempt_slack: bool | None = None,
    ) -> RecordResult:
        slack_ref = payload.slack or SlackReference()
        if attempt_slack is None:
            attempt_slack = self._notify_slack
        if not attempt_slack:
            slack_ref = slack_ref.model_copy(
                update={"delivery_status": SlackDeliveryStatus.SKIPPED}
            )
            payload = payload.model_copy(update={"slack": slack_ref})

        event, created = self._repo.append(payload)
        self._session.commit()

        if not attempt_slack or self._notifier is None:
            if attempt_slack and self._notifier is None:
                self._repo.mark_slack_failed(
                    event.id,
                    error=(
                        "Slack delivery not configured "
                        "(DEVELOPMENT_OPS_SLACK_BOT_TOKEN unset)"
                    ),
                )
                self._session.commit()
                refreshed = self._repo.get_by_id(event.id)
                assert refreshed is not None
                return RecordResult(
                    event=refreshed,
                    created=created,
                    slack_attempted=True,
                    slack_delivered=False,
                    slack_error="Slack delivery not configured",
                )
            return RecordResult(
                event=event,
                created=created,
                slack_attempted=False,
                slack_delivered=False,
            )

        try:
            delivery = self._deliver_slack(event)
        except Exception as exc:  # noqa: BLE001 — persist failure, do not lose event
            self._repo.mark_slack_failed(event.id, error=str(exc))
            self._session.commit()
            refreshed = self._repo.get_by_id(event.id)
            assert refreshed is not None
            return RecordResult(
                event=refreshed,
                created=created,
                slack_attempted=True,
                slack_delivered=False,
                slack_error=str(exc),
            )

        status = (
            SlackDeliveryStatus.DUPLICATE
            if delivery.duplicate
            else SlackDeliveryStatus.DELIVERED
        )
        updated = self._repo.record_slack_delivery(
            event.id,
            channel_id=delivery.channel_id,
            message_ts=delivery.message_ts,
            status=status,
        )
        self._session.commit()
        assert updated is not None
        return RecordResult(
            event=updated,
            created=created,
            slack_attempted=True,
            slack_delivered=True,
        )

    def confirm_slack_delivery(
        self,
        event_id: uuid.UUID,
        *,
        channel_id: str,
        message_ts: str,
        duplicate: bool = False,
    ) -> ActivityEvent | None:
        """Record Slack confirmation after Cursor MCP delivery."""
        status = (
            SlackDeliveryStatus.DUPLICATE
            if duplicate
            else SlackDeliveryStatus.DELIVERED
        )
        updated = self._repo.record_slack_delivery(
            event_id,
            channel_id=channel_id,
            message_ts=message_ts,
            status=status,
        )
        self._session.commit()
        return updated

    def _deliver_slack(self, event: ActivityEvent) -> SlackDeliveryResult:
        if self._notifier is None:
            raise NoOpSlackNotifier().deliver(event)
        return self._notifier.deliver(event)

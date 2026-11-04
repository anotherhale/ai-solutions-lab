"""Append-only activity event persistence with idempotent inserts."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import Select, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from development_ops.models import (
    DEFAULT_SLACK_CHANNEL_ID,
    ActivityEvent,
    ActivityEventCreate,
    GitHubReference,
    SlackDeliveryStatus,
    SlackReference,
)
from development_ops.persistence.orm import ActivityEventORM
from development_ops.taxonomy import EventSeverity, EventType


def _utc_now() -> datetime:
    return datetime.now(tz=UTC)


def _to_domain(row: ActivityEventORM) -> ActivityEvent:
    return ActivityEvent(
        id=row.id,
        idempotency_key=row.idempotency_key,
        occurred_at=row.occurred_at,
        recorded_at=row.recorded_at,
        run_id=row.run_id,
        task_id=row.task_id,
        agent_name=row.agent_name,
        event_type=EventType(row.event_type),
        severity=EventSeverity(row.severity),
        title=row.title,
        summary=row.summary,
        metadata=dict(row.event_metadata or {}),
        github=GitHubReference(
            repository=row.github_repository,
            pull_number=row.github_pull_number,
            commit_sha=row.github_commit_sha,
            actions_run_url=row.github_actions_run_url,
        ),
        slack=SlackReference(
            channel_id=row.slack_channel_id or DEFAULT_SLACK_CHANNEL_ID,
            message_ts=row.slack_message_ts,
            delivery_status=SlackDeliveryStatus(row.slack_delivery_status),
            delivery_error=row.slack_delivery_error,
            delivery_attempted_at=row.slack_delivery_attempted_at,
        ),
    )


class ActivityEventRepository:
    """PostgreSQL repository for development_ops.activity_events."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, event_id: uuid.UUID) -> ActivityEvent | None:
        row = self._session.get(ActivityEventORM, event_id)
        return _to_domain(row) if row is not None else None

    def get_by_idempotency_key(self, key: str) -> ActivityEvent | None:
        stmt = select(ActivityEventORM).where(ActivityEventORM.idempotency_key == key)
        row = self._session.scalar(stmt)
        return _to_domain(row) if row is not None else None

    def append(self, payload: ActivityEventCreate) -> tuple[ActivityEvent, bool]:
        """Insert an event.

        Returns `(event, created)`. `created` is false on idempotent replay.
        """
        if payload.idempotency_key:
            existing = self.get_by_idempotency_key(payload.idempotency_key)
            if existing is not None:
                return existing, False

        event_id = payload.event_id or uuid.uuid4()
        occurred_at = payload.occurred_at or _utc_now()
        recorded_at = _utc_now()
        github = payload.github or GitHubReference()
        slack = payload.slack or SlackReference()

        row = ActivityEventORM(
            id=event_id,
            idempotency_key=payload.idempotency_key,
            occurred_at=occurred_at,
            recorded_at=recorded_at,
            run_id=payload.run_id,
            task_id=payload.task_id,
            agent_name=payload.agent_name,
            event_type=payload.event_type.value,
            severity=payload.severity.value,
            title=payload.title,
            summary=payload.summary,
            event_metadata=payload.metadata,
            github_repository=github.repository,
            github_pull_number=github.pull_number,
            github_commit_sha=github.commit_sha,
            github_actions_run_url=github.actions_run_url,
            slack_channel_id=slack.channel_id,
            slack_message_ts=slack.message_ts,
            slack_delivery_status=slack.delivery_status.value,
            slack_delivery_error=slack.delivery_error,
            slack_delivery_attempted_at=slack.delivery_attempted_at,
        )
        self._session.add(row)
        try:
            self._session.flush()
        except IntegrityError:
            self._session.rollback()
            if payload.idempotency_key:
                replay = self.get_by_idempotency_key(payload.idempotency_key)
                if replay is not None:
                    return replay, False
            raise
        return _to_domain(row), True

    def record_slack_delivery(
        self,
        event_id: uuid.UUID,
        *,
        channel_id: str,
        message_ts: str,
        status: SlackDeliveryStatus,
        error: str | None = None,
        attempted_at: datetime | None = None,
    ) -> ActivityEvent | None:
        row = self._session.get(ActivityEventORM, event_id)
        if row is None:
            return None
        row.slack_channel_id = channel_id
        row.slack_message_ts = message_ts
        row.slack_delivery_status = status.value
        row.slack_delivery_error = error
        row.slack_delivery_attempted_at = attempted_at or _utc_now()
        self._session.flush()
        return _to_domain(row)

    def mark_slack_failed(
        self,
        event_id: uuid.UUID,
        *,
        error: str,
        attempted_at: datetime | None = None,
    ) -> ActivityEvent | None:
        row = self._session.get(ActivityEventORM, event_id)
        if row is None:
            return None
        row.slack_delivery_status = SlackDeliveryStatus.FAILED.value
        row.slack_delivery_error = error[:2000]
        row.slack_delivery_attempted_at = attempted_at or _utc_now()
        self._session.flush()
        return _to_domain(row)

    def search(self, query: ActivityEventQuery) -> list[ActivityEvent]:
        stmt = select(ActivityEventORM).order_by(
            ActivityEventORM.occurred_at.desc(),
            ActivityEventORM.recorded_at.desc(),
        )
        stmt = query.apply(stmt)
        rows = self._session.scalars(stmt).all()
        return [_to_domain(row) for row in rows]


class ActivityEventQuery:
    """Filter parameters for activity event reads."""

    def __init__(
        self,
        *,
        run_id: uuid.UUID | None = None,
        task_id: str | None = None,
        event_type: EventType | None = None,
        severity: EventSeverity | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 500,
    ) -> None:
        self.run_id = run_id
        self.task_id = task_id
        self.event_type = event_type
        self.severity = severity
        self.since = since
        self.until = until
        self.limit = min(max(limit, 1), 5000)

    def apply(
        self, stmt: Select[tuple[ActivityEventORM]]
    ) -> Select[tuple[ActivityEventORM]]:
        if self.run_id is not None:
            stmt = stmt.where(ActivityEventORM.run_id == self.run_id)
        if self.task_id is not None:
            stmt = stmt.where(ActivityEventORM.task_id == self.task_id)
        if self.event_type is not None:
            stmt = stmt.where(ActivityEventORM.event_type == self.event_type.value)
        if self.severity is not None:
            stmt = stmt.where(ActivityEventORM.severity == self.severity.value)
        if self.since is not None:
            stmt = stmt.where(ActivityEventORM.occurred_at >= self.since)
        if self.until is not None:
            stmt = stmt.where(ActivityEventORM.occurred_at <= self.until)
        return stmt.limit(self.limit)

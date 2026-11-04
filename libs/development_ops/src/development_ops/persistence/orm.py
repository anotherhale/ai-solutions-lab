"""SQLAlchemy ORM mapping for development_ops.activity_events."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class DevelopmentOpsBase(DeclarativeBase):
    pass


class ActivityEventORM(DevelopmentOpsBase):
    __tablename__ = "activity_events"
    __table_args__ = {"schema": "development_ops"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(255), unique=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    task_id: Mapped[str | None] = mapped_column(String(128), index=True)
    agent_name: Mapped[str | None] = mapped_column(String(128))
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    severity: Mapped[str] = mapped_column(String(16), index=True)
    title: Mapped[str] = mapped_column(String(512))
    summary: Mapped[str | None] = mapped_column(Text())
    event_metadata: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    github_repository: Mapped[str | None] = mapped_column(String(255))
    github_pull_number: Mapped[int | None] = mapped_column(Integer())
    github_commit_sha: Mapped[str | None] = mapped_column(String(64))
    github_actions_run_url: Mapped[str | None] = mapped_column(String(2048))
    slack_channel_id: Mapped[str | None] = mapped_column(String(32))
    slack_message_ts: Mapped[str | None] = mapped_column(String(32))
    slack_delivery_status: Mapped[str] = mapped_column(String(16), index=True)
    slack_delivery_error: Mapped[str | None] = mapped_column(Text())
    slack_delivery_attempted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )

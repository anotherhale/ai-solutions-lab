"""SQLAlchemy ORM mapping for development_ops.activity_events."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID  # noqa: TC002
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


class CoordinatorTaskORM(DevelopmentOpsBase):
    __tablename__ = "coordinator_tasks"
    __table_args__ = {"schema": "development_ops"}

    task_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(512))
    depends_on: Mapped[list] = mapped_column(JSONB, default=list)
    status: Mapped[str] = mapped_column(String(32), index=True)
    blocked_reason: Mapped[str | None] = mapped_column(Text())
    active_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    branch_name: Mapped[str | None] = mapped_column(String(255))
    pr_number: Mapped[int | None] = mapped_column(Integer())
    owner_agent: Mapped[str | None] = mapped_column(String(128))
    merge_commit_sha: Mapped[str | None] = mapped_column(String(64))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

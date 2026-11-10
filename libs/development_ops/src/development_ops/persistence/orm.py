"""SQLAlchemy ORM mapping for development_ops.activity_events."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
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
    base_branch: Mapped[str | None] = mapped_column(String(255))
    pr_number: Mapped[int | None] = mapped_column(Integer())
    owner_agent: Mapped[str | None] = mapped_column(String(128))
    merge_commit_sha: Mapped[str | None] = mapped_column(String(64))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempt_count: Mapped[int] = mapped_column(Integer(), default=0)
    last_error: Mapped[str | None] = mapped_column(Text())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class AgentWorktreeORM(DevelopmentOpsBase):
    """Durable association of a task, its worktree, and its child conversation.

    One row per task. The unique branch and worktree path make the registry the
    source of truth for cleanup, so an interrupted launch can be recovered and
    merged work can be reaped without guessing paths.
    """

    __tablename__ = "agent_worktrees"
    __table_args__ = {"schema": "development_ops"}

    task_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    branch_name: Mapped[str] = mapped_column(String(255), unique=True)
    worktree_path: Mapped[str] = mapped_column(String(1024), unique=True)
    base_ref: Mapped[str] = mapped_column(String(255))
    base_sha: Mapped[str | None] = mapped_column(String(64))
    conversation_id: Mapped[str | None] = mapped_column(String(128))
    run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    state: Mapped[str] = mapped_column(String(32), index=True)
    pr_number: Mapped[int | None] = mapped_column(Integer())
    notes: Mapped[str | None] = mapped_column(Text())
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class ChildExecutionORM(DevelopmentOpsBase):
    """Durable record of one child-agent execution attempt.

    One *active* execution per task is enforced by a partial unique index
    (``ux_child_executions_active_task``) on ``task_id`` where the state is an
    active one. Historical rows are preserved: a task may accumulate a failed
    attempt and a later successful one.

    ``conversation_id`` is the OpenHands conversation identity; ``attempt`` and
    ``idempotency_key`` make duplicate launch requests safe. ``progress_seq``
    advances only on a *meaningful* progress signal, so a live-but-idle child is
    distinguishable from a working one.
    """

    __tablename__ = "child_executions"
    __table_args__ = ({"schema": "development_ops"},)

    execution_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True
    )
    task_id: Mapped[str] = mapped_column(String(64), index=True)
    state: Mapped[str] = mapped_column(String(32), index=True)
    attempt: Mapped[int] = mapped_column(Integer(), default=1)
    idempotency_key: Mapped[str] = mapped_column(String(255), unique=True)
    run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    owner_agent: Mapped[str | None] = mapped_column(String(128))
    conversation_id: Mapped[str | None] = mapped_column(String(128), index=True)
    agent_server_url: Mapped[str | None] = mapped_column(String(512))
    worktree_path: Mapped[str | None] = mapped_column(String(1024))
    branch_name: Mapped[str | None] = mapped_column(String(255))
    pr_number: Mapped[int | None] = mapped_column(Integer())
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_progress_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    progress_seq: Mapped[int] = mapped_column(Integer(), default=0)
    last_event_count: Mapped[int | None] = mapped_column(Integer())
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_reason: Mapped[str | None] = mapped_column(Text())
    operator_intervention: Mapped[bool] = mapped_column(Boolean(), default=False)
    retry_count: Mapped[int] = mapped_column(Integer(), default=0)
    notes: Mapped[str | None] = mapped_column(Text())
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class OrchestrationSettingORM(DevelopmentOpsBase):
    """Durable key/value settings for the coordinator orchestration layer.

    The only setting today is ``child_execution_enabled``. It is a row, not an
    environment variable, so the operator's enable/disable decision survives a
    restart and cannot be flipped by an exported variable.
    """

    __tablename__ = "orchestration_settings"
    __table_args__ = {"schema": "development_ops"}

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[dict] = mapped_column(JSONB, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class ReviewVerdictORM(DevelopmentOpsBase):
    """Audit/cache mirror of a reviewer verdict (canonical source is GitHub)."""

    __tablename__ = "review_verdicts"
    __table_args__ = (
        UniqueConstraint(
            "repository",
            "pull_number",
            "head_sha",
            "review_id",
            name="uq_review_verdicts_identity",
        ),
        {"schema": "development_ops"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    repository: Mapped[str] = mapped_column(String(255), index=True)
    pull_number: Mapped[int] = mapped_column(Integer(), index=True)
    head_sha: Mapped[str] = mapped_column(String(64), index=True)
    review_id: Mapped[int] = mapped_column(BigInteger())
    reviewer_login: Mapped[str] = mapped_column(String(255))
    reviewer_user_id: Mapped[int] = mapped_column(BigInteger())
    verdict: Mapped[str] = mapped_column(String(32))
    blocking_count: Mapped[int] = mapped_column(Integer())
    policy_version: Mapped[str] = mapped_column(String(32))
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

"""Pydantic models for activity events."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from development_ops.taxonomy import EventSeverity, EventType

DEFAULT_SLACK_CHANNEL_ID = "C0CFJDH7PTJ"


class SlackDeliveryStatus(StrEnum):
    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"
    SKIPPED = "skipped"
    DUPLICATE = "duplicate"


class GitHubReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    repository: str | None = None
    pull_number: int | None = Field(default=None, ge=1)
    commit_sha: str | None = Field(default=None, max_length=64)
    actions_run_url: str | None = Field(default=None, max_length=2048)


class SlackReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    channel_id: str = Field(default=DEFAULT_SLACK_CHANNEL_ID, max_length=32)
    message_ts: str | None = Field(default=None, max_length=32)
    delivery_status: SlackDeliveryStatus = SlackDeliveryStatus.PENDING
    delivery_error: str | None = None
    delivery_attempted_at: datetime | None = None


class ActivityEventCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: uuid.UUID
    event_type: EventType
    severity: EventSeverity
    title: str = Field(min_length=1, max_length=512)
    summary: str | None = None
    task_id: str | None = Field(default=None, max_length=128)
    agent_name: str | None = Field(default=None, max_length=128)
    occurred_at: datetime | None = None
    idempotency_key: str | None = Field(default=None, max_length=255)
    metadata: dict[str, Any] = Field(default_factory=dict)
    github: GitHubReference | None = None
    slack: SlackReference | None = None
    event_id: uuid.UUID | None = None

    @field_validator("metadata")
    @classmethod
    def metadata_must_be_json_safe(cls, value: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(value, dict):
            msg = "metadata must be an object"
            raise TypeError(msg)
        return value


class ActivityEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    idempotency_key: str | None
    occurred_at: datetime
    recorded_at: datetime
    run_id: uuid.UUID
    task_id: str | None
    agent_name: str | None
    event_type: EventType
    severity: EventSeverity
    title: str
    summary: str | None
    metadata: dict[str, Any]
    github: GitHubReference
    slack: SlackReference

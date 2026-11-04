from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from development_ops.models import (
    ActivityEvent,
    ActivityEventCreate,
    GitHubReference,
    SlackReference,
)
from development_ops.slack.formatting import format_slack_message
from development_ops.taxonomy import EventSeverity, EventType


def test_activity_event_create_requires_title() -> None:
    with pytest.raises(ValueError):
        ActivityEventCreate(
            run_id=uuid.uuid4(),
            event_type=EventType.PROGRESS_REPORT,
            severity=EventSeverity.INFO,
            title="",
        )


def test_format_slack_message_includes_github_and_run() -> None:
    run_id = uuid.UUID("11111111-1111-1111-1111-111111111111")
    event = ActivityEvent(
        id=uuid.uuid4(),
        idempotency_key=None,
        occurred_at=datetime.now(tz=UTC),
        recorded_at=datetime.now(tz=UTC),
        run_id=run_id,
        task_id="DEV-1",
        agent_name="cursor-agent",
        event_type=EventType.PR_OPENED,
        severity=EventSeverity.NOTICE,
        title="Opened pull request",
        summary="Foundation for activity log",
        metadata={},
        github=GitHubReference(
            repository="anotherhale/ai-solutions-lab",
            pull_number=42,
            actions_run_url="https://github.com/anotherhale/ai-solutions-lab/actions/runs/1",
        ),
        slack=SlackReference(),
    )
    text = format_slack_message(event)
    assert "Opened pull request" in text
    assert "anotherhale/ai-solutions-lab#42" in text
    assert str(run_id) in text
    assert "DEV-1" in text

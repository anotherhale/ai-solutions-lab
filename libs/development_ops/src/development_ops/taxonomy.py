"""Standard event taxonomy for development activity."""

from __future__ import annotations

from enum import StrEnum


class EventType(StrEnum):
    RUN_STARTED = "run.started"
    RUN_COMPLETED = "run.completed"
    RUN_FAILED = "run.failed"
    TASK_SELECTED = "task.selected"
    TASK_DELEGATED = "task.delegated"
    IMPLEMENTATION_MILESTONE = "implementation.milestone"
    TEST_STARTED = "test.started"
    TEST_COMPLETED = "test.completed"
    TEST_FAILED = "test.failed"
    REVIEW_STARTED = "review.started"
    REVIEW_COMPLETED = "review.completed"
    PR_OPENED = "pr.opened"
    PR_UPDATED = "pr.updated"
    PR_MERGED = "pr.merged"
    PROGRESS_REPORT = "progress.report"
    BLOCKER_REPORTED = "blocker.reported"
    MILESTONE_REACHED = "milestone.reached"


class EventSeverity(StrEnum):
    DEBUG = "debug"
    INFO = "info"
    NOTICE = "notice"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

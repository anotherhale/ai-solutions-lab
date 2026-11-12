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
    COORDINATOR_RECOVERY = "coordinator.recovery"
    COORDINATOR_SCHEDULED = "coordinator.scheduled"
    COORDINATOR_AUTO_MERGE = "coordinator.auto_merge"
    # Child-agent execution lifecycle (Phase D). One event type per meaningful
    # transition so the activity log is a faithful execution history.
    CHILD_REQUESTED = "child.requested"
    CHILD_CLAIMED = "child.claimed"
    CHILD_WORKTREE_PREPARED = "child.worktree_prepared"
    CHILD_LAUNCH_REQUESTED = "child.launch_requested"
    CHILD_LAUNCH_SUCCEEDED = "child.launch_succeeded"
    CHILD_LAUNCH_FAILED = "child.launch_failed"
    CHILD_PROGRESS = "child.progress"
    CHILD_HEARTBEAT_TIMEOUT = "child.heartbeat_timeout"
    CHILD_STALLED = "child.stalled"
    CHILD_RECOVERY = "child.recovery"
    CHILD_RETRY = "child.retry"
    CHILD_COMPLETED = "child.completed"
    CHILD_PR_OPEN = "child.pr_open"
    CHILD_AWAITING_MERGE = "child.awaiting_merge"
    CHILD_MERGED = "child.merged"
    CHILD_OPERATOR_INTERVENTION = "child.operator_intervention"
    CHILD_EXECUTION_TOGGLED = "child.execution_toggled"


class EventSeverity(StrEnum):
    DEBUG = "debug"
    INFO = "info"
    NOTICE = "notice"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

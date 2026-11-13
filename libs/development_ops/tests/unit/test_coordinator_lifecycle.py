"""Coordinator lifecycle: catalog sync precedence and merge readiness."""

from __future__ import annotations

from development_ops.backlog import BacklogTaskStatus
from development_ops.github_client import PullRequestState
from development_ops.persistence.coordinator_repository import reconcile_status
from development_ops.scheduling import (
    CoordinatorTaskView,
    RuntimeTaskStatus,
    is_active,
    select_next_eligible,
)


def _pr(**overrides: object) -> PullRequestState:
    base: dict[str, object] = {
        "number": 92,
        "state": "OPEN",
        "merged": False,
        "mergeable": "MERGEABLE",
        "head_ref": "cursor/x",
        "base_ref": "ai-dev",
        "node_id": "PR_x",
        "auto_merge_enabled": False,
        "checks_green": True,
        "review_decision": None,
        "closed": False,
    }
    base.update(overrides)
    return PullRequestState(**base)  # type: ignore[arg-type]


def test_merge_ready_is_independent_of_auto_merge_support() -> None:
    # GitHub refuses to arm auto-merge for a clean PR; it is still merge-ready.
    pr = _pr(auto_merge_enabled=False)
    assert pr.merge_ready is True


def test_merge_ready_requires_green_checks() -> None:
    assert _pr(checks_green=False).merge_ready is False
    assert _pr(checks_green=None).merge_ready is False


def test_merge_ready_rejects_conflicts_closed_and_merged() -> None:
    assert _pr(mergeable="CONFLICTING").merge_ready is False
    assert _pr(closed=True).merge_ready is False
    assert _pr(merged=True).merge_ready is False


def test_reconcile_status_advances_forward() -> None:
    assert (
        reconcile_status("pending", BacklogTaskStatus.PR_OPEN)
        == RuntimeTaskStatus.PR_OPEN.value
    )
    assert (
        reconcile_status("in_progress", BacklogTaskStatus.MERGE_READY)
        == RuntimeTaskStatus.MERGE_READY.value
    )


def test_reconcile_status_never_regresses() -> None:
    # A stale catalog row must not reopen a merged task.
    assert (
        reconcile_status("merged", BacklogTaskStatus.PENDING)
        == RuntimeTaskStatus.MERGED.value
    )
    assert (
        reconcile_status("pr_open", BacklogTaskStatus.PENDING)
        == RuntimeTaskStatus.PR_OPEN.value
    )


def test_reconcile_status_merged_and_blocked_are_terminal() -> None:
    assert (
        reconcile_status("pr_open", BacklogTaskStatus.MERGED)
        == RuntimeTaskStatus.MERGED.value
    )
    assert (
        reconcile_status("in_progress", BacklogTaskStatus.BLOCKED)
        == RuntimeTaskStatus.BLOCKED.value
    )


def test_active_statuses_hold_the_task() -> None:
    for status in (
        RuntimeTaskStatus.ASSIGNED,
        RuntimeTaskStatus.IN_PROGRESS,
        RuntimeTaskStatus.PR_OPEN,
        RuntimeTaskStatus.MERGE_READY,
    ):
        assert is_active(status) is True
    for status in (
        RuntimeTaskStatus.PENDING,
        RuntimeTaskStatus.MERGED,
        RuntimeTaskStatus.BLOCKED,
    ):
        assert is_active(status) is False


def test_merge_ready_task_is_not_dispatched_again() -> None:
    tasks = [
        CoordinatorTaskView(
            task_id="TASK-A",
            title="A",
            depends_on=(),
            catalog_status=BacklogTaskStatus.MERGE_READY,
            runtime_status=RuntimeTaskStatus.MERGE_READY,
            pr_number=92,
            branch_name="cursor/x",
            blocked_reason=None,
        ),
        CoordinatorTaskView(
            task_id="TASK-B",
            title="B",
            depends_on=(),
            catalog_status=BacklogTaskStatus.PENDING,
            runtime_status=RuntimeTaskStatus.PENDING,
            pr_number=None,
            branch_name=None,
            blocked_reason=None,
        ),
    ]
    decision = select_next_eligible(tasks, max_concurrent=3, active_count=0)
    assert decision.task is not None
    assert decision.task.task_id == "TASK-B"

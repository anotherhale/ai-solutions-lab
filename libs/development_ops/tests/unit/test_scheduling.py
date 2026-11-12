"""Unit tests for coordinator scheduling."""

from __future__ import annotations

from development_ops.backlog import BacklogTask, BacklogTaskStatus
from development_ops.scheduling import (
    IN_FLIGHT_STATUSES,
    SLOT_CONSUMING_STATUSES,
    CoordinatorTaskView,
    RuntimeTaskStatus,
    merge_backlog_with_runtime,
    select_next_eligible,
)


def _view(
    task_id: str,
    *,
    depends_on: tuple[str, ...] = (),
    runtime: RuntimeTaskStatus = RuntimeTaskStatus.PENDING,
    catalog: BacklogTaskStatus = BacklogTaskStatus.PENDING,
) -> CoordinatorTaskView:
    return CoordinatorTaskView(
        task_id=task_id,
        title=task_id,
        depends_on=depends_on,
        catalog_status=catalog,
        runtime_status=runtime,
        pr_number=None,
        branch_name=None,
        blocked_reason=None,
    )


def test_selects_independent_task_while_pr_open_on_another() -> None:
    tasks = [
        _view("TASK-A", runtime=RuntimeTaskStatus.PR_OPEN),
        _view("TASK-B"),
    ]
    decision = select_next_eligible(tasks, max_concurrent=3, active_count=1)
    assert decision.task is not None
    assert decision.task.task_id == "TASK-B"


def test_awaiting_merge_does_not_consume_slot() -> None:
    tasks = [
        _view("TASK-A", runtime=RuntimeTaskStatus.AWAITING_MERGE),
        _view("TASK-B"),
    ]
    decision = select_next_eligible(tasks, max_concurrent=1, active_count=0)
    assert decision.task is not None
    assert decision.task.task_id == "TASK-B"


def test_slot_consuming_statuses_only_include_in_progress() -> None:
    assert SLOT_CONSUMING_STATUSES == frozenset({RuntimeTaskStatus.IN_PROGRESS})
    assert RuntimeTaskStatus.PR_OPEN not in SLOT_CONSUMING_STATUSES
    assert RuntimeTaskStatus.AWAITING_MERGE not in SLOT_CONSUMING_STATUSES


def test_in_flight_statuses_cover_active_states() -> None:
    assert RuntimeTaskStatus.IN_PROGRESS in IN_FLIGHT_STATUSES
    assert RuntimeTaskStatus.PR_OPEN in IN_FLIGHT_STATUSES
    assert RuntimeTaskStatus.AWAITING_MERGE in IN_FLIGHT_STATUSES
    assert RuntimeTaskStatus.PENDING not in IN_FLIGHT_STATUSES
    assert RuntimeTaskStatus.MERGED not in IN_FLIGHT_STATUSES


def test_holds_task_until_dependency_merged() -> None:
    tasks = [
        _view("TASK-A", runtime=RuntimeTaskStatus.PR_OPEN),
        _view("TASK-B", depends_on=("TASK-A",)),
    ]
    decision = select_next_eligible(tasks, max_concurrent=3, active_count=1)
    assert decision.task is None
    assert [item.task_id for item in decision.held_for_dependency] == ["TASK-B"]


def test_respects_max_concurrent() -> None:
    tasks = [_view("TASK-A"), _view("TASK-B")]
    decision = select_next_eligible(tasks, max_concurrent=1, active_count=1)
    assert decision.task is None


def test_merge_backlog_with_runtime() -> None:
    catalog = [
        BacklogTask(id="FIN-1", title="One", status=BacklogTaskStatus.MERGED),
        BacklogTask(id="FIN-2", title="Two", status=BacklogTaskStatus.IN_PROGRESS),
    ]
    views = merge_backlog_with_runtime(
        catalog,
        {"FIN-2": RuntimeTaskStatus.PR_OPEN},
        pr_by_task={"FIN-2": 34},
        branch_by_task={"FIN-2": "cursor/fin-2"},
        blocked_by_task={},
    )
    by_id = {view.task_id: view for view in views}
    assert by_id["FIN-1"].runtime_status == RuntimeTaskStatus.MERGED
    assert by_id["FIN-2"].pr_number == 34

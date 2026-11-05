"""Dependency-aware task selection for the development coordinator."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from development_ops.backlog import BacklogTask, BacklogTaskStatus


class TaskBlockReason(StrEnum):
    DEPENDENCY_OPEN = "dependency_open"
    DEPENDENCY_NOT_MERGED = "dependency_not_merged"
    HUMAN_BLOCK = "human_block"
    DUPLICATE_ASSIGNMENT = "duplicate_assignment"


class RuntimeTaskStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    PR_OPEN = "pr_open"
    MERGED = "merged"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class CoordinatorTaskView:
    task_id: str
    title: str
    depends_on: tuple[str, ...]
    catalog_status: BacklogTaskStatus
    runtime_status: RuntimeTaskStatus
    pr_number: int | None
    branch_name: str | None
    blocked_reason: str | None


@dataclass(frozen=True, slots=True)
class ScheduleDecision:
    task: CoordinatorTaskView | None
    blocked: tuple[CoordinatorTaskView, ...]
    held_for_dependency: tuple[CoordinatorTaskView, ...]


def _merged(task: CoordinatorTaskView) -> bool:
    return task.runtime_status == RuntimeTaskStatus.MERGED or (
        task.catalog_status == BacklogTaskStatus.MERGED
    )


def _dependencies_satisfied(
    task: CoordinatorTaskView, by_id: dict[str, CoordinatorTaskView]
) -> bool:
    for dep_id in task.depends_on:
        dep = by_id.get(dep_id)
        if dep is None or not _merged(dep):
            return False
    return True


def _is_active(task: CoordinatorTaskView) -> bool:
    return task.runtime_status in {
        RuntimeTaskStatus.IN_PROGRESS,
        RuntimeTaskStatus.PR_OPEN,
    }


def select_next_eligible(
    tasks: list[CoordinatorTaskView],
    *,
    max_concurrent: int,
    active_count: int,
    exclude_task_ids: frozenset[str] | None = None,
) -> ScheduleDecision:
    """Pick the next independent task that may start now."""
    exclude = exclude_task_ids or frozenset()
    by_id = {task.task_id: task for task in tasks}
    blocked: list[CoordinatorTaskView] = []
    held: list[CoordinatorTaskView] = []

    if active_count >= max_concurrent:
        return ScheduleDecision(task=None, blocked=tuple(blocked), held_for_dependency=tuple(held))

    candidates: list[CoordinatorTaskView] = []
    for task in tasks:
        if task.task_id in exclude:
            continue
        if _merged(task):
            continue
        if _is_active(task):
            continue
        if task.runtime_status == RuntimeTaskStatus.BLOCKED:
            blocked.append(task)
            continue
        if not _dependencies_satisfied(task, by_id):
            held.append(task)
            continue
        if task.catalog_status == BacklogTaskStatus.BLOCKED:
            blocked.append(task)
            continue
        candidates.append(task)

    candidates.sort(key=lambda item: item.task_id)
    chosen = candidates[0] if candidates else None
    return ScheduleDecision(task=chosen, blocked=tuple(blocked), held_for_dependency=tuple(held))


def merge_backlog_with_runtime(
    catalog: list[BacklogTask],
    runtime_by_id: dict[str, RuntimeTaskStatus],
    *,
    pr_by_task: dict[str, int | None],
    branch_by_task: dict[str, str | None],
    blocked_by_task: dict[str, str | None],
) -> list[CoordinatorTaskView]:
    views: list[CoordinatorTaskView] = []
    for item in catalog:
        runtime = runtime_by_id.get(item.id, RuntimeTaskStatus.PENDING)
        if item.status == BacklogTaskStatus.MERGED:
            runtime = RuntimeTaskStatus.MERGED
        views.append(
            CoordinatorTaskView(
                task_id=item.id,
                title=item.title,
                depends_on=tuple(item.depends_on),
                catalog_status=item.status,
                runtime_status=runtime,
                pr_number=pr_by_task.get(item.id, item.pr_number),
                branch_name=branch_by_task.get(item.id, item.branch),
                blocked_reason=blocked_by_task.get(item.id),
            )
        )
    return views

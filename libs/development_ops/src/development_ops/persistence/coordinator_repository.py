"""Persistence for coordinator task runtime state."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from development_ops.backlog import BacklogDocument, BacklogTaskStatus
from development_ops.persistence.orm import CoordinatorTaskORM
from development_ops.scheduling import RuntimeTaskStatus


def _utc_now() -> datetime:
    return datetime.now(tz=UTC)


def _runtime_from_catalog(status: BacklogTaskStatus) -> str:
    mapping = {
        BacklogTaskStatus.PENDING: RuntimeTaskStatus.PENDING.value,
        BacklogTaskStatus.ASSIGNED: RuntimeTaskStatus.ASSIGNED.value,
        BacklogTaskStatus.IN_PROGRESS: RuntimeTaskStatus.IN_PROGRESS.value,
        BacklogTaskStatus.PR_OPEN: RuntimeTaskStatus.PR_OPEN.value,
        BacklogTaskStatus.MERGE_READY: RuntimeTaskStatus.MERGE_READY.value,
        BacklogTaskStatus.MERGED: RuntimeTaskStatus.MERGED.value,
        BacklogTaskStatus.BLOCKED: RuntimeTaskStatus.BLOCKED.value,
    }
    return mapping[status]


# Catalog sync must never move a task backwards. A later lifecycle state wins so
# that a stale catalog row cannot regress runtime state that GitHub already
# advanced (for example, a merged task is never reopened by a pending row).
_RUNTIME_PRECEDENCE: dict[str, int] = {
    RuntimeTaskStatus.PENDING.value: 0,
    RuntimeTaskStatus.ASSIGNED.value: 1,
    RuntimeTaskStatus.IN_PROGRESS.value: 2,
    RuntimeTaskStatus.PR_OPEN.value: 3,
    RuntimeTaskStatus.MERGE_READY.value: 4,
    RuntimeTaskStatus.MERGED.value: 5,
}


def reconcile_status(current: str, catalog: BacklogTaskStatus) -> str:
    """Return the runtime status after applying a catalog row to current state.

    Catalog sync never moves a task backwards: the later of the current runtime
    status and the catalog status wins. ``merged`` and ``blocked`` are terminal
    and always apply.
    """
    if catalog == BacklogTaskStatus.MERGED:
        return RuntimeTaskStatus.MERGED.value
    if catalog == BacklogTaskStatus.BLOCKED:
        return RuntimeTaskStatus.BLOCKED.value
    candidate = _runtime_from_catalog(catalog)
    if _RUNTIME_PRECEDENCE.get(candidate, 0) > _RUNTIME_PRECEDENCE.get(current, 0):
        return candidate
    return current


class CoordinatorTaskRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def sync_catalog(self, document: BacklogDocument) -> None:
        for task in document.tasks:
            row = self._session.get(CoordinatorTaskORM, task.id)
            if row is None:
                row = CoordinatorTaskORM(
                    task_id=task.id,
                    title=task.title,
                    depends_on=list(task.depends_on),
                    status=_runtime_from_catalog(task.status),
                    branch_name=task.branch,
                    pr_number=task.pr_number,
                    merge_commit_sha=task.merge_commit,
                    updated_at=_utc_now(),
                )
                self._session.add(row)
                continue
            row.title = task.title
            row.depends_on = list(task.depends_on)
            row.status = reconcile_status(row.status, task.status)
            if task.status == BacklogTaskStatus.MERGED and task.merge_commit:
                row.merge_commit_sha = task.merge_commit
            if task.status != BacklogTaskStatus.BLOCKED:
                if task.pr_number is not None:
                    row.pr_number = task.pr_number
                if task.branch is not None:
                    row.branch_name = task.branch
            row.updated_at = _utc_now()
        self._session.commit()

    def list_tasks(self) -> list[CoordinatorTaskORM]:
        return list(self._session.scalars(select(CoordinatorTaskORM)).all())

    def get(self, task_id: str) -> CoordinatorTaskORM | None:
        return self._session.get(CoordinatorTaskORM, task_id)

    def mark_pr_open(
        self,
        task_id: str,
        *,
        run_id: uuid.UUID,
        branch_name: str,
        pr_number: int,
        owner_agent: str | None,
    ) -> CoordinatorTaskORM:
        row = self._require(task_id)
        row.status = RuntimeTaskStatus.PR_OPEN.value
        row.active_run_id = run_id
        row.branch_name = branch_name
        row.pr_number = pr_number
        row.owner_agent = owner_agent
        row.updated_at = _utc_now()
        self._session.commit()
        return row

    def mark_in_progress(
        self,
        task_id: str,
        *,
        run_id: uuid.UUID,
        owner_agent: str | None,
        branch_name: str | None = None,
    ) -> CoordinatorTaskORM:
        row = self._require(task_id)
        row.status = RuntimeTaskStatus.IN_PROGRESS.value
        row.active_run_id = run_id
        row.owner_agent = owner_agent
        if branch_name:
            row.branch_name = branch_name
        row.updated_at = _utc_now()
        self._session.commit()
        return row

    def mark_merge_ready(self, task_id: str) -> CoordinatorTaskORM:
        """Record that the open pull request is ready to merge.

        Merge readiness is derived from GitHub (a non-draft, conflict-free pull
        request whose required checks are green) and is independent of whether
        GitHub will accept an auto-merge request.
        """
        row = self._require(task_id)
        row.status = RuntimeTaskStatus.MERGE_READY.value
        row.updated_at = _utc_now()
        self._session.commit()
        return row

    def mark_merged(self, task_id: str, *, merge_commit_sha: str | None) -> None:
        row = self._require(task_id)
        row.status = RuntimeTaskStatus.MERGED.value
        if merge_commit_sha:
            row.merge_commit_sha = merge_commit_sha
        row.updated_at = _utc_now()
        self._session.commit()

    def mark_blocked(self, task_id: str, reason: str) -> None:
        row = self._require(task_id)
        row.status = RuntimeTaskStatus.BLOCKED.value
        row.blocked_reason = reason
        row.updated_at = _utc_now()
        self._session.commit()

    def release_stale_assignment(
        self, task_id: str, *, reason: str, run_id: uuid.UUID | None
    ) -> bool:
        row = self.get(task_id)
        if row is None:
            return False
        if run_id is not None and row.active_run_id != run_id:
            return False
        if row.status not in {
            RuntimeTaskStatus.ASSIGNED.value,
            RuntimeTaskStatus.IN_PROGRESS.value,
            RuntimeTaskStatus.PR_OPEN.value,
            RuntimeTaskStatus.MERGE_READY.value,
        }:
            return False
        row.status = RuntimeTaskStatus.PENDING.value
        row.blocked_reason = reason
        row.active_run_id = None
        row.owner_agent = None
        row.updated_at = _utc_now()
        self._session.commit()
        return True

    def _require(self, task_id: str) -> CoordinatorTaskORM:
        row = self.get(task_id)
        if row is None:
            msg = f"unknown coordinator task {task_id}"
            raise KeyError(msg)
        return row

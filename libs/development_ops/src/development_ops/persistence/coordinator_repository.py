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
    if status == BacklogTaskStatus.MERGED:
        return RuntimeTaskStatus.MERGED.value
    if status == BacklogTaskStatus.IN_PROGRESS:
        return RuntimeTaskStatus.PR_OPEN.value
    if status == BacklogTaskStatus.BLOCKED:
        return RuntimeTaskStatus.BLOCKED.value
    return RuntimeTaskStatus.PENDING.value


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
            if task.status == BacklogTaskStatus.MERGED:
                row.status = RuntimeTaskStatus.MERGED.value
                if task.merge_commit:
                    row.merge_commit_sha = task.merge_commit
            elif task.status == BacklogTaskStatus.IN_PROGRESS and task.pr_number:
                if row.status in {
                    RuntimeTaskStatus.PENDING.value,
                    RuntimeTaskStatus.IN_PROGRESS.value,
                }:
                    row.status = RuntimeTaskStatus.PR_OPEN.value
                row.pr_number = task.pr_number
                row.branch_name = task.branch
            elif row.status == RuntimeTaskStatus.PENDING.value and task.pr_number:
                row.pr_number = task.pr_number
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
            RuntimeTaskStatus.IN_PROGRESS.value,
            RuntimeTaskStatus.PR_OPEN.value,
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

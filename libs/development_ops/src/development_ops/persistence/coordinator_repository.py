"""Persistence for coordinator task runtime state.

State transitions here are the durability boundary for the coordinator. Claiming
uses a single conditional ``UPDATE`` so two concurrent ticks cannot own the same
task, and lease timestamps let a restart reclaim abandoned work without stealing
from a live run.
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from development_ops.backlog import BacklogDocument, BacklogTaskStatus
from development_ops.persistence.orm import CoordinatorTaskORM
from development_ops.scheduling import (
    SLOT_CONSUMING_STATUSES,
    RuntimeTaskStatus,
)

DEFAULT_LEASE_SECONDS = 900

# A claim is a compare-and-set. The guard repeats every reason a row must not be
# claimed: it is already owned, or it is not claimable work.
_CLAIMABLE_STATUSES = (
    RuntimeTaskStatus.PENDING.value,
    RuntimeTaskStatus.BLOCKED.value,
)


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


def lease_seconds_from_env() -> int:
    raw = os.environ.get("DEVELOPMENT_OPS_LEASE_SECONDS", "").strip()
    if not raw:
        return DEFAULT_LEASE_SECONDS
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_LEASE_SECONDS
    return value if value > 0 else DEFAULT_LEASE_SECONDS


class CoordinatorTaskRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    # -- catalog -----------------------------------------------------------

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
            elif row.status == RuntimeTaskStatus.PENDING.value and task.pr_number:
                row.pr_number = task.pr_number
                row.branch_name = task.branch
            row.updated_at = _utc_now()
        self._session.commit()

    def list_tasks(self) -> list[CoordinatorTaskORM]:
        return list(self._session.scalars(select(CoordinatorTaskORM)).all())

    def get(self, task_id: str) -> CoordinatorTaskORM | None:
        return self._session.get(CoordinatorTaskORM, task_id)

    def count_slot_consuming(self) -> int:
        """Number of tasks actively holding an implementation slot."""
        values = [status.value for status in SLOT_CONSUMING_STATUSES]
        stmt = (
            select(func.count())
            .select_from(CoordinatorTaskORM)
            .where(CoordinatorTaskORM.status.in_(values))
        )
        return int(self._session.scalar(stmt) or 0)

    # -- claims ------------------------------------------------------------

    def claim_for_implementation(
        self,
        task_id: str,
        *,
        run_id: uuid.UUID,
        owner_agent: str | None,
        branch_name: str | None = None,
        base_branch: str | None = None,
        lease_seconds: int | None = None,
    ) -> bool:
        """Atomically claim a task. Returns True only for the winning caller.

        The ``WHERE`` clause repeats the eligibility rules, so a losing race or a
        row already owned by another run updates zero rows and returns False.
        """
        now = _utc_now()
        lease = lease_seconds if lease_seconds is not None else lease_seconds_from_env()
        values: dict[str, object] = {
            "status": RuntimeTaskStatus.IN_PROGRESS.value,
            "active_run_id": run_id,
            "owner_agent": owner_agent,
            "lease_expires_at": now + timedelta(seconds=lease),
            "heartbeat_at": now,
            "attempt_count": CoordinatorTaskORM.attempt_count + 1,
            "updated_at": now,
        }
        if branch_name:
            values["branch_name"] = branch_name
        if base_branch:
            values["base_branch"] = base_branch
        stmt = (
            update(CoordinatorTaskORM)
            .where(CoordinatorTaskORM.task_id == task_id)
            .where(CoordinatorTaskORM.status.in_(_CLAIMABLE_STATUSES))
            .where(CoordinatorTaskORM.active_run_id.is_(None))
            .values(**values)
        )
        result = self._session.execute(stmt)
        self._session.commit()
        return result.rowcount == 1

    def heartbeat(self, task_id: str, *, run_id: uuid.UUID) -> bool:
        """Extend the lease for the run that owns the task."""
        now = _utc_now()
        stmt = (
            update(CoordinatorTaskORM)
            .where(CoordinatorTaskORM.task_id == task_id)
            .where(CoordinatorTaskORM.active_run_id == run_id)
            .values(
                heartbeat_at=now,
                lease_expires_at=now + timedelta(seconds=lease_seconds_from_env()),
                updated_at=now,
            )
        )
        result = self._session.execute(stmt)
        self._session.commit()
        return result.rowcount == 1

    def reclaim_expired_leases(self, *, now: datetime | None = None) -> list[str]:
        """Release in-flight tasks whose lease expired (crashed or stalled run).

        Only tasks with a lease at or before ``now`` are released. A live run
        with a fresh heartbeat is never touched.
        """
        moment = now or _utc_now()
        in_flight = [
            RuntimeTaskStatus.IN_PROGRESS.value,
            RuntimeTaskStatus.PR_OPEN.value,
            RuntimeTaskStatus.AWAITING_MERGE.value,
        ]
        stmt = select(CoordinatorTaskORM).where(
            CoordinatorTaskORM.status.in_(in_flight),
            CoordinatorTaskORM.lease_expires_at.is_not(None),
            CoordinatorTaskORM.lease_expires_at <= moment,
        )
        released: list[str] = []
        for row in self._session.scalars(stmt).all():
            row.status = RuntimeTaskStatus.PENDING.value
            row.active_run_id = None
            row.owner_agent = None
            row.lease_expires_at = None
            row.heartbeat_at = None
            row.last_error = row.last_error or "lease expired; reclaimed"
            row.updated_at = moment
            released.append(row.task_id)
        if released:
            self._session.commit()
        return released

    # -- transitions -------------------------------------------------------

    def mark_pr_open(
        self,
        task_id: str,
        *,
        run_id: uuid.UUID,
        branch_name: str,
        pr_number: int,
        owner_agent: str | None,
        base_branch: str | None = None,
        awaiting_merge: bool = False,
    ) -> CoordinatorTaskORM:
        row = self._require(task_id)
        row.status = (
            RuntimeTaskStatus.AWAITING_MERGE.value
            if awaiting_merge
            else RuntimeTaskStatus.PR_OPEN.value
        )
        row.active_run_id = run_id
        row.branch_name = branch_name
        if base_branch:
            row.base_branch = base_branch
        row.pr_number = pr_number
        row.owner_agent = owner_agent
        # A submitted PR no longer holds an implementation slot; the lease keeps
        # the row protected until merge reconciliation completes.
        now = _utc_now()
        row.lease_expires_at = now + timedelta(seconds=lease_seconds_from_env())
        row.heartbeat_at = now
        row.updated_at = now
        self._session.commit()
        return row

    def mark_merged(self, task_id: str, *, merge_commit_sha: str | None) -> None:
        row = self._require(task_id)
        row.status = RuntimeTaskStatus.MERGED.value
        if merge_commit_sha:
            row.merge_commit_sha = merge_commit_sha
        # Merged work is terminal: drop ownership so nothing looks in-flight.
        row.active_run_id = None
        row.owner_agent = None
        row.lease_expires_at = None
        row.heartbeat_at = None
        row.updated_at = _utc_now()
        self._session.commit()

    def mark_blocked(
        self, task_id: str, reason: str, *, run_id: uuid.UUID | None = None
    ) -> None:
        row = self._require(task_id)
        row.status = RuntimeTaskStatus.BLOCKED.value
        row.blocked_reason = reason
        row.last_error = reason
        row.active_run_id = None
        row.owner_agent = None
        row.lease_expires_at = None
        row.heartbeat_at = None
        row.updated_at = _utc_now()
        self._session.commit()

    def mark_pending(self, task_id: str, *, reason: str | None = None) -> None:
        row = self._require(task_id)
        row.status = RuntimeTaskStatus.PENDING.value
        if reason:
            row.blocked_reason = reason
        row.active_run_id = None
        row.owner_agent = None
        row.lease_expires_at = None
        row.heartbeat_at = None
        row.updated_at = _utc_now()
        self._session.commit()

    def release_stale_assignment(
        self,
        task_id: str,
        *,
        reason: str,
        run_id: uuid.UUID | None,
        force: bool = False,
    ) -> bool:
        """Release an in-flight assignment.

        With ``run_id`` set, only that run's assignment is released unless
        ``force`` is true. Prefer :meth:`reclaim_expired_leases` for recovery so a
        live run is not disturbed.
        """
        row = self.get(task_id)
        if row is None:
            return False
        if run_id is not None and row.active_run_id != run_id and not force:
            return False
        if row.status not in {
            RuntimeTaskStatus.IN_PROGRESS.value,
            RuntimeTaskStatus.PR_OPEN.value,
            RuntimeTaskStatus.AWAITING_MERGE.value,
        }:
            return False
        row.status = RuntimeTaskStatus.PENDING.value
        row.blocked_reason = reason
        row.active_run_id = None
        row.owner_agent = None
        row.lease_expires_at = None
        row.heartbeat_at = None
        row.updated_at = _utc_now()
        self._session.commit()
        return True

    def _require(self, task_id: str) -> CoordinatorTaskORM:
        row = self.get(task_id)
        if row is None:
            msg = f"unknown coordinator task {task_id}"
            raise KeyError(msg)
        return row

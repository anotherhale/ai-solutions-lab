"""Persistence for the child-agent execution registry.

This is the durability boundary for child execution. Every state change is a
single conditional ``UPDATE`` guarded by the expected current state, so two
coordinator ticks (or a tick and a recovery pass) cannot move the same execution
through an illegal or duplicated transition.

Concurrency is counted from the database (``count_active``), never from an
in-memory counter, so the limit holds across coordinator restarts. The partial
unique index ``ux_child_executions_active_task`` is the real guard against two
active executions for one task; this repository treats the resulting
``IntegrityError`` as "an active execution already exists".
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from development_ops.child_lifecycle import (
    ACTIVE_STATES,
    ChildExecutionState,
    require_legal_transition,
)
from development_ops.persistence.orm import ChildExecutionORM


class ChildExecutionConflict(RuntimeError):
    """Another writer already holds an active execution for this task."""


class ChildTransitionConflict(RuntimeError):
    """The row was not in the expected state when a transition was attempted."""


@dataclass(frozen=True, slots=True)
class ChildExecutionRecord:
    execution_id: uuid.UUID
    task_id: str
    state: ChildExecutionState
    attempt: int
    idempotency_key: str
    run_id: uuid.UUID | None
    owner_agent: str | None
    conversation_id: str | None
    agent_server_url: str | None
    worktree_path: str | None
    branch_name: str | None
    pr_number: int | None
    last_heartbeat_at: datetime | None
    last_progress_at: datetime | None
    progress_seq: int
    last_event_count: int | None
    lease_expires_at: datetime | None
    failure_reason: str | None
    operator_intervention: bool
    retry_count: int
    notes: str | None


def _utc_now() -> datetime:
    return datetime.now(tz=UTC)


def _to_record(row: ChildExecutionORM) -> ChildExecutionRecord:
    return ChildExecutionRecord(
        execution_id=row.execution_id,
        task_id=row.task_id,
        state=ChildExecutionState(row.state),
        attempt=row.attempt,
        idempotency_key=row.idempotency_key,
        run_id=row.run_id,
        owner_agent=row.owner_agent,
        conversation_id=row.conversation_id,
        agent_server_url=row.agent_server_url,
        worktree_path=row.worktree_path,
        branch_name=row.branch_name,
        pr_number=row.pr_number,
        last_heartbeat_at=row.last_heartbeat_at,
        last_progress_at=row.last_progress_at,
        progress_seq=row.progress_seq,
        last_event_count=row.last_event_count,
        lease_expires_at=row.lease_expires_at,
        failure_reason=row.failure_reason,
        operator_intervention=row.operator_intervention,
        retry_count=row.retry_count,
        notes=row.notes,
    )


class ChildExecutionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    # -- reads -------------------------------------------------------------

    def get(self, execution_id: uuid.UUID) -> ChildExecutionRecord | None:
        row = self._session.get(ChildExecutionORM, execution_id)
        return _to_record(row) if row else None

    def get_active_for_task(self, task_id: str) -> ChildExecutionRecord | None:
        stmt = select(ChildExecutionORM).where(
            ChildExecutionORM.task_id == task_id,
            ChildExecutionORM.state.in_([s.value for s in ACTIVE_STATES]),
        )
        row = self._session.scalars(stmt).first()
        return _to_record(row) if row else None

    def latest_for_task(self, task_id: str) -> ChildExecutionRecord | None:
        stmt = (
            select(ChildExecutionORM)
            .where(ChildExecutionORM.task_id == task_id)
            .order_by(ChildExecutionORM.attempt.desc())
        )
        row = self._session.scalars(stmt).first()
        return _to_record(row) if row else None

    def list_active(self) -> list[ChildExecutionRecord]:
        stmt = (
            select(ChildExecutionORM)
            .where(ChildExecutionORM.state.in_([s.value for s in ACTIVE_STATES]))
            .order_by(ChildExecutionORM.task_id)
        )
        return [_to_record(row) for row in self._session.scalars(stmt).all()]

    def list_all(self) -> list[ChildExecutionRecord]:
        stmt = select(ChildExecutionORM).order_by(
            ChildExecutionORM.task_id, ChildExecutionORM.attempt
        )
        return [_to_record(row) for row in self._session.scalars(stmt).all()]

    def list_by_state(self, *states: ChildExecutionState) -> list[ChildExecutionRecord]:
        stmt = select(ChildExecutionORM).where(
            ChildExecutionORM.state.in_([state.value for state in states])
        )
        return [_to_record(row) for row in self._session.scalars(stmt).all()]

    def count_active(self) -> int:
        """Active executions across all tasks. Database-backed, restart-safe."""
        stmt = (
            select(func.count())
            .select_from(ChildExecutionORM)
            .where(ChildExecutionORM.state.in_([s.value for s in ACTIVE_STATES]))
        )
        return int(self._session.scalar(stmt) or 0)

    def count_by_state(self) -> dict[str, int]:
        stmt = select(ChildExecutionORM.state, func.count()).group_by(
            ChildExecutionORM.state
        )
        return {str(state): int(count) for state, count in self._session.execute(stmt)}

    def list_expired_leases(
        self, *, now: datetime | None = None
    ) -> list[ChildExecutionRecord]:
        moment = now or _utc_now()
        stmt = select(ChildExecutionORM).where(
            ChildExecutionORM.state.in_([s.value for s in ACTIVE_STATES]),
            ChildExecutionORM.lease_expires_at.is_not(None),
            ChildExecutionORM.lease_expires_at <= moment,
        )
        return [_to_record(row) for row in self._session.scalars(stmt).all()]

    # -- registration ------------------------------------------------------

    def register(
        self,
        task_id: str,
        *,
        run_id: uuid.UUID | None,
        owner_agent: str | None,
        lease_seconds: int,
        worktree_path: str | None = None,
        branch_name: str | None = None,
        agent_server_url: str | None = None,
    ) -> ChildExecutionRecord:
        """Register a new ``claimed`` execution, or return the active one.

        Idempotent against duplicate launch requests: if an active execution
        already exists for the task it is returned unchanged. The partial unique
        index is the concurrency guard, so a racing insert surfaces as
        :class:`ChildExecutionConflict` and the caller treats it as a duplicate.
        """
        existing = self.get_active_for_task(task_id)
        if existing is not None:
            return existing
        attempt = self._next_attempt(task_id)
        now = _utc_now()
        row = ChildExecutionORM(
            execution_id=uuid.uuid4(),
            task_id=task_id,
            state=ChildExecutionState.CLAIMED.value,
            attempt=attempt,
            idempotency_key=f"child:{task_id}:{attempt}",
            run_id=run_id,
            owner_agent=owner_agent,
            worktree_path=worktree_path,
            branch_name=branch_name,
            agent_server_url=agent_server_url,
            last_heartbeat_at=now,
            progress_seq=0,
            lease_expires_at=now + timedelta(seconds=lease_seconds),
        )
        self._session.add(row)
        try:
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            raise ChildExecutionConflict(
                f"another active execution exists for {task_id}"
            ) from exc
        return _to_record(row)

    def _next_attempt(self, task_id: str) -> int:
        stmt = select(func.max(ChildExecutionORM.attempt)).where(
            ChildExecutionORM.task_id == task_id
        )
        return int(self._session.scalar(stmt) or 0) + 1

    # -- transitions -------------------------------------------------------

    def transition(
        self,
        execution_id: uuid.UUID,
        target: ChildExecutionState,
        *,
        conversation_id: str | None = None,
        pr_number: int | None = None,
        failure_reason: str | None = None,
        notes: str | None = None,
        operator_intervention: bool | None = None,
        lease_seconds: int | None = None,
        bump_retry: bool = False,
    ) -> ChildExecutionRecord:
        """Apply a state change, enforcing the legal-transition contract.

        The ``WHERE state = current`` guard makes this a compare-and-set: a stale
        caller that read an older state updates zero rows and raises
        :class:`ChildTransitionConflict` rather than corrupting the record.
        """
        row = self._session.get(ChildExecutionORM, execution_id)
        if row is None:
            msg = f"unknown child execution {execution_id}"
            raise KeyError(msg)
        current = ChildExecutionState(row.state)
        if current != target:
            require_legal_transition(current, target)
        now = _utc_now()
        values: dict[str, object] = {"state": target.value, "updated_at": now}
        if conversation_id is not None:
            values["conversation_id"] = conversation_id
        if pr_number is not None:
            values["pr_number"] = pr_number
        if failure_reason is not None:
            values["failure_reason"] = failure_reason
        if notes is not None:
            values["notes"] = notes
        if operator_intervention is not None:
            values["operator_intervention"] = operator_intervention
        if lease_seconds is not None:
            values["lease_expires_at"] = now + timedelta(seconds=lease_seconds)
            values["last_heartbeat_at"] = now
        if bump_retry:
            values["retry_count"] = ChildExecutionORM.retry_count + 1
        stmt = (
            update(ChildExecutionORM)
            .where(ChildExecutionORM.execution_id == execution_id)
            .where(ChildExecutionORM.state == current.value)
            .values(**values)
        )
        result = self._session.execute(stmt)
        self._session.commit()
        if result.rowcount != 1:
            raise ChildTransitionConflict(
                f"{execution_id} was not in state {current.value}"
            )
        refreshed = self._session.get(ChildExecutionORM, execution_id)
        assert refreshed is not None
        return _to_record(refreshed)

    def record_progress(
        self,
        execution_id: uuid.UUID,
        *,
        lease_seconds: int,
        event_count: int | None = None,
        note: str | None = None,
    ) -> ChildExecutionRecord | None:
        """Record a meaningful progress signal and renew the lease.

        Only a genuine progress signal calls this; polling success alone does
        not. ``progress_seq`` therefore distinguishes a working child from a
        live-but-idle one. Returns ``None`` when the row is not active (a stale
        signal for a finished execution is ignored, not an error).
        """
        now = _utc_now()
        values: dict[str, object] = {
            "last_progress_at": now,
            "last_heartbeat_at": now,
            "lease_expires_at": now + timedelta(seconds=lease_seconds),
            "progress_seq": ChildExecutionORM.progress_seq + 1,
            "updated_at": now,
        }
        if note is not None:
            values["notes"] = note
        if event_count is not None:
            values["last_event_count"] = event_count
        stmt = (
            update(ChildExecutionORM)
            .where(ChildExecutionORM.execution_id == execution_id)
            .where(ChildExecutionORM.state.in_([s.value for s in ACTIVE_STATES]))
            .values(**values)
        )
        result = self._session.execute(stmt)
        self._session.commit()
        if result.rowcount != 1:
            return None
        return self.get(execution_id)

    def heartbeat(
        self, execution_id: uuid.UUID, *, lease_seconds: int
    ) -> ChildExecutionRecord | None:
        """Renew a liveness lease without advancing progress.

        Used for a child that is reachable but has not reported meaningful
        progress. Callers must apply a bounded number of these before classifying
        a child stalled; an indefinite renewal would hide a stuck child.
        """
        now = _utc_now()
        stmt = (
            update(ChildExecutionORM)
            .where(ChildExecutionORM.execution_id == execution_id)
            .where(ChildExecutionORM.state.in_([s.value for s in ACTIVE_STATES]))
            .values(
                last_heartbeat_at=now,
                lease_expires_at=now + timedelta(seconds=lease_seconds),
                updated_at=now,
            )
        )
        result = self._session.execute(stmt)
        self._session.commit()
        if result.rowcount != 1:
            return None
        return self.get(execution_id)

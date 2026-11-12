"""Persistence for the agent worktree registry.

The registry is the durable link between a backlog task, its Git worktree and
branch, and the child conversation that works there. Cleanup reads it instead of
recomputing paths, and an interrupted launch can be reconciled from it.

Every state in :class:`WorktreeState` is produced by a real transition in
:mod:`development_ops.task_worktrees`; there are no placeholder states.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from enum import StrEnum

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from development_ops.persistence.orm import AgentWorktreeORM


class WorktreeRegistryConflict(RuntimeError):
    """A concurrent writer already claimed this task, branch, or worktree."""


class WorktreeState(StrEnum):
    PREPARING = "preparing"
    LAUNCHED = "launched"
    PR_OPEN = "pr_open"
    MERGED = "merged"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class AgentWorktreeRecord:
    task_id: str
    branch_name: str
    worktree_path: str
    base_ref: str
    base_sha: str | None
    conversation_id: str | None
    run_id: uuid.UUID | None
    state: WorktreeState
    pr_number: int | None
    notes: str | None


def _to_record(row: AgentWorktreeORM) -> AgentWorktreeRecord:
    return AgentWorktreeRecord(
        task_id=row.task_id,
        branch_name=row.branch_name,
        worktree_path=row.worktree_path,
        base_ref=row.base_ref,
        base_sha=row.base_sha,
        conversation_id=row.conversation_id,
        run_id=row.run_id,
        state=WorktreeState(row.state),
        pr_number=row.pr_number,
        notes=row.notes,
    )


class AgentWorktreeRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, task_id: str) -> AgentWorktreeRecord | None:
        row = self._session.get(AgentWorktreeORM, task_id)
        return _to_record(row) if row else None

    def list_all(self) -> list[AgentWorktreeRecord]:
        stmt = select(AgentWorktreeORM).order_by(AgentWorktreeORM.task_id)
        return [_to_record(row) for row in self._session.scalars(stmt).all()]

    def list_by_state(self, *states: WorktreeState) -> list[AgentWorktreeRecord]:
        stmt = select(AgentWorktreeORM).where(
            AgentWorktreeORM.state.in_([state.value for state in states])
        )
        return [_to_record(row) for row in self._session.scalars(stmt).all()]

    def upsert(
        self,
        task_id: str,
        *,
        branch_name: str,
        worktree_path: str,
        base_ref: str,
        base_sha: str | None,
        state: WorktreeState,
        run_id: uuid.UUID | None = None,
        conversation_id: str | None = None,
        pr_number: int | None = None,
        notes: str | None = None,
    ) -> AgentWorktreeRecord:
        row = self._session.get(AgentWorktreeORM, task_id)
        try:
            if row is None:
                row = AgentWorktreeORM(
                    task_id=task_id,
                    branch_name=branch_name,
                    worktree_path=worktree_path,
                    base_ref=base_ref,
                    base_sha=base_sha,
                    state=state.value,
                    run_id=run_id,
                    conversation_id=conversation_id,
                    pr_number=pr_number,
                    notes=notes,
                )
                self._session.add(row)
            else:
                row.branch_name = branch_name
                row.worktree_path = worktree_path
                row.base_ref = base_ref
                row.base_sha = base_sha
                row.state = state.value
                if run_id is not None:
                    row.run_id = run_id
                if conversation_id is not None:
                    row.conversation_id = conversation_id
                if pr_number is not None:
                    row.pr_number = pr_number
                if notes is not None:
                    row.notes = notes
            self._session.commit()
        except IntegrityError as exc:
            # Two writers raced to insert the same task/branch/worktree. The
            # unique constraints are the real guard; surface a clear error
            # instead of leaving a half-written row.
            self._session.rollback()
            msg = (
                f"another writer already registered worktree for {task_id} "
                f"(branch {branch_name!r})"
            )
            raise WorktreeRegistryConflict(msg) from exc
        return _to_record(row)

    def mark_state(
        self,
        task_id: str,
        state: WorktreeState,
        *,
        conversation_id: str | None = None,
        pr_number: int | None = None,
        notes: str | None = None,
    ) -> AgentWorktreeRecord:
        row = self._session.get(AgentWorktreeORM, task_id)
        if row is None:
            msg = f"unknown worktree registration for {task_id}"
            raise KeyError(msg)
        row.state = state.value
        if conversation_id is not None:
            row.conversation_id = conversation_id
        if pr_number is not None:
            row.pr_number = pr_number
        if notes is not None:
            row.notes = notes
        self._session.commit()
        return _to_record(row)

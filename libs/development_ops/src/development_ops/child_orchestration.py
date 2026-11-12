"""Bounded, observable, recoverable child-agent orchestration.

This is the application-layer owner of the child-execution lifecycle. It sits
between the coordinator engine (which owns *scheduling*: which task to start
next) and the infrastructure adapters (the Git worktree manager, the OpenHands
child launcher, and the agent-server observer).

Responsibilities:

* decide, each tick, whether a freshly claimed task may be delegated to a child,
  respecting the configured concurrency limit and the durable enable flag;
* launch the child through the existing :class:`TaskWorktreeOrchestrator` so the
  payload and worktree binding stay single-sourced (Phase C);
* monitor active children with meaningful progress signals and classify stalled,
  failed, or abandoned ones;
* recover deterministically after a coordinator or child failure without
  relaunching a child that may still be running;
* align child state with the pull-request state the coordinator already
  reconciled from GitHub;
* expose a read-only status snapshot and the operator enable/disable controls.

It never executes a paid model call on its own. A launch happens only when the
operator has durably enabled execution *and* a slot is free; otherwise the task
stays claimed and the reason is recorded.
"""

from __future__ import annotations

import json
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeout
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from sqlalchemy.orm import Session

from development_ops.agent_server import AgentServerObserver, ConversationHealth
from development_ops.child_config import (
    ChildOrchestrationConfig,
    resolve_enabled,
)
from development_ops.child_lifecycle import ChildExecutionState
from development_ops.models import ActivityEventCreate
from development_ops.persistence.child_repository import (
    ChildExecutionConflict,
    ChildExecutionRecord,
    ChildExecutionRepository,
    ChildTransitionConflict,
)
from development_ops.persistence.coordinator_repository import CoordinatorTaskRepository
from development_ops.persistence.settings_repository import (
    OrchestrationSettingsRepository,
)
from development_ops.persistence.worktree_repository import (
    AgentWorktreeRepository,
    WorktreeState,
)
from development_ops.recorder import ActivityRecorder
from development_ops.scheduling import RuntimeTaskStatus
from development_ops.task_worktrees import (
    TaskLaunchResult,
    TaskWorktreeOrchestrator,
)
from development_ops.taxonomy import EventSeverity, EventType


class ChildAgentSettingsLoader(Protocol):
    """Loads the child conversation ``agent_settings`` payload.

    Returning ``None`` means no settings are configured, which is a normal state
    while execution is disabled. Secrets never appear in logs.
    """

    def __call__(self) -> dict[str, Any] | None: ...


@dataclass(frozen=True, slots=True)
class ChildTickOutcome:
    """What the child-orchestration pass did in one coordinator tick."""

    enabled: bool
    active_children: int
    max_concurrent: int
    launched: tuple[str, ...] = ()
    rejected: tuple[str, ...] = ()
    stalled: tuple[str, ...] = ()
    failed: tuple[str, ...] = ()
    recovered: tuple[str, ...] = ()
    notes: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class ChildStatusView:
    """Read-only view of one child execution for the status command."""

    execution_id: str
    task_id: str
    state: str
    attempt: int
    conversation_id: str | None
    worktree_path: str | None
    branch_name: str | None
    pr_number: int | None
    active: bool
    last_heartbeat_at: str | None
    last_progress_at: str | None
    progress_seq: int
    last_event_count: int | None
    lease_expires_at: str | None
    retry_count: int
    stalled: bool
    operator_intervention: bool
    failure_reason: str | None


@dataclass(frozen=True, slots=True)
class ChildOrchestrationStatus:
    enabled: bool
    enabled_reason: str
    max_concurrent: int
    active_children: int
    available_slots: int
    agent_server_reachable: bool
    children: tuple[ChildStatusView, ...]
    counts_by_state: dict[str, int]


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _utc_now() -> datetime:
    return datetime.now(tz=UTC)


class ChildOrchestrator:
    def __init__(
        self,
        session: Session,
        *,
        config: ChildOrchestrationConfig,
        worktrees: TaskWorktreeOrchestrator | None,
        recorder: ActivityRecorder,
        run_id: uuid.UUID,
        repository: str,
        integration_branch: str = "ai-dev",
        observer: AgentServerObserver | None = None,
        settings_loader: ChildAgentSettingsLoader | None = None,
        owner_agent: str | None = None,
    ) -> None:
        self._session = session
        self._config = config
        self._worktrees = worktrees
        self._recorder = recorder
        self._run_id = run_id
        self._repository = repository
        self._integration_branch = integration_branch
        self._observer = observer
        self._settings_loader = settings_loader
        self._owner_agent = owner_agent
        self._executions = ChildExecutionRepository(session)
        self._tasks = CoordinatorTaskRepository(session)
        self._settings = OrchestrationSettingsRepository(session)
        self._worktree_registry = AgentWorktreeRepository(session)

    # -- enablement --------------------------------------------------------

    def is_enabled(self) -> tuple[bool, str]:
        return resolve_enabled(
            persisted_enabled=self._settings.child_execution_enabled(),
            config=self._config,
        )

    def set_enabled(
        self, enabled: bool, *, by: str | None = None, reason: str | None = None
    ) -> ChildOrchestrationStatus:
        """Durably enable or disable child execution.

        Disabling never destroys or terminates active work: existing children
        continue to be monitored and reconciled. Only *new* launches stop.
        """
        self._settings.set_child_execution_enabled(enabled, by=by, reason=reason)
        self._record(
            EventType.CHILD_EXECUTION_TOGGLED,
            EventSeverity.NOTICE,
            "Child execution "
            + ("enabled" if enabled else "disabled")
            + " by operator",
            summary=f"by={by or 'unknown'} reason={reason or 'n/a'}",
            metadata={"enabled": enabled, "by": by, "reason": reason},
            idempotency_key=None,
        )
        return self.status()

    # -- tick --------------------------------------------------------------

    def tick(self, *, paused: bool) -> ChildTickOutcome:
        """Run one monitoring + (optionally) launch pass.

        Monitoring and recovery always run, even while paused or disabled, so
        existing children are never silently abandoned. New launches happen only
        when execution is enabled and the coordinator is not paused.
        """
        enabled, reason = self.is_enabled()
        notes: list[str] = []
        if not enabled:
            notes.append(f"child execution disabled: {reason}")

        # Capture which children were already stalled *before* this tick's
        # monitor pass. A child stalled in this pass must not be escalated in the
        # same tick: it gets a full tick of grace, matching the production stall
        # window (stall threshold < lease horizon).
        already_stalled = {
            record.execution_id
            for record in self._executions.list_by_state(ChildExecutionState.STALLED)
        }
        monitored = self._monitor(notes)
        recovered = self._recover(already_stalled, notes)

        launched: list[str] = []
        rejected: list[str] = []
        if paused:
            notes.append("paused: no new child launches")
        elif enabled:
            launched, rejected = self._launch_ready(notes)

        active = self._executions.count_active()
        return ChildTickOutcome(
            enabled=enabled,
            active_children=active,
            max_concurrent=self._config.max_concurrent_children,
            launched=tuple(launched),
            rejected=tuple(rejected),
            stalled=tuple(monitored["stalled"]),
            failed=tuple(monitored["failed"]),
            recovered=tuple(recovered),
            notes=tuple(notes),
        )

    # -- monitoring --------------------------------------------------------

    def _monitor(self, notes: list[str]) -> dict[str, list[str]]:
        """Observe every active child and classify progress, stall, or failure.

        A live process is not proof of progress: a child is only kept ``running``
        when a *meaningful* signal (a rising conversation event count) is seen.
        A reachable-but-idle child past the stall threshold becomes ``stalled``;
        a missing conversation or an unreachable server is escalated rather than
        silently relaunched.

        An active execution with no conversation yet (registered, never launched)
        is skipped here and handled by recovery, which knows whether a launch is
        safe.
        """
        stalled: list[str] = []
        failed: list[str] = []
        for record in self._executions.list_active():
            self._align_with_task_state(record, notes)
            # Re-read: the alignment step may have moved the row out of active.
            current = self._executions.get(record.execution_id)
            if current is None or current.state not in _ACTIVE:
                continue
            if current.conversation_id is None:
                # Registered but never launched; recovery owns this case.
                continue
            observation = self._observe(current)
            if observation is None:
                continue
            if observation.health == ConversationHealth.MISSING:
                self._escalate(
                    current,
                    "child conversation is missing on the agent server",
                    notes,
                )
                failed.append(current.task_id)
                continue
            if observation.health == ConversationHealth.UNREACHABLE:
                # Transient: do not fail. The lease and stall logic will escalate
                # if the outage persists beyond the threshold.
                notes.append(
                    f"agent server unreachable for {current.task_id}: "
                    f"{observation.detail}"
                )
                self._classify_stall(current, notes, stalled)
                continue
            progressed = self._record_progress_if_advanced(current, observation, notes)
            if not progressed:
                self._classify_stall(current, notes, stalled)
        return {"stalled": stalled, "failed": failed}

    def _observe(self, record: ChildExecutionRecord) -> Any:
        if self._observer is None or record.conversation_id is None:
            return None
        return self._observer.observe(record.conversation_id)

    def _record_progress_if_advanced(
        self,
        record: ChildExecutionRecord,
        observation: Any,
        notes: list[str],
    ) -> bool:
        """Return True when the observation shows genuine progress."""
        new_count = observation.event_count
        previous = record.last_event_count
        advanced = new_count is not None and (previous is None or new_count > previous)
        if not advanced:
            return False
        updated = self._executions.record_progress(
            record.execution_id,
            lease_seconds=self._child_lease_seconds(),
            event_count=new_count,
        )
        if updated is None:
            return False
        # A stalled child that starts progressing again returns to running.
        if record.state == ChildExecutionState.STALLED:
            try:
                self._executions.transition(
                    record.execution_id, ChildExecutionState.RUNNING
                )
            except ChildTransitionConflict:  # pragma: no cover - benign race
                pass
            self._record(
                EventType.CHILD_RECOVERY,
                EventSeverity.NOTICE,
                f"Child for {record.task_id} resumed progress",
                summary=f"events={new_count}",
                task_id=record.task_id,
                conversation_id=record.conversation_id,
                metadata={"event_count": new_count},
                idempotency_key=None,
            )
        self._record(
            EventType.CHILD_PROGRESS,
            EventSeverity.DEBUG,
            f"Child progress for {record.task_id}",
            summary=f"conversation events={new_count}",
            task_id=record.task_id,
            conversation_id=record.conversation_id,
            metadata={"event_count": new_count, "progress_seq": updated.progress_seq},
            idempotency_key=(
                f"child.progress:{record.execution_id}:{updated.progress_seq}"
            ),
        )
        notes.append(f"child progress for {record.task_id} (events={new_count})")
        return True

    def _classify_stall(
        self,
        record: ChildExecutionRecord,
        notes: list[str],
        stalled: list[str],
    ) -> None:
        reference = record.last_progress_at or record.last_heartbeat_at
        if reference is None:
            return
        idle_seconds = (_utc_now() - reference).total_seconds()
        if idle_seconds < self._config.stall_seconds:
            return
        if record.state == ChildExecutionState.STALLED:
            # Already stalled; nothing new to record.
            stalled.append(record.task_id)
            return
        try:
            self._executions.transition(
                record.execution_id,
                ChildExecutionState.STALLED,
                notes=f"no progress for {int(idle_seconds)}s",
            )
        except (ChildTransitionConflict, KeyError):
            return
        self._record(
            EventType.CHILD_STALLED,
            EventSeverity.WARNING,
            f"Child for {record.task_id} stalled",
            summary=f"no progress for {int(idle_seconds)}s",
            task_id=record.task_id,
            conversation_id=record.conversation_id,
            metadata={"idle_seconds": int(idle_seconds)},
            idempotency_key=f"child.stalled:{record.execution_id}",
        )
        notes.append(f"child for {record.task_id} classified stalled")
        stalled.append(record.task_id)

    def _escalate(
        self,
        record: ChildExecutionRecord,
        reason: str,
        notes: list[str],
    ) -> None:
        """Mark a child for operator intervention instead of guessing."""
        try:
            self._executions.transition(
                record.execution_id,
                ChildExecutionState.FAILED,
                failure_reason=reason,
                operator_intervention=True,
            )
        except (ChildTransitionConflict, KeyError):
            return
        self._record(
            EventType.CHILD_OPERATOR_INTERVENTION,
            EventSeverity.ERROR,
            f"Child for {record.task_id} needs operator intervention",
            summary=reason,
            task_id=record.task_id,
            conversation_id=record.conversation_id,
            metadata={"reason": reason},
            idempotency_key=f"child.intervention:{record.execution_id}",
        )
        notes.append(f"child for {record.task_id}: {reason}")

    # -- alignment with task/PR state --------------------------------------

    def _align_with_task_state(
        self, record: ChildExecutionRecord, notes: list[str]
    ) -> None:
        """Sync child state with the pull-request state the engine reconciled.

        The coordinator engine is the only component that observes GitHub. When
        it moves the task to ``pr_open``/``awaiting_merge``/``merged``/``blocked``
        the child execution follows, releasing its slot on PR open and never
        treating a closed-unmerged PR as success.
        """
        row = self._tasks.get(record.task_id)
        if row is None:
            return
        status = row.status
        try:
            if status == RuntimeTaskStatus.MERGED.value:
                self._executions.transition(
                    record.execution_id, ChildExecutionState.MERGED
                )
                self._record(
                    EventType.CHILD_MERGED,
                    EventSeverity.NOTICE,
                    f"Child for {record.task_id} merged",
                    task_id=record.task_id,
                    conversation_id=record.conversation_id,
                    metadata={"pr_number": row.pr_number},
                    idempotency_key=f"child.merged:{record.execution_id}",
                )
            elif status == RuntimeTaskStatus.AWAITING_MERGE.value:
                self._executions.transition(
                    record.execution_id,
                    ChildExecutionState.AWAITING_MERGE,
                    pr_number=row.pr_number,
                )
                self._record(
                    EventType.CHILD_AWAITING_MERGE,
                    EventSeverity.NOTICE,
                    f"Child for {record.task_id} awaiting merge",
                    task_id=record.task_id,
                    conversation_id=record.conversation_id,
                    metadata={"pr_number": row.pr_number},
                    idempotency_key=f"child.awaiting:{record.execution_id}",
                )
            elif status == RuntimeTaskStatus.PR_OPEN.value:
                self._executions.transition(
                    record.execution_id,
                    ChildExecutionState.PR_OPEN,
                    pr_number=row.pr_number,
                )
                self._record(
                    EventType.CHILD_PR_OPEN,
                    EventSeverity.NOTICE,
                    f"Child for {record.task_id} opened a pull request",
                    task_id=record.task_id,
                    conversation_id=record.conversation_id,
                    metadata={"pr_number": row.pr_number},
                    idempotency_key=f"child.pr_open:{record.execution_id}",
                )
            elif status == RuntimeTaskStatus.BLOCKED.value:
                # A closed-but-unmerged PR is not success. Preserve the worktree
                # and escalate.
                self._executions.transition(
                    record.execution_id,
                    ChildExecutionState.FAILED,
                    failure_reason=row.blocked_reason or "task blocked",
                    operator_intervention=True,
                )
                self._record(
                    EventType.CHILD_OPERATOR_INTERVENTION,
                    EventSeverity.ERROR,
                    f"Child for {record.task_id} blocked",
                    summary=row.blocked_reason,
                    task_id=record.task_id,
                    conversation_id=record.conversation_id,
                    metadata={"reason": row.blocked_reason},
                    idempotency_key=f"child.blocked:{record.execution_id}",
                )
        except ChildTransitionConflict:
            notes.append(f"child state race for {record.task_id}; will retry next tick")

    # -- recovery ----------------------------------------------------------

    def _recover(self, already_stalled: set[uuid.UUID], notes: list[str]) -> list[str]:
        """Deterministic, idempotent recovery for interrupted executions.

        A child whose conversation exists is never relaunched: it may still be
        running. Executions that were never launched are returned to the launch
        queue. A child that was already stalled at the start of the tick and whose
        lease has also expired has no live signal left, so it is escalated to the
        operator rather than guessed at. Everything ambiguous is escalated.
        """
        recovered: list[str] = []
        now = _utc_now()
        for record in self._executions.list_active():
            if record.conversation_id is None:
                self._recover_unlaunched(record, notes)
                recovered.append(record.task_id)
                continue
            if (
                record.execution_id in already_stalled
                and record.lease_expires_at is not None
                and record.lease_expires_at <= now
            ):
                # A stalled child whose lease also expired has no live signal.
                self._escalate(
                    record,
                    "child lease expired while stalled",
                    notes,
                )
                recovered.append(record.task_id)
        return recovered

    def _recover_unlaunched(
        self, record: ChildExecutionRecord, notes: list[str]
    ) -> None:
        """A claimed/launch-pending row with no conversation is safe to re-drive."""
        if record.state == ChildExecutionState.LAUNCH_PENDING:
            return
        try:
            self._executions.transition(
                record.execution_id,
                ChildExecutionState.LAUNCH_PENDING,
                notes="recovery: no conversation recorded; safe to launch",
            )
            self._record(
                EventType.CHILD_RECOVERY,
                EventSeverity.NOTICE,
                f"Recovered unlaunched child for {record.task_id}",
                task_id=record.task_id,
                conversation_id=None,
                metadata={"attempt": record.attempt},
                idempotency_key=f"child.recovery:{record.execution_id}",
            )
            notes.append(f"recovered unlaunched child for {record.task_id}")
        except ChildTransitionConflict:
            pass

    # -- launching ---------------------------------------------------------

    def _launch_ready(self, notes: list[str]) -> tuple[list[str], list[str]]:
        """Launch children for ready tasks up to the concurrency limit.

        "Ready" means the task is claimed and an isolated worktree is registered,
        but no active child execution exists. This covers a fresh claim and a
        task whose launch never completed before a restart. The limit is enforced
        against the database count, so two concurrent ticks cannot oversubscribe.
        """
        launched: list[str] = []
        rejected: list[str] = []
        if self._worktrees is None:
            return launched, rejected
        for task_row in self._tasks.list_tasks():
            if task_row.status != RuntimeTaskStatus.IN_PROGRESS.value:
                continue
            task_id = task_row.task_id
            existing = self._executions.get_active_for_task(task_id)
            if existing is not None:
                if existing.state in (
                    ChildExecutionState.CLAIMED,
                    ChildExecutionState.LAUNCH_PENDING,
                ):
                    # Never launched yet; safe to (re)drive.
                    if self._try_launch(task_id, task_row.title, existing, notes):
                        launched.append(task_id)
                    continue
                continue
            worktree = self._worktree_registry.get(task_id)
            if worktree is None or worktree.state != WorktreeState.PREPARING:
                continue
            if not self._has_slot():
                rejected.append(task_id)
                self._record(
                    EventType.CHILD_REQUESTED,
                    EventSeverity.WARNING,
                    f"Child launch rejected for {task_id}: concurrency limit",
                    summary=(
                        f"active={self._executions.count_active()} "
                        f"max={self._config.max_concurrent_children}"
                    ),
                    task_id=task_id,
                    metadata={
                        "active": self._executions.count_active(),
                        "max": self._config.max_concurrent_children,
                    },
                    idempotency_key=None,
                )
                notes.append(f"child launch rejected for {task_id}: at limit")
                continue
            registered = self._register(task_id, worktree)
            if registered is None:
                continue
            # The registration already reserved the slot for this task, so the
            # launch must not re-check the limit or it would see itself.
            if self._try_launch(
                task_id, task_row.title, registered, notes, slot_reserved=True
            ):
                launched.append(task_id)
        return launched, rejected

    def _has_slot(self) -> bool:
        return self._executions.count_active() < self._config.max_concurrent_children

    def _register(self, task_id: str, worktree: Any) -> ChildExecutionRecord | None:
        try:
            record = self._executions.register(
                task_id,
                run_id=self._run_id,
                owner_agent=self._owner_agent,
                lease_seconds=self._child_lease_seconds(),
                worktree_path=worktree.worktree_path,
                branch_name=worktree.branch_name,
                agent_server_url=(
                    self._observer.base_url if self._observer is not None else None
                ),
            )
        except ChildExecutionConflict:
            return self._executions.get_active_for_task(task_id)
        self._record(
            EventType.CHILD_CLAIMED,
            EventSeverity.NOTICE,
            f"Child claimed for {task_id}",
            summary=f"attempt={record.attempt}",
            task_id=task_id,
            metadata={
                "attempt": record.attempt,
                "worktree_path": record.worktree_path,
                "branch_name": record.branch_name,
            },
            idempotency_key=f"child.claimed:{record.execution_id}",
        )
        return record

    def _try_launch(
        self,
        task_id: str,
        title: str,
        record: ChildExecutionRecord,
        notes: list[str],
        *,
        slot_reserved: bool = False,
    ) -> bool:
        if self._worktrees is None:
            return False
        if not slot_reserved and not self._has_slot():
            return False
        settings = self._settings_loader() if self._settings_loader else None
        if not settings:
            self._fail_launch(
                record,
                "no child agent settings configured; cannot launch",
                notes,
                intervention=True,
            )
            return False
        # Move to launch_pending before the network call so a crash mid-launch
        # leaves a durable "was launching" marker, not an ambiguous claimed row.
        try:
            if record.state != ChildExecutionState.LAUNCH_PENDING:
                record = self._executions.transition(
                    record.execution_id, ChildExecutionState.LAUNCH_PENDING
                )
        except ChildTransitionConflict:
            return False
        self._record(
            EventType.CHILD_LAUNCH_REQUESTED,
            EventSeverity.NOTICE,
            f"Child launch requested for {task_id}",
            task_id=task_id,
            metadata={"attempt": record.attempt},
            idempotency_key=f"child.launch_requested:{record.execution_id}",
        )
        try:
            result = self._launch_bounded(task_id, title=title, agent_settings=settings)
        except FuturesTimeout:
            # The launch did not return in time. We cannot know whether a
            # conversation was created, so we do not retry blindly: the row is
            # failed *with operator intervention* and no slot is reclaimed.
            self._fail_launch(
                record,
                f"launch exceeded {self._config.launch_timeout_seconds:g}s timeout",
                notes,
                intervention=True,
            )
            return False
        except Exception as exc:  # noqa: BLE001 - launch failures are recoverable
            self._fail_launch(record, f"launch failed: {exc}", notes)
            return False
        if not result.launched or not result.conversation_id:
            self._fail_launch(
                record,
                "launch returned no conversation id",
                notes,
                intervention=True,
            )
            return False
        self._executions.transition(
            record.execution_id,
            ChildExecutionState.RUNNING,
            conversation_id=result.conversation_id,
            notes=f"worktree={result.worktree_path}",
        )
        self._record(
            EventType.CHILD_LAUNCH_SUCCEEDED,
            EventSeverity.NOTICE,
            f"Child launched for {task_id}",
            summary=f"conversation={result.conversation_id}",
            task_id=task_id,
            conversation_id=result.conversation_id,
            metadata={
                "conversation_id": result.conversation_id,
                "worktree_path": str(result.worktree_path),
                "branch_name": result.branch_name,
            },
            idempotency_key=f"child.launch_succeeded:{record.execution_id}",
        )
        notes.append(f"launched child for {task_id}")
        return True

    def _launch_bounded(
        self, task_id: str, *, title: str, agent_settings: dict
    ) -> TaskLaunchResult:
        """Run the launch in a worker thread bounded by the launch timeout.

        The worktree orchestrator's launch is synchronous and may block on the
        agent-server. Running it in a worker lets the coordinator keep a bounded
        tick cadence and classify an over-time launch deterministically instead
        of hanging.

        The executor is deliberately *not* used as a context manager: exiting the
        ``with`` block would join the still-running worker and re-block the tick.
        On timeout the worker is abandoned (it cannot be interrupted) and its
        result discarded; the execution row is failed with operator intervention
        by the caller so a possibly-orphaned conversation is never retried blind.
        """
        pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="child-launch")
        try:
            future = pool.submit(
                self._worktrees.launch,
                task_id,
                title=title,
                agent_settings=agent_settings,
            )
            return future.result(timeout=self._config.launch_timeout_seconds)
        finally:
            pool.shutdown(wait=False, cancel_futures=True)

    def _fail_launch(
        self,
        record: ChildExecutionRecord,
        reason: str,
        notes: list[str],
        *,
        intervention: bool = False,
    ) -> None:
        try:
            self._executions.transition(
                record.execution_id,
                ChildExecutionState.FAILED,
                failure_reason=reason,
                operator_intervention=intervention,
                bump_retry=True,
            )
        except ChildTransitionConflict:
            return
        self._record(
            EventType.CHILD_LAUNCH_FAILED,
            EventSeverity.WARNING,
            f"Child launch failed for {record.task_id}",
            summary=reason,
            task_id=record.task_id,
            metadata={
                "reason": reason,
                "retry_count": record.retry_count + 1,
                "intervention": intervention,
            },
            idempotency_key=f"child.launch_failed:{record.execution_id}",
        )
        notes.append(f"child launch failed for {record.task_id}: {reason}")

    # -- status ------------------------------------------------------------

    def status(self) -> ChildOrchestrationStatus:
        enabled, reason = self.is_enabled()
        active = self._executions.count_active()
        children = tuple(self._view(record) for record in self._executions.list_all())
        reachable = False
        if self._observer is not None:
            try:
                reachable = self._observer.ping()
            except Exception:  # noqa: BLE001 - status must not raise
                reachable = False
        return ChildOrchestrationStatus(
            enabled=enabled,
            enabled_reason=reason,
            max_concurrent=self._config.max_concurrent_children,
            active_children=active,
            available_slots=max(0, self._config.max_concurrent_children - active),
            agent_server_reachable=reachable,
            children=children,
            counts_by_state=self._executions.count_by_state(),
        )

    def _view(self, record: ChildExecutionRecord) -> ChildStatusView:
        reference = record.last_progress_at or record.last_heartbeat_at
        stalled = False
        if record.state == ChildExecutionState.STALLED:
            stalled = True
        elif record.state in _ACTIVE and reference is not None:
            stalled = (
                _utc_now() - reference
            ).total_seconds() >= self._config.stall_seconds
        return ChildStatusView(
            execution_id=str(record.execution_id),
            task_id=record.task_id,
            state=record.state.value,
            attempt=record.attempt,
            conversation_id=record.conversation_id,
            worktree_path=record.worktree_path,
            branch_name=record.branch_name,
            pr_number=record.pr_number,
            active=record.state in _ACTIVE,
            last_heartbeat_at=_iso(record.last_heartbeat_at),
            last_progress_at=_iso(record.last_progress_at),
            progress_seq=record.progress_seq,
            last_event_count=record.last_event_count,
            lease_expires_at=_iso(record.lease_expires_at),
            retry_count=record.retry_count,
            stalled=stalled,
            operator_intervention=record.operator_intervention,
            failure_reason=record.failure_reason,
        )

    # -- helpers -----------------------------------------------------------

    def _child_lease_seconds(self) -> int:
        # The lease is the crash-recovery horizon, not the stall threshold: keep
        # it comfortably longer than the stall window so a stalled-but-live child
        # is classified (and escalated) before its lease is treated as abandoned.
        # Floor at 60s so a pathologically small threshold cannot produce a
        # zero-length lease that expires the instant it is written.
        return max(
            60,
            int(max(self._config.stall_seconds * 2, self._config.heartbeat_seconds)),
        )

    def _record(
        self,
        event_type: EventType,
        severity: EventSeverity,
        title: str,
        *,
        summary: str | None = None,
        task_id: str | None = None,
        conversation_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        idempotency_key: str | None,
    ) -> None:
        payload = dict(metadata or {})
        if conversation_id is not None:
            payload["conversation_id"] = conversation_id
        if self._run_id is not None:
            payload["run_id"] = str(self._run_id)
        self._recorder.record(
            ActivityEventCreate(
                run_id=self._run_id,
                task_id=task_id,
                agent_name=self._owner_agent,
                event_type=event_type,
                severity=severity,
                title=title,
                summary=summary,
                metadata=payload,
                idempotency_key=idempotency_key,
            )
        )


_ACTIVE = frozenset(
    {
        ChildExecutionState.CLAIMED,
        ChildExecutionState.LAUNCH_PENDING,
        ChildExecutionState.RUNNING,
        ChildExecutionState.STALLED,
    }
)


def agent_settings_loader_from_env() -> ChildAgentSettingsLoader | None:
    """Build a loader that reads the child ``agent_settings`` JSON file.

    ``DEVELOPMENT_OPS_CHILD_AGENT_SETTINGS`` names a file outside the checkout
    (mode 600) holding the encrypted-secret payload the agent server expects.
    The file contents are never logged; only its path is ever surfaced.
    """
    raw = os.environ.get("DEVELOPMENT_OPS_CHILD_AGENT_SETTINGS", "").strip()
    if not raw:
        return None
    path = Path(raw).expanduser()

    def _load() -> dict[str, Any] | None:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        return data if isinstance(data, dict) else None

    return _load


def observer_from_env(
    *,
    base_url: str | None = None,
    timeout: float = 15.0,
) -> AgentServerObserver:
    """Build an agent-server observer from environment configuration."""
    resolved = (
        base_url
        or os.environ.get("DEVELOPMENT_OPS_AGENT_SERVER_URL")
        or "http://localhost:18000"
    )
    return AgentServerObserver(
        base_url=resolved,
        api_key=os.environ.get("OPENHANDS_SESSION_API_KEY"),
        timeout=timeout,
    )

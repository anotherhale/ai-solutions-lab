"""Compose the persistent runner from the existing coordinator components.

This is the application/infrastructure seam: it builds a per-tick coordinator
engine on a fresh database session, adapts the activity recorder to the
runner's telemetry protocol, and supplies startup recovery and heartbeat
callables. Scheduling policy stays in the coordinator engine; process lifecycle
stays in :mod:`development_ops.runner`.
"""

from __future__ import annotations

import os
import uuid
from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from development_ops.backlog import default_backlog_path
from development_ops.catalog import YamlBacklogCatalogWriter
from development_ops.child_config import ChildOrchestrationConfig
from development_ops.child_orchestration import (
    ChildOrchestrator,
    agent_settings_loader_from_env,
    observer_from_env,
)
from development_ops.coordinator_engine import CoordinatorEngine
from development_ops.github_client import github_client_from_env
from development_ops.models import ActivityEventCreate
from development_ops.persistence.coordinator_repository import CoordinatorTaskRepository
from development_ops.recorder import ActivityRecorder
from development_ops.runner import CoordinatorRunner, RecoveryReport, TickOutcome
from development_ops.runner_config import RunnerConfig
from development_ops.runner_state import RunnerStateStore
from development_ops.task_worktrees import (
    TaskWorktreeOrchestrator,
    worktree_manager_from_env,
)
from development_ops.taxonomy import EventSeverity, EventType


class RecorderTelemetry:
    """Adapt :class:`ActivityRecorder` to the runner telemetry protocol.

    A fresh session is opened per event so a long-lived runner never holds a
    stale connection between polls.
    """

    def __init__(self, factory: sessionmaker[Session]) -> None:
        self._factory = factory
        self._agent_name = os.environ.get("DEVELOPMENT_OPS_AGENT_NAME", "coordinator")

    def record(
        self,
        *,
        event_type: EventType,
        severity: EventSeverity,
        title: str,
        summary: str | None = None,
        metadata: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> None:
        session = self._factory()
        try:
            recorder = ActivityRecorder(session, notify_slack=False)
            recorder.record(
                ActivityEventCreate(
                    run_id=_run_id_from_env(),
                    agent_name=self._agent_name,
                    event_type=event_type,
                    severity=severity,
                    title=title,
                    summary=summary,
                    metadata=metadata or {},
                    idempotency_key=idempotency_key,
                )
            )
        finally:
            session.close()


def _session_factory() -> sessionmaker[Session]:
    from development_ops.cli import _session_factory as cli_session_factory

    return cli_session_factory()


def _build_engine(
    session: Session,
    *,
    run_id: uuid.UUID,
    config: RunnerConfig,
) -> CoordinatorEngine:
    repository = config.repository
    worktrees = TaskWorktreeOrchestrator(
        session,
        worktree_manager_from_env(),
        repository=repository,
        launcher=None,
        github=github_client_from_env(),
        run_id=run_id,
    )
    children = _build_child_orchestrator(
        session, run_id=run_id, repository=repository, worktrees=worktrees
    )
    return CoordinatorEngine(
        session,
        github=github_client_from_env(),
        recorder=ActivityRecorder(session, notify_slack=False),
        run_id=run_id,
        repository=repository,
        backlog_path=config.backlog_path,
        worktrees=worktrees,
        catalog=(
            YamlBacklogCatalogWriter(config.backlog_path or default_backlog_path())
            if config.update_catalog
            else None
        ),
        children=children,
    )


def _build_child_orchestrator(
    session: Session,
    *,
    run_id: uuid.UUID,
    repository: str,
    worktrees: TaskWorktreeOrchestrator,
) -> ChildOrchestrator:
    """Build the Phase D child orchestrator.

    Execution remains disabled unless the durable operator flag is set; the
    environment can express intent but never enables paid child execution on its
    own (see :func:`development_ops.child_config.resolve_enabled`).
    """
    child_config = ChildOrchestrationConfig.from_env()
    return ChildOrchestrator(
        session,
        config=child_config,
        worktrees=worktrees,
        recorder=ActivityRecorder(session, notify_slack=False),
        run_id=run_id,
        repository=repository,
        observer=observer_from_env(),
        settings_loader=agent_settings_loader_from_env(),
        owner_agent=os.environ.get("DEVELOPMENT_OPS_AGENT_NAME", "coordinator"),
    )


def build_runner_from_env(
    config: RunnerConfig | None = None,
) -> tuple[CoordinatorRunner, sessionmaker[Session]]:
    """Build a runner bound to the operational development_ops database.

    Returns the runner and the session factory so the caller can run the status
    side or a single tick without rebuilding configuration.
    """
    resolved = config or RunnerConfig.from_env()
    factory = _session_factory()

    def _tick(*, max_concurrent: int | None = None) -> TickOutcome:
        session = factory()
        run_id = _run_id_from_env()
        try:
            engine = _build_engine(session, run_id=run_id, config=resolved)
            result = engine.tick(
                max_concurrent=max_concurrent,
                reclaim_expired=resolved.reclaim_expired_leases,
            )
            return TickOutcome(
                selected_task_id=result.selected_task_id,
                active_tasks=result.active_tasks,
                notes=tuple(result.notes),
                recovered=tuple(result.recovered_worktrees),
                cleaned=tuple(result.cleaned_worktrees),
            )
        finally:
            session.close()

    def _startup_recovery() -> RecoveryReport:
        session = factory()
        try:
            tasks = CoordinatorTaskRepository(session)
            reclaimed = tasks.reclaim_expired_leases()
            notes: list[str] = []
            if reclaimed:
                notes.append("reclaimed expired leases: " + ", ".join(reclaimed))
            recovered: list[str] = []
            try:
                worktrees = TaskWorktreeOrchestrator(
                    session,
                    worktree_manager_from_env(),
                    repository=resolved.repository,
                    launcher=None,
                    github=github_client_from_env(),
                    run_id=_run_id_from_env(),
                )
                recovered = worktrees.recover_interrupted()
            except Exception as exc:  # noqa: BLE001 - worktree recovery is optional
                notes.append(f"worktree recovery skipped: {exc}")
            if recovered:
                notes.append("recoverable worktrees: " + ", ".join(recovered))
            return RecoveryReport(
                reclaimed_tasks=tuple(reclaimed),
                recovered_worktrees=tuple(recovered),
                notes=tuple(notes),
            )
        finally:
            session.close()

    def _heartbeat() -> list[str]:
        session = factory()
        try:
            tasks = CoordinatorTaskRepository(session)
            return tasks.renew_leases(run_id=_run_id_from_env())
        finally:
            session.close()

    runner = CoordinatorRunner(
        resolved,
        tick=_tick,
        telemetry=RecorderTelemetry(factory),
        state_store=RunnerStateStore(resolved.state_dir / "runner-state.json"),
        startup_recovery=_startup_recovery,
        heartbeat=_heartbeat,
    )
    return runner, factory


def _run_id_from_env() -> uuid.UUID:
    """A stable run id for this runner process.

    The runner sets ``DEVELOPMENT_OPS_RUN_ID`` once at startup so every tick,
    heartbeat, and recovery event shares one run id, matching the operating
    model's requirement to reuse a single id for a run.
    """
    raw = os.environ.get("DEVELOPMENT_OPS_RUN_ID", "").strip()
    if raw:
        try:
            return uuid.UUID(raw)
        except ValueError:
            pass
    generated = uuid.uuid4()
    os.environ["DEVELOPMENT_OPS_RUN_ID"] = str(generated)
    return generated


def ensure_database() -> None:
    from development_ops.database import ensure_development_ops_database

    ensure_development_ops_database()


__all__ = [
    "RecorderTelemetry",
    "build_runner_from_env",
    "ensure_database",
]

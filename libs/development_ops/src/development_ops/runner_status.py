"""Read-only operational status for the persistent coordinator runner.

Everything here is observation: it opens a connection, reads rows, and closes.
It never claims a task, renews a lease, or mutates the lock or state file.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from development_ops.instance_lock import CoordinatorInstanceLock
from development_ops.persistence.coordinator_repository import CoordinatorTaskRepository
from development_ops.runner_config import RunnerConfig
from development_ops.runner_state import RunnerStateStore


@dataclass(frozen=True, slots=True)
class TaskLeaseView:
    task_id: str
    status: str
    active_run_id: str | None
    owner_agent: str | None
    lease_expires_at: str | None
    heartbeat_at: str | None
    pr_number: int | None


@dataclass(frozen=True, slots=True)
class RunnerStatus:
    """A point-in-time, read-only snapshot of runner and coordinator health."""

    database_ok: bool
    database_error: str | None
    paused: bool
    runner_active: bool
    owner_pid: int | None
    owner_hostname: str | None
    owner_run_id: str | None
    lock_path: str
    lock_stale: bool
    last_tick_started_at: str | None
    last_tick_completed_at: str | None
    last_tick_error: str | None
    last_tick_run_id: str | None
    last_recovery_at: str | None
    recovery_events: int
    active_leases: list[TaskLeaseView] = field(default_factory=list)
    awaiting_pull_request: list[TaskLeaseView] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        return payload


def _iso(value: Any) -> str | None:
    return value.isoformat() if value is not None else None


def _task_view(row: Any) -> TaskLeaseView:
    return TaskLeaseView(
        task_id=row.task_id,
        status=row.status,
        active_run_id=str(row.active_run_id) if row.active_run_id else None,
        owner_agent=row.owner_agent,
        lease_expires_at=_iso(row.lease_expires_at),
        heartbeat_at=_iso(row.heartbeat_at),
        pr_number=row.pr_number,
    )


def _check_database(factory: sessionmaker[Session]) -> tuple[bool, str | None]:
    session = factory()
    try:
        session.execute(text("SELECT 1"))
        return True, None
    except SQLAlchemyError as exc:
        return False, str(exc)
    finally:
        session.close()


def collect_status(
    config: RunnerConfig,
    *,
    session_factory: sessionmaker[Session],
) -> RunnerStatus:
    """Build a read-only status snapshot.

    A database outage is reported, not raised: the operator still needs to see
    lock ownership and pause state when the database is unreachable.
    """
    state_store = RunnerStateStore(config.state_dir / "runner-state.json")
    state = state_store.load()
    lock = CoordinatorInstanceLock(config.resolved_lock_path)
    owner = lock.read_owner()
    lock_stale = lock.is_stale()
    # A lock is "active" only when the recorded owner process is alive. We do not
    # attempt to acquire it, which would mutate state.
    runner_active = owner is not None and not lock_stale

    database_ok, database_error = _check_database(session_factory)
    active_leases: list[TaskLeaseView] = []
    awaiting: list[TaskLeaseView] = []
    if database_ok:
        session = session_factory()
        try:
            repo = CoordinatorTaskRepository(session)
            active_leases = [_task_view(row) for row in repo.list_active_leases()]
            awaiting = [_task_view(row) for row in repo.list_awaiting_pull_request()]
        except SQLAlchemyError as exc:
            database_ok = False
            database_error = str(exc)
        finally:
            session.close()

    return RunnerStatus(
        database_ok=database_ok,
        database_error=database_error,
        paused=state.paused,
        runner_active=runner_active,
        owner_pid=owner.pid if owner else None,
        owner_hostname=owner.hostname if owner else None,
        owner_run_id=owner.run_id if owner else None,
        lock_path=str(config.resolved_lock_path),
        lock_stale=lock_stale,
        last_tick_started_at=state.last_tick_started_at,
        last_tick_completed_at=state.last_tick_completed_at,
        last_tick_error=state.last_tick_error,
        last_tick_run_id=state.last_tick_run_id,
        last_recovery_at=state.last_recovery_at,
        recovery_events=state.recovery_events,
        active_leases=active_leases,
        awaiting_pull_request=awaiting,
    )

"""Persistent, restart-safe coordinator runner.

The runner repeatedly executes the existing coordinator tick through an injected
callable, so scheduling policy stays in :mod:`development_ops.coordinator_engine`
and this module owns only process lifecycle: polling, signals, single-instance
ownership, heartbeats, startup recovery, and pause/resume.

It runs one tick at a time on a single thread, so ticks can never overlap. A
transient tick failure is logged and recorded, then the loop continues; only
configuration errors and loss of the instance lock stop it.
"""

from __future__ import annotations

import inspect
import logging
import signal
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from types import FrameType
from typing import Any, Protocol

from development_ops.instance_lock import CoordinatorInstanceLock
from development_ops.runner_config import RunnerConfig
from development_ops.runner_state import RunnerState, RunnerStateStore
from development_ops.taxonomy import EventSeverity, EventType

LOGGER_NAME = "development_ops.coordinator.runner"


class RunnerTelemetry(Protocol):
    """Structured sink for runner lifecycle milestones."""

    def record(
        self,
        *,
        event_type: EventType,
        severity: EventSeverity,
        title: str,
        summary: str | None = None,
        metadata: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> None: ...


@dataclass(frozen=True, slots=True)
class TickOutcome:
    """Normalized result of one tick, independent of the engine's type."""

    selected_task_id: str | None = None
    active_tasks: int = 0
    notes: tuple[str, ...] = ()
    recovered: tuple[str, ...] = ()
    cleaned: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RecoveryReport:
    """Summary of startup recovery work."""

    reclaimed_tasks: tuple[str, ...] = ()
    recovered_worktrees: tuple[str, ...] = ()
    notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def total(self) -> int:
        return len(self.reclaimed_tasks) + len(self.recovered_worktrees)


def _accepts_max_concurrent(tick: Callable[..., Any]) -> bool:
    """True when ``tick`` accepts a ``max_concurrent`` keyword argument."""
    try:
        signature = inspect.signature(tick)
    except (TypeError, ValueError):  # builtins and some callables
        return False
    parameters = signature.parameters
    if "max_concurrent" in parameters:
        return True
    return any(
        param.kind is inspect.Parameter.VAR_KEYWORD for param in parameters.values()
    )


def _coerce_tick_outcome(raw: Any) -> TickOutcome:
    """Adapt a CoordinatorTickResult (or a test double) to a TickOutcome."""
    if isinstance(raw, TickOutcome):
        return raw
    return TickOutcome(
        selected_task_id=getattr(raw, "selected_task_id", None),
        active_tasks=int(getattr(raw, "active_tasks", 0) or 0),
        notes=tuple(getattr(raw, "notes", ()) or ()),
        recovered=tuple(getattr(raw, "recovered_worktrees", ()) or ()),
        cleaned=tuple(getattr(raw, "cleaned_worktrees", ()) or ()),
    )


class CoordinatorRunner:
    """Own the coordinator loop on one workstation."""

    def __init__(
        self,
        config: RunnerConfig,
        *,
        tick: Callable[..., Any],
        telemetry: RunnerTelemetry,
        state_store: RunnerStateStore | None = None,
        lock: CoordinatorInstanceLock | None = None,
        startup_recovery: Callable[[], RecoveryReport] | None = None,
        heartbeat: Callable[[], list[str]] | None = None,
        paused: Callable[[], bool] | None = None,
        logger: logging.Logger | None = None,
        sleep: Callable[[float], bool] | None = None,
    ) -> None:
        self._config = config
        self._tick = tick
        self._telemetry = telemetry
        self._state_store = state_store or RunnerStateStore(
            config.state_dir / "runner-state.json"
        )
        self._lock = lock or CoordinatorInstanceLock(
            config.resolved_lock_path, run_id=None
        )
        self._startup_recovery = startup_recovery
        self._heartbeat = heartbeat
        self._paused = paused or self._paused_from_state
        self._log = logger or logging.getLogger(LOGGER_NAME)
        # sleep returns True when a shutdown was requested while sleeping.
        self._sleep = sleep or self._default_sleep
        self._run_id = uuid.uuid4()
        self._stop = threading.Event()
        self._in_tick = False
        self._signals_installed = False
        self._last_heartbeat = 0.0
        self._tick_count = 0
        self._tick_accepts_max_concurrent: bool | None = None

    def _paused_from_state(self) -> bool:
        return self._state_store.load().paused

    def _invoke_tick(self, *, max_concurrent: int | None) -> Any:
        """Call the injected tick.

        Test doubles may be zero-argument; inspect once rather than swallowing a
        ``TypeError`` that could mask a real failure inside the tick.
        """
        if self._tick_accepts_max_concurrent is None:
            self._tick_accepts_max_concurrent = _accepts_max_concurrent(self._tick)
        if self._tick_accepts_max_concurrent:
            return self._tick(max_concurrent=max_concurrent)
        return self._tick()

    # -- lifecycle ---------------------------------------------------------

    @property
    def run_id(self) -> uuid.UUID:
        return self._run_id

    @property
    def tick_count(self) -> int:
        return self._tick_count

    def install_signal_handlers(self) -> None:
        """Install SIGTERM/SIGINT handlers that request a graceful stop."""
        if self._signals_installed:
            return
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, self._handle_signal)
        self._signals_installed = True

    def _handle_signal(self, signum: int, _frame: FrameType | None) -> None:
        self._log.info(
            "received signal; requesting graceful shutdown",
            extra={"event": "runner.signal", "signal": signum},
        )
        self.request_shutdown()

    def request_shutdown(self) -> None:
        self._stop.set()

    @property
    def stop_requested(self) -> bool:
        return self._stop.is_set()

    def _default_sleep(self, seconds: float) -> bool:
        return self._stop.wait(timeout=seconds)

    def run(self, *, max_ticks: int | None = None) -> int:
        """Run the loop until shutdown or ``max_ticks`` ticks complete.

        Returns the number of ticks executed. Raises nothing for a transient
        tick failure; those are recorded and the loop continues.
        """
        owner = self._lock.acquire()
        self._log.info(
            "coordinator runner acquired instance lock",
            extra={
                "event": "runner.lock_acquired",
                "lock_path": str(self._lock.path),
                "pid": owner.pid,
                "hostname": owner.hostname,
            },
        )
        self._record(
            EventType.RUN_STARTED,
            EventSeverity.INFO,
            "Persistent coordinator runner started",
            metadata={
                "pid": owner.pid,
                "hostname": owner.hostname,
                "lock_path": str(self._lock.path),
                "poll_interval_seconds": self._config.poll_interval_seconds,
            },
        )
        try:
            if self._config.recover_on_startup:
                self._run_startup_recovery()
            while not self._stop.is_set():
                self._run_one_tick()
                if max_ticks is not None and self._tick_count >= max_ticks:
                    break
                if self._stop.is_set():
                    break
                if self._sleep(self._config.poll_interval_seconds):
                    break
        finally:
            self._record(
                EventType.RUN_COMPLETED,
                EventSeverity.INFO,
                "Persistent coordinator runner stopped",
                metadata={"ticks": self._tick_count},
            )
            self._lock.release()
            self._log.info(
                "coordinator runner released instance lock",
                extra={"event": "runner.lock_released", "ticks": self._tick_count},
            )
        return self._tick_count

    # -- recovery ----------------------------------------------------------

    def _run_startup_recovery(self) -> RecoveryReport:
        if self._startup_recovery is None:
            return RecoveryReport()
        try:
            report = self._startup_recovery()
        except Exception as exc:  # noqa: BLE001 - recovery must not kill startup
            self._log.warning(
                "startup recovery failed; continuing",
                extra={"event": "runner.recovery_failed", "error": str(exc)},
            )
            self._record(
                EventType.BLOCKER_REPORTED,
                EventSeverity.WARNING,
                "Startup recovery failed",
                summary=str(exc),
            )
            return RecoveryReport()
        self._state_store.record_recovery(count=report.total)
        self._record(
            EventType.COORDINATOR_RECOVERY,
            EventSeverity.NOTICE,
            "Startup recovery completed",
            summary="; ".join(report.notes) if report.notes else None,
            metadata={
                "reclaimed_tasks": list(report.reclaimed_tasks),
                "recovered_worktrees": list(report.recovered_worktrees),
            },
        )
        return report

    # -- tick loop ---------------------------------------------------------

    def _run_one_tick(self) -> None:
        if self._in_tick:  # defensive: the loop is single-threaded
            self._log.error(
                "refusing to start an overlapping tick",
                extra={"event": "runner.overlap_refused"},
            )
            return
        self._in_tick = True
        run_id = str(self._run_id)
        paused = self._paused()
        self._state_store.record_tick_started(run_id=run_id)
        try:
            # While paused, reconciliation (GitHub PR state, auto-merge, worktree
            # cleanup) still runs so PR tracking is preserved, but the concurrency
            # limit of zero prevents any new task claim.
            result = _coerce_tick_outcome(
                self._invoke_tick(max_concurrent=0 if paused else None)
            )
            self._tick_count += 1
            self._state_store.record_tick_completed(run_id=run_id)
            self._maybe_heartbeat()
            title = (
                "Coordinator runner tick completed (paused)"
                if paused
                else "Coordinator runner tick completed"
            )
            self._record(
                EventType.COORDINATOR_SCHEDULED,
                EventSeverity.INFO,
                title,
                summary="; ".join(result.notes) if result.notes else None,
                metadata={
                    "tick": self._tick_count,
                    "paused": paused,
                    "selected_task_id": result.selected_task_id,
                    "active_tasks": result.active_tasks,
                    "cleaned_worktrees": list(result.cleaned),
                },
                idempotency_key=f"runner.tick:{run_id}:{self._tick_count}",
            )
        except Exception as exc:  # noqa: BLE001 - transient failures must not stop
            self._state_store.record_tick_error(run_id=run_id, error=str(exc))
            self._log.warning(
                "coordinator tick failed; continuing",
                extra={"event": "runner.tick_failed", "error": str(exc)},
            )
            self._record(
                EventType.BLOCKER_REPORTED,
                EventSeverity.WARNING,
                "Coordinator runner tick failed",
                summary=str(exc),
                metadata={"tick": self._tick_count + 1},
            )
        finally:
            self._in_tick = False

    def _maybe_heartbeat(self) -> None:
        if self._heartbeat is None:
            return
        interval = self._config.heartbeat_interval_seconds
        now = time.monotonic()
        if self._last_heartbeat and (now - self._last_heartbeat) < interval:
            return
        self._last_heartbeat = now
        try:
            renewed = self._heartbeat()
        except Exception as exc:  # noqa: BLE001 - heartbeat is best effort
            self._log.warning(
                "heartbeat failed; continuing",
                extra={"event": "runner.heartbeat_failed", "error": str(exc)},
            )
            return
        if renewed:
            self._record(
                EventType.PROGRESS_REPORT,
                EventSeverity.DEBUG,
                "Renewed task leases",
                metadata={"tasks": list(renewed)},
                idempotency_key=None,
            )

    # -- telemetry ---------------------------------------------------------

    def _record(
        self,
        event_type: EventType,
        severity: EventSeverity,
        title: str,
        *,
        summary: str | None = None,
        metadata: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> None:
        try:
            self._telemetry.record(
                event_type=event_type,
                severity=severity,
                title=title,
                summary=summary,
                metadata=metadata,
                idempotency_key=idempotency_key,
            )
        except Exception as exc:  # noqa: BLE001 - telemetry must not stop the loop
            self._log.warning(
                "failed to record runner telemetry",
                extra={"event": "runner.telemetry_failed", "error": str(exc)},
            )

    def current_state(self) -> RunnerState:
        return self._state_store.load()

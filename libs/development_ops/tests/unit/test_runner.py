"""Unit tests for the persistent coordinator runner building blocks."""

from __future__ import annotations

import json
import logging
import threading
import time
from pathlib import Path

import pytest
from development_ops.instance_lock import (
    CoordinatorInstanceLock,
    InstanceLockedError,
)
from development_ops.runner import (
    CoordinatorRunner,
    RecoveryReport,
    TickOutcome,
)
from development_ops.runner_config import RunnerConfig, RunnerConfigError
from development_ops.runner_state import RunnerStateStore
from development_ops.taxonomy import EventType


def _config(tmp_path: Path, **overrides: object) -> RunnerConfig:
    values: dict[str, object] = {
        "repository": "example/test",
        "poll_interval_seconds": 0.01,
        "heartbeat_interval_seconds": 0.01,
        "lease_seconds": 900,
        "state_dir": tmp_path,
    }
    values.update(overrides)
    return RunnerConfig(**values)  # type: ignore[arg-type]


class RecordingTelemetry:
    def __init__(self) -> None:
        self.events: list[tuple[EventType, str, dict | None]] = []

    def record(
        self,
        *,
        event_type: EventType,
        severity: object,
        title: str,
        summary: str | None = None,
        metadata: dict | None = None,
        idempotency_key: str | None = None,
    ) -> None:
        self.events.append((event_type, title, metadata))

    def types(self) -> list[EventType]:
        return [event_type for event_type, _, _ in self.events]


# --- configuration -----------------------------------------------------------


def test_config_rejects_blank_repository(tmp_path: Path) -> None:
    with pytest.raises(RunnerConfigError):
        _config(tmp_path, repository="   ")


def test_config_rejects_nonpositive_poll(tmp_path: Path) -> None:
    with pytest.raises(RunnerConfigError):
        _config(tmp_path, poll_interval_seconds=0)


def test_config_rejects_heartbeat_longer_than_lease(tmp_path: Path) -> None:
    with pytest.raises(RunnerConfigError):
        _config(tmp_path, heartbeat_interval_seconds=1000, lease_seconds=900)


def test_config_rejects_unknown_log_level(tmp_path: Path) -> None:
    with pytest.raises(RunnerConfigError):
        _config(tmp_path, log_level="loud")


def test_config_from_env_defaults(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("DEVELOPMENT_OPS_RUNNER_POLL_SECONDS", raising=False)
    monkeypatch.setenv("DEVELOPMENT_OPS_RUNNER_STATE_DIR", str(tmp_path))
    config = RunnerConfig.from_env()
    assert config.poll_interval_seconds > 0
    assert config.heartbeat_interval_seconds <= config.lease_seconds
    assert config.resolved_lock_path == tmp_path / "coordinator.lock"


def test_config_from_env_rejects_bad_number(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("DEVELOPMENT_OPS_RUNNER_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("DEVELOPMENT_OPS_RUNNER_POLL_SECONDS", "soon")
    with pytest.raises(RunnerConfigError):
        RunnerConfig.from_env()


# --- instance lock -----------------------------------------------------------


def test_lock_excludes_second_holder(tmp_path: Path) -> None:
    path = tmp_path / "coordinator.lock"
    first = CoordinatorInstanceLock(path)
    second = CoordinatorInstanceLock(path)
    first.acquire()
    try:
        with pytest.raises(InstanceLockedError):
            second.acquire()
    finally:
        first.release()


def test_lock_released_and_reacquired(tmp_path: Path) -> None:
    path = tmp_path / "coordinator.lock"
    first = CoordinatorInstanceLock(path)
    first.acquire()
    first.release()
    second = CoordinatorInstanceLock(path)
    second.acquire()
    try:
        assert second.held
    finally:
        second.release()


def test_lock_records_owner_metadata(tmp_path: Path) -> None:
    path = tmp_path / "coordinator.lock"
    lock = CoordinatorInstanceLock(path, run_id="run-123")
    lock.acquire()
    try:
        owner = CoordinatorInstanceLock(path).read_owner()
        assert owner is not None
        assert owner.run_id == "run-123"
    finally:
        lock.release()


def test_lock_metadata_of_dead_pid_is_stale(tmp_path: Path) -> None:
    path = tmp_path / "coordinator.lock"
    path.write_text(
        json.dumps(
            {
                "pid": 999_999_999,
                "hostname": __import__("socket").gethostname(),
                "acquired_at": 0.0,
                "run_id": None,
            }
        ),
        encoding="utf-8",
    )
    lock = CoordinatorInstanceLock(path)
    assert lock.is_stale() is True
    # A stale record does not block a fresh acquisition.
    lock.acquire()
    try:
        assert lock.held
    finally:
        lock.release()


def test_lock_released_when_process_context_exits(tmp_path: Path) -> None:
    path = tmp_path / "coordinator.lock"
    with CoordinatorInstanceLock(path):
        assert CoordinatorInstanceLock(path).read_owner() is not None
    assert CoordinatorInstanceLock(path).held is False


# --- runner state ------------------------------------------------------------


def test_pause_is_durable_across_store_instances(tmp_path: Path) -> None:
    path = tmp_path / "runner-state.json"
    RunnerStateStore(path).pause(by="operator", reason="maintenance")
    reloaded = RunnerStateStore(path).load()
    assert reloaded.paused is True
    assert reloaded.paused_by == "operator"
    assert reloaded.pause_reason == "maintenance"


def test_resume_clears_pause(tmp_path: Path) -> None:
    path = tmp_path / "runner-state.json"
    store = RunnerStateStore(path)
    store.pause(by="operator")
    store.resume()
    assert RunnerStateStore(path).load().paused is False


def test_state_survives_corrupt_file(tmp_path: Path) -> None:
    path = tmp_path / "runner-state.json"
    path.write_text("{not json", encoding="utf-8")
    assert RunnerStateStore(path).load().paused is False


# --- runner loop -------------------------------------------------------------


def test_runner_executes_repeated_ticks(tmp_path: Path) -> None:
    calls: list[int] = []

    def tick(**_: object) -> TickOutcome:
        calls.append(1)
        return TickOutcome(selected_task_id="TASK-A")

    runner = CoordinatorRunner(
        _config(tmp_path),
        tick=tick,
        telemetry=RecordingTelemetry(),
        sleep=lambda _seconds: False,
    )
    ticks = runner.run(max_ticks=3)
    assert ticks == 3
    assert len(calls) == 3


def test_runner_does_not_overlap_ticks(tmp_path: Path) -> None:
    state = {"active": 0, "max": 0, "count": 0}

    def tick(**_: object) -> TickOutcome:
        state["active"] += 1
        state["max"] = max(state["max"], state["active"])
        state["count"] += 1
        time.sleep(0.01)
        state["active"] -= 1
        return TickOutcome()

    runner = CoordinatorRunner(
        _config(tmp_path),
        tick=tick,
        telemetry=RecordingTelemetry(),
        sleep=lambda _seconds: False,
    )
    runner.run(max_ticks=4)
    assert state["max"] == 1
    assert state["count"] == 4


def test_runner_graceful_shutdown_on_stop_request(tmp_path: Path) -> None:
    telemetry = RecordingTelemetry()
    runner = CoordinatorRunner(
        _config(tmp_path),
        tick=lambda **_: TickOutcome(),
        telemetry=telemetry,
        sleep=lambda _seconds: False,
    )

    def request_after_first() -> None:
        time.sleep(0.02)
        runner.request_shutdown()

    thread = threading.Thread(target=request_after_first)
    thread.start()
    runner.run()
    thread.join()
    assert runner.tick_count >= 1
    assert EventType.RUN_STARTED in telemetry.types()
    assert EventType.RUN_COMPLETED in telemetry.types()


def test_runner_signal_handler_requests_shutdown(tmp_path: Path) -> None:
    runner = CoordinatorRunner(
        _config(tmp_path),
        tick=lambda **_: TickOutcome(),
        telemetry=RecordingTelemetry(),
        sleep=lambda _seconds: False,
    )
    runner.install_signal_handlers()
    runner._handle_signal(15, None)  # type: ignore[arg-type]
    assert runner.stop_requested is True


def test_runner_transient_failure_does_not_stop(tmp_path: Path) -> None:
    attempts = {"n": 0}

    def tick(**_: object) -> TickOutcome:
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise RuntimeError("database hiccup")
        return TickOutcome()

    telemetry = RecordingTelemetry()
    runner = CoordinatorRunner(
        _config(tmp_path),
        tick=tick,
        telemetry=telemetry,
        sleep=lambda _seconds: False,
    )
    ticks = runner.run(max_ticks=1)
    # The first attempt failed (not counted), the second succeeded and ended
    # the loop at the requested tick count.
    assert ticks == 1
    assert attempts["n"] == 2
    assert EventType.BLOCKER_REPORTED in telemetry.types()
    state = RunnerStateStore(tmp_path / "runner-state.json").load()
    assert state.last_tick_error is None or "hiccup" in (state.last_tick_error or "")


def test_runner_records_startup_recovery_telemetry(tmp_path: Path) -> None:
    telemetry = RecordingTelemetry()
    runner = CoordinatorRunner(
        _config(tmp_path),
        tick=lambda **_: TickOutcome(),
        telemetry=telemetry,
        startup_recovery=lambda: RecoveryReport(
            reclaimed_tasks=("TASK-X",), notes=("reclaimed expired leases: TASK-X",)
        ),
        sleep=lambda _seconds: False,
    )
    runner.run(max_ticks=1)
    assert EventType.COORDINATOR_RECOVERY in telemetry.types()
    state = RunnerStateStore(tmp_path / "runner-state.json").load()
    assert state.recovery_events == 1


def test_runner_startup_recovery_failure_is_non_fatal(tmp_path: Path) -> None:
    def boom() -> RecoveryReport:
        raise RuntimeError("github down")

    telemetry = RecordingTelemetry()
    runner = CoordinatorRunner(
        _config(tmp_path),
        tick=lambda **_: TickOutcome(),
        telemetry=telemetry,
        startup_recovery=boom,
        sleep=lambda _seconds: False,
    )
    ticks = runner.run(max_ticks=1)
    assert ticks == 1
    assert EventType.BLOCKER_REPORTED in telemetry.types()


def test_runner_paused_skips_claims_but_still_reconciles(tmp_path: Path) -> None:
    store = RunnerStateStore(tmp_path / "runner-state.json")
    store.pause(by="operator")
    observed: list[int | None] = []

    def tick(**kwargs: object) -> TickOutcome:
        observed.append(kwargs.get("max_concurrent"))  # type: ignore[arg-type]
        return TickOutcome()

    runner = CoordinatorRunner(
        _config(tmp_path),
        tick=tick,
        telemetry=RecordingTelemetry(),
        state_store=store,
        sleep=lambda _seconds: False,
    )
    runner.run(max_ticks=1)
    # A paused tick passes a zero concurrency limit, so no task is claimed.
    assert observed == [0]


def test_runner_pause_cleared_by_resume(tmp_path: Path) -> None:
    store = RunnerStateStore(tmp_path / "runner-state.json")
    store.pause(by="operator")
    observed: list[int | None] = []

    def tick(**kwargs: object) -> TickOutcome:
        observed.append(kwargs.get("max_concurrent"))  # type: ignore[arg-type]
        return TickOutcome()

    store.resume()
    runner = CoordinatorRunner(
        _config(tmp_path),
        tick=tick,
        telemetry=RecordingTelemetry(),
        state_store=store,
        sleep=lambda _seconds: False,
    )
    runner.run(max_ticks=1)
    assert observed == [None]


def test_runner_telemetry_failure_is_non_fatal(tmp_path: Path) -> None:
    class BrokenTelemetry:
        def record(self, **_: object) -> None:
            raise RuntimeError("telemetry sink down")

    runner = CoordinatorRunner(
        _config(tmp_path),
        tick=lambda **_: TickOutcome(),
        telemetry=BrokenTelemetry(),
        sleep=lambda _seconds: False,
    )
    assert runner.run(max_ticks=1) == 1


def test_runner_heartbeat_invoked(tmp_path: Path) -> None:
    beats: list[int] = []
    runner = CoordinatorRunner(
        _config(tmp_path, heartbeat_interval_seconds=0.001),
        tick=lambda **_: TickOutcome(),
        telemetry=RecordingTelemetry(),
        heartbeat=lambda: beats.append(1) or ["TASK-A"],
        sleep=lambda _seconds: False,
    )
    runner.run(max_ticks=2)
    assert beats


def test_runner_logs_structured_json(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    from development_ops.runner_logging import configure_logging

    logger = configure_logging(level="INFO", fmt="json")
    runner = CoordinatorRunner(
        _config(tmp_path),
        tick=lambda **_: TickOutcome(),
        telemetry=RecordingTelemetry(),
        logger=logger,
        sleep=lambda _seconds: False,
    )
    runner.run(max_ticks=1)
    captured = capsys.readouterr()
    lines = [line for line in captured.err.splitlines() if line.strip()]
    parsed = [json.loads(line) for line in lines]
    assert any(entry.get("event") == "runner.lock_acquired" for entry in parsed)
    assert all("ts" in entry and "level" in entry for entry in parsed)


def test_runner_logger_name_is_stable() -> None:
    assert logging.getLogger("development_ops.coordinator.runner").name.endswith(
        "runner"
    )

"""CLI tests for `development-ops runner` against a disposable database.

The runner commands exercise the real application services. These tests verify
the command wiring, the JSON contract, single-instance exclusion, and that the
run lifecycle is recorded in ``development_ops.activity_events``.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import time
import uuid
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine

from wasatch_api.testing.postgres import assert_engine_is_disposable

REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "..")
)
API_ROOT = Path(REPO_ROOT) / "services" / "wasatch-api"


@pytest.fixture(autouse=True)
def _clean_disposable_ops_tables(ops_test_engine: Engine) -> None:
    assert_engine_is_disposable(ops_test_engine)
    with ops_test_engine.begin() as connection:
        connection.execute(text("DELETE FROM development_ops.activity_events"))
        connection.execute(text("DELETE FROM development_ops.coordinator_tasks"))
        connection.execute(text("DELETE FROM development_ops.agent_worktrees"))


def _run_cli(
    engine: Engine,
    *args: str,
    env: dict[str, str] | None = None,
    timeout: float = 60.0,
) -> subprocess.CompletedProcess[str]:
    from alembic import command
    from alembic.config import Config

    run_env = os.environ.copy()
    assert_engine_is_disposable(engine)
    ops_url = engine.url.render_as_string(hide_password=False)
    alembic_cfg = Config(str(API_ROOT / "alembic.ini"))
    alembic_cfg.set_main_option("sqlalchemy.url", ops_url)
    alembic_cfg.set_main_option("script_location", str(API_ROOT / "alembic"))
    command.upgrade(alembic_cfg, "head")
    run_env["DEVELOPMENT_OPS_DATABASE_URL"] = ops_url
    run_env["WASATCH_DATABASE_URL"] = ops_url
    run_env["PYTHONPATH"] = os.path.join(REPO_ROOT, "libs", "development_ops", "src")
    run_env["DEVELOPMENT_OPS_DISABLE_GITHUB"] = "1"
    if env:
        run_env.update(env)
    return subprocess.run(
        ["python3", "-m", "development_ops.cli", *args],
        capture_output=True,
        text=True,
        env=run_env,
        check=False,
        timeout=timeout,
    )


def test_runner_status_is_read_only_json(
    ops_test_engine: Engine, tmp_path: Path
) -> None:
    state_dir = tmp_path / "state"
    result = _run_cli(
        ops_test_engine,
        "runner",
        "status",
        env={"DEVELOPMENT_OPS_RUNNER_STATE_DIR": str(state_dir)},
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["database_ok"] is True
    assert payload["paused"] is False
    assert payload["active_leases"] == []
    # A read-only status call must not create a pause state file.
    assert not (state_dir / "runner-state.json").exists()


def test_runner_pause_then_resume_is_durable(
    ops_test_engine: Engine, tmp_path: Path
) -> None:
    state_dir = tmp_path / "state"
    env = {"DEVELOPMENT_OPS_RUNNER_STATE_DIR": str(state_dir)}
    paused = _run_cli(
        ops_test_engine, "runner", "pause", "--by", "operator", "--reason", "x", env=env
    )
    assert paused.returncode == 0, paused.stderr
    assert json.loads(paused.stdout)["paused"] is True

    status = _run_cli(ops_test_engine, "runner", "status", env=env)
    assert json.loads(status.stdout)["paused"] is True

    resumed = _run_cli(ops_test_engine, "runner", "resume", env=env)
    assert resumed.returncode == 0, resumed.stderr
    assert json.loads(resumed.stdout)["paused"] is False


def test_runner_once_records_lifecycle_telemetry(
    ops_test_engine: Engine, tmp_path: Path
) -> None:
    state_dir = tmp_path / "state"
    run_id = uuid.uuid4()
    env = {
        "DEVELOPMENT_OPS_RUNNER_STATE_DIR": str(state_dir),
        "DEVELOPMENT_OPS_RUNNER_RECOVER": "0",
        "DEVELOPMENT_OPS_RUN_ID": str(run_id),
    }
    result = _run_cli(ops_test_engine, "runner", "once", env=env)
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["ticks"] == 1

    with ops_test_engine.connect() as connection:
        types = [
            row[0]
            for row in connection.execute(
                text(
                    "SELECT event_type FROM development_ops.activity_events "
                    "WHERE run_id = :run_id ORDER BY occurred_at"
                ),
                {"run_id": str(run_id)},
            )
        ]
    assert "run.started" in types
    assert "run.completed" in types
    assert "coordinator.scheduled" in types


def test_runner_second_instance_is_rejected(
    ops_test_engine: Engine, tmp_path: Path
) -> None:
    """A held lock makes a second `runner run` exit non-zero without ticking."""
    state_dir = tmp_path / "state"
    lock_path = state_dir / "coordinator.lock"
    env = {
        "DEVELOPMENT_OPS_RUNNER_STATE_DIR": str(state_dir),
        "DEVELOPMENT_OPS_RUNNER_RECOVER": "0",
    }
    first = subprocess.Popen(
        [
            "python3",
            "-m",
            "development_ops.cli",
            "runner",
            "run",
            "--max-ticks",
            "50",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={**os.environ, **_cli_env(ops_test_engine, env)},
    )
    try:
        _wait_for(lock_path, timeout=30.0)
        second = _run_cli(ops_test_engine, "runner", "once", env=env)
        assert second.returncode != 0
        assert "another coordinator runner" in second.stderr
    finally:
        first.send_signal(signal.SIGTERM)
        try:
            first.wait(timeout=30)
        except subprocess.TimeoutExpired:  # pragma: no cover - defensive
            first.kill()
            first.wait(timeout=10)


def test_runner_graceful_sigterm_shutdown(
    ops_test_engine: Engine, tmp_path: Path
) -> None:
    """SIGTERM stops the loop and the process exits zero."""
    state_dir = tmp_path / "state"
    env = {
        "DEVELOPMENT_OPS_RUNNER_STATE_DIR": str(state_dir),
        "DEVELOPMENT_OPS_RUNNER_RECOVER": "0",
        "DEVELOPMENT_OPS_RUNNER_POLL_SECONDS": "0.2",
    }
    proc = subprocess.Popen(
        [
            "python3",
            "-m",
            "development_ops.cli",
            "runner",
            "run",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={**os.environ, **_cli_env(ops_test_engine, env)},
    )
    try:
        _wait_for(state_dir / "coordinator.lock", timeout=30.0)
        time.sleep(0.6)
        proc.send_signal(signal.SIGTERM)
        stdout, _stderr = proc.communicate(timeout=30)
        assert proc.returncode == 0
        assert json.loads(stdout)["ticks"] >= 1
    finally:
        if proc.poll() is None:  # pragma: no cover - defensive
            proc.kill()
            proc.wait(timeout=10)
    # Lock is released so a fresh runner can start.
    again = _run_cli(ops_test_engine, "runner", "once", env=env)
    assert again.returncode == 0, again.stderr


def _cli_env(engine: Engine, extra: dict[str, str]) -> dict[str, str]:
    ops_url = engine.url.render_as_string(hide_password=False)
    return {
        "DEVELOPMENT_OPS_DATABASE_URL": ops_url,
        "WASATCH_DATABASE_URL": ops_url,
        "DEVELOPMENT_OPS_DISABLE_GITHUB": "1",
        "PYTHONPATH": os.path.join(REPO_ROOT, "libs", "development_ops", "src"),
        **extra,
    }


def _wait_for(path: Path, *, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if path.exists():
            return
        time.sleep(0.05)
    raise AssertionError(f"{path} was not created within {timeout}s")

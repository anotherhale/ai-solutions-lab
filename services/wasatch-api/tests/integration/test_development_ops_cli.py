"""CLI integration tests for development activity recording."""

from __future__ import annotations

import json
import os
import subprocess
import uuid

import pytest
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from development_ops.persistence.repository import (
    ActivityEventQuery,
    ActivityEventRepository,
)

REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "..")
)


def _run_cli(
    engine: Engine, *args: str, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    run_env = os.environ.copy()
    run_env["WASATCH_DATABASE_URL"] = engine.url.render_as_string(hide_password=False)
    run_env["PYTHONPATH"] = os.path.join(REPO_ROOT, "libs", "development_ops", "src")
    if env:
        run_env.update(env)
    return subprocess.run(
        ["python3", "-m", "development_ops.cli", *args],
        capture_output=True,
        text=True,
        env=run_env,
        check=False,
    )


def test_cli_records_correlated_run_lifecycle(engine: Engine) -> None:
    run_id = uuid.uuid4()
    base_env = {
        "DEVELOPMENT_OPS_RUN_ID": str(run_id),
        "DEVELOPMENT_OPS_GITHUB_REPOSITORY": "anotherhale/ai-solutions-lab",
        "DEVELOPMENT_OPS_AGENT_NAME": "test-coordinator",
    }
    steps = [
        (
            "record",
            "--event-type",
            "run.started",
            "--title",
            "Run started",
            "--idempotency-key",
            f"{run_id}:run.started",
        ),
        (
            "record",
            "--event-type",
            "task.selected",
            "--task-id",
            "phase-2-cli",
            "--title",
            "Task selected",
        ),
        (
            "record",
            "--event-type",
            "implementation.milestone",
            "--title",
            "CLI implemented",
            "--metadata",
            '{"component":"development-ops-record"}',
        ),
        (
            "record",
            "--event-type",
            "test.completed",
            "--title",
            "Integration tests passed",
        ),
        (
            "record",
            "--event-type",
            "pr.opened",
            "--title",
            "Opened PR",
            "--github-pull-number",
            "99",
        ),
    ]
    for step in steps:
        result = _run_cli(engine, *step, env=base_env)
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload["persisted"] is True
        assert payload["run_id"] == str(run_id)

    session = sessionmaker(bind=engine)()
    try:
        events = ActivityEventRepository(session).search(
            ActivityEventQuery(run_id=run_id, limit=100)
        )
    finally:
        session.close()
    assert len(events) == len(steps)
    types = {event.event_type.value for event in events}
    assert "run.started" in types
    assert "pr.opened" in types


def test_cli_idempotency_replay(engine: Engine) -> None:
    run_id = uuid.uuid4()
    env = {"DEVELOPMENT_OPS_RUN_ID": str(run_id)}
    key = f"{run_id}:once"
    args = [
        "record",
        "--event-type",
        "progress.report",
        "--title",
        "Once",
        "--idempotency-key",
        key,
    ]
    first = _run_cli(engine, *args, env=env)
    second = _run_cli(engine, *args, env=env)
    assert first.returncode == 0
    assert second.returncode == 0
    assert json.loads(first.stdout)["created"] is True
    assert json.loads(second.stdout)["created"] is False


def test_cli_persistence_failure_exits_nonzero() -> None:
    repo_root = REPO_ROOT
    result = subprocess.run(
        [
            "python3",
            "-m",
            "development_ops.cli",
            "record",
            "--run-id",
            str(uuid.uuid4()),
            "--event-type",
            "progress.report",
            "--title",
            "Should fail",
        ],
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "PYTHONPATH": os.path.join(repo_root, "libs", "development_ops", "src"),
            "WASATCH_DATABASE_URL": "postgresql+psycopg://invalid:invalid@127.0.0.1:1/none",
        },
        check=False,
    )
    assert result.returncode == 1
    assert "persisted" in result.stderr or "persisted" in result.stdout


def test_cli_confirm_slack_delivery(engine: Engine) -> None:
    run_id = uuid.uuid4()
    env = {"DEVELOPMENT_OPS_RUN_ID": str(run_id)}
    recorded = _run_cli(
        engine,
        "record",
        "--event-type",
        "progress.report",
        "--title",
        "Notify",
        env=env,
    )
    assert recorded.returncode == 0
    event_id = json.loads(recorded.stdout)["event_id"]
    confirmed = _run_cli(
        engine,
        "confirm-slack",
        "--event-id",
        event_id,
        "--channel-id",
        "C0CFJDH7PTJ",
        "--message-ts",
        "1234.5678",
        env=env,
    )
    assert confirmed.returncode == 0
    body = json.loads(confirmed.stdout)
    assert body["slack_delivered"] is True

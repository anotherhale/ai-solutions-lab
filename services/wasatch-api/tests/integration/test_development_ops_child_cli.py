"""CLI tests for `development-ops child` against a disposable database.

These exercise the real application services through the CLI: the read-only
status contract, the durable enable/disable controls, and the guarantee that
child execution is disabled by default. No paid model call is made: the CLI
never launches a child, only reports and toggles state.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
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
        connection.execute(text("DELETE FROM development_ops.child_executions"))
        connection.execute(text("DELETE FROM development_ops.orchestration_settings"))
        connection.execute(text("DELETE FROM development_ops.activity_events"))
        connection.execute(text("DELETE FROM development_ops.coordinator_tasks"))
        connection.execute(text("DELETE FROM development_ops.agent_worktrees"))
        # Re-seed the durable default: disabled.
        connection.execute(
            text(
                "INSERT INTO development_ops.orchestration_settings (key, value) "
                "VALUES ('child_execution_enabled', '{\"enabled\": false}'::jsonb) "
                "ON CONFLICT (key) DO UPDATE SET value = '{\"enabled\": false}'::jsonb"
            )
        )


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
    # Never let the operator enable path leak from the ambient environment.
    run_env.pop("DEVELOPMENT_OPS_ENABLE_CHILD_EXECUTION", None)
    if env:
        run_env.update(env)
    return subprocess.run(
        [sys.executable, "-m", "development_ops.cli", *args],
        capture_output=True,
        text=True,
        env=run_env,
        check=False,
        timeout=timeout,
    )


def test_child_status_is_disabled_by_default(ops_test_engine: Engine) -> None:
    result = _run_cli(ops_test_engine, "child", "status")
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["enabled"] is False
    assert payload["max_concurrent"] == 2
    assert payload["active_children"] == 0
    assert payload["available_slots"] == 2
    assert payload["children"] == []


def test_child_enable_then_disable_is_durable(ops_test_engine: Engine) -> None:
    enabled = _run_cli(
        ops_test_engine, "child", "enable", "--by", "operator", "--reason", "reviewed"
    )
    assert enabled.returncode == 0, enabled.stderr
    assert json.loads(enabled.stdout)["enabled"] is True

    status = _run_cli(ops_test_engine, "child", "status")
    assert json.loads(status.stdout)["enabled"] is True

    disabled = _run_cli(
        ops_test_engine, "child", "disable", "--by", "operator", "--reason", "done"
    )
    assert disabled.returncode == 0, disabled.stderr
    assert json.loads(disabled.stdout)["enabled"] is False

    status2 = _run_cli(ops_test_engine, "child", "status")
    assert json.loads(status2.stdout)["enabled"] is False


def test_environment_alone_does_not_enable(ops_test_engine: Engine) -> None:
    """An exported variable must not switch on child execution."""
    status = _run_cli(
        ops_test_engine,
        "child",
        "status",
        env={"DEVELOPMENT_OPS_ENABLE_CHILD_EXECUTION": "1"},
    )
    assert status.returncode == 0, status.stderr
    payload = json.loads(status.stdout)
    assert payload["enabled"] is False
    assert "durable operator flag" in payload["enabled_reason"]


def test_child_status_records_no_launch(ops_test_engine: Engine) -> None:
    """Status and toggles must never create a child execution."""
    _run_cli(ops_test_engine, "child", "enable", "--by", "operator")
    _run_cli(ops_test_engine, "child", "status")
    with ops_test_engine.connect() as connection:
        count = connection.execute(
            text("SELECT count(*) FROM development_ops.child_executions")
        ).scalar()
    assert count == 0

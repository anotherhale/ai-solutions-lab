"""CLI tests for `development-ops worktree` against a disposable database.

Uses real temporary Git repositories and the disposable ops-test database. The
commands call the same application services the coordinator uses; this verifies
the wiring and the JSON contract, not a second implementation.
"""

from __future__ import annotations

import json
import os
import subprocess
import threading
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest
from sqlalchemy.engine import Engine

from wasatch_api.testing.postgres import assert_engine_is_disposable

REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "..")
)
API_ROOT = Path(REPO_ROOT) / "services" / "wasatch-api"


def _git(args: list[str], cwd: Path) -> str:
    result = subprocess.run(
        ["git", *args], cwd=str(cwd), capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} failed: {result.stderr}")
    return result.stdout.strip()


@pytest.fixture(autouse=True)
def _clean_disposable_ops_tables(ops_test_engine: Engine) -> None:
    assert_engine_is_disposable(ops_test_engine)
    from sqlalchemy import text

    with ops_test_engine.begin() as connection:
        connection.execute(text("DELETE FROM development_ops.agent_worktrees"))
        connection.execute(text("DELETE FROM development_ops.activity_events"))
        connection.execute(text("DELETE FROM development_ops.coordinator_tasks"))


@pytest.fixture
def work_repo(tmp_path: Path) -> tuple[Path, Path]:
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", str(origin)], check=True)
    seed = tmp_path / "seed"
    seed.mkdir()
    _git(["init", "-q", "-b", "main"], seed)
    _git(["config", "user.email", "t@t.t"], seed)
    _git(["config", "user.name", "t"], seed)
    (seed / "README.md").write_text("base\n", encoding="utf-8")
    _git(["add", "-A"], seed)
    _git(["commit", "-qm", "base"], seed)
    _git(["checkout", "-q", "-b", "ai-dev"], seed)
    (seed / "ai.txt").write_text("ai\n", encoding="utf-8")
    _git(["add", "-A"], seed)
    _git(["commit", "-qm", "ai"], seed)
    _git(["remote", "add", "origin", str(origin)], seed)
    _git(["push", "-q", "origin", "main", "ai-dev"], seed)
    subprocess.run(
        ["git", "--git-dir", str(origin), "symbolic-ref", "HEAD", "refs/heads/main"],
        check=True,
    )
    work = tmp_path / "work"
    subprocess.run(["git", "clone", "-q", str(origin), str(work)], check=True)
    _git(["config", "user.email", "t@t.t"], work)
    _git(["config", "user.name", "t"], work)
    return work, tmp_path / "worktrees"


def _run_cli(
    engine: Engine, work_repo: tuple[Path, Path], *args: str
) -> subprocess.CompletedProcess[str]:
    from alembic import command
    from alembic.config import Config

    assert_engine_is_disposable(engine)
    ops_url = engine.url.render_as_string(hide_password=False)
    alembic_cfg = Config(str(API_ROOT / "alembic.ini"))
    alembic_cfg.set_main_option("sqlalchemy.url", ops_url)
    alembic_cfg.set_main_option("script_location", str(API_ROOT / "alembic"))
    command.upgrade(alembic_cfg, "head")

    work, wt_root = work_repo
    env = os.environ.copy()
    env["DEVELOPMENT_OPS_DATABASE_URL"] = ops_url
    env["DEVELOPMENT_OPS_REPO_ROOT"] = str(work)
    env["DEVELOPMENT_OPS_WORKTREE_ROOT"] = str(wt_root)
    env["DEVELOPMENT_OPS_GITHUB_REPOSITORY"] = "example/test"
    env["DEVELOPMENT_OPS_DISABLE_GITHUB"] = "1"
    env["PYTHONPATH"] = os.path.join(REPO_ROOT, "libs", "development_ops", "src")
    return subprocess.run(
        ["python3", "-m", "development_ops.cli", "worktree", *args],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


def test_worktree_list_empty(
    ops_test_engine: Engine, work_repo: tuple[Path, Path]
) -> None:
    result = _run_cli(ops_test_engine, work_repo, "list")
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"worktrees": []}


def test_worktree_prepare_then_status(
    ops_test_engine: Engine, work_repo: tuple[Path, Path]
) -> None:
    task_id = f"CLI-{uuid.uuid4().hex[:6]}"
    prepared = _run_cli(
        ops_test_engine, work_repo, "prepare", task_id, "--title", "cli"
    )
    assert prepared.returncode == 0, prepared.stderr
    body = json.loads(prepared.stdout)
    assert body["task_id"] == task_id
    assert body["branch_name"] == f"cursor/{task_id}"
    assert body["base_ref"] == "origin/ai-dev"
    assert Path(body["worktree_path"]).exists()

    status = _run_cli(ops_test_engine, work_repo, "status", task_id)
    assert status.returncode == 0, status.stderr
    status_body = json.loads(status.stdout)
    assert status_body["task_id"] == task_id
    assert status_body["filesystem"]["exists"] is True
    assert status_body["filesystem"]["dirty"] is False


def test_worktree_status_unknown_task(
    ops_test_engine: Engine, work_repo: tuple[Path, Path]
) -> None:
    result = _run_cli(ops_test_engine, work_repo, "status", "NOPE-1")
    assert result.returncode != 0
    assert "no worktree registered" in result.stderr


def test_worktree_cleanup_refuses_without_verified_merge(
    ops_test_engine: Engine, work_repo: tuple[Path, Path]
) -> None:
    task_id = f"CLI-{uuid.uuid4().hex[:6]}"
    assert _run_cli(ops_test_engine, work_repo, "prepare", task_id).returncode == 0
    # No pull request is registered, so cleanup must refuse.
    cleanup = _run_cli(ops_test_engine, work_repo, "cleanup", task_id)
    assert cleanup.returncode != 0
    body = json.loads(cleanup.stdout)
    assert body["cleaned"] is False
    assert body["verified_merge"] is False


class _StubAgentServer:
    """Minimal agent-server stand-in that accepts one child conversation."""

    def __init__(self) -> None:
        self.requests: list[dict] = []
        stub = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:  # noqa: N802 - http.server API
                length = int(self.headers.get("Content-Length", "0"))
                body = json.loads(self.rfile.read(length) or b"{}")
                stub.requests.append(body)
                payload = json.dumps({"id": "conv-cli-1"}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *args) -> None:  # silence test output
                return

        self._server = HTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    @property
    def url(self) -> str:
        host, port = self._server.server_address[:2]
        return f"http://{host}:{port}"

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()


def test_worktree_launch_starts_child_in_worktree(
    ops_test_engine: Engine, work_repo: tuple[Path, Path], tmp_path: Path
) -> None:
    server = _StubAgentServer()
    try:
        task_id = f"CLI-{uuid.uuid4().hex[:6]}"
        settings = tmp_path / "agent_settings.json"
        settings.write_text(json.dumps({"llm": {"model": "test"}}), encoding="utf-8")
        result = _run_cli(
            ops_test_engine,
            work_repo,
            "launch",
            task_id,
            "--title",
            "cli launch",
            "--agent-settings",
            str(settings),
            "--agent-server-url",
            server.url,
        )
        assert result.returncode == 0, result.stderr
        body = json.loads(result.stdout)
        assert body["launched"] is True
        assert body["conversation_id"] == "conv-cli-1"

        # The child was pointed at the registered worktree with worktree
        # creation disabled.
        sent = server.requests[0]
        assert sent["worktree"] is False
        assert Path(sent["workspace"]["working_dir"]).exists()

        # Registry recorded the conversation.
        status = _run_cli(ops_test_engine, work_repo, "status", task_id)
        status_body = json.loads(status.stdout)
        assert status_body["conversation_id"] == "conv-cli-1"
        assert status_body["state"] == "launched"
    finally:
        server.stop()


def test_worktree_launch_requires_agent_settings_file(
    ops_test_engine: Engine, work_repo: tuple[Path, Path], tmp_path: Path
) -> None:
    missing = tmp_path / "nope.json"
    result = _run_cli(
        ops_test_engine,
        work_repo,
        "launch",
        "CLI-MISSING",
        "--agent-settings",
        str(missing),
    )
    assert result.returncode != 0
    assert "agent settings not found" in result.stderr

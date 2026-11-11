"""Acceptance-style tests for coordinator continuity."""

from __future__ import annotations

import os
import textwrap
import uuid
from pathlib import Path

import pytest
from development_ops.coordinator_engine import CoordinatorEngine
from development_ops.database import ensure_development_ops_database
from development_ops.github_client import (
    AutoMergeAttempt,
    GitHubClient,
    PullRequestState,
)
from development_ops.recorder import ActivityRecorder
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from wasatch_api.testing.postgres import wasatch_development_ops_database_url_for_tests


class FakeGitHub(GitHubClient):
    def __init__(self, prs: dict[int, PullRequestState]) -> None:
        self._prs = prs
        self.auto_merge_calls: list[int] = []

    def get_pull_request(self, repository: str, number: int) -> PullRequestState:
        return self._prs[number]

    def list_open_pull_requests(self, repository: str) -> list[PullRequestState]:
        return [pr for pr in self._prs.values() if not pr.merged]

    def enable_squash_auto_merge(
        self, repository: str, number: int
    ) -> AutoMergeAttempt:
        self.auto_merge_calls.append(number)
        return AutoMergeAttempt(
            pull_number=number,
            requested=True,
            auto_merge_request_present=False,
            error="Pull request is in clean status",
            raw_response="graphql simulated failure",
        )


def _pr(
    number: int, *, merged: bool = False, checks_green: bool = True
) -> PullRequestState:
    return PullRequestState(
        number=number,
        state="MERGED" if merged else "OPEN",
        merged=merged,
        mergeable="MERGEABLE",
        head_ref=f"cursor/task-{number}",
        base_ref="develop",
        node_id=f"PR_node_{number}",
        auto_merge_enabled=False,
        checks_green=checks_green,
        review_decision="REVIEW_REQUIRED",
    )


@pytest.fixture(autouse=True)
def _reset_coordinator_tables(ops_engine: Engine) -> None:
    with ops_engine.begin() as connection:
        connection.execute(text("DELETE FROM development_ops.activity_events"))
        connection.execute(text("DELETE FROM development_ops.coordinator_tasks"))


@pytest.fixture
def ops_engine() -> Engine:
    from sqlalchemy import create_engine, text

    url = ensure_development_ops_database(
        wasatch_development_ops_database_url_for_tests()
    )
    from sqlalchemy.engine import make_url

    parsed = make_url(url)
    target = parsed.database or "wasatch_development_ops"
    for admin_name in ("wasatch", "postgres"):
        if admin_name == target:
            continue
        admin = create_engine(
            parsed.set(database=admin_name),
            isolation_level="AUTOCOMMIT",
            pool_pre_ping=True,
        )
        try:
            with admin.connect() as connection:
                connection.execute(
                    text(
                        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                        "WHERE datname = :name AND pid <> pg_backend_pid()"
                    ),
                    {"name": target},
                )
                connection.execute(text(f'DROP DATABASE IF EXISTS "{target}"'))
                connection.execute(text(f'CREATE DATABASE "{target}"'))
            break
        except Exception:
            continue
        finally:
            admin.dispose()
    ensure_development_ops_database(url)
    os.environ["DEVELOPMENT_OPS_DATABASE_URL"] = url
    os.environ["WASATCH_DATABASE_URL"] = url
    from alembic import command
    from alembic.config import Config

    from wasatch_api.config import REPO_ROOT, get_settings

    api_root = REPO_ROOT / "services" / "wasatch-api"
    get_settings.cache_clear()
    cfg = Config(str(api_root / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", url)
    cfg.set_main_option("script_location", str(api_root / "alembic"))
    command.upgrade(cfg, "head")
    engine = create_engine(url, pool_pre_ping=True)
    yield engine
    engine.dispose()


@pytest.fixture
def backlog_file(tmp_path: Path) -> Path:
    path = tmp_path / "backlog.yaml"
    path.write_text(
        textwrap.dedent(
            """
            repository: example/test
            integration_branch: develop
            tasks:
              - id: TASK-A
                title: Agent A work
                status: in_progress
                pr_number: 100
                branch: cursor/task-a
                depends_on: []
              - id: TASK-B
                title: Independent follow-on
                status: pending
                depends_on: []
              - id: TASK-C
                title: Depends on A
                status: pending
                depends_on: [TASK-A]
            """
        ).strip(),
        encoding="utf-8",
    )
    return path


def test_open_pr_does_not_block_independent_task(
    ops_engine: Engine, backlog_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DEVELOPMENT_OPS_ATTEMPT_AUTO_MERGE", "0")
    run_id = uuid.uuid4()
    session = sessionmaker(bind=ops_engine, autoflush=False)()
    github = FakeGitHub({100: _pr(100)})
    try:
        engine = CoordinatorEngine(
            session,
            github=github,
            recorder=ActivityRecorder(session, notify_slack=False),
            run_id=run_id,
            repository="example/test",
            backlog_path=backlog_file,
        )
        result = engine.tick()
        assert result.selected_task_id == "TASK-B"
        assert 100 in result.open_pull_requests
    finally:
        session.close()


def test_auto_merge_failure_does_not_stop_selection(
    ops_engine: Engine, backlog_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DEVELOPMENT_OPS_ATTEMPT_AUTO_MERGE", "1")
    run_id = uuid.uuid4()
    session = sessionmaker(bind=ops_engine, autoflush=False)()
    github = FakeGitHub({100: _pr(100, checks_green=True)})
    try:
        engine = CoordinatorEngine(
            session,
            github=github,
            recorder=ActivityRecorder(session, notify_slack=False),
            run_id=run_id,
            repository="example/test",
            backlog_path=backlog_file,
        )
        result = engine.tick()
        assert github.auto_merge_calls == [100]
        assert result.auto_merge_attempts[0].error is not None
        assert result.selected_task_id == "TASK-B"
    finally:
        session.close()


def test_dependency_held_until_parent_merged(
    ops_engine: Engine, backlog_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DEVELOPMENT_OPS_ATTEMPT_AUTO_MERGE", "0")
    run_id = uuid.uuid4()
    session = sessionmaker(bind=ops_engine, autoflush=False)()
    github = FakeGitHub({100: _pr(100)})
    try:
        engine = CoordinatorEngine(
            session,
            github=github,
            recorder=ActivityRecorder(session, notify_slack=False),
            run_id=run_id,
            repository="example/test",
            backlog_path=backlog_file,
        )
        result = engine.tick()
        assert "TASK-C" in result.held_for_dependency
    finally:
        session.close()


def test_many_pr_open_tasks_do_not_exhaust_concurrency_slots(
    ops_engine: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression: catalog in_progress + runtime PR_OPEN must not block pending work."""
    monkeypatch.setenv("DEVELOPMENT_OPS_ATTEMPT_AUTO_MERGE", "0")
    backlog = tmp_path / "backlog.yaml"
    backlog.write_text(
        textwrap.dedent(
            """
            repository: example/test
            integration_branch: develop
            tasks:
              - id: DOC-A
                title: Doc A
                status: in_progress
                pr_number: 201
                branch: cursor/doc-a
                depends_on: []
              - id: DOC-B
                title: Doc B
                status: in_progress
                pr_number: 202
                branch: cursor/doc-b
                depends_on: []
              - id: DOC-C
                title: Doc C
                status: in_progress
                pr_number: 203
                branch: cursor/doc-c
                depends_on: []
              - id: DOC-D
                title: Doc D
                status: in_progress
                pr_number: 204
                branch: cursor/doc-d
                depends_on: []
              - id: NEXT-1
                title: Next implementation
                status: pending
                depends_on: []
            """
        ).strip(),
        encoding="utf-8",
    )
    run_id = uuid.uuid4()
    session = sessionmaker(bind=ops_engine, autoflush=False)()
    github = FakeGitHub(
        {
            201: _pr(201),
            202: _pr(202),
            203: _pr(203),
            204: _pr(204),
        }
    )
    try:
        engine = CoordinatorEngine(
            session,
            github=github,
            recorder=ActivityRecorder(session, notify_slack=False),
            run_id=run_id,
            repository="example/test",
            backlog_path=backlog,
        )
        result = engine.tick()
        assert result.active_tasks == 0
        assert result.selected_task_id == "NEXT-1"
    finally:
        session.close()


def test_recovery_reclaims_stale_assignment(
    ops_engine: Engine, backlog_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DEVELOPMENT_OPS_ATTEMPT_AUTO_MERGE", "0")
    first_run = uuid.uuid4()
    second_run = uuid.uuid4()
    session = sessionmaker(bind=ops_engine, autoflush=False)()
    github = FakeGitHub({100: _pr(100)})
    try:
        engine = CoordinatorEngine(
            session,
            github=github,
            recorder=ActivityRecorder(session, notify_slack=False),
            run_id=first_run,
            repository="example/test",
            backlog_path=backlog_file,
        )
        engine.tick()
        monkeypatch.setenv("DEVELOPMENT_OPS_RECLAIM_STALE", "1")
        engine2 = CoordinatorEngine(
            session,
            github=github,
            recorder=ActivityRecorder(session, notify_slack=False),
            run_id=second_run,
            repository="example/test",
            backlog_path=backlog_file,
        )
        result = engine2.tick()
        assert result.selected_task_id == "TASK-B"
    finally:
        session.close()

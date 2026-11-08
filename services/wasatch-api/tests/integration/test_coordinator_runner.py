"""Integration tests for the persistent coordinator runner.

All database work runs against the disposable ``wasatch_development_ops_test``
database. The operational ``wasatch_development_ops`` database is never touched.
"""

from __future__ import annotations

import subprocess
import textwrap
import uuid
from pathlib import Path

import pytest
from development_ops.coordinator_engine import CoordinatorEngine
from development_ops.github_client import (
    AutoMergeAttempt,
    GitHubClient,
    PullRequestState,
)
from development_ops.instance_lock import CoordinatorInstanceLock, InstanceLockedError
from development_ops.persistence.coordinator_repository import (
    CoordinatorTaskRepository,
)
from development_ops.recorder import ActivityRecorder
from development_ops.runner import CoordinatorRunner, TickOutcome
from development_ops.runner_config import RunnerConfig
from development_ops.runner_state import RunnerStateStore
from development_ops.runner_status import collect_status
from development_ops.scheduling import RuntimeTaskStatus
from development_ops.task_worktrees import TaskWorktreeOrchestrator
from development_ops.taxonomy import EventType
from development_ops.worktrees import WorktreeManager
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from wasatch_api.testing.postgres import assert_engine_is_disposable


class FakeGitHub(GitHubClient):
    def __init__(self, prs: dict[int, PullRequestState]) -> None:
        self._prs = prs
        self.auto_merge_calls: list[int] = []

    def get_pull_request(self, repository: str, number: int) -> PullRequestState:
        return self._prs[number]

    def list_open_pull_requests(self, repository: str) -> list[PullRequestState]:
        return [pr for pr in self._prs.values() if not pr.merged and not pr.closed]

    def enable_squash_auto_merge(
        self, repository: str, number: int
    ) -> AutoMergeAttempt:
        self.auto_merge_calls.append(number)
        return AutoMergeAttempt(
            pull_number=number,
            requested=True,
            auto_merge_request_present=True,
            error=None,
            raw_response="ok",
        )


def _pr(
    number: int,
    *,
    merged: bool = False,
    closed: bool = False,
    base_ref: str = "ai-dev",
) -> PullRequestState:
    return PullRequestState(
        number=number,
        state="CLOSED" if closed and not merged else ("MERGED" if merged else "OPEN"),
        merged=merged,
        mergeable="MERGEABLE",
        head_ref=f"cursor/task-{number}",
        base_ref=base_ref,
        node_id=f"PR_node_{number}",
        auto_merge_enabled=False,
        checks_green=True,
        review_decision="REVIEW_REQUIRED",
        closed=closed or merged,
        checks_state="green",
    )


def _git(args: list[str], cwd: Path) -> str:
    result = subprocess.run(
        ["git", *args], cwd=str(cwd), capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} failed: {result.stderr}")
    return result.stdout.strip()


def _make_repo(tmp_path: Path) -> tuple[Path, Path]:
    """A real local repository with an ``ai-dev`` branch, for worktree tests."""
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
    (seed / "ai.txt").write_text("ai-dev\n", encoding="utf-8")
    _git(["add", "-A"], seed)
    _git(["commit", "-qm", "ai-dev"], seed)
    _git(["remote", "add", "origin", str(origin)], seed)
    _git(["push", "-q", "origin", "main", "ai-dev"], seed)
    work = tmp_path / "work"
    subprocess.run(["git", "clone", "-q", str(origin), str(work)], check=True)
    _git(["config", "user.email", "t@t.t"], work)
    _git(["config", "user.name", "t"], work)
    return work, tmp_path / "worktrees"


@pytest.fixture(autouse=True)
def _clean_disposable_ops_tables(ops_test_engine: Engine) -> None:
    assert_engine_is_disposable(ops_test_engine)
    with ops_test_engine.begin() as connection:
        connection.execute(text("DELETE FROM development_ops.activity_events"))
        connection.execute(text("DELETE FROM development_ops.coordinator_tasks"))
        connection.execute(text("DELETE FROM development_ops.agent_worktrees"))


@pytest.fixture
def factory(ops_test_engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=ops_test_engine, autoflush=False)


@pytest.fixture
def backlog_file(tmp_path: Path) -> Path:
    path = tmp_path / "backlog.yaml"
    path.write_text(
        textwrap.dedent(
            """
            repository: example/test
            integration_branch: ai-dev
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
            """
        ).strip(),
        encoding="utf-8",
    )
    return path


def _config(tmp_path: Path, backlog: Path) -> RunnerConfig:
    return RunnerConfig(
        repository="example/test",
        poll_interval_seconds=0.01,
        heartbeat_interval_seconds=0.01,
        lease_seconds=900,
        state_dir=tmp_path / "state",
        backlog_path=backlog,
    )


def _engine_tick(
    factory: sessionmaker[Session],
    *,
    github: GitHubClient,
    backlog: Path,
    run_id: uuid.UUID,
    max_concurrent: int | None = None,
):
    session = factory()
    try:
        engine = CoordinatorEngine(
            session,
            github=github,
            recorder=ActivityRecorder(session, notify_slack=False),
            run_id=run_id,
            repository="example/test",
            backlog_path=backlog,
        )
        return engine.tick(
            max_concurrent=max_concurrent,
            reclaim_expired=False,
        )
    finally:
        session.close()


class RecordingTelemetry:
    def __init__(self) -> None:
        self.events: list[EventType] = []

    def record(self, *, event_type: EventType, **_: object) -> None:
        self.events.append(event_type)


def test_runner_repeated_ticks_against_database(
    factory: sessionmaker[Session],
    backlog_file: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEVELOPMENT_OPS_ATTEMPT_AUTO_MERGE", "0")
    github = FakeGitHub({100: _pr(100)})
    run_id = uuid.uuid4()

    def tick(**_: object) -> TickOutcome:
        result = _engine_tick(
            factory, github=github, backlog=backlog_file, run_id=run_id
        )
        return TickOutcome(selected_task_id=result.selected_task_id)

    runner = CoordinatorRunner(
        _config(tmp_path, backlog_file),
        tick=tick,
        telemetry=RecordingTelemetry(),
        sleep=lambda _seconds: False,
    )
    assert runner.run(max_ticks=3) == 3


def test_startup_recovery_reclaims_expired_lease(
    factory: sessionmaker[Session],
    backlog_file: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEVELOPMENT_OPS_ATTEMPT_AUTO_MERGE", "0")
    github = FakeGitHub({100: _pr(100)})
    # First run claims TASK-B.
    first = _engine_tick(
        factory, github=github, backlog=backlog_file, run_id=uuid.uuid4()
    )
    assert first.selected_task_id == "TASK-B"
    # Simulate a crash: expire the lease.
    session = factory()
    try:
        session.execute(
            text(
                "UPDATE development_ops.coordinator_tasks "
                "SET lease_expires_at = now() - interval '1 hour' "
                "WHERE task_id = 'TASK-B'"
            )
        )
        session.commit()
    finally:
        session.close()

    def startup_recovery():
        from development_ops.runner import RecoveryReport

        session = factory()
        try:
            repo = CoordinatorTaskRepository(session)
            reclaimed = repo.reclaim_expired_leases()
            return RecoveryReport(reclaimed_tasks=tuple(reclaimed))
        finally:
            session.close()

    runner = CoordinatorRunner(
        _config(tmp_path, backlog_file),
        tick=lambda **_: TickOutcome(),
        telemetry=RecordingTelemetry(),
        startup_recovery=startup_recovery,
        sleep=lambda _seconds: False,
    )
    runner.run(max_ticks=1)
    session = factory()
    try:
        row = CoordinatorTaskRepository(session).get("TASK-B")
        assert row is not None
        assert row.status == RuntimeTaskStatus.PENDING.value
        assert row.active_run_id is None
    finally:
        session.close()


def test_repeated_recovery_is_idempotent(
    factory: sessionmaker[Session],
    backlog_file: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEVELOPMENT_OPS_ATTEMPT_AUTO_MERGE", "0")
    github = FakeGitHub({100: _pr(100)})
    _engine_tick(factory, github=github, backlog=backlog_file, run_id=uuid.uuid4())
    session = factory()
    try:
        session.execute(
            text(
                "UPDATE development_ops.coordinator_tasks "
                "SET lease_expires_at = now() - interval '1 hour' "
                "WHERE task_id = 'TASK-B'"
            )
        )
        session.commit()
        repo = CoordinatorTaskRepository(session)
        first = repo.reclaim_expired_leases()
        second = repo.reclaim_expired_leases()
    finally:
        session.close()
    assert first == ["TASK-B"]
    assert second == []


def test_recovery_preserves_pr_open_and_awaiting_merge(
    factory: sessionmaker[Session],
    backlog_file: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A task with an open PR is finished work, not an abandoned worker."""
    monkeypatch.setenv("DEVELOPMENT_OPS_ATTEMPT_AUTO_MERGE", "0")
    session = factory()
    try:
        repo = CoordinatorTaskRepository(session)
        from development_ops.backlog import load_backlog

        repo.sync_catalog(load_backlog(backlog_file))
        repo.mark_pr_open(
            "TASK-B",
            run_id=uuid.uuid4(),
            branch_name="cursor/task-b",
            pr_number=200,
            owner_agent="coordinator",
        )
        session.execute(
            text(
                "UPDATE development_ops.coordinator_tasks "
                "SET lease_expires_at = now() - interval '1 hour' "
                "WHERE task_id = 'TASK-B'"
            )
        )
        session.commit()
        reclaimed = repo.reclaim_expired_leases()
        row = repo.get("TASK-B")
    finally:
        session.close()
    assert reclaimed == []
    assert row is not None
    assert row.status == RuntimeTaskStatus.PR_OPEN.value
    assert row.pr_number == 200


def test_closed_unmerged_pr_blocks_task_not_merged(
    factory: sessionmaker[Session],
    backlog_file: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A closed-but-unmerged PR must never be treated as merged."""
    monkeypatch.setenv("DEVELOPMENT_OPS_ATTEMPT_AUTO_MERGE", "0")
    github = FakeGitHub({100: _pr(100, closed=True)})
    session = factory()
    try:
        engine = CoordinatorEngine(
            session,
            github=github,
            recorder=ActivityRecorder(session, notify_slack=False),
            run_id=uuid.uuid4(),
            repository="example/test",
            backlog_path=backlog_file,
        )
        engine.tick(reclaim_expired=False)
        repo = CoordinatorTaskRepository(session)
        row = repo.get("TASK-A")
    finally:
        session.close()
    assert row is not None
    assert row.status == RuntimeTaskStatus.BLOCKED.value
    assert "closed without merge" in (row.blocked_reason or "")


def test_worktree_cleanup_only_after_verified_merge(
    factory: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    """Worktree cleanup requires GitHub to confirm the specific PR merged."""
    repo_root, worktree_root = _make_repo(tmp_path)
    manager = WorktreeManager(repo_root, worktree_root, fetch=False)
    session = factory()
    try:
        # Unmerged PR: cleanup must refuse.
        unmerged = FakeGitHub({300: _pr(300, merged=False)})
        orch = TaskWorktreeOrchestrator(
            session,
            manager,
            repository="example/test",
            github=unmerged,
        )
        orch.prepare("TASK-W", title="work")
        orch.register_pull_request("TASK-W", 300)
        outcome = orch.cleanup_after_merge("TASK-W")
        assert outcome.cleaned is False
        assert outcome.verified_merge is False

        # Merged PR: cleanup is allowed.
        merged = FakeGitHub({300: _pr(300, merged=True)})
        orch2 = TaskWorktreeOrchestrator(
            session,
            manager,
            repository="example/test",
            github=merged,
        )
        outcome2 = orch2.cleanup_after_merge("TASK-W")
        assert outcome2.verified_merge is True
    finally:
        session.close()


def test_status_reports_pause_and_leases(
    factory: sessionmaker[Session],
    backlog_file: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEVELOPMENT_OPS_ATTEMPT_AUTO_MERGE", "0")
    github = FakeGitHub({100: _pr(100)})
    _engine_tick(factory, github=github, backlog=backlog_file, run_id=uuid.uuid4())
    config = _config(tmp_path, backlog_file)
    RunnerStateStore(config.state_dir / "runner-state.json").pause(by="operator")
    status = collect_status(config, session_factory=factory)
    assert status.database_ok is True
    assert status.paused is True
    assert any(lease.task_id == "TASK-B" for lease in status.active_leases)
    assert any(item.task_id == "TASK-A" for item in status.awaiting_pull_request)


def test_status_reports_database_failure_without_raising(tmp_path: Path) -> None:
    from sqlalchemy import create_engine

    broken = create_engine(
        "postgresql+psycopg://wasatch:replace-me@localhost:1/wasatch_development_ops_test",
        pool_pre_ping=True,
    )
    config = RunnerConfig(
        repository="example/test",
        state_dir=tmp_path / "state",
        poll_interval_seconds=1,
        heartbeat_interval_seconds=1,
    )
    status = collect_status(config, session_factory=sessionmaker(bind=broken))
    assert status.database_ok is False
    assert status.database_error


def test_pause_is_durable_across_runner_restart(
    factory: sessionmaker[Session],
    backlog_file: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEVELOPMENT_OPS_ATTEMPT_AUTO_MERGE", "0")
    config = _config(tmp_path, backlog_file)
    state_path = config.state_dir / "runner-state.json"
    # A first "process" pauses the runner.
    RunnerStateStore(state_path).pause(by="operator", reason="maintenance")
    observed: list[int | None] = []

    def tick(**kwargs: object) -> TickOutcome:
        observed.append(kwargs.get("max_concurrent"))  # type: ignore[arg-type]
        return TickOutcome()

    # A second runner starts and must still see the pause.
    runner = CoordinatorRunner(
        config,
        tick=tick,
        telemetry=RecordingTelemetry(),
        state_store=RunnerStateStore(state_path),
        sleep=lambda _seconds: False,
    )
    runner.run(max_ticks=1)
    assert observed == [0]


def test_resume_re_enables_scheduling(
    factory: sessionmaker[Session],
    backlog_file: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEVELOPMENT_OPS_ATTEMPT_AUTO_MERGE", "0")
    config = _config(tmp_path, backlog_file)
    state_path = config.state_dir / "runner-state.json"
    store = RunnerStateStore(state_path)
    store.pause(by="operator")
    store.resume()
    observed: list[int | None] = []

    def tick(**kwargs: object) -> TickOutcome:
        observed.append(kwargs.get("max_concurrent"))  # type: ignore[arg-type]
        return TickOutcome()

    runner = CoordinatorRunner(
        config,
        tick=tick,
        telemetry=RecordingTelemetry(),
        state_store=RunnerStateStore(state_path),
        sleep=lambda _seconds: False,
    )
    runner.run(max_ticks=1)
    assert observed == [None]


def test_single_instance_exclusion_against_real_lock(tmp_path: Path) -> None:
    path = tmp_path / "coordinator.lock"
    holder = CoordinatorInstanceLock(path)
    holder.acquire()
    try:
        with pytest.raises(InstanceLockedError):
            CoordinatorInstanceLock(path).acquire()
    finally:
        holder.release()
    # After release a new owner may take it.
    reacquired = CoordinatorInstanceLock(path)
    reacquired.acquire()
    try:
        assert reacquired.held
    finally:
        reacquired.release()

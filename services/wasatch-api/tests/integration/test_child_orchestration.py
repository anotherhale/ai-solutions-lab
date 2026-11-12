"""Integration tests for bounded child-agent orchestration (Phase D).

All database work runs against the disposable ``wasatch_development_ops_test``
database. The Git work runs against real temporary repositories. Child launches
go through a recording stub launcher and a fake agent-server observer, so **no
paid model call is ever made**.

The operational ``wasatch_development_ops`` database is never touched.
"""

from __future__ import annotations

import subprocess
import uuid
from pathlib import Path

import pytest
from development_ops.agent_server import ConversationHealth, ConversationObservation
from development_ops.backlog import BacklogDocument, BacklogTask, BacklogTaskStatus
from development_ops.child_config import ChildOrchestrationConfig
from development_ops.child_lifecycle import ChildExecutionState
from development_ops.child_orchestration import ChildOrchestrator
from development_ops.github_client import AutoMergeAttempt, PullRequestState
from development_ops.persistence.child_repository import (
    ChildExecutionRepository,
    ChildTransitionConflict,
)
from development_ops.persistence.coordinator_repository import (
    CoordinatorTaskRepository,
)
from development_ops.persistence.orm import ChildExecutionORM
from development_ops.persistence.settings_repository import (
    OrchestrationSettingsRepository,
)
from development_ops.persistence.worktree_repository import (
    AgentWorktreeRepository,
)
from development_ops.recorder import ActivityRecorder
from development_ops.task_worktrees import TaskWorktreeOrchestrator
from development_ops.taxonomy import EventType
from development_ops.worktrees import WorktreeManager
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from wasatch_api.testing.postgres import assert_engine_is_disposable


def _git(args: list[str], cwd: Path) -> str:
    result = subprocess.run(
        ["git", *args], cwd=str(cwd), capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} failed: {result.stderr}")
    return result.stdout.strip()


def _init_repo(root: Path) -> None:
    _git(["init", "-q", "-b", "main"], root)
    _git(["config", "user.email", "t@t.t"], root)
    _git(["config", "user.name", "t"], root)
    (root / "README.md").write_text("base\n", encoding="utf-8")
    _git(["add", "-A"], root)
    _git(["commit", "-qm", "main base"], root)


@pytest.fixture
def repo(tmp_path: Path) -> tuple[Path, Path]:
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", str(origin)], check=True)
    seed = tmp_path / "seed"
    seed.mkdir()
    _init_repo(seed)
    _git(["checkout", "-q", "-b", "ai-dev"], seed)
    (seed / "ai.txt").write_text("ai-dev only\n", encoding="utf-8")
    _git(["add", "-A"], seed)
    _git(["commit", "-qm", "ai-dev change"], seed)
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


@pytest.fixture(autouse=True)
def _clean_disposable_ops_tables(ops_test_engine: Engine) -> None:
    assert_engine_is_disposable(ops_test_engine)
    with ops_test_engine.begin() as connection:
        connection.execute(text("DELETE FROM development_ops.child_executions"))
        connection.execute(text("DELETE FROM development_ops.orchestration_settings"))
        connection.execute(text("DELETE FROM development_ops.agent_worktrees"))
        connection.execute(text("DELETE FROM development_ops.activity_events"))
        connection.execute(text("DELETE FROM development_ops.coordinator_tasks"))


@pytest.fixture
def session(ops_test_engine: Engine) -> Session:
    factory = sessionmaker(bind=ops_test_engine, autoflush=False)
    session = factory()
    yield session
    session.close()


class RecordingLauncher:
    """A stub child-agent launcher. Records payloads; never calls a model."""

    def __init__(self, *, fail: bool = False) -> None:
        self.payloads: list[dict] = []
        self._fail = fail
        self._counter = 0

    def launch(self, payload: dict) -> str:
        self.payloads.append(payload)
        if self._fail:
            raise RuntimeError("simulated launch failure")
        self._counter += 1
        return f"conv-{self._counter}"


class FakeObserver:
    """A fake agent-server observer with per-conversation scripted responses."""

    def __init__(
        self,
        *,
        counts: dict[str, int | None] | None = None,
        health: dict[str, ConversationHealth] | None = None,
        reachable: bool = True,
    ) -> None:
        self._counts = counts or {}
        self._health = health or {}
        self._reachable = reachable
        self.base_url = "http://fake-agent-server"

    def observe(self, conversation_id: str) -> ConversationObservation:
        health = self._health.get(conversation_id, ConversationHealth.REACHABLE)
        return ConversationObservation(
            conversation_id=conversation_id,
            health=health,
            event_count=self._counts.get(conversation_id),
        )

    def ping(self) -> bool:
        return self._reachable


class FakeGitHub:
    def __init__(self, prs: dict[int, PullRequestState] | None = None) -> None:
        self._prs = prs or {}

    def get_pull_request(self, repository: str, number: int) -> PullRequestState:
        if number not in self._prs:
            raise RuntimeError(f"no such pull request {number}")
        return self._prs[number]

    def list_open_pull_requests(self, repository: str) -> list[PullRequestState]:
        return [pr for pr in self._prs.values() if not pr.merged and not pr.closed]

    def enable_squash_auto_merge(
        self, repository: str, number: int
    ) -> AutoMergeAttempt:  # pragma: no cover - unused
        return AutoMergeAttempt(number, False, False, error="not used")


def _pr(number: int, *, merged: bool = False, closed: bool = False) -> PullRequestState:
    return PullRequestState(
        number=number,
        state="MERGED" if merged else ("CLOSED" if closed else "OPEN"),
        merged=merged,
        mergeable="MERGEABLE",
        head_ref=f"cursor/task-{number}",
        base_ref="ai-dev",
        node_id=f"PR_node_{number}",
        auto_merge_enabled=False,
        checks_green=True,
        review_decision="APPROVED",
        closed=closed or merged,
        checks_state="green",
    )


def _backlog(*task_ids: str) -> BacklogDocument:
    return BacklogDocument(
        repository="anotherhale/ai-solutions-lab",
        tasks=[
            BacklogTask(
                id=task_id,
                title=f"Task {task_id}",
                status=BacklogTaskStatus.PENDING,
            )
            for task_id in task_ids
        ],
    )


def _claim(session: Session, task_id: str, run_id: uuid.UUID) -> None:
    repo = CoordinatorTaskRepository(session)
    claimed = repo.claim_for_implementation(
        task_id, run_id=run_id, owner_agent="coordinator"
    )
    assert claimed, f"could not claim {task_id}"


def _make_orchestrator(
    session: Session,
    repo: tuple[Path, Path],
    *,
    launcher: RecordingLauncher | None = None,
    observer: FakeObserver | None = None,
    config: ChildOrchestrationConfig | None = None,
    settings: dict | None = None,
    run_id: uuid.UUID | None = None,
    github: FakeGitHub | None = None,
) -> ChildOrchestrator:
    work, wt_root = repo
    manager = WorktreeManager(work, wt_root)
    worktrees = TaskWorktreeOrchestrator(
        session,
        manager,
        repository="anotherhale/ai-solutions-lab",
        launcher=launcher,
        github=github,
    )
    return ChildOrchestrator(
        session,
        config=config or ChildOrchestrationConfig(),
        worktrees=worktrees,
        recorder=ActivityRecorder(session, notify_slack=False),
        run_id=run_id or uuid.uuid4(),
        repository="anotherhale/ai-solutions-lab",
        observer=observer or FakeObserver(),
        settings_loader=(lambda: settings) if settings is not None else None,
        owner_agent="coordinator",
    )


def _prepare_and_enable(
    session: Session,
    orchestrator: ChildOrchestrator,
    *,
    task_id: str,
    title: str = "",
) -> None:
    """Claim a task, prepare its worktree, and durably enable child execution."""
    orchestrator._settings.set_child_execution_enabled(True, by="test")  # noqa: SLF001
    orchestrator._worktrees.prepare(task_id, title=title or task_id)  # noqa: SLF001


# --- concurrency ----------------------------------------------------------


def test_two_simultaneous_children_accepted(
    session: Session, repo: tuple[Path, Path]
) -> None:
    document = _backlog("T-A", "T-B")
    CoordinatorTaskRepository(session).sync_catalog(document)
    run_id = uuid.uuid4()
    _claim(session, "T-A", run_id)
    _claim(session, "T-B", run_id)
    launcher = RecordingLauncher()
    orchestrator = _make_orchestrator(
        session, repo, launcher=launcher, settings={"llm": {}}
    )
    _prepare_and_enable(session, orchestrator, task_id="T-A")
    _prepare_and_enable(session, orchestrator, task_id="T-B")

    outcome = orchestrator.tick(paused=False)
    assert set(outcome.launched) == {"T-A", "T-B"}
    assert outcome.active_children == 2
    assert len(launcher.payloads) == 2


def test_third_execution_rejected_at_limit(
    session: Session, repo: tuple[Path, Path]
) -> None:
    document = _backlog("T-A", "T-B", "T-C")
    CoordinatorTaskRepository(session).sync_catalog(document)
    run_id = uuid.uuid4()
    for task_id in ("T-A", "T-B", "T-C"):
        _claim(session, task_id, run_id)
    launcher = RecordingLauncher()
    orchestrator = _make_orchestrator(
        session, repo, launcher=launcher, settings={"llm": {}}
    )
    for task_id in ("T-A", "T-B", "T-C"):
        _prepare_and_enable(session, orchestrator, task_id=task_id)

    outcome = orchestrator.tick(paused=False)
    assert len(outcome.launched) == 2
    assert "T-C" in outcome.rejected
    assert outcome.active_children == 2
    # The rejected task stays claimed and unlaunched; no third payload.
    assert len(launcher.payloads) == 2
    assert ChildExecutionRepository(session).get_active_for_task("T-C") is None


def test_duplicate_task_launch_is_idempotent(
    session: Session, repo: tuple[Path, Path]
) -> None:
    document = _backlog("T-DUP")
    CoordinatorTaskRepository(session).sync_catalog(document)
    _claim(session, "T-DUP", uuid.uuid4())
    launcher = RecordingLauncher()
    orchestrator = _make_orchestrator(
        session, repo, launcher=launcher, settings={"llm": {}}
    )
    _prepare_and_enable(session, orchestrator, task_id="T-DUP")

    first = orchestrator.tick(paused=False)
    second = orchestrator.tick(paused=False)
    assert first.launched == ("T-DUP",)
    # The second tick finds an active execution and never relaunches.
    assert second.launched == ()
    assert len(launcher.payloads) == 1


def test_separate_tasks_get_separate_worktrees(
    session: Session, repo: tuple[Path, Path]
) -> None:
    document = _backlog("T-A", "T-B")
    CoordinatorTaskRepository(session).sync_catalog(document)
    run_id = uuid.uuid4()
    _claim(session, "T-A", run_id)
    _claim(session, "T-B", run_id)
    launcher = RecordingLauncher()
    orchestrator = _make_orchestrator(
        session, repo, launcher=launcher, settings={"llm": {}}
    )
    _prepare_and_enable(session, orchestrator, task_id="T-A")
    _prepare_and_enable(session, orchestrator, task_id="T-B")
    orchestrator.tick(paused=False)

    registry = AgentWorktreeRepository(session)
    a = registry.get("T-A")
    b = registry.get("T-B")
    assert a is not None and b is not None
    assert a.worktree_path != b.worktree_path
    assert a.branch_name != b.branch_name


def test_worktree_starts_from_origin_ai_dev(
    session: Session, repo: tuple[Path, Path]
) -> None:
    work, _ = repo
    expected_sha = _git(["rev-parse", "origin/ai-dev"], work)
    document = _backlog("T-BASE")
    CoordinatorTaskRepository(session).sync_catalog(document)
    _claim(session, "T-BASE", uuid.uuid4())
    orchestrator = _make_orchestrator(
        session, repo, launcher=RecordingLauncher(), settings={"llm": {}}
    )
    _prepare_and_enable(session, orchestrator, task_id="T-BASE")
    orchestrator.tick(paused=False)

    record = AgentWorktreeRepository(session).get("T-BASE")
    assert record is not None
    assert record.base_ref == "origin/ai-dev"
    assert record.base_sha == expected_sha


def test_launch_uses_local_workspace_and_worktree_false(
    session: Session, repo: tuple[Path, Path]
) -> None:
    document = _backlog("T-WS")
    CoordinatorTaskRepository(session).sync_catalog(document)
    _claim(session, "T-WS", uuid.uuid4())
    launcher = RecordingLauncher()
    orchestrator = _make_orchestrator(
        session, repo, launcher=launcher, settings={"llm": {}}
    )
    _prepare_and_enable(session, orchestrator, task_id="T-WS")
    orchestrator.tick(paused=False)

    payload = launcher.payloads[0]
    record = AgentWorktreeRepository(session).get("T-WS")
    assert record is not None
    assert payload["workspace"]["kind"] == "LocalWorkspace"
    assert payload["workspace"]["working_dir"] == record.worktree_path
    assert payload["worktree"] is False


def test_no_shared_workspace_fallback_without_worktrees(
    session: Session, repo: tuple[Path, Path]
) -> None:
    """Without a worktree orchestrator, no child is launched at all."""
    document = _backlog("T-NOWT")
    CoordinatorTaskRepository(session).sync_catalog(document)
    _claim(session, "T-NOWT", uuid.uuid4())
    orchestrator = ChildOrchestrator(
        session,
        config=ChildOrchestrationConfig(),
        worktrees=None,
        recorder=ActivityRecorder(session, notify_slack=False),
        run_id=uuid.uuid4(),
        repository="anotherhale/ai-solutions-lab",
        observer=FakeObserver(),
        settings_loader=lambda: {"llm": {}},
    )
    orchestrator._settings.set_child_execution_enabled(True, by="test")  # noqa: SLF001
    outcome = orchestrator.tick(paused=False)
    assert outcome.launched == ()
    assert ChildExecutionRepository(session).get_active_for_task("T-NOWT") is None


def test_conversation_identity_persists(
    session: Session, repo: tuple[Path, Path]
) -> None:
    document = _backlog("T-ID")
    CoordinatorTaskRepository(session).sync_catalog(document)
    _claim(session, "T-ID", uuid.uuid4())
    orchestrator = _make_orchestrator(
        session, repo, launcher=RecordingLauncher(), settings={"llm": {}}
    )
    _prepare_and_enable(session, orchestrator, task_id="T-ID")
    orchestrator.tick(paused=False)

    record = ChildExecutionRepository(session).get_active_for_task("T-ID")
    assert record is not None
    assert record.conversation_id == "conv-1"
    assert record.state == ChildExecutionState.RUNNING


# --- failure handling -----------------------------------------------------


def test_launch_failure_marks_failed_and_bounded(
    session: Session, repo: tuple[Path, Path]
) -> None:
    document = _backlog("T-FAIL")
    CoordinatorTaskRepository(session).sync_catalog(document)
    _claim(session, "T-FAIL", uuid.uuid4())
    launcher = RecordingLauncher(fail=True)
    orchestrator = _make_orchestrator(
        session, repo, launcher=launcher, settings={"llm": {}}
    )
    _prepare_and_enable(session, orchestrator, task_id="T-FAIL")

    orchestrator.tick(paused=False)
    record = ChildExecutionRepository(session).latest_for_task("T-FAIL")
    assert record is not None
    assert record.state == ChildExecutionState.FAILED
    assert record.retry_count == 1
    # A failed execution no longer consumes a slot.
    assert ChildExecutionRepository(session).count_active() == 0


def test_launch_timeout_is_bounded_and_retried(
    session: Session, repo: tuple[Path, Path]
) -> None:
    """A launch that exceeds the timeout is bounded, marked failed, and retried."""
    import time

    document = _backlog("T-TIMEOUT")
    CoordinatorTaskRepository(session).sync_catalog(document)
    _claim(session, "T-TIMEOUT", uuid.uuid4())

    class SlowLauncher:
        def __init__(self) -> None:
            self.calls = 0

        def launch(self, payload: dict) -> str:
            self.calls += 1
            time.sleep(1.0)
            return "conv-slow"

    launcher = SlowLauncher()
    config = ChildOrchestrationConfig(launch_timeout_seconds=0.05)
    orchestrator = _make_orchestrator(
        session, repo, launcher=launcher, config=config, settings={"llm": {}}
    )
    _prepare_and_enable(session, orchestrator, task_id="T-TIMEOUT")

    started = time.monotonic()
    orchestrator.tick(paused=False)
    elapsed = time.monotonic() - started
    # The tick returns promptly rather than blocking on the 1s launch.
    assert elapsed < 0.5
    record = ChildExecutionRepository(session).latest_for_task("T-TIMEOUT")
    assert record is not None
    assert record.state == ChildExecutionState.FAILED
    assert record.retry_count == 1


def test_missing_conversation_escalates_to_operator(
    session: Session, repo: tuple[Path, Path]
) -> None:
    document = _backlog("T-GONE")
    CoordinatorTaskRepository(session).sync_catalog(document)
    _claim(session, "T-GONE", uuid.uuid4())
    observer = FakeObserver(health={"conv-1": ConversationHealth.MISSING})
    orchestrator = _make_orchestrator(
        session,
        repo,
        launcher=RecordingLauncher(),
        observer=observer,
        settings={"llm": {}},
    )
    _prepare_and_enable(session, orchestrator, task_id="T-GONE")
    orchestrator.tick(paused=False)
    orchestrator.tick(paused=False)

    record = ChildExecutionRepository(session).latest_for_task("T-GONE")
    assert record is not None
    assert record.state == ChildExecutionState.FAILED
    assert record.operator_intervention is True


def test_agent_server_unavailable_is_not_a_failure(
    session: Session, repo: tuple[Path, Path]
) -> None:
    document = _backlog("T-DOWN")
    CoordinatorTaskRepository(session).sync_catalog(document)
    _claim(session, "T-DOWN", uuid.uuid4())
    observer = FakeObserver(health={"conv-1": ConversationHealth.UNREACHABLE})
    orchestrator = _make_orchestrator(
        session,
        repo,
        launcher=RecordingLauncher(),
        observer=observer,
        settings={"llm": {}},
    )
    _prepare_and_enable(session, orchestrator, task_id="T-DOWN")
    orchestrator.tick(paused=False)
    orchestrator.tick(paused=False)

    record = ChildExecutionRepository(session).get_active_for_task("T-DOWN")
    # A transient outage must not fail the child; it is still active.
    assert record is not None
    assert record.state == ChildExecutionState.RUNNING


# --- progress and stall ---------------------------------------------------


def test_meaningful_progress_advances_and_renews(
    session: Session, repo: tuple[Path, Path]
) -> None:
    document = _backlog("T-PROG")
    CoordinatorTaskRepository(session).sync_catalog(document)
    _claim(session, "T-PROG", uuid.uuid4())
    observer = FakeObserver(counts={"conv-1": 10})
    orchestrator = _make_orchestrator(
        session,
        repo,
        launcher=RecordingLauncher(),
        observer=observer,
        settings={"llm": {}},
    )
    _prepare_and_enable(session, orchestrator, task_id="T-PROG")
    orchestrator.tick(paused=False)

    before = ChildExecutionRepository(session).get_active_for_task("T-PROG")
    assert before is not None
    orchestrator.tick(paused=False)
    after = ChildExecutionRepository(session).get_active_for_task("T-PROG")
    assert after is not None
    assert after.progress_seq == before.progress_seq + 1
    assert after.last_event_count == 10
    assert after.last_progress_at is not None


def test_polling_success_alone_is_not_progress(
    session: Session, repo: tuple[Path, Path]
) -> None:
    """An unchanged event count must not advance the progress sequence."""
    document = _backlog("T-IDLE")
    CoordinatorTaskRepository(session).sync_catalog(document)
    _claim(session, "T-IDLE", uuid.uuid4())
    observer = FakeObserver(counts={"conv-1": 5})
    orchestrator = _make_orchestrator(
        session,
        repo,
        launcher=RecordingLauncher(),
        observer=observer,
        settings={"llm": {}},
    )
    _prepare_and_enable(session, orchestrator, task_id="T-IDLE")
    orchestrator.tick(paused=False)
    orchestrator.tick(paused=False)  # same count: no new progress

    record = ChildExecutionRepository(session).get_active_for_task("T-IDLE")
    assert record is not None
    # Only the first observation of a count is progress; a repeat is not.
    assert record.progress_seq == 1


def test_live_but_stalled_child_is_classified(
    session: Session, repo: tuple[Path, Path]
) -> None:
    document = _backlog("T-STALL")
    CoordinatorTaskRepository(session).sync_catalog(document)
    _claim(session, "T-STALL", uuid.uuid4())
    # Zero stall threshold forces immediate classification.
    config = ChildOrchestrationConfig(heartbeat_seconds=0.001, stall_seconds=0.002)
    observer = FakeObserver(counts={"conv-1": None})
    orchestrator = _make_orchestrator(
        session,
        repo,
        launcher=RecordingLauncher(),
        observer=observer,
        config=config,
        settings={"llm": {}},
    )
    _prepare_and_enable(session, orchestrator, task_id="T-STALL")
    orchestrator.tick(paused=False)
    import time

    time.sleep(0.01)
    outcome = orchestrator.tick(paused=False)
    assert "T-STALL" in outcome.stalled
    record = ChildExecutionRepository(session).get_active_for_task("T-STALL")
    assert record is not None
    assert record.state == ChildExecutionState.STALLED


def test_stalled_child_recovers_on_progress(
    session: Session, repo: tuple[Path, Path]
) -> None:
    document = _backlog("T-REC")
    CoordinatorTaskRepository(session).sync_catalog(document)
    _claim(session, "T-REC", uuid.uuid4())
    config = ChildOrchestrationConfig(heartbeat_seconds=0.001, stall_seconds=0.002)
    # No event count at first, so the child makes no observable progress.
    observer = FakeObserver(counts={})
    orchestrator = _make_orchestrator(
        session,
        repo,
        launcher=RecordingLauncher(),
        observer=observer,
        config=config,
        settings={"llm": {}},
    )
    _prepare_and_enable(session, orchestrator, task_id="T-REC")
    orchestrator.tick(paused=False)
    import time

    time.sleep(0.01)
    orchestrator.tick(paused=False)  # classify stalled (no progress)
    stalled = ChildExecutionRepository(session).get_active_for_task("T-REC")
    assert stalled is not None and stalled.state == ChildExecutionState.STALLED

    observer._counts["conv-1"] = 99  # new progress arrives
    orchestrator.tick(paused=False)
    recovered = ChildExecutionRepository(session).get_active_for_task("T-REC")
    assert recovered is not None
    assert recovered.state == ChildExecutionState.RUNNING


# --- restart / recovery ---------------------------------------------------


def test_restart_with_running_child_does_not_relaunch(
    session: Session, repo: tuple[Path, Path]
) -> None:
    document = _backlog("T-RESTART")
    CoordinatorTaskRepository(session).sync_catalog(document)
    _claim(session, "T-RESTART", uuid.uuid4())
    launcher = RecordingLauncher()
    orchestrator = _make_orchestrator(
        session, repo, launcher=launcher, settings={"llm": {}}
    )
    _prepare_and_enable(session, orchestrator, task_id="T-RESTART")
    orchestrator.tick(paused=False)
    assert len(launcher.payloads) == 1

    # Simulate a coordinator restart: a brand-new orchestrator on the same DB.
    restarted = _make_orchestrator(
        session, repo, launcher=launcher, settings={"llm": {}}
    )
    restarted.tick(paused=False)
    # The running child is still owned; no second conversation.
    assert len(launcher.payloads) == 1


def test_unlaunched_child_is_recovered_and_launched(
    session: Session, repo: tuple[Path, Path]
) -> None:
    """A claimed row with no conversation is safe to (re)launch after restart."""
    document = _backlog("T-UNLAUNCHED")
    CoordinatorTaskRepository(session).sync_catalog(document)
    _claim(session, "T-UNLAUNCHED", uuid.uuid4())
    launcher = RecordingLauncher()
    orchestrator = _make_orchestrator(
        session, repo, launcher=launcher, settings={"llm": {}}
    )
    _prepare_and_enable(session, orchestrator, task_id="T-UNLAUNCHED")
    # Simulate a crash after registration but before launch.
    registry = AgentWorktreeRepository(session).get("T-UNLAUNCHED")
    assert registry is not None
    orchestrator._executions.register(  # noqa: SLF001
        "T-UNLAUNCHED",
        run_id=uuid.uuid4(),
        owner_agent="coordinator",
        lease_seconds=900,
        worktree_path=registry.worktree_path,
        branch_name=registry.branch_name,
    )
    record = ChildExecutionRepository(session).get_active_for_task("T-UNLAUNCHED")
    assert record is not None and record.conversation_id is None

    outcome = orchestrator.tick(paused=False)
    assert "T-UNLAUNCHED" in outcome.launched
    assert len(launcher.payloads) == 1


# --- PR lifecycle and slot accounting -------------------------------------


def test_pr_open_releases_slot(session: Session, repo: tuple[Path, Path]) -> None:
    document = _backlog("T-PR")
    CoordinatorTaskRepository(session).sync_catalog(document)
    run_id = uuid.uuid4()
    _claim(session, "T-PR", run_id)
    orchestrator = _make_orchestrator(
        session, repo, launcher=RecordingLauncher(), settings={"llm": {}}
    )
    _prepare_and_enable(session, orchestrator, task_id="T-PR")
    orchestrator.tick(paused=False)
    assert ChildExecutionRepository(session).count_active() == 1

    # The engine reconciles a PR and moves the task to pr_open.
    CoordinatorTaskRepository(session).mark_pr_open(
        "T-PR",
        run_id=run_id,
        branch_name="cursor/T-PR",
        pr_number=700,
        owner_agent="coordinator",
    )
    orchestrator.tick(paused=False)
    record = ChildExecutionRepository(session).latest_for_task("T-PR")
    assert record is not None
    assert record.state == ChildExecutionState.PR_OPEN
    # A PR-open child no longer consumes an implementation slot.
    assert ChildExecutionRepository(session).count_active() == 0


def test_closed_unmerged_pr_is_preserved_and_escalated(
    session: Session, repo: tuple[Path, Path]
) -> None:
    document = _backlog("T-CLOSED")
    CoordinatorTaskRepository(session).sync_catalog(document)
    _claim(session, "T-CLOSED", uuid.uuid4())
    orchestrator = _make_orchestrator(
        session, repo, launcher=RecordingLauncher(), settings={"llm": {}}
    )
    _prepare_and_enable(session, orchestrator, task_id="T-CLOSED")
    orchestrator.tick(paused=False)

    CoordinatorTaskRepository(session).mark_blocked(
        "T-CLOSED", "pull request #800 closed without merge"
    )
    orchestrator.tick(paused=False)
    record = ChildExecutionRepository(session).latest_for_task("T-CLOSED")
    assert record is not None
    # Not treated as success; the worktree registration survives.
    assert record.state == ChildExecutionState.FAILED
    assert record.operator_intervention is True
    assert AgentWorktreeRepository(session).get("T-CLOSED") is not None


def test_merged_aligns_child_state(session: Session, repo: tuple[Path, Path]) -> None:
    document = _backlog("T-MERGE")
    CoordinatorTaskRepository(session).sync_catalog(document)
    _claim(session, "T-MERGE", uuid.uuid4())
    orchestrator = _make_orchestrator(
        session, repo, launcher=RecordingLauncher(), settings={"llm": {}}
    )
    _prepare_and_enable(session, orchestrator, task_id="T-MERGE")
    orchestrator.tick(paused=False)

    CoordinatorTaskRepository(session).mark_merged("T-MERGE", merge_commit_sha="abc")
    orchestrator.tick(paused=False)
    record = ChildExecutionRepository(session).latest_for_task("T-MERGE")
    assert record is not None
    assert record.state == ChildExecutionState.MERGED


# --- pause / enable / disable ---------------------------------------------


def test_pause_prevents_new_launch(session: Session, repo: tuple[Path, Path]) -> None:
    document = _backlog("T-PAUSE")
    CoordinatorTaskRepository(session).sync_catalog(document)
    _claim(session, "T-PAUSE", uuid.uuid4())
    launcher = RecordingLauncher()
    orchestrator = _make_orchestrator(
        session, repo, launcher=launcher, settings={"llm": {}}
    )
    _prepare_and_enable(session, orchestrator, task_id="T-PAUSE")

    outcome = orchestrator.tick(paused=True)
    assert outcome.launched == ()
    assert launcher.payloads == []


def test_pause_does_not_stop_monitoring(
    session: Session, repo: tuple[Path, Path]
) -> None:
    document = _backlog("T-PAUSE2")
    CoordinatorTaskRepository(session).sync_catalog(document)
    _claim(session, "T-PAUSE2", uuid.uuid4())
    observer = FakeObserver(counts={"conv-1": 3})
    orchestrator = _make_orchestrator(
        session,
        repo,
        launcher=RecordingLauncher(),
        observer=observer,
        settings={"llm": {}},
    )
    _prepare_and_enable(session, orchestrator, task_id="T-PAUSE2")
    orchestrator.tick(paused=False)

    before = ChildExecutionRepository(session).get_active_for_task("T-PAUSE2")
    assert before is not None
    orchestrator.tick(paused=True)
    after = ChildExecutionRepository(session).get_active_for_task("T-PAUSE2")
    assert after is not None
    # Monitoring continues while paused: progress still advanced.
    assert after.progress_seq == before.progress_seq + 1


def test_disabled_survives_restart_and_blocks_launch(
    session: Session, repo: tuple[Path, Path]
) -> None:
    document = _backlog("T-DISABLED")
    CoordinatorTaskRepository(session).sync_catalog(document)
    _claim(session, "T-DISABLED", uuid.uuid4())
    launcher = RecordingLauncher()
    orchestrator = _make_orchestrator(
        session, repo, launcher=launcher, settings={"llm": {}}
    )
    # Explicitly disabled (the default) and durable.
    orchestrator._worktrees.prepare("T-DISABLED", title="x")  # noqa: SLF001
    outcome = orchestrator.tick(paused=False)
    assert outcome.enabled is False
    assert outcome.launched == ()
    assert launcher.payloads == []

    # A fresh orchestrator (restart) still sees disabled.
    restarted = _make_orchestrator(
        session, repo, launcher=launcher, settings={"llm": {}}
    )
    assert restarted.is_enabled()[0] is False


def test_explicit_enable_then_disable(
    session: Session, repo: tuple[Path, Path]
) -> None:
    orchestrator = _make_orchestrator(
        session, repo, launcher=RecordingLauncher(), settings={"llm": {}}
    )
    assert orchestrator.is_enabled()[0] is False
    enabled = orchestrator.set_enabled(True, by="operator", reason="test")
    assert enabled.enabled is True
    assert OrchestrationSettingsRepository(session).child_execution_enabled() is True
    disabled = orchestrator.set_enabled(False, by="operator", reason="done")
    assert disabled.enabled is False
    assert OrchestrationSettingsRepository(session).child_execution_enabled() is False


def test_disabling_does_not_kill_active_child(
    session: Session, repo: tuple[Path, Path]
) -> None:
    document = _backlog("T-KEEP")
    CoordinatorTaskRepository(session).sync_catalog(document)
    _claim(session, "T-KEEP", uuid.uuid4())
    orchestrator = _make_orchestrator(
        session,
        repo,
        launcher=RecordingLauncher(),
        settings={"llm": {}},
    )
    _prepare_and_enable(session, orchestrator, task_id="T-KEEP")
    orchestrator.tick(paused=False)
    active = ChildExecutionRepository(session).get_active_for_task("T-KEEP")
    assert active is not None

    orchestrator.set_enabled(False, by="operator")
    # Disabling stops new launches but leaves the active child in place.
    still = ChildExecutionRepository(session).get_active_for_task("T-KEEP")
    assert still is not None
    assert still.execution_id == active.execution_id


# --- status / telemetry ---------------------------------------------------


def test_status_reports_concurrency_and_children(
    session: Session, repo: tuple[Path, Path]
) -> None:
    document = _backlog("T-STAT")
    CoordinatorTaskRepository(session).sync_catalog(document)
    _claim(session, "T-STAT", uuid.uuid4())
    orchestrator = _make_orchestrator(
        session, repo, launcher=RecordingLauncher(), settings={"llm": {}}
    )
    _prepare_and_enable(session, orchestrator, task_id="T-STAT")
    orchestrator.tick(paused=False)

    status = orchestrator.status()
    assert status.enabled is True
    assert status.max_concurrent == 2
    assert status.active_children == 1
    assert status.available_slots == 1
    assert status.agent_server_reachable is True
    assert any(view.task_id == "T-STAT" for view in status.children)
    child = next(view for view in status.children if view.task_id == "T-STAT")
    assert child.conversation_id == "conv-1"
    assert child.worktree_path is not None
    assert child.branch_name == "cursor/T-STAT"


def test_telemetry_events_correlate_task_and_conversation(
    session: Session, repo: tuple[Path, Path]
) -> None:
    document = _backlog("T-TEL")
    CoordinatorTaskRepository(session).sync_catalog(document)
    run_id = uuid.uuid4()
    _claim(session, "T-TEL", run_id)
    orchestrator = _make_orchestrator(
        session,
        repo,
        launcher=RecordingLauncher(),
        settings={"llm": {}},
        run_id=run_id,
    )
    _prepare_and_enable(session, orchestrator, task_id="T-TEL")
    orchestrator.tick(paused=False)

    rows = session.execute(
        text(
            "SELECT event_type, task_id, metadata FROM development_ops.activity_events "
            "WHERE task_id = 'T-TEL'"
        )
    ).all()
    types = {row.event_type for row in rows}
    assert EventType.CHILD_CLAIMED.value in types
    assert EventType.CHILD_LAUNCH_SUCCEEDED.value in types
    launched = next(
        row for row in rows if row.event_type == EventType.CHILD_LAUNCH_SUCCEEDED.value
    )
    assert launched.metadata["conversation_id"] == "conv-1"
    assert launched.metadata["run_id"] == str(run_id)


def test_secrets_never_recorded_in_events(
    session: Session, repo: tuple[Path, Path]
) -> None:
    secret = "sk-" + "super-secret-token-value"
    document = _backlog("T-SECRET")
    CoordinatorTaskRepository(session).sync_catalog(document)
    _claim(session, "T-SECRET", uuid.uuid4())
    orchestrator = _make_orchestrator(
        session,
        repo,
        launcher=RecordingLauncher(),
        settings={"llm": {"api_key": secret}},
    )
    _prepare_and_enable(session, orchestrator, task_id="T-SECRET")
    orchestrator.tick(paused=False)

    rows = session.execute(
        text(
            "SELECT title, summary, metadata::text AS meta "
            "FROM development_ops.activity_events"
        )
    ).all()
    for row in rows:
        blob = f"{row.title} {row.summary} {row.meta}"
        assert secret not in blob


# --- concurrency under concurrent ticks -----------------------------------


def test_concurrent_ticks_cannot_oversubscribe(
    session: Session, repo: tuple[Path, Path]
) -> None:
    """Two separate engines on two sessions must not both exceed the limit."""
    document = _backlog("T-C1", "T-C2", "T-C3")
    CoordinatorTaskRepository(session).sync_catalog(document)
    run_id = uuid.uuid4()
    for task_id in ("T-C1", "T-C2", "T-C3"):
        _claim(session, task_id, run_id)
    launcher = RecordingLauncher()
    orchestrator = _make_orchestrator(
        session, repo, launcher=launcher, settings={"llm": {}}
    )
    for task_id in ("T-C1", "T-C2", "T-C3"):
        _prepare_and_enable(session, orchestrator, task_id=task_id)

    # Two independent orchestrators sharing one database, as two racing ticks.
    other = _make_orchestrator(session, repo, launcher=launcher, settings={"llm": {}})
    first = orchestrator.tick(paused=False)
    second = other.tick(paused=False)
    total = len(first.launched) + len(second.launched)
    assert total == 2
    assert ChildExecutionRepository(session).count_active() == 2
    assert len(launcher.payloads) == 2


def test_awaiting_merge_does_not_consume_slot(
    session: Session, repo: tuple[Path, Path]
) -> None:
    document = _backlog("T-AW")
    CoordinatorTaskRepository(session).sync_catalog(document)
    run_id = uuid.uuid4()
    _claim(session, "T-AW", run_id)
    orchestrator = _make_orchestrator(
        session, repo, launcher=RecordingLauncher(), settings={"llm": {}}
    )
    _prepare_and_enable(session, orchestrator, task_id="T-AW")
    orchestrator.tick(paused=False)

    CoordinatorTaskRepository(session).mark_pr_open(
        "T-AW",
        run_id=run_id,
        branch_name="cursor/T-AW",
        pr_number=900,
        owner_agent="coordinator",
        awaiting_merge=True,
    )
    orchestrator.tick(paused=False)
    record = ChildExecutionRepository(session).latest_for_task("T-AW")
    assert record is not None
    assert record.state == ChildExecutionState.AWAITING_MERGE
    assert ChildExecutionRepository(session).count_active() == 0


def test_lease_expiry_recovers_unlaunched(
    session: Session, repo: tuple[Path, Path]
) -> None:
    """A never-launched child whose lease expired is safe to re-drive."""
    document = _backlog("T-LEASE")
    CoordinatorTaskRepository(session).sync_catalog(document)
    _claim(session, "T-LEASE", uuid.uuid4())
    launcher = RecordingLauncher()
    orchestrator = _make_orchestrator(
        session, repo, launcher=launcher, settings={"llm": {}}
    )
    _prepare_and_enable(session, orchestrator, task_id="T-LEASE")
    registry = AgentWorktreeRepository(session).get("T-LEASE")
    assert registry is not None
    # A crashed registration with a lease that has already expired.
    record = orchestrator._executions.register(  # noqa: SLF001
        "T-LEASE",
        run_id=uuid.uuid4(),
        owner_agent="coordinator",
        lease_seconds=1,
        worktree_path=registry.worktree_path,
        branch_name=registry.branch_name,
    )
    # Force the lease into the past.
    session.execute(
        text(
            "UPDATE development_ops.child_executions "
            "SET lease_expires_at = now() - interval '1 hour' "
            "WHERE execution_id = :id"
        ),
        {"id": record.execution_id},
    )
    session.commit()

    outcome = orchestrator.tick(paused=False)
    assert "T-LEASE" in outcome.launched
    assert len(launcher.payloads) == 1


def test_worktree_cleanup_only_after_verified_merge(
    session: Session, repo: tuple[Path, Path]
) -> None:
    """The Phase C cleanup gate still refuses an unmerged PR."""
    document = _backlog("T-CLEAN")
    CoordinatorTaskRepository(session).sync_catalog(document)
    run_id = uuid.uuid4()
    _claim(session, "T-CLEAN", run_id)
    github = FakeGitHub({950: _pr(950, merged=False)})
    orchestrator = _make_orchestrator(
        session,
        repo,
        launcher=RecordingLauncher(),
        settings={"llm": {}},
        github=github,
    )
    _prepare_and_enable(session, orchestrator, task_id="T-CLEAN")
    orchestrator.tick(paused=False)
    orchestrator._worktrees.register_pull_request("T-CLEAN", 950)  # noqa: SLF001

    outcome = orchestrator._worktrees.cleanup_after_merge("T-CLEAN")  # noqa: SLF001
    assert outcome.cleaned is False
    assert outcome.verified_merge is False
    record = AgentWorktreeRepository(session).get("T-CLEAN")
    assert record is not None
    assert Path(record.worktree_path).exists()


# --- persistence guard ----------------------------------------------------


def test_repository_rejects_illegal_transition(
    session: Session, repo: tuple[Path, Path]
) -> None:
    document = _backlog("T-ILLEGAL")
    CoordinatorTaskRepository(session).sync_catalog(document)
    _claim(session, "T-ILLEGAL", uuid.uuid4())
    orchestrator = _make_orchestrator(
        session, repo, launcher=RecordingLauncher(), settings={"llm": {}}
    )
    _prepare_and_enable(session, orchestrator, task_id="T-ILLEGAL")
    orchestrator.tick(paused=False)
    record = ChildExecutionRepository(session).get_active_for_task("T-ILLEGAL")
    assert record is not None
    from development_ops.child_lifecycle import IllegalChildTransition

    with pytest.raises(IllegalChildTransition):
        ChildExecutionRepository(session).transition(
            record.execution_id, ChildExecutionState.QUEUED
        )


def test_one_active_execution_per_task_enforced(
    session: Session, repo: tuple[Path, Path]
) -> None:
    document = _backlog("T-ONE")
    CoordinatorTaskRepository(session).sync_catalog(document)
    _claim(session, "T-ONE", uuid.uuid4())
    orchestrator = _make_orchestrator(
        session, repo, launcher=RecordingLauncher(), settings={"llm": {}}
    )
    _prepare_and_enable(session, orchestrator, task_id="T-ONE")
    orchestrator.tick(paused=False)

    repo_layer = ChildExecutionRepository(session)
    existing = repo_layer.get_active_for_task("T-ONE")
    assert existing is not None
    # A second register returns the same active execution (idempotent).
    again = repo_layer.register(
        "T-ONE", run_id=uuid.uuid4(), owner_agent="x", lease_seconds=900
    )
    assert again.execution_id == existing.execution_id


def test_transition_conflict_on_stale_state(
    session: Session, repo: tuple[Path, Path], ops_test_engine: Engine
) -> None:
    """A compare-and-set from a stale state updates zero rows and is refused."""
    document = _backlog("T-RACE")
    CoordinatorTaskRepository(session).sync_catalog(document)
    _claim(session, "T-RACE", uuid.uuid4())
    orchestrator = _make_orchestrator(
        session, repo, launcher=RecordingLauncher(), settings={"llm": {}}
    )
    _prepare_and_enable(session, orchestrator, task_id="T-RACE")
    orchestrator.tick(paused=False)
    record = ChildExecutionRepository(session).get_active_for_task("T-RACE")
    assert record is not None
    # Prime this session's identity map with the RUNNING row, holding a strong
    # reference so it is not garbage-collected and re-fetched (SQLAlchemy's
    # identity map uses weak references).
    orm_row = session.get(ChildExecutionORM, record.execution_id)
    assert orm_row is not None and orm_row.state == "running"

    # A second writer moves the row to FAILED while this session still sees it
    # as RUNNING (its identity map is stale).
    other = sessionmaker(bind=ops_test_engine)()
    try:
        ChildExecutionRepository(other).transition(
            record.execution_id, ChildExecutionState.FAILED, failure_reason="raced"
        )
    finally:
        other.close()

    # The stale writer's guard (WHERE state = 'running') matches zero rows.
    with pytest.raises(ChildTransitionConflict):
        ChildExecutionRepository(session).transition(
            record.execution_id, ChildExecutionState.STALLED
        )

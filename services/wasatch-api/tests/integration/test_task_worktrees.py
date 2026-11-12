"""Worktree registry and orchestrator against the disposable ops-test database.

The Git work runs against real temporary repositories; the registry runs against
the disposable ``wasatch_development_ops_test`` database. The operational
``wasatch_development_ops`` database is never touched.
"""

from __future__ import annotations

import subprocess
import uuid
from pathlib import Path

import pytest
from development_ops.child_agents import ChildAgentLaunchError
from development_ops.github_client import AutoMergeAttempt, PullRequestState
from development_ops.persistence.worktree_repository import (
    AgentWorktreeRepository,
    WorktreeState,
)
from development_ops.task_worktrees import TaskWorktreeOrchestrator
from development_ops.worktrees import (
    WorktreeError,
    WorktreeLockedError,
    WorktreeManager,
)
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
        connection.execute(text("DELETE FROM development_ops.agent_worktrees"))
        connection.execute(text("DELETE FROM development_ops.activity_events"))
        connection.execute(text("DELETE FROM development_ops.coordinator_tasks"))


@pytest.fixture
def session(ops_test_engine: Engine) -> Session:
    factory = sessionmaker(bind=ops_test_engine, autoflush=False)
    session = factory()
    yield session
    session.close()


class _RecordingLauncher:
    def __init__(self, *, fail: bool = False) -> None:
        self.payloads: list[dict] = []
        self._fail = fail

    def launch(self, payload: dict) -> str:
        self.payloads.append(payload)
        if self._fail:
            raise ChildAgentLaunchError("simulated launch failure")
        return "conv-test-1"


class _FakeGitHub:
    """Minimal GitHub stand-in: merged state keyed by pull number."""

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
    ) -> AutoMergeAttempt:  # pragma: no cover - not used here
        return AutoMergeAttempt(number, False, False, error="not used")


def _pr(
    number: int,
    *,
    merged: bool = False,
    base_ref: str = "ai-dev",
    closed: bool = False,
) -> PullRequestState:
    return PullRequestState(
        number=number,
        state="MERGED" if merged else ("CLOSED" if closed else "OPEN"),
        merged=merged,
        mergeable="MERGEABLE",
        head_ref=f"cursor/task-{number}",
        base_ref=base_ref,
        node_id=f"PR_node_{number}",
        auto_merge_enabled=False,
        checks_green=True,
        review_decision="APPROVED",
        closed=closed or merged,
        checks_state="green",
    )


def _orchestrator(
    session: Session,
    repo: tuple[Path, Path],
    launcher=None,
    github=None,
) -> TaskWorktreeOrchestrator:
    work, wt_root = repo
    manager = WorktreeManager(work, wt_root)
    return TaskWorktreeOrchestrator(
        session,
        manager,
        repository="anotherhale/ai-solutions-lab",
        launcher=launcher,
        github=github,
        run_id=uuid.uuid4(),
    )


def _merge_branch(repo: tuple[Path, Path], branch: str) -> None:
    work, _ = repo
    _git(["checkout", "-q", "ai-dev"], work)
    _git(["merge", "-q", "--ff-only", branch], work)
    _git(["push", "-q", "origin", "ai-dev"], work)
    _git(["checkout", "-q", "main"], work)


def test_registry_row_links_task_worktree_and_conversation(
    session: Session, repo: tuple[Path, Path]
) -> None:
    launcher = _RecordingLauncher()
    orchestrator = _orchestrator(session, repo, launcher)
    result = orchestrator.launch(
        "PHASE-C-1", title="Isolated worktrees", agent_settings={"llm": {}}
    )
    assert result.launched
    assert result.conversation_id == "conv-test-1"

    record = AgentWorktreeRepository(session).get("PHASE-C-1")
    assert record is not None
    assert record.state == WorktreeState.LAUNCHED
    assert record.conversation_id == "conv-test-1"
    assert record.branch_name == "cursor/PHASE-C-1"
    assert record.base_ref == "origin/ai-dev"
    assert Path(record.worktree_path).exists()

    # The launched payload points at the registered worktree, with server-side
    # worktree creation disabled.
    assert launcher.payloads[0]["workspace"]["working_dir"] == record.worktree_path
    assert launcher.payloads[0]["worktree"] is False


def test_two_tasks_get_two_isolated_worktrees(
    session: Session, repo: tuple[Path, Path]
) -> None:
    launcher = _RecordingLauncher()
    orchestrator = _orchestrator(session, repo, launcher)
    first = orchestrator.launch("PHASE-C-A", title="A", agent_settings={"llm": {}})
    second = orchestrator.launch("PHASE-C-B", title="B", agent_settings={"llm": {}})
    assert first.worktree_path != second.worktree_path
    assert first.branch_name != second.branch_name
    assert first.worktree_path.exists() and second.worktree_path.exists()


def test_duplicate_launch_reuses_conversation(
    session: Session, repo: tuple[Path, Path]
) -> None:
    launcher = _RecordingLauncher()
    orchestrator = _orchestrator(session, repo, launcher)
    first = orchestrator.launch("PHASE-C-DUP", title="dup", agent_settings={"llm": {}})
    second = orchestrator.launch("PHASE-C-DUP", title="dup", agent_settings={"llm": {}})
    assert first.conversation_id == second.conversation_id == "conv-test-1"
    # Only one child conversation was ever started.
    assert len(launcher.payloads) == 1


def test_failed_launch_marks_failed_and_keeps_worktree(
    session: Session, repo: tuple[Path, Path]
) -> None:
    launcher = _RecordingLauncher(fail=True)
    orchestrator = _orchestrator(session, repo, launcher)
    with pytest.raises(ChildAgentLaunchError):
        orchestrator.launch("PHASE-C-2", title="boom", agent_settings={"llm": {}})
    record = AgentWorktreeRepository(session).get("PHASE-C-2")
    assert record is not None
    assert record.state == WorktreeState.FAILED
    # The worktree remains so a retry reuses it instead of leaking another.
    assert Path(record.worktree_path).exists()


def test_recover_interrupted_excludes_live_children(
    session: Session, repo: tuple[Path, Path]
) -> None:
    orchestrator = _orchestrator(session, repo, _RecordingLauncher())
    orchestrator.prepare("PHASE-C-3", title="interrupted")
    orchestrator.launch("PHASE-C-LIVE", title="live", agent_settings={"llm": {}})
    recoverable = orchestrator.recover_interrupted()
    assert "PHASE-C-3" in recoverable
    # A launched child is never reclaimed automatically.
    assert "PHASE-C-LIVE" not in recoverable


def test_concurrent_prepare_is_locked(
    session: Session, repo: tuple[Path, Path]
) -> None:
    """A second prepare for the same task cannot run while the lock is held."""
    work, wt_root = repo
    manager = WorktreeManager(work, wt_root)
    with manager.task_lock("PHASE-C-LOCK"):
        with pytest.raises(WorktreeLockedError):
            manager.prepare("PHASE-C-LOCK")


def test_cleanup_requires_verified_merge(
    session: Session, repo: tuple[Path, Path]
) -> None:
    launcher = _RecordingLauncher()
    github = _FakeGitHub({500: _pr(500, merged=False)})
    orchestrator = _orchestrator(session, repo, launcher, github)
    result = orchestrator.launch(
        "PHASE-C-4", title="merge me", agent_settings={"llm": {}}
    )
    orchestrator.register_pull_request("PHASE-C-4", 500)

    outcome = orchestrator.cleanup_after_merge("PHASE-C-4")
    assert outcome.cleaned is False
    assert outcome.verified_merge is False
    assert result.worktree_path.exists()


def test_cleanup_after_verified_merge_removes_worktree(
    session: Session, repo: tuple[Path, Path]
) -> None:
    launcher = _RecordingLauncher()
    github = _FakeGitHub({501: _pr(501, merged=True)})
    orchestrator = _orchestrator(session, repo, launcher, github)
    result = orchestrator.launch(
        "PHASE-C-5", title="merged", agent_settings={"llm": {}}
    )
    orchestrator.register_pull_request("PHASE-C-5", 501)
    _merge_branch(repo, result.branch_name)

    outcome = orchestrator.cleanup_after_merge("PHASE-C-5")
    assert outcome.cleaned is True
    assert outcome.verified_merge is True
    assert not result.worktree_path.exists()
    record = AgentWorktreeRepository(session).get("PHASE-C-5")
    assert record is not None and record.state == WorktreeState.MERGED


def test_cleanup_refuses_wrong_base_branch(
    session: Session, repo: tuple[Path, Path]
) -> None:
    """A PR merged into main is not eligible for autonomous cleanup."""
    launcher = _RecordingLauncher()
    github = _FakeGitHub({502: _pr(502, merged=True, base_ref="main")})
    orchestrator = _orchestrator(session, repo, launcher, github)
    result = orchestrator.launch("PHASE-C-6", title="main", agent_settings={"llm": {}})
    orchestrator.register_pull_request("PHASE-C-6", 502)

    outcome = orchestrator.cleanup_after_merge("PHASE-C-6")
    assert outcome.cleaned is False
    assert "ai-dev" in outcome.reason
    assert result.worktree_path.exists()


def test_cleanup_refuses_dirty_worktree(
    session: Session, repo: tuple[Path, Path]
) -> None:
    launcher = _RecordingLauncher()
    github = _FakeGitHub({503: _pr(503, merged=True)})
    orchestrator = _orchestrator(session, repo, launcher, github)
    result = orchestrator.launch("PHASE-C-7", title="dirty", agent_settings={"llm": {}})
    orchestrator.register_pull_request("PHASE-C-7", 503)
    (result.worktree_path / "uncommitted.txt").write_text("x\n", encoding="utf-8")

    with pytest.raises(WorktreeError):
        orchestrator.cleanup_after_merge("PHASE-C-7")
    assert result.worktree_path.exists()


def test_cleanup_requires_github_client(
    session: Session, repo: tuple[Path, Path]
) -> None:
    launcher = _RecordingLauncher()
    orchestrator = _orchestrator(session, repo, launcher, github=None)
    orchestrator.launch("PHASE-C-8", title="no github", agent_settings={"llm": {}})
    orchestrator.register_pull_request("PHASE-C-8", 504)
    outcome = orchestrator.cleanup_after_merge("PHASE-C-8")
    assert outcome.cleaned is False
    assert "github" in outcome.reason.lower()


def test_cleanup_is_idempotent(session: Session, repo: tuple[Path, Path]) -> None:
    launcher = _RecordingLauncher()
    github = _FakeGitHub({505: _pr(505, merged=True)})
    orchestrator = _orchestrator(session, repo, launcher, github)
    result = orchestrator.launch("PHASE-C-9", title="twice", agent_settings={"llm": {}})
    orchestrator.register_pull_request("PHASE-C-9", 505)
    _merge_branch(repo, result.branch_name)

    first = orchestrator.cleanup_after_merge("PHASE-C-9")
    assert first.cleaned is True
    # A second cleanup finds the row already MERGED and is a no-op.
    second = orchestrator.cleanup_after_merge("PHASE-C-9")
    assert second.cleaned is False

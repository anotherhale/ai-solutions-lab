"""End-to-end coordinator → isolated child worktree lifecycle.

Exercises the real coordinator tick against real temporary Git repositories, the
disposable ops-test database, and stubbed GitHub/OpenHands interfaces. No paid
agent is launched and no real pull request is created.
"""

from __future__ import annotations

import subprocess
import textwrap
import uuid
from pathlib import Path

import pytest
from development_ops.coordinator_engine import CoordinatorEngine
from development_ops.github_client import AutoMergeAttempt, PullRequestState
from development_ops.persistence.worktree_repository import (
    AgentWorktreeRepository,
    WorktreeState,
)
from development_ops.recorder import ActivityRecorder
from development_ops.task_worktrees import TaskWorktreeOrchestrator
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
        connection.execute(text("DELETE FROM development_ops.agent_worktrees"))
        connection.execute(text("DELETE FROM development_ops.activity_events"))
        connection.execute(text("DELETE FROM development_ops.coordinator_tasks"))


@pytest.fixture
def session(ops_test_engine: Engine) -> Session:
    factory = sessionmaker(bind=ops_test_engine, autoflush=False)
    session = factory()
    yield session
    session.close()


@pytest.fixture
def backlog_file(tmp_path: Path) -> Path:
    path = tmp_path / "backlog.yaml"
    path.write_text(
        textwrap.dedent(
            """
            repository: example/test
            integration_branch: ai-dev
            tasks:
              - id: PHASE-C-E2E
                title: Isolated child work
                status: pending
                depends_on: []
            """
        ).strip(),
        encoding="utf-8",
    )
    return path


class _MutableGitHub:
    """GitHub stub whose merged state the test can flip mid-flight."""

    def __init__(self) -> None:
        self.prs: dict[int, PullRequestState] = {}

    def get_pull_request(self, repository: str, number: int) -> PullRequestState:
        return self.prs[number]

    def list_open_pull_requests(self, repository: str) -> list[PullRequestState]:
        return [pr for pr in self.prs.values() if not pr.merged and not pr.closed]

    def enable_squash_auto_merge(
        self, repository: str, number: int
    ) -> AutoMergeAttempt:  # pragma: no cover - not exercised
        return AutoMergeAttempt(number, False, False, error="not used")

    def mark_merged(self, number: int, base_ref: str = "ai-dev") -> None:
        self.prs[number] = PullRequestState(
            number=number,
            state="MERGED",
            merged=True,
            mergeable="MERGEABLE",
            head_ref="cursor/PHASE-C-E2E",
            base_ref=base_ref,
            node_id=f"PR_node_{number}",
            auto_merge_enabled=False,
            checks_green=True,
            review_decision="APPROVED",
            closed=True,
            checks_state="green",
        )


def _engine(
    session: Session,
    repo: tuple[Path, Path],
    backlog_file: Path,
    github: _MutableGitHub,
    run_id: uuid.UUID,
) -> CoordinatorEngine:
    work, wt_root = repo
    orchestrator = TaskWorktreeOrchestrator(
        session,
        WorktreeManager(work, wt_root),
        repository="example/test",
        launcher=None,
        github=github,
        run_id=run_id,
    )
    return CoordinatorEngine(
        session,
        github=github,
        recorder=ActivityRecorder(session, notify_slack=False),
        run_id=run_id,
        repository="example/test",
        backlog_path=backlog_file,
        worktrees=orchestrator,
    )


def test_coordinator_prepares_isolated_worktree_on_claim(
    session: Session,
    repo: tuple[Path, Path],
    backlog_file: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEVELOPMENT_OPS_ATTEMPT_AUTO_MERGE", "0")
    github = _MutableGitHub()
    engine = _engine(session, repo, backlog_file, github, uuid.uuid4())
    result = engine.tick()

    assert result.selected_task_id == "PHASE-C-E2E"
    assert result.prepared_worktree is not None
    record = AgentWorktreeRepository(session).get("PHASE-C-E2E")
    assert record is not None
    assert record.state == WorktreeState.PREPARING
    assert record.branch_name == "cursor/PHASE-C-E2E"
    assert record.base_ref == "origin/ai-dev"
    assert Path(record.worktree_path).exists()
    # The primary checkout is untouched.
    assert _git(["status", "--porcelain"], repo[0]) == ""


def test_coordinator_cleans_up_after_verified_merge(
    session: Session,
    repo: tuple[Path, Path],
    backlog_file: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEVELOPMENT_OPS_ATTEMPT_AUTO_MERGE", "0")
    github = _MutableGitHub()
    run_id = uuid.uuid4()
    engine = _engine(session, repo, backlog_file, github, run_id)

    first = engine.tick()
    assert first.prepared_worktree is not None
    record = AgentWorktreeRepository(session).get("PHASE-C-E2E")
    assert record is not None
    worktree_path = Path(record.worktree_path)

    # The child opens a PR; the coordinator records it on the worktree registry.
    engine.register_pull_request_opened(
        "PHASE-C-E2E",
        pull_number=777,
        branch_name="cursor/PHASE-C-E2E",
        title="feat: isolated child work",
    )
    registered = AgentWorktreeRepository(session).get("PHASE-C-E2E")
    assert registered is not None
    assert registered.pr_number == 777
    assert registered.state == WorktreeState.PR_OPEN

    # GitHub reports the PR merged, and the branch really is in ai-dev.
    work, _ = repo
    _git(["checkout", "-q", "ai-dev"], work)
    _git(["merge", "-q", "--ff-only", "cursor/PHASE-C-E2E"], work)
    _git(["push", "-q", "origin", "ai-dev"], work)
    _git(["checkout", "-q", "main"], work)
    github.mark_merged(777)

    second = engine.tick()
    assert "PHASE-C-E2E" in second.cleaned_worktrees
    assert not worktree_path.exists()
    cleaned = AgentWorktreeRepository(session).get("PHASE-C-E2E")
    assert cleaned is not None and cleaned.state == WorktreeState.MERGED


def test_coordinator_leaves_unmerged_worktree_in_place(
    session: Session,
    repo: tuple[Path, Path],
    backlog_file: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEVELOPMENT_OPS_ATTEMPT_AUTO_MERGE", "0")
    github = _MutableGitHub()
    engine = _engine(session, repo, backlog_file, github, uuid.uuid4())

    engine.tick()
    engine.register_pull_request_opened(
        "PHASE-C-E2E",
        pull_number=888,
        branch_name="cursor/PHASE-C-E2E",
        title="feat: isolated child work",
    )
    # PR is still open (registered but not merged) and the branch is unmerged.
    github.prs[888] = PullRequestState(
        number=888,
        state="OPEN",
        merged=False,
        mergeable="MERGEABLE",
        head_ref="cursor/PHASE-C-E2E",
        base_ref="ai-dev",
        node_id="PR_node_888",
        auto_merge_enabled=False,
        checks_green=True,
        review_decision=None,
        closed=False,
        checks_state="green",
    )
    record = AgentWorktreeRepository(session).get("PHASE-C-E2E")
    assert record is not None
    worktree_path = Path(record.worktree_path)

    result = engine.tick()
    assert result.cleaned_worktrees == ()
    assert worktree_path.exists()

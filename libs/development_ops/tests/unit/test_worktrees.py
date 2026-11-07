"""Worktree isolation tests against real temporary Git repositories.

These exercise the actual ``git worktree`` behavior — no mocks — so the
isolation guarantees are proven, not asserted against stubs.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from development_ops.worktrees import WorktreeError, WorktreeManager


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
    """An 'origin' bare repo plus a clone with local ``ai-dev`` and ``main``.

    ``origin/HEAD`` points at ``main`` so the repository reproduces the exact
    shape that made the default worktree start from the wrong branch.
    """
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


def _manager(repo: tuple[Path, Path]) -> WorktreeManager:
    work, wt_root = repo
    return WorktreeManager(work, wt_root)


def test_worktree_starts_from_latest_ai_dev(repo: tuple[Path, Path]) -> None:
    """The worktree's base commit is origin/ai-dev, never origin/main."""
    manager = _manager(repo)
    spec = manager.prepare("TASK-1")

    ai_dev_sha = _git(["rev-parse", "origin/ai-dev"], repo[0])
    main_sha = _git(["rev-parse", "origin/main"], repo[0])
    head = _git(["rev-parse", "HEAD"], spec.worktree_path)

    assert spec.base_ref == "origin/ai-dev"
    assert head == ai_dev_sha
    assert head != main_sha
    # The ai-dev-only file is present, proving the base is ai-dev.
    assert (spec.worktree_path / "ai.txt").exists()


def test_explicit_branch_name_is_created(repo: tuple[Path, Path]) -> None:
    manager = _manager(repo)
    spec = manager.prepare("TASK-2")
    assert spec.branch_name == "cursor/TASK-2"
    current = _git(["rev-parse", "--abbrev-ref", "HEAD"], spec.worktree_path)
    assert current == "cursor/TASK-2"


def test_two_tasks_get_independent_worktrees(repo: tuple[Path, Path]) -> None:
    manager = _manager(repo)
    first = manager.prepare("TASK-A")
    second = manager.prepare("TASK-B")

    assert first.worktree_path != second.worktree_path
    assert first.branch_name != second.branch_name
    assert first.worktree_path.exists() and second.worktree_path.exists()

    # Writing in one worktree does not appear in the other.
    (first.worktree_path / "only-a.txt").write_text("a\n", encoding="utf-8")
    assert (first.worktree_path / "only-a.txt").exists()
    assert not (second.worktree_path / "only-a.txt").exists()


def test_primary_checkout_is_unchanged(repo: tuple[Path, Path]) -> None:
    work, _ = repo
    manager = _manager(repo)
    before_branch = _git(["rev-parse", "--abbrev-ref", "HEAD"], work)
    before_head = _git(["rev-parse", "HEAD"], work)
    manager.prepare("TASK-3")
    assert _git(["rev-parse", "--abbrev-ref", "HEAD"], work) == before_branch
    assert _git(["rev-parse", "HEAD"], work) == before_head
    assert _git(["status", "--porcelain"], work) == ""


def test_prepare_is_idempotent(repo: tuple[Path, Path]) -> None:
    manager = _manager(repo)
    first = manager.prepare("TASK-4")
    second = manager.prepare("TASK-4")
    assert first.worktree_path == second.worktree_path
    assert first.branch_name == second.branch_name
    listing = _git(["worktree", "list", "--porcelain"], repo[0])
    entries = [line for line in listing.splitlines() if line.startswith("worktree ")]
    assert str(first.worktree_path) in "\n".join(entries)
    assert len(entries) == 2  # primary checkout + one task worktree


def test_missing_base_branch_raises(repo: tuple[Path, Path]) -> None:
    work, wt_root = repo
    manager = WorktreeManager(work, wt_root, base_branch="does-not-exist")
    with pytest.raises(WorktreeError):
        manager.prepare("TASK-5")


def test_unsafe_task_id_is_rejected(repo: tuple[Path, Path]) -> None:
    manager = _manager(repo)
    with pytest.raises(WorktreeError):
        manager.prepare("../escape")
    with pytest.raises(WorktreeError):
        manager.prepare("has space")


def test_cleanup_removes_merged_worktree(repo: tuple[Path, Path]) -> None:
    manager = _manager(repo)
    spec = manager.prepare("TASK-6")
    # Simulate the merge: fast-forward ai-dev onto the branch, then clean up.
    _git(["checkout", "-q", "ai-dev"], repo[0])
    _git(["merge", "-q", "--ff-only", spec.branch_name], repo[0])
    _git(["push", "-q", "origin", "ai-dev"], repo[0])
    _git(["checkout", "-q", "main"], repo[0])
    manager.fetch_base()

    assert manager.branch_is_merged("TASK-6")
    result = manager.cleanup("TASK-6", merged=True)
    assert result.removed_worktree
    assert result.deleted_branch
    assert not spec.worktree_path.exists()
    assert not manager._git_ok(
        "show-ref",
        "--verify",
        "--quiet",
        f"refs/heads/{spec.branch_name}",
        cwd=repo[0],
    )


def test_cleanup_refuses_dirty_worktree(repo: tuple[Path, Path]) -> None:
    manager = _manager(repo)
    spec = manager.prepare("TASK-7")
    (spec.worktree_path / "uncommitted.txt").write_text("x\n", encoding="utf-8")
    with pytest.raises(WorktreeError):
        manager.cleanup("TASK-7", merged=True)
    assert spec.worktree_path.exists()


def test_cleanup_refuses_unmerged_branch(repo: tuple[Path, Path]) -> None:
    manager = _manager(repo)
    spec = manager.prepare("TASK-8")
    # Commit work on the branch that is not on ai-dev: genuinely unmerged.
    (spec.worktree_path / "work.txt").write_text("new\n", encoding="utf-8")
    _git(["add", "-A"], spec.worktree_path)
    _git(["commit", "-qm", "task work"], spec.worktree_path)
    assert not manager.branch_is_merged("TASK-8")
    with pytest.raises(WorktreeError):
        manager.cleanup("TASK-8", merged=False)
    assert spec.worktree_path.exists()


def test_cleanup_allows_branch_with_no_extra_work(repo: tuple[Path, Path]) -> None:
    """A branch with no commits beyond base holds no unmerged work."""
    manager = _manager(repo)
    spec = manager.prepare("TASK-8B")
    assert manager.branch_is_merged("TASK-8B")
    result = manager.cleanup("TASK-8B", merged=False)
    assert result.removed_worktree
    assert not spec.worktree_path.exists()


def test_cleanup_is_idempotent(repo: tuple[Path, Path]) -> None:
    manager = _manager(repo)
    manager.prepare("TASK-9")
    first = manager.cleanup("TASK-9", merged=True, delete_branch=False)
    assert first.removed_worktree
    second = manager.cleanup("TASK-9", merged=True, delete_branch=False)
    assert second.already_clean


def test_interrupted_launch_is_recovered(repo: tuple[Path, Path]) -> None:
    """A second prepare after a crash reuses the existing worktree."""
    manager = _manager(repo)
    spec = manager.prepare("TASK-10")
    (spec.worktree_path / "partial.txt").write_text("wip\n", encoding="utf-8")

    resumed = manager.prepare("TASK-10")
    assert resumed.worktree_path == spec.worktree_path
    assert (resumed.worktree_path / "partial.txt").exists()
    assert manager.is_dirty("TASK-10")


def test_existing_path_with_foreign_checkout_is_refused(
    repo: tuple[Path, Path],
) -> None:
    manager = _manager(repo)
    spec = manager.prepare("TASK-11")
    # Replace the worktree's checkout with an unrelated one at the same path.
    manager.cleanup("TASK-11", merged=True, delete_branch=False)
    spec.worktree_path.mkdir(parents=True)
    _init_repo(spec.worktree_path)
    with pytest.raises(WorktreeError):
        manager.prepare("TASK-11")


def test_task_lock_blocks_a_second_holder(repo: tuple[Path, Path]) -> None:
    from development_ops.worktrees import WorktreeLockedError

    manager = _manager(repo)
    with manager.task_lock("TASK-LOCK"):
        with pytest.raises(WorktreeLockedError):
            with manager.task_lock("TASK-LOCK"):
                pass


def test_task_lock_serializes_prepare(repo: tuple[Path, Path]) -> None:
    from development_ops.worktrees import WorktreeLockedError

    manager = _manager(repo)
    with manager.task_lock("TASK-LOCK2"):
        with pytest.raises(WorktreeLockedError):
            manager.prepare("TASK-LOCK2")
    # Once released, prepare succeeds.
    spec = manager.prepare("TASK-LOCK2")
    assert spec.worktree_path.exists()


def test_cleanup_requires_verified_merge_flag(repo: tuple[Path, Path]) -> None:
    """Cleanup must be told the PR merged; it never assumes it."""
    manager = _manager(repo)
    spec = manager.prepare("TASK-12")
    (spec.worktree_path / "work.txt").write_text("new\n", encoding="utf-8")
    _git(["add", "-A"], spec.worktree_path)
    _git(["commit", "-qm", "work"], spec.worktree_path)
    with pytest.raises(WorktreeError):
        manager.cleanup("TASK-12", merged=False)
    assert spec.worktree_path.exists()

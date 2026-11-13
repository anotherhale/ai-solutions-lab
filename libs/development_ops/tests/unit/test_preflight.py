"""Integration-branch preflight tests against real temporary Git repositories.

The preflight is read-only, so these tests exercise the actual ``git``
behavior — no mocks — and assert both the verdict and the absence of mutation.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from development_ops.preflight import (
    IntegrationBranchPreflight,
    PreflightError,
)


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
    """An 'origin' bare repo plus a clone with a local ``ai-dev`` branch."""
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
    # A local tracking branch mirroring origin/ai-dev.
    _git(["branch", "-q", "ai-dev", "origin/ai-dev"], work)
    return work, seed


def _preflight(work: Path, *, remote: str = "origin") -> IntegrationBranchPreflight:
    return IntegrationBranchPreflight(work, remote=remote)


def test_in_sync_report_is_ok(repo: tuple[Path, Path]) -> None:
    work, _ = repo
    report = _preflight(work).run()
    assert report.ok is True
    assert report.ahead == 0
    assert report.behind == 0
    assert report.base_sha == report.remote_sha
    report.raise_if_failed()  # must not raise


def test_local_ahead_blocks_and_raises(repo: tuple[Path, Path]) -> None:
    work, _ = repo
    _git(["checkout", "-q", "ai-dev"], work)
    (work / "unpushed.txt").write_text("local\n", encoding="utf-8")
    _git(["add", "-A"], work)
    _git(["commit", "-qm", "unpushed local work"], work)
    report = _preflight(work).run()
    assert report.ok is False
    assert report.ahead == 1
    assert any(
        c.name == "not_ahead" and not c.ok and c.blocking
        for c in report.blocking_failures
    )
    with pytest.raises(PreflightError):
        report.raise_if_failed()


def test_local_behind_is_advisory_not_blocking(repo: tuple[Path, Path]) -> None:
    work, seed = repo
    (seed / "next.txt").write_text("next\n", encoding="utf-8")
    _git(["add", "-A"], seed)
    _git(["commit", "-qm", "advance ai-dev"], seed)
    _git(["push", "-q", "origin", "ai-dev"], seed)
    _git(["fetch", "-q", "origin"], work)
    report = _preflight(work).run()
    assert report.ok is True
    assert report.behind == 1
    assert any(c.name == "up_to_date" for c in report.advisories)


def test_unreachable_remote_blocks(repo: tuple[Path, Path]) -> None:
    work, _ = repo
    report = _preflight(work, remote="ghost").run()
    assert report.ok is False
    assert any(
        c.name == "remote_reachable" and not c.ok for c in report.blocking_failures
    )


def test_missing_local_branch_is_advisory(repo: tuple[Path, Path]) -> None:
    work, _ = repo
    _git(["branch", "-D", "ai-dev"], work)
    report = _preflight(work).run()
    assert report.ok is True
    assert any(c.name == "local_branch_present" and not c.ok for c in report.advisories)


def test_dirty_primary_tree_is_advisory(repo: tuple[Path, Path]) -> None:
    work, _ = repo
    (work / "dirty.txt").write_text("uncommitted\n", encoding="utf-8")
    report = _preflight(work).run()
    assert report.ok is True
    assert any(c.name == "clean_primary_tree" and not c.ok for c in report.advisories)


def test_preflight_is_read_only(repo: tuple[Path, Path]) -> None:
    work, _ = repo
    before = _git(["rev-parse", "refs/heads/ai-dev"], work)
    before_remote = _git(["rev-parse", "origin/ai-dev"], work)
    _preflight(work).run()
    _preflight(work).run()
    assert _git(["rev-parse", "refs/heads/ai-dev"], work) == before
    assert _git(["rev-parse", "origin/ai-dev"], work) == before_remote


def test_unauthorized_branch_is_rejected(tmp_path: Path) -> None:
    from development_ops.integration import UnauthorizedBaseBranchError

    with pytest.raises(UnauthorizedBaseBranchError):
        IntegrationBranchPreflight(tmp_path, integration_branch="main")

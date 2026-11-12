"""Isolated Git worktrees for autonomous child agents.

Every autonomous task runs in its own worktree and branch, cut from the latest
``origin/ai-dev``, so two agents never share a writable working directory and no
agent can move the primary checkout's branch.

This module is deliberately Git-only: it shells out to ``git`` with argument
lists (never a shell), holds no database or OpenHands dependency, and is
exercised against throwaway repositories in tests.
"""

from __future__ import annotations

import fcntl
import os
import re
import subprocess
import time
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from development_ops.integration import (
    AUTONOMOUS_INTEGRATION_BRANCH,
    assert_authorized_base_branch,
)

# Task identifiers reach us from the backlog and become both a directory name and
# a branch segment, so restrict them to a safe alphabet.
_TASK_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


class WorktreeError(RuntimeError):
    """A worktree operation failed or a safety rule blocked it."""


class WorktreeLockedError(WorktreeError):
    """Another process already holds the per-task worktree lock."""


class GitRunner(Protocol):
    def __call__(
        self, args: Sequence[str], cwd: Path | None = ...
    ) -> subprocess.CompletedProcess[str]: ...


def _default_runner(
    args: Sequence[str], cwd: Path | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd) if cwd is not None else None,
        capture_output=True,
        text=True,
        check=False,
    )


@dataclass(frozen=True, slots=True)
class WorktreeSpec:
    """Identity of a task's isolated worktree and branch."""

    task_id: str
    branch_name: str
    worktree_path: Path
    base_ref: str
    base_sha: str


@dataclass(frozen=True, slots=True)
class WorktreeStatus:
    task_id: str
    branch_name: str
    worktree_path: Path
    exists: bool
    dirty: bool
    head_sha: str | None
    merged_into_base: bool


@dataclass(frozen=True, slots=True)
class CleanupResult:
    task_id: str
    removed_worktree: bool
    deleted_branch: bool
    already_clean: bool
    notes: tuple[str, ...] = ()


class WorktreeManager:
    """Create, inspect, and safely remove per-task worktrees.

    ``repo_root`` is the primary checkout. Worktrees are created under
    ``worktree_root`` (outside the primary checkout by default) so the primary
    working tree and its checked-out branch are never disturbed.
    """

    def __init__(
        self,
        repo_root: Path | str,
        worktree_root: Path | str,
        *,
        base_branch: str = AUTONOMOUS_INTEGRATION_BRANCH,
        remote: str = "origin",
        branch_prefix: str = "cursor/",
        fetch: bool = True,
        runner: GitRunner | None = None,
    ) -> None:
        self._repo_root = Path(repo_root).resolve()
        self._worktree_root = Path(worktree_root).expanduser().resolve()
        self._base_branch = assert_authorized_base_branch(
            base_branch,
            operation="worktree base branch",
        )
        self._remote = remote
        self._branch_prefix = branch_prefix
        self._fetch = fetch
        self._run = runner or _default_runner

    # -- naming ------------------------------------------------------------

    @property
    def base_ref(self) -> str:
        return f"{self._remote}/{self._base_branch}"

    @property
    def repo_name(self) -> str:
        return self._repo_root.name

    def branch_name(self, task_id: str) -> str:
        self._validate_task_id(task_id)
        return f"{self._branch_prefix}{task_id}"

    def worktree_path(self, task_id: str) -> Path:
        self._validate_task_id(task_id)
        return self._worktree_root / self.repo_name / task_id

    # -- git plumbing ------------------------------------------------------

    def _git(self, *args: str, cwd: Path | None = None) -> str:
        result = self._run(args, cwd)
        if result.returncode != 0:
            message = (result.stderr or result.stdout or "").strip()
            raise WorktreeError(
                f"git {' '.join(args)} failed ({result.returncode}): {message}"
            )
        return result.stdout.strip()

    def _git_ok(self, *args: str, cwd: Path | None = None) -> bool:
        return self._run(args, cwd).returncode == 0

    def _validate_task_id(self, task_id: str) -> None:
        if not _TASK_ID_PATTERN.match(task_id):
            msg = (
                f"unsafe task id {task_id!r}: expected "
                "[A-Za-z0-9][A-Za-z0-9._-]{0,63}"
            )
            raise WorktreeError(msg)

    # -- concurrency -------------------------------------------------------

    def lock_path(self, task_id: str) -> Path:
        self._validate_task_id(task_id)
        return self._worktree_root / ".locks" / f"{task_id}.lock"

    @contextmanager
    def task_lock(self, task_id: str, *, timeout: float = 0.0) -> Iterator[None]:
        """Serialize prepare/cleanup for one task across processes.

        Two workers that prepare the same task must not race on the branch and
        worktree. An exclusive ``flock`` on a per-task file is the cross-process
        guard; a second caller either blocks briefly or fails fast when
        ``timeout`` is zero. The lock is advisory but every path that mutates a
        worktree goes through it.
        """
        path = self.lock_path(task_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        handle = os.open(str(path), os.O_CREAT | os.O_RDWR, 0o644)
        try:
            if timeout == 0.0:
                try:
                    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except OSError as exc:
                    msg = (
                        f"worktree for {task_id} is locked by another process; "
                        "retry after it completes"
                    )
                    raise WorktreeLockedError(msg) from exc
            else:
                end = time.monotonic() + timeout
                while True:
                    try:
                        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        break
                    except OSError as exc:
                        if time.monotonic() >= end:
                            msg = f"timed out waiting for worktree lock on {task_id}"
                            raise WorktreeLockedError(msg) from exc
                        time.sleep(0.05)
            yield
        finally:
            try:
                fcntl.flock(handle, fcntl.LOCK_UN)
            finally:
                os.close(handle)

    def fetch_base(self) -> None:
        """Refresh ``origin`` so worktrees start from the latest ai-dev."""
        if not self._fetch:
            return
        self._git("fetch", "--prune", self._remote, cwd=self._repo_root)

    def resolve_base_sha(self) -> str:
        """Resolve ``origin/ai-dev`` to a commit, failing loudly when absent."""
        try:
            return self._git(
                "rev-parse",
                "--verify",
                "--quiet",
                f"{self.base_ref}^{{commit}}",
                cwd=self._repo_root,
            )
        except WorktreeError as exc:
            msg = (
                f"base ref {self.base_ref!r} is unavailable; run with a "
                f"{self._remote!r} remote that has {self._base_branch!r}"
            )
            raise WorktreeError(msg) from exc

    def spec_for(self, task_id: str) -> WorktreeSpec:
        """Compute the spec without touching Git (names only)."""
        return WorktreeSpec(
            task_id=task_id,
            branch_name=self.branch_name(task_id),
            worktree_path=self.worktree_path(task_id),
            base_ref=self.base_ref,
            base_sha="",
        )

    # -- lifecycle ---------------------------------------------------------

    def prepare(self, task_id: str) -> WorktreeSpec:
        """Create (or reuse) the task's branch and worktree from latest ai-dev.

        Idempotent: a second call returns the same spec. An interrupted launch
        is recovered by reusing the existing worktree rather than recreating it.
        A per-task lock serializes concurrent prepares for the same task.
        """
        self._validate_task_id(task_id)
        with self.task_lock(task_id):
            return self._prepare_locked(task_id)

    def _prepare_locked(self, task_id: str) -> WorktreeSpec:
        self.fetch_base()
        base_sha = self.resolve_base_sha()
        branch = self.branch_name(task_id)
        path = self.worktree_path(task_id)

        if path.exists() and self._worktree_checked_out(path) == branch:
            return WorktreeSpec(task_id, branch, path, self.base_ref, base_sha)
        if path.exists():
            msg = (
                f"worktree path {path} exists but is not checked out on "
                f"{branch!r}; refusing to overwrite"
            )
            raise WorktreeError(msg)

        path.parent.mkdir(parents=True, exist_ok=True)
        self._git("worktree", "prune", cwd=self._repo_root)
        if self._git_ok(
            "show-ref",
            "--verify",
            "--quiet",
            f"refs/heads/{branch}",
            cwd=self._repo_root,
        ):
            self._git("worktree", "add", str(path), branch, cwd=self._repo_root)
        else:
            self._git(
                "worktree",
                "add",
                "-b",
                branch,
                str(path),
                base_sha,
                cwd=self._repo_root,
            )
        return WorktreeSpec(task_id, branch, path, self.base_ref, base_sha)

    def _worktree_checked_out(self, path: Path) -> str | None:
        if not self._git_ok("rev-parse", "--git-dir", cwd=path):
            return None
        result = self._run(["rev-parse", "--abbrev-ref", "HEAD"], path)
        if result.returncode != 0:
            return None
        branch = result.stdout.strip()
        return branch or None

    def is_dirty(self, task_id: str) -> bool:
        path = self.worktree_path(task_id)
        if not path.exists():
            return False
        result = self._run(["status", "--porcelain", "--untracked-files=normal"], path)
        if result.returncode != 0:
            # Fail safe: an unreadable worktree must never be auto-deleted.
            return True
        return bool(result.stdout.strip())

    def status(self, task_id: str) -> WorktreeStatus:
        path = self.worktree_path(task_id)
        branch = self.branch_name(task_id)
        exists = path.exists() and self._worktree_checked_out(path) == branch
        head_sha: str | None = None
        if exists:
            result = self._run(["rev-parse", "HEAD"], path)
            head_sha = result.stdout.strip() if result.returncode == 0 else None
        return WorktreeStatus(
            task_id=task_id,
            branch_name=branch,
            worktree_path=path,
            exists=exists,
            dirty=self.is_dirty(task_id) if exists else False,
            head_sha=head_sha,
            merged_into_base=exists and self.branch_is_merged(task_id),
        )

    def branch_is_merged(self, task_id: str) -> bool:
        """True when the task branch is fully contained in the base ref."""
        branch = self.branch_name(task_id)
        if not self._git_ok(
            "show-ref",
            "--verify",
            "--quiet",
            f"refs/heads/{branch}",
            cwd=self._repo_root,
        ):
            return False
        return self._git_ok(
            "merge-base",
            "--is-ancestor",
            branch,
            self.base_ref,
            cwd=self._repo_root,
        )

    def cleanup(
        self,
        task_id: str,
        *,
        merged: bool,
        delete_branch: bool = True,
    ) -> CleanupResult:
        """Remove a task's worktree after its PR is verified merged.

        Refuses to remove a dirty worktree or to delete an unmerged branch. A
        ``merged`` flag is required so cleanup never races ahead of the merge
        check. Preconditions are validated before any mutation, so a refusal
        leaves the worktree and branch untouched. Idempotent: cleaning an
        already-absent worktree is a no-op.
        """
        self._validate_task_id(task_id)
        with self.task_lock(task_id):
            return self._cleanup_locked(
                task_id, merged=merged, delete_branch=delete_branch
            )

    def _cleanup_locked(
        self,
        task_id: str,
        *,
        merged: bool,
        delete_branch: bool,
    ) -> CleanupResult:
        path = self.worktree_path(task_id)
        branch = self.branch_name(task_id)
        notes: list[str] = []

        branch_present = self._git_ok(
            "show-ref",
            "--verify",
            "--quiet",
            f"refs/heads/{branch}",
            cwd=self._repo_root,
        )
        if path.exists() and self.is_dirty(task_id):
            msg = (
                f"refusing to remove dirty worktree for {task_id} at {path}; "
                "commit or discard changes first"
            )
            raise WorktreeError(msg)
        if delete_branch and branch_present and not merged:
            if not self.branch_is_merged(task_id):
                msg = (
                    f"refusing to delete unmerged branch {branch!r}; verify the "
                    "pull request merged before cleanup"
                )
                raise WorktreeError(msg)

        if not path.exists():
            if not branch_present:
                return CleanupResult(task_id, False, False, True, ("already clean",))
            if delete_branch:
                self._git("branch", "-D", branch, cwd=self._repo_root)
                return CleanupResult(task_id, False, True, False, ("branch only",))
            return CleanupResult(task_id, False, False, True, ("worktree absent",))

        self._git("worktree", "remove", str(path), cwd=self._repo_root)
        notes.append("worktree removed")
        deleted = False
        if delete_branch and branch_present:
            self._git("branch", "-D", branch, cwd=self._repo_root)
            deleted = True
            notes.append("branch deleted")
        self._git("worktree", "prune", cwd=self._repo_root)
        return CleanupResult(task_id, True, deleted, False, tuple(notes))

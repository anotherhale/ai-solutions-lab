"""Fail-closed preflight for the autonomous integration branch.

Before the coordinator cuts a child worktree, launches an agent, or arms
auto-merge, the local view of the integration branch (``ai-dev``) must agree
with the remote. A stale or diverged local ref, an unreachable remote, or a
missing branch would otherwise let a child branch from the wrong commit and
produce a pull request the coordinator cannot integrate.

The preflight is deliberately Git-only and read-only: it shells out to ``git``
with argument lists (never a shell), never fetches or mutates a ref, and is
exercised against throwaway repositories in tests. Callers decide what to do
with a failed report; :meth:`PreflightReport.raise_if_failed` is provided for
the common fail-fast case.

A check is either *blocking* (a hard failure that must stop autonomous work) or
*advisory* (a hygiene signal that is surfaced but does not stop work). A dirty
primary checkout, for example, is advisory: worktrees are created outside the
primary tree, so uncommitted changes there do not corrupt a child's base.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from development_ops.integration import (
    AUTONOMOUS_INTEGRATION_BRANCH,
    assert_authorized_base_branch,
)


class PreflightError(RuntimeError):
    """The integration branch failed a blocking preflight check."""


class PreflightGitRunner:
    """Run ``git`` for the preflight; injectable for tests."""

    def __call__(
        self, args: Sequence[str], cwd: Path | None = None
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args],
            cwd=str(cwd) if cwd is not None else None,
            capture_output=True,
            text=True,
            check=False,
        )


@dataclass(frozen=True, slots=True)
class PreflightCheck:
    name: str
    ok: bool
    detail: str
    blocking: bool = True


@dataclass(frozen=True, slots=True)
class PreflightReport:
    repository_root: str
    integration_branch: str
    remote: str
    base_sha: str | None
    remote_sha: str | None
    ahead: int
    behind: int
    checks: tuple[PreflightCheck, ...]

    @property
    def blocking_failures(self) -> tuple[PreflightCheck, ...]:
        return tuple(c for c in self.checks if not c.ok and c.blocking)

    @property
    def advisories(self) -> tuple[PreflightCheck, ...]:
        return tuple(c for c in self.checks if not c.ok and not c.blocking)

    @property
    def ok(self) -> bool:
        return not self.blocking_failures

    def summary(self) -> str:
        if self.ok and not self.advisories:
            return f"integration branch {self.integration_branch!r} is ready"
        parts: list[str] = []
        if self.blocking_failures:
            parts.append(
                "blocked: "
                + "; ".join(f"{c.name}: {c.detail}" for c in self.blocking_failures)
            )
        if self.advisories:
            parts.append(
                "advisory: "
                + "; ".join(f"{c.name}: {c.detail}" for c in self.advisories)
            )
        return " | ".join(parts)

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "integration_branch": self.integration_branch,
            "remote": self.remote,
            "base_sha": self.base_sha,
            "remote_sha": self.remote_sha,
            "ahead": self.ahead,
            "behind": self.behind,
            "summary": self.summary(),
            "checks": [
                {
                    "name": c.name,
                    "ok": c.ok,
                    "blocking": c.blocking,
                    "detail": c.detail,
                }
                for c in self.checks
            ],
        }

    def raise_if_failed(self) -> None:
        if not self.ok:
            raise PreflightError(self.summary())


class IntegrationBranchPreflight:
    """Verify the local integration branch agrees with the remote."""

    def __init__(
        self,
        repo_root: Path | str,
        *,
        integration_branch: str = AUTONOMOUS_INTEGRATION_BRANCH,
        remote: str = "origin",
        runner: PreflightGitRunner | None = None,
    ) -> None:
        self._root = Path(repo_root).expanduser().resolve()
        self._branch = assert_authorized_base_branch(
            integration_branch,
            operation="integration branch preflight",
        )
        self._remote = remote
        self._run = runner or PreflightGitRunner()

    @property
    def base_ref(self) -> str:
        return f"{self._remote}/{self._branch}"

    def run(self) -> PreflightReport:
        checks: list[PreflightCheck] = []

        remote_reachable = self._run(
            ["ls-remote", "--exit-code", self._remote, self._branch],
            cwd=self._root,
        )
        reachable = remote_reachable.returncode == 0
        checks.append(
            PreflightCheck(
                name="remote_reachable",
                ok=reachable,
                detail=(
                    f"{self._remote} is reachable and has {self._branch}"
                    if reachable
                    else (
                        f"cannot reach {self._remote} or it has no {self._branch}: "
                        f"{self._error(remote_reachable)}"
                    )
                ),
            )
        )

        remote_sha = self._rev_parse(self.base_ref)
        checks.append(
            PreflightCheck(
                name="remote_ref_present",
                ok=remote_sha is not None,
                detail=(
                    f"{self.base_ref} = {remote_sha[:12]}"
                    if remote_sha
                    else f"{self.base_ref} does not resolve locally; run git fetch"
                ),
            )
        )

        local_sha = self._rev_parse(f"refs/heads/{self._branch}")
        checks.append(
            PreflightCheck(
                name="local_branch_present",
                ok=local_sha is not None,
                detail=(
                    f"refs/heads/{self._branch} = {local_sha[:12]}"
                    if local_sha
                    else f"no local branch {self._branch!r}"
                ),
                blocking=False,
            )
        )

        ahead = behind = 0
        if local_sha and remote_sha:
            ahead, behind = self._ahead_behind(local_sha, remote_sha)
            checks.append(
                PreflightCheck(
                    name="not_ahead",
                    ok=ahead == 0,
                    detail=(
                        "local integration branch has no unpushed commits"
                        if ahead == 0
                        else (
                            f"local {self._branch} is {ahead} commit(s) ahead of "
                            f"{self.base_ref}; push or reset before integrating"
                        )
                    ),
                )
            )
            checks.append(
                PreflightCheck(
                    name="up_to_date",
                    ok=behind == 0,
                    detail=(
                        "local integration branch includes the remote tip"
                        if behind == 0
                        else (
                            f"local {self._branch} is {behind} commit(s) behind "
                            f"{self.base_ref}; fast-forward before integrating "
                            "(advisory)"
                        )
                    ),
                    blocking=False,
                )
            )

        clean = self._run(["status", "--porcelain"], cwd=self._root)
        tree_clean = clean.returncode == 0 and not clean.stdout.strip()
        checks.append(
            PreflightCheck(
                name="clean_primary_tree",
                ok=tree_clean,
                detail=(
                    "primary checkout has no uncommitted changes"
                    if tree_clean
                    else "primary checkout has uncommitted changes (advisory)"
                ),
                blocking=False,
            )
        )

        return PreflightReport(
            repository_root=str(self._root),
            integration_branch=self._branch,
            remote=self._remote,
            base_sha=local_sha,
            remote_sha=remote_sha,
            ahead=ahead,
            behind=behind,
            checks=tuple(checks),
        )

    # -- git helpers -------------------------------------------------------

    def _rev_parse(self, ref: str) -> str | None:
        result = self._run(
            ["rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"],
            cwd=self._root,
        )
        if result.returncode != 0:
            return None
        return result.stdout.strip() or None

    def _ahead_behind(self, local_sha: str, remote_sha: str) -> tuple[int, int]:
        result = self._run(
            ["rev-list", "--left-right", "--count", f"{local_sha}...{remote_sha}"],
            cwd=self._root,
        )
        if result.returncode != 0:
            return 0, 0
        parts = result.stdout.split()
        if len(parts) != 2:
            return 0, 0
        return int(parts[0]), int(parts[1])

    @staticmethod
    def _error(result: subprocess.CompletedProcess[str]) -> str:
        return (result.stderr or result.stdout).strip() or "no output"


def preflight_from_env(repo_root: Path | str | None = None) -> PreflightReport:
    """Run the preflight using the standard environment configuration."""
    root = repo_root or os.environ.get("DEVELOPMENT_OPS_REPO_ROOT") or Path.cwd()
    remote = os.environ.get("DEVELOPMENT_OPS_REMOTE", "origin")
    return IntegrationBranchPreflight(root, remote=remote).run()


def preflight_callable_from_env() -> Callable[[], PreflightReport]:
    """A zero-argument preflight callable bound to the environment.

    Production wiring passes this into
    :class:`~development_ops.task_worktrees.TaskWorktreeOrchestrator` so a fresh
    worktree is cut only from a healthy integration branch.
    """
    root = os.environ.get("DEVELOPMENT_OPS_REPO_ROOT") or Path.cwd()
    remote = os.environ.get("DEVELOPMENT_OPS_REMOTE", "origin")

    def run() -> PreflightReport:
        return IntegrationBranchPreflight(root, remote=remote).run()

    return run

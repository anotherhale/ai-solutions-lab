"""Bind a backlog task to an isolated worktree, child conversation, and PR.

This is the coordinator-facing entry point for Phase C. It composes the Git
worktree manager, the child-agent launcher, and the worktree registry so a task
moves through: prepare worktree → launch child → record PR → clean up after the
pull request is *verified* merged.

Ownership of state is deliberate and single-sourced:

* GitHub is the only authority on whether a pull request is merged. This module
  never trusts a caller-supplied boolean; it re-verifies through
  :func:`verify_pull_request_merged` before deleting anything.
* ``development_ops.agent_worktrees`` is the registry of the worktree, branch,
  and child conversation. The coordinator updates it; it is never polled
  independently, so there is no second PR-state store to drift.
* ``development_ops.coordinator_tasks`` continues to own *scheduling* state
  (slots, dependencies, leases), which is a different concern.

The Git work is delegated to :class:`WorktreeManager`; this module owns the
ordering, the registry writes, and the safety checks that gate cleanup.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from development_ops.child_agents import (
    ChildAgentLaunch,
    ChildAgentLauncher,
    build_conversation_payload,
    build_worktree_prompt,
)
from development_ops.github_client import (
    GitHubClient,
    verify_pull_request_merged,
)
from development_ops.integration import (
    AUTONOMOUS_INTEGRATION_BRANCH,
    assert_authorized_base_branch,
)
from development_ops.persistence.worktree_repository import (
    AgentWorktreeRecord,
    AgentWorktreeRepository,
    WorktreeState,
)
from development_ops.preflight import PreflightReport
from development_ops.worktrees import WorktreeManager, WorktreeSpec

# A conversation that exists means a child was launched and must not be
# re-launched without operator intent.
_LAUNCHED_STATES = frozenset(
    {WorktreeState.LAUNCHED, WorktreeState.PR_OPEN, WorktreeState.MERGED}
)
# States a coordinator may safely re-drive: registered but never launched, or a
# launch that failed. A live child's worktree is never reclaimed automatically.
_RECOVERABLE_STATES = frozenset({WorktreeState.PREPARING, WorktreeState.FAILED})


@dataclass(frozen=True, slots=True)
class TaskLaunchResult:
    task_id: str
    conversation_id: str | None
    worktree_path: Path
    branch_name: str
    launched: bool
    notes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CleanupOutcome:
    task_id: str
    cleaned: bool
    verified_merge: bool
    reason: str


class TaskWorktreeOrchestrator:
    def __init__(
        self,
        session: Session,
        manager: WorktreeManager,
        *,
        repository: str,
        integration_branch: str = AUTONOMOUS_INTEGRATION_BRANCH,
        launcher: ChildAgentLauncher | None = None,
        github: GitHubClient | None = None,
        run_id: uuid.UUID | None = None,
        preflight: Callable[[], PreflightReport] | None = None,
    ) -> None:
        self._repo = AgentWorktreeRepository(session)
        self._manager = manager
        self._repository = repository
        self._integration_branch = assert_authorized_base_branch(
            integration_branch,
            operation="worktree orchestration",
        )
        self._launcher = launcher
        self._github = github
        self._run_id = run_id
        self._preflight = preflight

    @property
    def manager(self) -> WorktreeManager:
        return self._manager

    @property
    def registry(self) -> AgentWorktreeRepository:
        return self._repo

    def check_preflight(self) -> PreflightReport | None:
        """Run the integration-branch preflight, failing closed on a blocker.

        Returns ``None`` when no preflight is configured. A blocking failure
        raises :class:`PreflightError` so no worktree is cut from a stale or
        diverged base. Advisory findings are returned for the caller to log.
        """
        if self._preflight is None:
            return None
        report = self._preflight()
        report.raise_if_failed()
        return report

    def prepare(self, task_id: str, *, title: str = "") -> AgentWorktreeRecord:
        """Create the worktree and register it before a child is launched.

        Registration happens first so an interrupted launch still leaves a
        durable record that recovery can act on. A fresh worktree is cut only
        after the integration-branch preflight passes; reusing an existing
        worktree is never blocked, so a child already in flight is undisturbed.
        """
        if not self._manager.worktree_path(task_id).exists():
            self.check_preflight()
        self._repo.upsert(
            task_id,
            branch_name=self._manager.branch_name(task_id),
            worktree_path=str(self._manager.worktree_path(task_id)),
            base_ref=self._manager.base_ref,
            base_sha=None,
            state=WorktreeState.PREPARING,
            run_id=self._run_id,
            notes=title or None,
        )
        spec = self._manager.prepare(task_id)
        return self._repo.upsert(
            task_id,
            branch_name=spec.branch_name,
            worktree_path=str(spec.worktree_path),
            base_ref=spec.base_ref,
            base_sha=spec.base_sha,
            state=WorktreeState.PREPARING,
            run_id=self._run_id,
            notes=title or None,
        )

    def launch(
        self,
        task_id: str,
        *,
        title: str,
        agent_settings: dict,
        extra_instructions: str | None = None,
    ) -> TaskLaunchResult:
        """Prepare the worktree and launch the child conversation inside it.

        Idempotent against duplicate launches: if a conversation already exists
        for the task, it is returned instead of starting a second one. A failed
        launch marks the registration ``failed`` and leaves the worktree in place
        so a retry reuses it instead of leaking a second one.
        """
        existing = self._repo.get(task_id)
        if (
            existing is not None
            and existing.conversation_id
            and existing.state in _LAUNCHED_STATES
        ):
            return TaskLaunchResult(
                task_id=task_id,
                conversation_id=existing.conversation_id,
                worktree_path=Path(existing.worktree_path),
                branch_name=existing.branch_name,
                launched=True,
                notes=("reused existing child conversation",),
            )

        record = self.prepare(task_id, title=title)
        spec = WorktreeSpec(
            task_id=task_id,
            branch_name=record.branch_name,
            worktree_path=Path(record.worktree_path),
            base_ref=record.base_ref,
            base_sha=record.base_sha or "",
        )
        if self._launcher is None:
            return TaskLaunchResult(
                task_id=task_id,
                conversation_id=None,
                worktree_path=spec.worktree_path,
                branch_name=spec.branch_name,
                launched=False,
                notes=("no launcher configured; worktree prepared only",),
            )
        prompt = build_worktree_prompt(
            spec,
            task_id=task_id,
            task_title=title,
            repository=self._repository,
            integration_branch=self._integration_branch,
            extra_instructions=extra_instructions,
        )
        launch = ChildAgentLaunch(
            task_id=task_id,
            task_title=title,
            branch_name=spec.branch_name,
            worktree_path=spec.worktree_path,
            base_ref=spec.base_ref,
            prompt=prompt,
        )
        payload = build_conversation_payload(launch, agent_settings=agent_settings)
        try:
            conversation_id = self._launcher.launch(payload)
        except Exception as exc:
            self._repo.mark_state(
                task_id,
                WorktreeState.FAILED,
                notes=f"launch failed: {exc}",
            )
            raise
        self._repo.mark_state(
            task_id,
            WorktreeState.LAUNCHED,
            conversation_id=conversation_id,
        )
        return TaskLaunchResult(
            task_id=task_id,
            conversation_id=conversation_id,
            worktree_path=spec.worktree_path,
            branch_name=spec.branch_name,
            launched=True,
        )

    def register_pull_request(
        self, task_id: str, pr_number: int
    ) -> AgentWorktreeRecord:
        """Record the pull request a child opened. Called by the coordinator.

        The coordinator is the only component that observes GitHub; this records
        what it saw so cleanup has a PR number to verify. It does not itself
        decide merge status.
        """
        return self._repo.mark_state(
            task_id, WorktreeState.PR_OPEN, pr_number=pr_number
        )

    def recover_interrupted(self) -> list[str]:
        """Tasks a coordinator may safely re-drive without duplicating work.

        Returns tasks that were registered but never launched, or whose launch
        failed. A task whose child was launched is deliberately excluded: its
        worktree and conversation are left intact so a live agent is never
        disturbed. The next :meth:`launch` reuses the existing worktree.
        """
        records = self._repo.list_by_state(*_RECOVERABLE_STATES)
        return [record.task_id for record in records]

    def cleanup_after_merge(self, task_id: str) -> CleanupOutcome:
        """Remove the worktree only after GitHub confirms the PR merged.

        Verification is performed here, not taken from the caller: the specific
        pull request must exist, be merged, and target the integration branch.
        A dirty worktree or an unmerged branch is refused by the manager, which
        validates before mutating.
        """
        record = self._repo.get(task_id)
        if record is None:
            return CleanupOutcome(task_id, False, False, "no worktree registration")
        if record.pr_number is None:
            return CleanupOutcome(
                task_id, False, False, "no pull request recorded for task"
            )
        if self._github is None:
            return CleanupOutcome(
                task_id,
                False,
                False,
                "github client unavailable; cannot verify merge",
            )
        verification = verify_pull_request_merged(
            self._github,
            repository=self._repository,
            pull_number=record.pr_number,
            integration_branch=self._integration_branch,
        )
        if not verification.verified:
            return CleanupOutcome(task_id, False, False, verification.reason)
        result = self._manager.cleanup(task_id, merged=True)
        notes = "; ".join(result.notes) or verification.reason
        removed = result.removed_worktree or result.deleted_branch
        if removed:
            self._repo.mark_state(task_id, WorktreeState.MERGED, notes=notes)
        return CleanupOutcome(task_id, removed, True, notes)


def worktree_manager_from_env(
    *,
    repo_root: Path | str | None = None,
    fetch: bool = True,
) -> WorktreeManager:
    """Build a :class:`WorktreeManager` from environment configuration.

    ``DEVELOPMENT_OPS_REPO_ROOT`` is the primary checkout (default: cwd).
    ``DEVELOPMENT_OPS_WORKTREE_ROOT`` holds task worktrees outside it (default:
    ``/tmp/ai-solutions-lab-worktrees``). ``DEVELOPMENT_OPS_WORKTREE_BRANCH_PREFIX``
    defaults to ``cursor/``.
    """
    root = repo_root or os.environ.get("DEVELOPMENT_OPS_REPO_ROOT") or Path.cwd()
    worktree_root = (
        os.environ.get("DEVELOPMENT_OPS_WORKTREE_ROOT")
        or "/tmp/ai-solutions-lab-worktrees"
    )
    return WorktreeManager(
        root,
        worktree_root,
        base_branch=os.environ.get(
            "DEVELOPMENT_OPS_BASE_BRANCH", AUTONOMOUS_INTEGRATION_BRANCH
        ),
        remote=os.environ.get("DEVELOPMENT_OPS_REMOTE", "origin"),
        branch_prefix=os.environ.get(
            "DEVELOPMENT_OPS_WORKTREE_BRANCH_PREFIX", "cursor/"
        ),
        fetch=fetch,
    )

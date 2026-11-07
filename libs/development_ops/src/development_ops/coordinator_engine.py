"""Coordinator reconciliation, scheduling, and PR housekeeping."""

from __future__ import annotations

import os
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from development_ops.backlog import BacklogDocument, load_backlog
from development_ops.github_client import (
    AUTONOMOUS_INTEGRATION_BRANCH,
    AutoMergeAttempt,
    GitHubClient,
    PullRequestState,
)
from development_ops.models import ActivityEventCreate, GitHubReference
from development_ops.persistence.coordinator_repository import CoordinatorTaskRepository
from development_ops.persistence.orm import CoordinatorTaskORM
from development_ops.recorder import ActivityRecorder
from development_ops.scheduling import (
    IN_FLIGHT_STATUSES,
    CoordinatorTaskView,
    RuntimeTaskStatus,
    merge_backlog_with_runtime,
    select_next_eligible,
)
from development_ops.task_worktrees import TaskWorktreeOrchestrator
from development_ops.taxonomy import EventSeverity, EventType
from development_ops.worktrees import WorktreeError

IN_FLIGHT_STATUSES_VALUES = frozenset(status.value for status in IN_FLIGHT_STATUSES)


@dataclass(frozen=True, slots=True)
class CoordinatorTickResult:
    run_id: uuid.UUID
    recovery: bool
    selected_task_id: str | None
    selected_task_title: str | None
    skipped_duplicate: bool
    active_tasks: int
    open_pull_requests: tuple[int, ...]
    auto_merge_attempts: tuple[AutoMergeAttempt, ...]
    held_for_dependency: tuple[str, ...]
    blocked_tasks: tuple[str, ...]
    notes: tuple[str, ...]
    prepared_worktree: str | None = None
    recovered_worktrees: tuple[str, ...] = ()
    cleaned_worktrees: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["run_id"] = str(self.run_id)
        payload["auto_merge_attempts"] = [
            asdict(item) for item in self.auto_merge_attempts
        ]
        return payload


class CoordinatorEngine:
    def __init__(
        self,
        session: Session,
        *,
        github: GitHubClient | None,
        recorder: ActivityRecorder,
        run_id: uuid.UUID,
        repository: str,
        backlog_path: Path | None = None,
        worktrees: TaskWorktreeOrchestrator | None = None,
    ) -> None:
        self._session = session
        self._github = github
        self._recorder = recorder
        self._run_id = run_id
        self._repository = repository
        self._backlog_path = backlog_path
        self._tasks = CoordinatorTaskRepository(session)
        # Optional: worktree isolation for child agents. When absent the
        # coordinator schedules and reconciles exactly as before.
        self._worktrees = worktrees

    def tick(self) -> CoordinatorTickResult:
        document = load_backlog(self._backlog_path)
        self._tasks.sync_catalog(document)
        self._session.expire_all()
        reclaimed: list[str] = []
        if os.environ.get("DEVELOPMENT_OPS_RECLAIM_STALE") == "1":
            reclaimed = self._tasks.reclaim_expired_leases()
        notes: list[str] = []
        if reclaimed:
            notes.append("reclaimed expired leases: " + ", ".join(sorted(reclaimed)))
        open_prs: list[int] = []
        auto_attempts: list[AutoMergeAttempt] = []
        prepared_worktree: str | None = None
        recovered_worktrees: list[str] = []
        cleaned_worktrees: list[str] = []

        github_reconciled = False
        if self._github is not None:
            try:
                pr_states = self._github.list_open_pull_requests(self._repository)
                github_reconciled = True
            except RuntimeError as exc:
                notes.append(f"github list failed: {exc}")
                pr_states = []
            open_prs = [pr.number for pr in pr_states]
            if github_reconciled:
                self._reconcile_pull_requests(document, pr_states, auto_attempts, notes)
                cleaned_worktrees = self._reconcile_worktrees(notes)
        else:
            notes.append("github client unavailable; using persisted task state only")

        views = self._task_views(document)
        # Only tasks actively being implemented consume a slot. Open PRs and
        # tasks awaiting merge have released their implementer.
        active_count = self._tasks.count_slot_consuming()
        max_concurrent = int(os.environ.get("DEVELOPMENT_OPS_MAX_CONCURRENT", "3"))
        resume_task_id = os.environ.get("DEVELOPMENT_OPS_TASK_ID", "").strip()
        selected_id: str | None = None
        selected_title: str | None = None
        skipped_duplicate = False
        if resume_task_id:
            resume_view = next(
                (view for view in views if view.task_id == resume_task_id),
                None,
            )
            if resume_view and resume_view.runtime_status in IN_FLIGHT_STATUSES:
                selected_id = resume_view.task_id
                selected_title = resume_view.title
                notes.append(f"resumed in-flight task {resume_task_id}")
        decision = select_next_eligible(
            views,
            max_concurrent=max_concurrent,
            active_count=active_count,
        )
        if selected_id is None and decision.task is not None:
            existing = self._tasks.get(decision.task.task_id)
            if (
                existing is not None
                and existing.status in IN_FLIGHT_STATUSES_VALUES
                and existing.active_run_id != self._run_id
            ):
                skipped_duplicate = True
                notes.append(
                    f"skipped duplicate assignment for {decision.task.task_id} "
                    f"(owned by run {existing.active_run_id})"
                )
            else:
                claimed = self._tasks.claim_for_implementation(
                    decision.task.task_id,
                    run_id=self._run_id,
                    owner_agent=os.environ.get(
                        "DEVELOPMENT_OPS_AGENT_NAME", "coordinator"
                    ),
                )
                if claimed:
                    selected_id = decision.task.task_id
                    selected_title = decision.task.title
                    self._record_scheduled(selected_id, selected_title)
                    prepared_worktree = self._prepare_worktree_for(
                        selected_id, selected_title, notes
                    )
                else:
                    # Lost the race to a concurrent tick, or the row became
                    # ineligible between selection and claim.
                    skipped_duplicate = True
                    notes.append(
                        f"skipped duplicate assignment for "
                        f"{decision.task.task_id} (claim lost)"
                    )
        elif selected_id is not None and resume_task_id:
            self._record_recovery_only(selected_id, notes)
            return CoordinatorTickResult(
                run_id=self._run_id,
                recovery=True,
                selected_task_id=selected_id,
                selected_task_title=selected_title,
                skipped_duplicate=skipped_duplicate,
                active_tasks=active_count,
                open_pull_requests=tuple(open_prs),
                auto_merge_attempts=tuple(auto_attempts),
                held_for_dependency=tuple(
                    item.task_id for item in decision.held_for_dependency
                ),
                blocked_tasks=tuple(item.task_id for item in decision.blocked),
                notes=tuple(notes),
                prepared_worktree=prepared_worktree,
                recovered_worktrees=tuple(recovered_worktrees),
                cleaned_worktrees=tuple(cleaned_worktrees),
            )

        self._record_recovery(
            open_prs=tuple(open_prs),
            selected_task_id=selected_id,
            notes=notes,
            auto_attempts=auto_attempts,
            active_count=active_count,
        )

        return CoordinatorTickResult(
            run_id=self._run_id,
            recovery=True,
            selected_task_id=selected_id,
            selected_task_title=selected_title,
            skipped_duplicate=skipped_duplicate,
            active_tasks=active_count,
            open_pull_requests=tuple(open_prs),
            auto_merge_attempts=tuple(auto_attempts),
            held_for_dependency=tuple(
                item.task_id for item in decision.held_for_dependency
            ),
            blocked_tasks=tuple(item.task_id for item in decision.blocked),
            notes=tuple(notes),
            prepared_worktree=prepared_worktree,
            recovered_worktrees=tuple(recovered_worktrees),
            cleaned_worktrees=tuple(cleaned_worktrees),
        )

    def register_pull_request_opened(
        self,
        task_id: str,
        *,
        pull_number: int,
        branch_name: str,
        title: str,
        base_branch: str | None = None,
        awaiting_merge: bool = False,
    ) -> None:
        self._tasks.mark_pr_open(
            task_id,
            run_id=self._run_id,
            branch_name=branch_name,
            pr_number=pull_number,
            owner_agent=os.environ.get("DEVELOPMENT_OPS_AGENT_NAME"),
            base_branch=base_branch,
            awaiting_merge=awaiting_merge,
        )
        self._recorder.record(
            ActivityEventCreate(
                run_id=self._run_id,
                task_id=task_id,
                event_type=EventType.PR_OPENED,
                severity=EventSeverity.NOTICE,
                title=title,
                idempotency_key=f"{self._run_id}:pr.opened:{pull_number}",
                github=GitHubReference(
                    repository=self._repository,
                    pull_number=pull_number,
                ),
            )
        )
        # Record the PR on the worktree registry so cleanup can verify the exact
        # PR later. Tasks without a worktree registration (legacy work) are
        # unaffected.
        if self._worktrees is not None:
            record = self._worktrees.registry.get(task_id)
            if record is not None:
                self._worktrees.register_pull_request(task_id, pull_number)

    def _prepare_worktree_for(
        self, task_id: str, title: str, notes: list[str]
    ) -> str | None:
        """Create the isolated worktree for a freshly claimed task.

        Returns the worktree path, or ``None`` when worktree isolation is not
        configured. A failure is recorded as a note and does not abort the tick:
        the task stays claimed and the operator sees the reason.
        """
        if self._worktrees is None:
            return None
        try:
            record = self._worktrees.prepare(task_id, title=title)
        except WorktreeError as exc:
            notes.append(f"worktree prepare failed for {task_id}: {exc}")
            return None
        notes.append(f"prepared worktree for {task_id} at {record.worktree_path}")
        return record.worktree_path

    def _reconcile_worktrees(self, notes: list[str]) -> list[str]:
        """Clean up worktrees whose PRs GitHub confirms merged.

        Returns the task ids cleaned. A worktree is removed only after the
        orchestrator re-verifies the merge against GitHub; unmerged or dirty
        worktrees are left in place and surfaced in the notes.
        """
        if self._worktrees is None:
            return []
        cleaned: list[str] = []
        for record in self._worktrees.registry.list_all():
            if record.pr_number is None or record.state.value == "merged":
                continue
            outcome = self._worktrees.cleanup_after_merge(record.task_id)
            if outcome.cleaned:
                cleaned.append(record.task_id)
                notes.append(f"cleaned worktree for {record.task_id}: {outcome.reason}")
            elif outcome.verified_merge:
                notes.append(f"worktree cleanup skipped for {record.task_id}")
        return cleaned

    def release_assignment(
        self,
        task_id: str,
        *,
        reason: str,
        run_id: uuid.UUID | None = None,
        force: bool = False,
    ) -> bool:
        return self._tasks.release_stale_assignment(
            task_id, reason=reason, run_id=run_id, force=force
        )

    def _task_views(self, document: BacklogDocument) -> list[CoordinatorTaskView]:
        rows = {row.task_id: row for row in self._tasks.list_tasks()}
        runtime = {
            task_id: RuntimeTaskStatus(row.status) for task_id, row in rows.items()
        }
        pr_numbers = {task_id: row.pr_number for task_id, row in rows.items()}
        branches = {task_id: row.branch_name for task_id, row in rows.items()}
        blocked = {task_id: row.blocked_reason for task_id, row in rows.items()}
        return merge_backlog_with_runtime(
            document.tasks,
            runtime,
            pr_by_task=pr_numbers,
            branch_by_task=branches,
            blocked_by_task=blocked,
        )

    def _reconcile_pull_requests(
        self,
        document: BacklogDocument,
        pr_states: list[PullRequestState],
        auto_attempts: list[AutoMergeAttempt],
        notes: list[str],
    ) -> None:
        by_pr = {state.number: state for state in pr_states}
        for task in document.tasks:
            row = self._tasks.get(task.id)
            pr_number = task.pr_number or (row.pr_number if row else None)
            if pr_number is None:
                continue
            state = by_pr.get(pr_number)
            if state is None:
                self._reconcile_missing_pull_request(
                    task.id, pr_number, row, task.merge_commit, notes
                )
                continue
            if state.merged:
                self._tasks.mark_merged(task.id, merge_commit_sha=None)
                continue
            if state.closed_unmerged:
                self._tasks.mark_blocked(
                    task.id, f"pull request #{pr_number} closed without merge"
                )
                notes.append(f"pr #{pr_number} closed without merge; task blocked")
                continue
            if row is not None and row.status == RuntimeTaskStatus.PENDING.value:
                self._tasks.mark_pr_open(
                    task.id,
                    run_id=row.active_run_id or self._run_id,
                    branch_name=state.head_ref,
                    pr_number=state.number,
                    owner_agent=row.owner_agent,
                    base_branch=state.base_ref,
                )
            self._maybe_attempt_auto_merge(task.id, state, auto_attempts, notes)

    def _reconcile_missing_pull_request(
        self,
        task_id: str,
        pr_number: int,
        row: CoordinatorTaskORM | None,
        catalog_merge_commit: str | None,
        notes: list[str],
    ) -> None:
        """A task PR that is absent from the open list is merged or closed.

        Distinguish the two by fetching the pull request directly. Merged work is
        terminal and clears ownership; a closed-without-merge PR blocks the task
        for human attention instead of silently claiming success.
        """
        if row is None or row.status not in IN_FLIGHT_STATUSES_VALUES:
            return
        if self._github is None:
            return
        try:
            state = self._github.get_pull_request(self._repository, pr_number)
        except RuntimeError as exc:
            notes.append(f"pr #{pr_number} lookup failed: {exc}")
            return
        if state.merged:
            self._tasks.mark_merged(task_id, merge_commit_sha=catalog_merge_commit)
            notes.append(f"pr #{pr_number} merged externally")
            return
        if state.closed_unmerged:
            self._tasks.mark_blocked(
                task_id, f"pull request #{pr_number} closed without merge"
            )
            notes.append(f"pr #{pr_number} closed without merge; task blocked")
            return
        notes.append(f"pr #{pr_number} is not open but not merged; leaving task state")

    def _maybe_attempt_auto_merge(
        self,
        task_id: str,
        state: PullRequestState,
        auto_attempts: list[AutoMergeAttempt],
        notes: list[str],
    ) -> None:
        """Attempt squash auto-merge only for green PRs targeting ``ai-dev``.

        Auto-merge into ``main`` or any other branch is never attempted, even if
        the base-branch guard is later relaxed elsewhere.
        """
        if os.environ.get("DEVELOPMENT_OPS_ATTEMPT_AUTO_MERGE", "1") != "1":
            return
        if state.auto_merge_enabled:
            return
        if not state.targets_integration_branch:
            notes.append(
                f"auto-merge skipped for pr #{state.number}: base "
                f"'{state.base_ref}' is not {AUTONOMOUS_INTEGRATION_BRANCH}"
            )
            return
        if state.checks_green is not True:
            notes.append(
                f"auto-merge skipped for pr #{state.number}: checks "
                f"{state.checks_state}"
            )
            return
        attempt = self._github.enable_squash_auto_merge(  # type: ignore[union-attr]
            self._repository,
            state.number,
        )
        auto_attempts.append(attempt)
        self._record_auto_merge(task_id, attempt)
        if attempt.error:
            notes.append(f"auto-merge pr #{state.number}: {attempt.error}; continuing")

    def _record_recovery_only(
        self, selected_task_id: str | None, notes: list[str]
    ) -> None:
        self._recorder.record(
            ActivityEventCreate(
                run_id=self._run_id,
                event_type=EventType.COORDINATOR_RECOVERY,
                severity=EventSeverity.INFO,
                title="Coordinator resumed existing assignment",
                summary="; ".join(notes) if notes else None,
                metadata={"selected_task_id": selected_task_id, "resumed": True},
            )
        )

    def _record_recovery(
        self,
        *,
        open_prs: tuple[int, ...],
        selected_task_id: str | None,
        notes: list[str],
        auto_attempts: list[AutoMergeAttempt],
        active_count: int,
    ) -> None:
        self._recorder.record(
            ActivityEventCreate(
                run_id=self._run_id,
                event_type=EventType.COORDINATOR_RECOVERY,
                severity=EventSeverity.INFO,
                title="Coordinator recovery tick",
                summary="; ".join(notes) if notes else None,
                metadata={
                    "open_pull_requests": list(open_prs),
                    "selected_task_id": selected_task_id,
                    "auto_merge_errors": [
                        item.error for item in auto_attempts if item.error
                    ],
                },
                idempotency_key=(
                    f"{self._run_id}:coordinator.recovery:"
                    f"{selected_task_id or 'none'}:{active_count}"
                ),
            )
        )

    def _record_scheduled(self, task_id: str, title: str) -> None:
        self._recorder.record(
            ActivityEventCreate(
                run_id=self._run_id,
                task_id=task_id,
                event_type=EventType.COORDINATOR_SCHEDULED,
                severity=EventSeverity.NOTICE,
                title=f"Scheduled {task_id}",
                summary=title,
                idempotency_key=f"{self._run_id}:coordinator.scheduled:{task_id}",
            )
        )
        self._recorder.record(
            ActivityEventCreate(
                run_id=self._run_id,
                task_id=task_id,
                event_type=EventType.TASK_SELECTED,
                severity=EventSeverity.INFO,
                title=f"Task selected: {task_id}",
                summary=title,
                idempotency_key=f"{self._run_id}:task.selected:{task_id}",
            )
        )

    def _record_auto_merge(self, task_id: str, attempt: AutoMergeAttempt) -> None:
        severity = (
            EventSeverity.INFO
            if attempt.auto_merge_request_present
            else EventSeverity.WARNING
        )
        self._recorder.record(
            ActivityEventCreate(
                run_id=self._run_id,
                task_id=task_id,
                event_type=EventType.COORDINATOR_AUTO_MERGE,
                severity=severity,
                title=f"Auto-merge attempt for PR #{attempt.pull_number}",
                summary=attempt.error,
                metadata={
                    "pull_number": attempt.pull_number,
                    "auto_merge_request_present": attempt.auto_merge_request_present,
                },
                idempotency_key=(
                    f"{self._run_id}:coordinator.auto_merge:{attempt.pull_number}"
                ),
            )
        )

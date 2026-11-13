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
    AutoMergeAttempt,
    GitHubClient,
    PullRequestState,
)
from development_ops.models import ActivityEventCreate, GitHubReference
from development_ops.persistence.coordinator_repository import CoordinatorTaskRepository
from development_ops.recorder import ActivityRecorder
from development_ops.scheduling import (
    CoordinatorTaskView,
    RuntimeTaskStatus,
    is_active,
    merge_backlog_with_runtime,
    select_next_eligible,
)
from development_ops.taxonomy import EventSeverity, EventType


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
    ) -> None:
        self._session = session
        self._github = github
        self._recorder = recorder
        self._run_id = run_id
        self._repository = repository
        self._backlog_path = backlog_path
        self._tasks = CoordinatorTaskRepository(session)

    def tick(self) -> CoordinatorTickResult:
        document = load_backlog(self._backlog_path)
        self._tasks.sync_catalog(document)
        self._session.expire_all()
        if os.environ.get("DEVELOPMENT_OPS_RECLAIM_STALE") == "1":
            for row in self._tasks.list_tasks():
                if (
                    row.active_run_id
                    and row.active_run_id != self._run_id
                    and is_active(RuntimeTaskStatus(row.status))
                ):
                    self._tasks.release_stale_assignment(
                        row.task_id,
                        reason="stale assignment reclaimed on coordinator recovery",
                        run_id=row.active_run_id,
                    )
        notes: list[str] = []
        open_prs: list[int] = []
        auto_attempts: list[AutoMergeAttempt] = []

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
        else:
            notes.append("github client unavailable; using persisted task state only")

        views = self._task_views(document)
        # Open pull requests awaiting human review stay PR_OPEN; they must not
        # consume implementation concurrency slots (see COORDINATOR_CONTINUITY.md).
        active_count = sum(
            1 for view in views if view.runtime_status == RuntimeTaskStatus.IN_PROGRESS
        )
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
            if resume_view and resume_view.runtime_status in {
                RuntimeTaskStatus.IN_PROGRESS,
                RuntimeTaskStatus.PR_OPEN,
            }:
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
                decision.task.pr_number is not None
                and decision.task.pr_number in open_prs
            ):
                # The catalog already carries an open pull request for this task.
                # Treat it as an existing assignment and never dispatch it again.
                self._tasks.mark_pr_open(
                    decision.task.task_id,
                    run_id=self._run_id,
                    branch_name=decision.task.branch_name or decision.task.task_id,
                    pr_number=decision.task.pr_number,
                    owner_agent=os.environ.get(
                        "DEVELOPMENT_OPS_AGENT_NAME", "coordinator"
                    ),
                )
                skipped_duplicate = True
                notes.append(
                    f"catalog task {decision.task.task_id} already has open pr "
                    f"#{decision.task.pr_number}; skipped new assignment"
                )
            elif (
                existing is not None
                and is_active(RuntimeTaskStatus(existing.status))
                and existing.active_run_id != self._run_id
                and os.environ.get("DEVELOPMENT_OPS_RECLAIM_STALE") != "1"
            ):
                skipped_duplicate = True
                notes.append(
                    f"skipped duplicate assignment for {decision.task.task_id} "
                    f"(owned by run {existing.active_run_id})"
                )
            else:
                selected_id = decision.task.task_id
                selected_title = decision.task.title
                self._tasks.mark_in_progress(
                    selected_id,
                    run_id=self._run_id,
                    owner_agent=os.environ.get(
                        "DEVELOPMENT_OPS_AGENT_NAME", "coordinator"
                    ),
                )
                self._record_scheduled(selected_id, selected_title)
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
        )

    def register_pull_request_opened(
        self,
        task_id: str,
        *,
        pull_number: int,
        branch_name: str,
        title: str,
    ) -> None:
        self._tasks.mark_pr_open(
            task_id,
            run_id=self._run_id,
            branch_name=branch_name,
            pr_number=pull_number,
            owner_agent=os.environ.get("DEVELOPMENT_OPS_AGENT_NAME"),
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

    def release_assignment(
        self, task_id: str, *, reason: str, run_id: uuid.UUID | None = None
    ) -> bool:
        return self._tasks.release_stale_assignment(
            task_id, reason=reason, run_id=run_id
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
            if task.pr_number is None:
                continue
            state = by_pr.get(task.pr_number)
            row = self._tasks.get(task.id)
            if state is None:
                if row and row.status in {
                    RuntimeTaskStatus.PR_OPEN.value,
                    RuntimeTaskStatus.MERGE_READY.value,
                }:
                    notes.append(f"pr #{task.pr_number} closed or merged externally")
                    self._tasks.mark_merged(task.id, merge_commit_sha=task.merge_commit)
                continue
            if state.merged:
                self._tasks.mark_merged(task.id, merge_commit_sha=None)
                continue
            if row is not None and row.status in {
                RuntimeTaskStatus.PENDING.value,
                RuntimeTaskStatus.ASSIGNED.value,
                RuntimeTaskStatus.IN_PROGRESS.value,
            }:
                self._tasks.mark_pr_open(
                    task.id,
                    run_id=row.active_run_id or self._run_id,
                    branch_name=state.head_ref,
                    pr_number=state.number,
                    owner_agent=row.owner_agent,
                )
                row = self._tasks.get(task.id)
            # Merge readiness is recorded independently of auto-merge eligibility.
            # A clean, green pull request is merge-ready even when GitHub refuses
            # to arm auto-merge ("Pull request is in clean status"); that refusal
            # is not a test failure and never authorizes bypassing branch rules.
            if (
                state.merge_ready
                and row is not None
                and row.status
                in {
                    RuntimeTaskStatus.IN_PROGRESS.value,
                    RuntimeTaskStatus.PR_OPEN.value,
                }
            ):
                self._tasks.mark_merge_ready(task.id)
                row = self._tasks.get(task.id)
            if (
                state.checks_green
                and not state.has_conflicts
                and not state.auto_merge_enabled
                and os.environ.get("DEVELOPMENT_OPS_ATTEMPT_AUTO_MERGE", "1") == "1"
            ):
                attempt = self._github.enable_squash_auto_merge(  # type: ignore[union-attr]
                    self._repository,
                    state.number,
                )
                auto_attempts.append(attempt)
                self._record_auto_merge(task.id, attempt)
                if attempt.error:
                    notes.append(
                        f"auto-merge pr #{state.number}: {attempt.error}; continuing"
                    )

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

"""Coordinator reconciliation, scheduling, and PR housekeeping."""

from __future__ import annotations

import os
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from development_ops.backlog import BacklogDocument, load_backlog
from development_ops.catalog import BacklogCatalogWriter, CatalogWriteError
from development_ops.child_orchestration import ChildOrchestrator, ChildTickOutcome
from development_ops.gate_github_client import AI_REVIEW_CHECK_NAME, GATE_APP_ID
from development_ops.github_client import (
    AutoMergeAttempt,
    GitHubClient,
    PullRequestState,
)
from development_ops.integration import (
    AUTONOMOUS_INTEGRATION_BRANCH,
    assert_authorized_base_branch,
)
from development_ops.models import ActivityEventCreate, GitHubReference
from development_ops.persistence.coordinator_repository import CoordinatorTaskRepository
from development_ops.persistence.orm import CoordinatorTaskORM
from development_ops.persistence.verdict_repository import ReviewVerdictRepository
from development_ops.recorder import ActivityRecorder
from development_ops.review_gate import CONCLUSION_SUCCESS, GateDecision, ReviewGate
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


def _utc_now() -> datetime:
    return datetime.now(tz=UTC)


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
    children: dict[str, Any] | None = None

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
        catalog: BacklogCatalogWriter | None = None,
        children: ChildOrchestrator | None = None,
        gate: ReviewGate | None = None,
        verdicts: ReviewVerdictRepository | None = None,
        gate_enabled: bool | None = None,
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
        # Optional: the sanctioned writer for catalog status. When absent the
        # coordinator only updates runtime state in PostgreSQL and the catalog
        # is left to humans. When present it records a verified merge in the
        # catalog so no implementation agent needs to edit the tracked file.
        self._catalog = catalog
        # Optional: bounded child-agent orchestration (Phase D). When absent no
        # child is launched and no execution state is tracked.
        self._children = children
        self._gate = gate
        self._verdicts = verdicts
        self._gate_enabled = gate is not None if gate_enabled is None else gate_enabled

    def tick(
        self,
        *,
        max_concurrent: int | None = None,
        reclaim_expired: bool | None = None,
        paused: bool | None = None,
    ) -> CoordinatorTickResult:
        """Run one reconciliation/scheduling cycle.

        ``max_concurrent`` and ``reclaim_expired`` override the environment
        defaults so a persistent runner can pass explicit policy (for example,
        ``max_concurrent=0`` while paused) without mutating process state.

        ``paused`` tells the child orchestrator whether new child launches are
        allowed. When omitted it is inferred from ``max_concurrent == 0`` so the
        existing pause mechanism continues to work without a new call path.
        """
        document = load_backlog(self._backlog_path)
        self._tasks.sync_catalog(document)
        self._session.expire_all()
        reclaimed: list[str] = []
        should_reclaim = (
            reclaim_expired
            if reclaim_expired is not None
            else os.environ.get("DEVELOPMENT_OPS_RECLAIM_STALE") == "1"
        )
        if should_reclaim:
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
        max_concurrent = (
            max_concurrent
            if max_concurrent is not None
            else int(os.environ.get("DEVELOPMENT_OPS_MAX_CONCURRENT", "3"))
        )
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
            child_outcome = self._run_child_pass(paused, max_concurrent, notes)
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
                children=child_outcome,
            )

        child_outcome = self._run_child_pass(paused, max_concurrent, notes)
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
            children=child_outcome,
        )

    def _run_child_pass(
        self,
        paused: bool | None,
        max_concurrent: int | None,
        notes: list[str],
    ) -> dict[str, Any] | None:
        """Run one child-orchestration pass and return its serialized outcome.

        Child execution is a separate concern from task scheduling: this only
        delegates a task the engine already claimed. Monitoring and recovery run
        every tick, including while paused, so existing children are never
        abandoned. Returns ``None`` when child orchestration is not configured.
        """
        if self._children is None:
            return None
        is_paused = paused if paused is not None else max_concurrent == 0
        outcome: ChildTickOutcome = self._children.tick(paused=is_paused)
        notes.extend(outcome.notes)
        if outcome.launched:
            notes.append("launched children: " + ", ".join(outcome.launched))
        if outcome.rejected:
            notes.append(
                "child launches rejected at limit: " + ", ".join(outcome.rejected)
            )
        return {
            "enabled": outcome.enabled,
            "active_children": outcome.active_children,
            "max_concurrent": outcome.max_concurrent,
            "launched": list(outcome.launched),
            "rejected": list(outcome.rejected),
            "stalled": list(outcome.stalled),
            "failed": list(outcome.failed),
            "recovered": list(outcome.recovered),
        }

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
        if base_branch is not None:
            # Fail fast rather than record a pull request the coordinator can
            # never auto-merge. ``develop`` and ``main`` are human branches.
            assert_authorized_base_branch(
                base_branch,
                operation=f"registering pr #{pull_number}",
            )
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
                self._record_catalog_merged(task.id, merge_commit=None, notes=notes)
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
            self._run_gate(task.id, state, notes)
            self._maybe_attempt_auto_merge(task.id, state, auto_attempts, notes)

    def _run_gate(
        self,
        task_id: str,
        state: PullRequestState,
        notes: list[str],
    ) -> None:
        if self._gate is None:
            return
        decision = self._gate.run(state.number)
        if self._verdicts is not None and decision.review_id is not None:
            self._mirror_verdict(task_id, state, decision, notes)
        self._record_gate(task_id, state, decision)
        if decision.is_success and decision.published:
            notes.append(
                f"gate: AI review success for pr #{state.number} "
                f"@{decision.head_sha[:12]}"
            )
        elif not decision.published:
            notes.append(
                f"gate: publish failed for pr #{state.number}: {decision.publish_error}"
            )
        else:
            notes.append(
                f"gate: {decision.conclusion} for pr #{state.number} "
                f"({decision.reason})"
            )

    def _mirror_verdict(
        self,
        task_id: str,
        state: PullRequestState,
        decision: GateDecision,
        notes: list[str],
    ) -> None:
        assert self._verdicts is not None
        try:
            _, created = self._verdicts.record(
                repository=self._repository,
                pull_number=state.number,
                head_sha=decision.head_sha,
                review_id=int(decision.review_id or 0),
                reviewer_login=decision.reviewer_login or "",
                reviewer_user_id=int(decision.reviewer_user_id or 0),
                verdict=decision.conclusion,
                blocking_count=decision.blocking_count,
                policy_version=decision.policy_version or "",
                reviewed_at=decision.reviewed_at or _utc_now(),
            )
        except Exception as exc:  # noqa: BLE001
            self._session.rollback()
            notes.append(f"gate: verdict mirror failed for pr #{state.number}: {exc}")
            return
        if created:
            self._recorder.record(
                ActivityEventCreate(
                    run_id=self._run_id,
                    task_id=task_id,
                    event_type=EventType.REVIEW_VERDICT_RECORDED,
                    severity=EventSeverity.INFO,
                    title=f"Recorded review verdict for PR #{state.number}",
                    metadata={
                        "pull_number": state.number,
                        "head_sha": decision.head_sha,
                        "review_id": decision.review_id,
                        "verdict": decision.conclusion,
                    },
                    github=GitHubReference(
                        repository=self._repository,
                        pull_number=state.number,
                        commit_sha=decision.head_sha,
                    ),
                    idempotency_key=(
                        f"review.verdict_recorded:{self._repository}:"
                        f"{state.number}:{decision.head_sha}:{decision.review_id}"
                    ),
                )
            )

    def _record_gate(
        self,
        task_id: str,
        state: PullRequestState,
        decision: GateDecision,
    ) -> None:
        if not decision.published:
            event_type = EventType.GATE_PUBLISH_FAILED
            severity = EventSeverity.WARNING
            title = f"AI review gate publish failed for PR #{state.number}"
        elif decision.is_success:
            event_type = EventType.GATE_PUBLISHED
            severity = EventSeverity.INFO
            title = f"AI review gate published success for PR #{state.number}"
        else:
            event_type = EventType.GATE_REJECTED
            severity = EventSeverity.NOTICE
            title = (
                f"AI review gate published {decision.conclusion} for PR #{state.number}"
            )
        self._recorder.record(
            ActivityEventCreate(
                run_id=self._run_id,
                task_id=task_id,
                event_type=event_type,
                severity=severity,
                title=title,
                summary=decision.reason,
                metadata={
                    "pull_number": state.number,
                    "head_sha": decision.head_sha,
                    "conclusion": decision.conclusion,
                    "published": decision.published,
                    "review_id": decision.review_id,
                    "verdict_id": decision.verdict_id,
                    "policy_version": decision.policy_version,
                },
                github=GitHubReference(
                    repository=self._repository,
                    pull_number=state.number,
                    commit_sha=decision.head_sha,
                ),
                idempotency_key=(
                    f"gate:{decision.conclusion}:{self._repository}:"
                    f"{state.number}:{decision.head_sha}"
                ),
            )
        )

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
            self._record_catalog_merged(
                task_id, merge_commit=catalog_merge_commit, notes=notes
            )
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
        """Attempt squash auto-merge only for eligible PRs targeting ``ai-dev``.

        Every gate is evaluated through :meth:`PullRequestState.auto_merge_blockers`
        so the coordinator and the client agree on what "eligible" means: base
        branch, checks, draft state, unresolved review threads, and merge
        conflicts. Auto-merge into ``main`` or ``develop`` is never attempted.
        A blocked PR is re-evaluated on every tick, so once the blocking
        condition clears (threads resolved, conflicts resolved, checks turn
        green) the next tick arms auto-merge without operator action.
        """
        if os.environ.get("DEVELOPMENT_OPS_ATTEMPT_AUTO_MERGE", "1") != "1":
            return
        if state.auto_merge_enabled:
            return
        blockers = state.auto_merge_blockers()
        if blockers:
            reason = "; ".join(blockers)
            notes.append(f"auto-merge blocked for pr #{state.number}: {reason}")
            self._record_auto_merge_blocked(task_id, state, reason)
            return
        if self._gate is not None:
            blocked = self._verify_ai_review_check(state, notes)
            if blocked is not None:
                return
        elif self._gate_enabled:
            notes.append(
                f"auto-merge skipped for pr #{state.number}: AI review gate is "
                "enabled but unavailable"
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

    def _verify_ai_review_check(
        self,
        state: PullRequestState,
        notes: list[str],
    ) -> str | None:
        """Independently verify the gate's check. Returns a block reason or None."""
        if self._github is None:
            notes.append(
                f"auto-merge skipped for pr #{state.number}: github client unavailable"
            )
            return "github client unavailable"
        try:
            live = self._github.get_pull_request(self._repository, state.number)
        except RuntimeError as exc:
            reason = f"live pull request re-read failed: {exc}"
            notes.append(f"auto-merge skipped for pr #{state.number}: {reason}")
            return reason
        if not live.targets_integration_branch:
            reason = (
                f"base branch '{live.base_ref}' is not {AUTONOMOUS_INTEGRATION_BRANCH}"
            )
            notes.append(f"auto-merge skipped for pr #{state.number}: {reason}")
            return reason
        if live.merged or live.closed:
            reason = "pull request is no longer open"
            notes.append(f"auto-merge skipped for pr #{state.number}: {reason}")
            return reason
        if not live.head_sha:
            reason = "live head sha unavailable"
            notes.append(f"auto-merge skipped for pr #{state.number}: {reason}")
            return reason
        if live.head_sha != state.head_sha:
            reason = (
                "head sha changed between listing and merge: "
                f"{state.head_sha[:12]} -> {live.head_sha[:12]}"
            )
            notes.append(f"auto-merge skipped for pr #{state.number}: {reason}")
            return reason

        get_check = getattr(self._github, "get_review_check", None)
        if get_check is None:
            reason = "github client cannot verify the AI review check"
            notes.append(f"auto-merge skipped for pr #{state.number}: {reason}")
            return reason
        try:
            check = get_check(self._repository, live.head_sha, AI_REVIEW_CHECK_NAME)
        except RuntimeError as exc:
            reason = f"AI review check lookup failed: {exc}"
            notes.append(f"auto-merge skipped for pr #{state.number}: {reason}")
            return reason
        if check is None:
            reason = "AI review check is absent for the current head sha"
            notes.append(f"auto-merge skipped for pr #{state.number}: {reason}")
            return reason
        if check.name != AI_REVIEW_CHECK_NAME:
            reason = f"check name '{check.name}' is not '{AI_REVIEW_CHECK_NAME}'"
            notes.append(f"auto-merge skipped for pr #{state.number}: {reason}")
            return reason
        if check.app_id != GATE_APP_ID:
            reason = f"AI review check is not from the gate App (app id {check.app_id})"
            notes.append(f"auto-merge skipped for pr #{state.number}: {reason}")
            return reason
        if check.head_sha != live.head_sha:
            reason = "AI review check is bound to a different head sha"
            notes.append(f"auto-merge skipped for pr #{state.number}: {reason}")
            return reason
        if check.conclusion != CONCLUSION_SUCCESS:
            reason = f"AI review conclusion '{check.conclusion}' is not success"
            notes.append(f"auto-merge skipped for pr #{state.number}: {reason}")
            return reason
        return None

    def _record_catalog_merged(
        self,
        task_id: str,
        *,
        merge_commit: str | None,
        notes: list[str],
    ) -> None:
        """Mark a task merged in the catalog through the sanctioned writer.

        Only reached after GitHub confirms the pull request merged, so the
        catalog never claims a merge that did not happen. A write failure is a
        note, not a fatal error: runtime state is already durable, and the next
        tick retries. This is the mechanism that removes the need for any
        implementation agent to edit ``data/coordinator/backlog.yaml``.
        """
        if self._catalog is None:
            return
        try:
            changed = self._catalog.mark_merged(task_id, merge_commit=merge_commit)
        except CatalogWriteError as exc:
            notes.append(f"catalog update failed for {task_id}: {exc}")
            return
        if changed:
            notes.append(f"catalog marked {task_id} merged")

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

    def _record_auto_merge_blocked(
        self, task_id: str, state: PullRequestState, reason: str
    ) -> None:
        """Record *why* an eligible-looking PR cannot be auto-merged yet.

        Idempotent per (PR, reason) so a PR that stays blocked across many ticks
        does not flood the activity log, while a change in the blocking reason
        is recorded as a new event.
        """
        self._recorder.record(
            ActivityEventCreate(
                run_id=self._run_id,
                task_id=task_id,
                event_type=EventType.COORDINATOR_AUTO_MERGE,
                severity=EventSeverity.WARNING,
                title=f"Auto-merge blocked for PR #{state.number}",
                summary=reason,
                metadata={
                    "pull_number": state.number,
                    "base_ref": state.base_ref,
                    "merge_state_status": state.merge_state_status,
                    "unresolved_threads": state.unresolved_threads,
                    "checks_state": state.checks_state,
                    "blockers": list(state.auto_merge_blockers()),
                },
                idempotency_key=(
                    f"coordinator.auto_merge_blocked:{state.number}:{reason}"
                ),
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

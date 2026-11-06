"""Convenience helpers for agent/coordinator instrumentation."""

from __future__ import annotations

import uuid
from typing import Any

from development_ops.models import ActivityEventCreate, GitHubReference
from development_ops.recorder import ActivityRecorder, RecordResult
from development_ops.taxonomy import EventSeverity, EventType


class RunContext:
    """Correlate milestones for one agent run."""

    def __init__(
        self,
        recorder: ActivityRecorder,
        *,
        run_id: uuid.UUID | None = None,
        task_id: str | None = None,
        agent_name: str | None = None,
        github_repository: str | None = None,
    ) -> None:
        self._recorder = recorder
        self.run_id = run_id or uuid.uuid4()
        self.task_id = task_id
        self.agent_name = agent_name
        self.github_repository = github_repository

    def _record(
        self,
        event_type: EventType,
        severity: EventSeverity,
        title: str,
        *,
        summary: str | None = None,
        metadata: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
        github: GitHubReference | None = None,
        attempt_slack: bool | None = None,
    ) -> RecordResult:
        gh = github or GitHubReference(repository=self.github_repository)
        payload = ActivityEventCreate(
            run_id=self.run_id,
            task_id=self.task_id,
            agent_name=self.agent_name,
            event_type=event_type,
            severity=severity,
            title=title,
            summary=summary,
            metadata=metadata or {},
            idempotency_key=idempotency_key,
            github=gh,
        )
        return self._recorder.record(payload, attempt_slack=attempt_slack)

    def run_started(self, title: str = "Agent run started") -> RecordResult:
        return self._record(
            EventType.RUN_STARTED,
            EventSeverity.INFO,
            title,
            idempotency_key=f"{self.run_id}:run.started",
        )

    def run_completed(self, title: str = "Agent run completed") -> RecordResult:
        return self._record(
            EventType.RUN_COMPLETED,
            EventSeverity.INFO,
            title,
            idempotency_key=f"{self.run_id}:run.completed",
        )

    def run_failed(self, title: str, *, summary: str | None = None) -> RecordResult:
        return self._record(
            EventType.RUN_FAILED,
            EventSeverity.ERROR,
            title,
            summary=summary,
        )

    def task_selected(self, task_id: str, title: str) -> RecordResult:
        self.task_id = task_id
        return self._record(
            EventType.TASK_SELECTED,
            EventSeverity.INFO,
            title,
            idempotency_key=f"{self.run_id}:task.selected:{task_id}",
        )

    def task_delegated(
        self,
        task_id: str,
        title: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> RecordResult:
        self.task_id = task_id
        return self._record(
            EventType.TASK_DELEGATED,
            EventSeverity.INFO,
            title,
            metadata=metadata,
        )

    def milestone(
        self,
        title: str,
        *,
        summary: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> RecordResult:
        return self._record(
            EventType.IMPLEMENTATION_MILESTONE,
            EventSeverity.NOTICE,
            title,
            summary=summary,
            metadata=metadata,
        )

    def tests_started(self, title: str = "Tests started") -> RecordResult:
        return self._record(
            EventType.TEST_STARTED,
            EventSeverity.INFO,
            title,
        )

    def tests_completed(
        self,
        title: str = "Tests completed",
        *,
        metadata: dict[str, Any] | None = None,
    ) -> RecordResult:
        return self._record(
            EventType.TEST_COMPLETED,
            EventSeverity.INFO,
            title,
            metadata=metadata,
        )

    def tests_failed(self, title: str, *, summary: str) -> RecordResult:
        return self._record(
            EventType.TEST_FAILED,
            EventSeverity.ERROR,
            title,
            summary=summary,
        )

    def review_started(self, title: str = "Review started") -> RecordResult:
        return self._record(
            EventType.REVIEW_STARTED,
            EventSeverity.INFO,
            title,
        )

    def review_completed(
        self,
        title: str,
        *,
        summary: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> RecordResult:
        return self._record(
            EventType.REVIEW_COMPLETED,
            EventSeverity.NOTICE,
            title,
            summary=summary,
            metadata=metadata,
        )

    def pr_opened(
        self,
        pull_number: int,
        title: str,
        *,
        actions_run_url: str | None = None,
    ) -> RecordResult:
        github = GitHubReference(
            repository=self.github_repository,
            pull_number=pull_number,
            actions_run_url=actions_run_url,
        )
        return self._record(
            EventType.PR_OPENED,
            EventSeverity.NOTICE,
            title,
            github=github,
            idempotency_key=f"{self.run_id}:pr.opened:{pull_number}",
        )

    def pr_updated(self, pull_number: int, title: str) -> RecordResult:
        github = GitHubReference(
            repository=self.github_repository,
            pull_number=pull_number,
        )
        return self._record(
            EventType.PR_UPDATED,
            EventSeverity.INFO,
            title,
            github=github,
        )

    def pr_merged(self, pull_number: int, title: str) -> RecordResult:
        github = GitHubReference(
            repository=self.github_repository,
            pull_number=pull_number,
        )
        return self._record(
            EventType.PR_MERGED,
            EventSeverity.NOTICE,
            title,
            github=github,
            idempotency_key=f"{self.run_id}:pr.merged:{pull_number}",
        )

    def blocker(self, title: str, *, summary: str) -> RecordResult:
        return self._record(
            EventType.BLOCKER_REPORTED,
            EventSeverity.WARNING,
            title,
            summary=summary,
        )

    def progress(
        self,
        title: str,
        *,
        summary: str | None = None,
        attempt_slack: bool | None = None,
    ) -> RecordResult:
        return self._record(
            EventType.PROGRESS_REPORT,
            EventSeverity.INFO,
            title,
            summary=summary,
            attempt_slack=attempt_slack,
        )

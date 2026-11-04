"""Coordinator lifecycle helpers for agent runs."""

from __future__ import annotations

import os
import uuid
from contextlib import contextmanager
from typing import Any, Iterator

from development_ops.cli import _session_factory
from development_ops.instrumentation import RunContext
from development_ops.recorder import ActivityRecorder, RecordResult


def run_id_from_env(*, required: bool = True) -> uuid.UUID:
    raw = os.environ.get("DEVELOPMENT_OPS_RUN_ID", "").strip()
    if not raw:
        if required:
            msg = "DEVELOPMENT_OPS_RUN_ID is not set"
            raise RuntimeError(msg)
        return uuid.uuid4()
    return uuid.UUID(raw)


def github_repository_from_env() -> str | None:
    value = os.environ.get("DEVELOPMENT_OPS_GITHUB_REPOSITORY", "").strip()
    return value or None


@contextmanager
def coordinator_run(
    *,
    notify_slack: bool = False,
    run_id: uuid.UUID | None = None,
    task_id: str | None = None,
) -> Iterator[RunContext]:
    """Open a database session and RunContext for coordinator milestones."""
    factory = _session_factory()
    session = factory()
    try:
        recorder = ActivityRecorder(session, notify_slack=notify_slack)
        ctx = RunContext(
            recorder,
            run_id=run_id or run_id_from_env(required=False),
            task_id=task_id or os.environ.get("DEVELOPMENT_OPS_TASK_ID"),
            agent_name=os.environ.get("DEVELOPMENT_OPS_AGENT_NAME", "coordinator"),
            github_repository=github_repository_from_env(),
        )
        yield ctx
    finally:
        session.close()


class CoordinatorWorkflow:
    """Named lifecycle milestones for coordinator-driven development runs."""

    def __init__(self, ctx: RunContext) -> None:
        self._ctx = ctx

    @property
    def run_id(self) -> uuid.UUID:
        return self._ctx.run_id

    def start(self, title: str = "Coordinator run started") -> RecordResult:
        return self._ctx.run_started(title)

    def select_task(self, task_id: str, title: str) -> RecordResult:
        return self._ctx.task_selected(task_id, title)

    def delegate_task(self, task_id: str, title: str, *, worker: str) -> RecordResult:
        return self._ctx.task_delegated(
            task_id,
            title,
            metadata={"worker": worker},
        )

    def implementation(self, title: str, **metadata: Any) -> RecordResult:
        return self._ctx.milestone(title, metadata=metadata or None)

    def tests_started(self, title: str = "Tests started") -> RecordResult:
        return self._ctx.tests_started(title)

    def tests_passed(
        self, title: str = "Tests passed", **metadata: Any
    ) -> RecordResult:
        return self._ctx.tests_completed(title, metadata=metadata or None)

    def tests_failed(self, title: str, *, summary: str) -> RecordResult:
        return self._ctx.tests_failed(title, summary=summary)

    def review_started(
        self, title: str = "Independent review requested"
    ) -> RecordResult:
        return self._ctx.review_started(title)

    def review_completed(
        self,
        title: str,
        *,
        summary: str | None = None,
        findings: list[str] | None = None,
    ) -> RecordResult:
        metadata = {"findings": findings} if findings else None
        return self._ctx.review_completed(title, summary=summary, metadata=metadata)

    def pr_created(
        self,
        pull_number: int,
        title: str,
        *,
        actions_run_url: str | None = None,
    ) -> RecordResult:
        return self._ctx.pr_opened(
            pull_number,
            title,
            actions_run_url=actions_run_url,
        )

    def pr_updated(self, pull_number: int, title: str) -> RecordResult:
        return self._ctx.pr_updated(pull_number, title)

    def pr_merged(self, pull_number: int, title: str) -> RecordResult:
        return self._ctx.pr_merged(pull_number, title)

    def blocker(self, title: str, *, summary: str) -> RecordResult:
        return self._ctx.blocker(title, summary=summary)

    def complete(self, title: str = "Coordinator run completed") -> RecordResult:
        return self._ctx.run_completed(title)

    def fail(self, title: str, *, summary: str) -> RecordResult:
        return self._ctx.run_failed(title, summary=summary)

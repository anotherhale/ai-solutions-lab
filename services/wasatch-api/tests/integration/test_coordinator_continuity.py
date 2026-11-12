"""Acceptance-style tests for coordinator continuity."""

from __future__ import annotations

import textwrap
import uuid
from pathlib import Path

import pytest
from development_ops.coordinator_engine import CoordinatorEngine
from development_ops.github_client import (
    AutoMergeAttempt,
    GitHubClient,
    PullRequestState,
)
from development_ops.persistence.coordinator_repository import (
    CoordinatorTaskRepository,
)
from development_ops.recorder import ActivityRecorder
from development_ops.scheduling import RuntimeTaskStatus
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from wasatch_api.testing.postgres import assert_engine_is_disposable


class FakeGitHub(GitHubClient):
    def __init__(self, prs: dict[int, PullRequestState]) -> None:
        self._prs = prs
        self.auto_merge_calls: list[int] = []

    def get_pull_request(self, repository: str, number: int) -> PullRequestState:
        return self._prs[number]

    def list_open_pull_requests(self, repository: str) -> list[PullRequestState]:
        return [pr for pr in self._prs.values() if not pr.merged and not pr.closed]

    def enable_squash_auto_merge(
        self, repository: str, number: int
    ) -> AutoMergeAttempt:
        self.auto_merge_calls.append(number)
        return AutoMergeAttempt(
            pull_number=number,
            requested=True,
            auto_merge_request_present=False,
            error="Pull request is in clean status",
            raw_response="graphql simulated failure",
        )


def _pr(
    number: int,
    *,
    merged: bool = False,
    checks_green: bool = True,
    base_ref: str = "ai-dev",
    closed: bool = False,
    checks_state: str = "green",
    unresolved_threads: int = 0,
    is_draft: bool = False,
) -> PullRequestState:
    return PullRequestState(
        number=number,
        state="CLOSED" if closed and not merged else ("MERGED" if merged else "OPEN"),
        merged=merged,
        mergeable="MERGEABLE",
        head_ref=f"cursor/task-{number}",
        base_ref=base_ref,
        node_id=f"PR_node_{number}",
        auto_merge_enabled=False,
        checks_green=checks_green,
        review_decision="REVIEW_REQUIRED",
        closed=closed or merged,
        checks_state=checks_state,
        unresolved_threads=unresolved_threads,
        is_draft=is_draft,
    )


@pytest.fixture(autouse=True)
def _reset_coordinator_tables(ops_engine: Engine) -> None:
    # Clean only the disposable ops-test database this fixture created.
    assert_engine_is_disposable(ops_engine)
    with ops_engine.begin() as connection:
        connection.execute(text("DELETE FROM development_ops.activity_events"))
        connection.execute(text("DELETE FROM development_ops.coordinator_tasks"))


@pytest.fixture
def ops_engine(ops_test_engine: Engine) -> Engine:
    """The disposable ops-test engine; coordinator code uses the passed session."""
    return ops_test_engine


@pytest.fixture
def backlog_file(tmp_path: Path) -> Path:
    path = tmp_path / "backlog.yaml"
    path.write_text(
        textwrap.dedent(
            """
            repository: example/test
            integration_branch: ai-dev
            tasks:
              - id: TASK-A
                title: Agent A work
                status: in_progress
                pr_number: 100
                branch: cursor/task-a
                depends_on: []
              - id: TASK-B
                title: Independent follow-on
                status: pending
                depends_on: []
              - id: TASK-C
                title: Depends on A
                status: pending
                depends_on: [TASK-A]
            """
        ).strip(),
        encoding="utf-8",
    )
    return path


def test_open_pr_does_not_block_independent_task(
    ops_engine: Engine, backlog_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DEVELOPMENT_OPS_ATTEMPT_AUTO_MERGE", "0")
    run_id = uuid.uuid4()
    session = sessionmaker(bind=ops_engine, autoflush=False)()
    github = FakeGitHub({100: _pr(100)})
    try:
        engine = CoordinatorEngine(
            session,
            github=github,
            recorder=ActivityRecorder(session, notify_slack=False),
            run_id=run_id,
            repository="example/test",
            backlog_path=backlog_file,
        )
        result = engine.tick()
        assert result.selected_task_id == "TASK-B"
        assert 100 in result.open_pull_requests
    finally:
        session.close()


def test_auto_merge_failure_does_not_stop_selection(
    ops_engine: Engine, backlog_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DEVELOPMENT_OPS_ATTEMPT_AUTO_MERGE", "1")
    run_id = uuid.uuid4()
    session = sessionmaker(bind=ops_engine, autoflush=False)()
    github = FakeGitHub({100: _pr(100, checks_green=True)})
    try:
        engine = CoordinatorEngine(
            session,
            github=github,
            recorder=ActivityRecorder(session, notify_slack=False),
            run_id=run_id,
            repository="example/test",
            backlog_path=backlog_file,
        )
        result = engine.tick()
        assert github.auto_merge_calls == [100]
        assert result.auto_merge_attempts[0].error is not None
        assert result.selected_task_id == "TASK-B"
    finally:
        session.close()


def test_dependency_held_until_parent_merged(
    ops_engine: Engine, backlog_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DEVELOPMENT_OPS_ATTEMPT_AUTO_MERGE", "0")
    run_id = uuid.uuid4()
    session = sessionmaker(bind=ops_engine, autoflush=False)()
    github = FakeGitHub({100: _pr(100)})
    try:
        engine = CoordinatorEngine(
            session,
            github=github,
            recorder=ActivityRecorder(session, notify_slack=False),
            run_id=run_id,
            repository="example/test",
            backlog_path=backlog_file,
        )
        result = engine.tick()
        assert "TASK-C" in result.held_for_dependency
    finally:
        session.close()


def test_recovery_reclaims_expired_lease(
    ops_engine: Engine, backlog_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DEVELOPMENT_OPS_ATTEMPT_AUTO_MERGE", "0")
    first_run = uuid.uuid4()
    second_run = uuid.uuid4()
    session = sessionmaker(bind=ops_engine, autoflush=False)()
    github = FakeGitHub({100: _pr(100)})
    try:
        engine = CoordinatorEngine(
            session,
            github=github,
            recorder=ActivityRecorder(session, notify_slack=False),
            run_id=first_run,
            repository="example/test",
            backlog_path=backlog_file,
        )
        first = engine.tick()
        assert first.selected_task_id == "TASK-B"
        # Simulate a crashed run: the TASK-B lease is now in the past.
        with ops_engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE development_ops.coordinator_tasks "
                    "SET lease_expires_at = now() - interval '1 hour' "
                    "WHERE task_id = 'TASK-B'"
                )
            )
        monkeypatch.setenv("DEVELOPMENT_OPS_RECLAIM_STALE", "1")
        engine2 = CoordinatorEngine(
            session,
            github=github,
            recorder=ActivityRecorder(session, notify_slack=False),
            run_id=second_run,
            repository="example/test",
            backlog_path=backlog_file,
        )
        result = engine2.tick()
        assert result.selected_task_id == "TASK-B"
    finally:
        session.close()


def test_recovery_does_not_reclaim_live_lease(
    ops_engine: Engine, backlog_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A fresh heartbeat must protect a running task from being stolen."""
    monkeypatch.setenv("DEVELOPMENT_OPS_ATTEMPT_AUTO_MERGE", "0")
    first_run = uuid.uuid4()
    second_run = uuid.uuid4()
    session = sessionmaker(bind=ops_engine, autoflush=False)()
    github = FakeGitHub({100: _pr(100)})
    try:
        engine = CoordinatorEngine(
            session,
            github=github,
            recorder=ActivityRecorder(session, notify_slack=False),
            run_id=first_run,
            repository="example/test",
            backlog_path=backlog_file,
        )
        first = engine.tick()
        assert first.selected_task_id == "TASK-B"
        monkeypatch.setenv("DEVELOPMENT_OPS_RECLAIM_STALE", "1")
        engine2 = CoordinatorEngine(
            session,
            github=github,
            recorder=ActivityRecorder(session, notify_slack=False),
            run_id=second_run,
            repository="example/test",
            backlog_path=backlog_file,
        )
        result = engine2.tick()
        # TASK-B is still owned by the live first run: it is neither reclaimed
        # nor re-selected, and its owner is unchanged.
        assert result.selected_task_id is None
        repo = CoordinatorTaskRepository(session)
        row = repo.get("TASK-B")
        assert row is not None
        assert row.status == RuntimeTaskStatus.IN_PROGRESS.value
        assert row.active_run_id == first_run
    finally:
        session.close()


# --- Phase A: slot accounting and atomic claims -------------------------------


def _write_backlog(path: Path, body: str) -> Path:
    path.write_text(textwrap.dedent(body).strip(), encoding="utf-8")
    return path


@pytest.fixture
def slot_backlog(tmp_path: Path) -> Path:
    return _write_backlog(
        tmp_path / "backlog.yaml",
        """
        repository: example/test
        integration_branch: ai-dev
        tasks:
          - id: TASK-A
            title: A
            status: in_progress
            pr_number: 101
            branch: cursor/task-a
            depends_on: []
          - id: TASK-B
            title: B
            status: in_progress
            pr_number: 102
            branch: cursor/task-b
            depends_on: []
          - id: TASK-C
            title: C
            status: in_progress
            pr_number: 103
            branch: cursor/task-c
            depends_on: []
          - id: TASK-D
            title: D
            status: pending
            depends_on: []
        """,
    )


def test_three_open_prs_do_not_block_new_implementation(
    ops_engine: Engine, slot_backlog: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Three open PRs must not consume the three implementation slots."""
    monkeypatch.setenv("DEVELOPMENT_OPS_ATTEMPT_AUTO_MERGE", "0")
    monkeypatch.setenv("DEVELOPMENT_OPS_MAX_CONCURRENT", "3")
    run_id = uuid.uuid4()
    session = sessionmaker(bind=ops_engine, autoflush=False)()
    github = FakeGitHub({101: _pr(101), 102: _pr(102), 103: _pr(103)})
    try:
        engine = CoordinatorEngine(
            session,
            github=github,
            recorder=ActivityRecorder(session, notify_slack=False),
            run_id=run_id,
            repository="example/test",
            backlog_path=slot_backlog,
        )
        result = engine.tick()
        assert result.selected_task_id == "TASK-D"
        assert result.active_tasks == 0
    finally:
        session.close()


def test_pr_open_does_not_consume_slot_but_in_progress_does(
    ops_engine: Engine, slot_backlog: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DEVELOPMENT_OPS_ATTEMPT_AUTO_MERGE", "0")
    run_id = uuid.uuid4()
    session = sessionmaker(bind=ops_engine, autoflush=False)()
    try:
        engine = CoordinatorEngine(
            session,
            github=None,
            recorder=ActivityRecorder(session, notify_slack=False),
            run_id=run_id,
            repository="example/test",
            backlog_path=slot_backlog,
        )
        engine.tick()
        repo = CoordinatorTaskRepository(session)
        # sync_catalog maps catalog in_progress to runtime pr_open.
        assert repo.get("TASK-A").status == RuntimeTaskStatus.PR_OPEN.value
        # Three PR-open tasks plus the newly claimed TASK-D: only D consumes a slot.
        assert repo.count_slot_consuming() == 1
        # A freshly claimed task consumes a slot.
        repo.mark_pending("TASK-A")
        assert (
            repo.claim_for_implementation(
                "TASK-A", run_id=uuid.uuid4(), owner_agent="x"
            )
            is True
        )
        assert repo.count_slot_consuming() == 2
    finally:
        session.close()


def test_concurrent_claims_have_exactly_one_owner(
    ops_engine: Engine, slot_backlog: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DEVELOPMENT_OPS_ATTEMPT_AUTO_MERGE", "0")
    session = sessionmaker(bind=ops_engine, autoflush=False)()
    try:
        from development_ops.backlog import load_backlog

        repo = CoordinatorTaskRepository(session)
        repo.sync_catalog(load_backlog(slot_backlog))
        run_a = uuid.uuid4()
        run_b = uuid.uuid4()
        won_a = repo.claim_for_implementation("TASK-D", run_id=run_a, owner_agent="a")
        won_b = repo.claim_for_implementation("TASK-D", run_id=run_b, owner_agent="b")
        assert won_a is True
        assert won_b is False
        row = repo.get("TASK-D")
        assert row is not None
        assert row.active_run_id == run_a
        assert row.attempt_count == 1
    finally:
        session.close()


def test_claim_refused_for_already_in_flight_task(
    ops_engine: Engine, slot_backlog: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DEVELOPMENT_OPS_ATTEMPT_AUTO_MERGE", "0")
    session = sessionmaker(bind=ops_engine, autoflush=False)()
    try:
        engine = CoordinatorEngine(
            session,
            github=None,
            recorder=ActivityRecorder(session, notify_slack=False),
            run_id=uuid.uuid4(),
            repository="example/test",
            backlog_path=slot_backlog,
        )
        engine.tick()  # claims TASK-D as in_progress
        repo = CoordinatorTaskRepository(session)
        assert (
            repo.claim_for_implementation(
                "TASK-D", run_id=uuid.uuid4(), owner_agent="other"
            )
            is False
        )
    finally:
        session.close()


def test_mark_merged_clears_ownership(
    ops_engine: Engine, slot_backlog: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DEVELOPMENT_OPS_ATTEMPT_AUTO_MERGE", "0")
    session = sessionmaker(bind=ops_engine, autoflush=False)()
    try:
        engine = CoordinatorEngine(
            session,
            github=None,
            recorder=ActivityRecorder(session, notify_slack=False),
            run_id=uuid.uuid4(),
            repository="example/test",
            backlog_path=slot_backlog,
        )
        engine.tick()
        repo = CoordinatorTaskRepository(session)
        repo.mark_merged("TASK-D", merge_commit_sha="abc123")
        row = repo.get("TASK-D")
        assert row is not None
        assert row.status == RuntimeTaskStatus.MERGED.value
        assert row.active_run_id is None
        assert row.owner_agent is None
        assert row.lease_expires_at is None
        assert repo.count_slot_consuming() == 0
    finally:
        session.close()


def test_mark_blocked_clears_ownership_and_blocks(
    ops_engine: Engine, slot_backlog: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DEVELOPMENT_OPS_ATTEMPT_AUTO_MERGE", "0")
    session = sessionmaker(bind=ops_engine, autoflush=False)()
    try:
        engine = CoordinatorEngine(
            session,
            github=None,
            recorder=ActivityRecorder(session, notify_slack=False),
            run_id=uuid.uuid4(),
            repository="example/test",
            backlog_path=slot_backlog,
        )
        engine.tick()
        repo = CoordinatorTaskRepository(session)
        repo.mark_blocked("TASK-D", "needs human decision")
        row = repo.get("TASK-D")
        assert row is not None
        assert row.status == RuntimeTaskStatus.BLOCKED.value
        assert row.blocked_reason == "needs human decision"
        assert row.active_run_id is None
        assert repo.count_slot_consuming() == 0
    finally:
        session.close()


def test_heartbeat_extends_lease_only_for_owner(
    ops_engine: Engine, slot_backlog: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DEVELOPMENT_OPS_ATTEMPT_AUTO_MERGE", "0")
    session = sessionmaker(bind=ops_engine, autoflush=False)()
    try:
        engine = CoordinatorEngine(
            session,
            github=None,
            recorder=ActivityRecorder(session, notify_slack=False),
            run_id=uuid.uuid4(),
            repository="example/test",
            backlog_path=slot_backlog,
        )
        engine.tick()
        repo = CoordinatorTaskRepository(session)
        row = repo.get("TASK-D")
        assert row is not None and row.active_run_id is not None
        owner = row.active_run_id
        first_expiry = row.lease_expires_at
        assert first_expiry is not None
        assert repo.heartbeat("TASK-D", run_id=owner) is True
        assert repo.heartbeat("TASK-D", run_id=uuid.uuid4()) is False
        session.expire_all()
        refreshed = repo.get("TASK-D")
        assert refreshed is not None
        assert refreshed.lease_expires_at is not None
        assert refreshed.lease_expires_at >= first_expiry
    finally:
        session.close()


# --- Phase E: merge safety ----------------------------------------------------


def test_auto_merge_refused_for_main(
    ops_engine: Engine, backlog_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A green PR targeting main must never receive an auto-merge request."""
    monkeypatch.setenv("DEVELOPMENT_OPS_ATTEMPT_AUTO_MERGE", "1")
    run_id = uuid.uuid4()
    session = sessionmaker(bind=ops_engine, autoflush=False)()
    github = FakeGitHub({100: _pr(100, base_ref="main", checks_green=True)})
    try:
        engine = CoordinatorEngine(
            session,
            github=github,
            recorder=ActivityRecorder(session, notify_slack=False),
            run_id=run_id,
            repository="example/test",
            backlog_path=backlog_file,
        )
        engine.tick()
        assert github.auto_merge_calls == []
    finally:
        session.close()


def test_auto_merge_allowed_for_green_ai_dev_pr(
    ops_engine: Engine, backlog_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DEVELOPMENT_OPS_ATTEMPT_AUTO_MERGE", "1")
    run_id = uuid.uuid4()
    session = sessionmaker(bind=ops_engine, autoflush=False)()
    github = FakeGitHub({100: _pr(100, base_ref="ai-dev", checks_green=True)})
    try:
        engine = CoordinatorEngine(
            session,
            github=github,
            recorder=ActivityRecorder(session, notify_slack=False),
            run_id=run_id,
            repository="example/test",
            backlog_path=backlog_file,
        )
        engine.tick()
        assert github.auto_merge_calls == [100]
    finally:
        session.close()


def test_auto_merge_refused_when_checks_not_green(
    ops_engine: Engine, backlog_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DEVELOPMENT_OPS_ATTEMPT_AUTO_MERGE", "1")
    run_id = uuid.uuid4()
    session = sessionmaker(bind=ops_engine, autoflush=False)()
    github = FakeGitHub(
        {100: _pr(100, base_ref="ai-dev", checks_green=False, checks_state="pending")}
    )
    try:
        engine = CoordinatorEngine(
            session,
            github=github,
            recorder=ActivityRecorder(session, notify_slack=False),
            run_id=run_id,
            repository="example/test",
            backlog_path=backlog_file,
        )
        engine.tick()
        assert github.auto_merge_calls == []
    finally:
        session.close()


def test_closed_unmerged_pr_blocks_task(
    ops_engine: Engine, backlog_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DEVELOPMENT_OPS_ATTEMPT_AUTO_MERGE", "0")
    run_id = uuid.uuid4()
    session = sessionmaker(bind=ops_engine, autoflush=False)()
    github = FakeGitHub({100: _pr(100, closed=True, merged=False)})
    try:
        engine = CoordinatorEngine(
            session,
            github=github,
            recorder=ActivityRecorder(session, notify_slack=False),
            run_id=run_id,
            repository="example/test",
            backlog_path=backlog_file,
        )
        engine.tick()
        repo = CoordinatorTaskRepository(session)
        row = repo.get("TASK-A")
        assert row is not None
        assert row.status == RuntimeTaskStatus.BLOCKED.value
    finally:
        session.close()


def test_merged_pr_reconciles_and_clears_ownership(
    ops_engine: Engine, backlog_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DEVELOPMENT_OPS_ATTEMPT_AUTO_MERGE", "0")
    run_id = uuid.uuid4()
    session = sessionmaker(bind=ops_engine, autoflush=False)()
    github = FakeGitHub({100: _pr(100, merged=True)})
    try:
        engine = CoordinatorEngine(
            session,
            github=github,
            recorder=ActivityRecorder(session, notify_slack=False),
            run_id=run_id,
            repository="example/test",
            backlog_path=backlog_file,
        )
        engine.tick()
        repo = CoordinatorTaskRepository(session)
        row = repo.get("TASK-A")
        assert row is not None
        assert row.status == RuntimeTaskStatus.MERGED.value
        assert row.active_run_id is None
    finally:
        session.close()


# --- catalog reconciliation and auto-merge blocking ---------------------------


def _event_rows(engine: Engine, event_type: str) -> list[dict]:
    with engine.begin() as connection:
        rows = connection.execute(
            text(
                "SELECT title, summary, metadata FROM development_ops.activity_events "
                "WHERE event_type = :event_type ORDER BY recorded_at"
            ),
            {"event_type": event_type},
        ).mappings()
        return [dict(row) for row in rows]


def test_verified_merge_marks_catalog_merged(
    ops_engine: Engine, backlog_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A GitHub-confirmed merge is written to the catalog by the coordinator."""
    from development_ops.backlog import BacklogTaskStatus, load_backlog
    from development_ops.catalog import YamlBacklogCatalogWriter

    monkeypatch.setenv("DEVELOPMENT_OPS_ATTEMPT_AUTO_MERGE", "0")
    run_id = uuid.uuid4()
    session = sessionmaker(bind=ops_engine, autoflush=False)()
    github = FakeGitHub({100: _pr(100, merged=True)})
    try:
        engine = CoordinatorEngine(
            session,
            github=github,
            recorder=ActivityRecorder(session, notify_slack=False),
            run_id=run_id,
            repository="example/test",
            backlog_path=backlog_file,
            catalog=YamlBacklogCatalogWriter(backlog_file),
        )
        engine.tick()
        document = load_backlog(backlog_file)
        task = next(item for item in document.tasks if item.id == "TASK-A")
        assert task.status == BacklogTaskStatus.MERGED
    finally:
        session.close()


def test_catalog_not_written_when_no_catalog_configured(
    ops_engine: Engine, backlog_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without a catalog writer the coordinator only updates runtime state."""
    from development_ops.backlog import BacklogTaskStatus, load_backlog

    monkeypatch.setenv("DEVELOPMENT_OPS_ATTEMPT_AUTO_MERGE", "0")
    before = backlog_file.read_text(encoding="utf-8")
    run_id = uuid.uuid4()
    session = sessionmaker(bind=ops_engine, autoflush=False)()
    github = FakeGitHub({100: _pr(100, merged=True)})
    try:
        engine = CoordinatorEngine(
            session,
            github=github,
            recorder=ActivityRecorder(session, notify_slack=False),
            run_id=run_id,
            repository="example/test",
            backlog_path=backlog_file,
        )
        engine.tick()
        assert backlog_file.read_text(encoding="utf-8") == before
        document = load_backlog(backlog_file)
        task = next(item for item in document.tasks if item.id == "TASK-A")
        assert task.status == BacklogTaskStatus.IN_PROGRESS
    finally:
        session.close()


def test_blocked_auto_merge_records_reason(
    ops_engine: Engine, backlog_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A PR blocked by unresolved threads records a precise reason event."""
    monkeypatch.setenv("DEVELOPMENT_OPS_ATTEMPT_AUTO_MERGE", "1")
    run_id = uuid.uuid4()
    session = sessionmaker(bind=ops_engine, autoflush=False)()
    github = FakeGitHub({100: _pr(100, unresolved_threads=2)})
    try:
        engine = CoordinatorEngine(
            session,
            github=github,
            recorder=ActivityRecorder(session, notify_slack=False),
            run_id=run_id,
            repository="example/test",
            backlog_path=backlog_file,
        )
        result = engine.tick()
        # No mutation was attempted: the PR is blocked before the GraphQL call.
        assert github.auto_merge_calls == []
        assert any("unresolved" in note for note in result.notes)
        rows = _event_rows(ops_engine, "coordinator.auto_merge")
        assert any("unresolved" in (row["summary"] or "") for row in rows)
    finally:
        session.close()


def test_pr_on_develop_is_never_auto_merged(
    ops_engine: Engine, backlog_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A PR targeting develop is reported, not merged, and never mutated."""
    monkeypatch.setenv("DEVELOPMENT_OPS_ATTEMPT_AUTO_MERGE", "1")
    run_id = uuid.uuid4()
    session = sessionmaker(bind=ops_engine, autoflush=False)()
    github = FakeGitHub({100: _pr(100, base_ref="develop")})
    try:
        engine = CoordinatorEngine(
            session,
            github=github,
            recorder=ActivityRecorder(session, notify_slack=False),
            run_id=run_id,
            repository="example/test",
            backlog_path=backlog_file,
        )
        result = engine.tick()
        assert github.auto_merge_calls == []
        assert any("develop" in note for note in result.notes)
    finally:
        session.close()


def test_register_pull_request_rejects_develop_base(
    ops_engine: Engine, backlog_file: Path
) -> None:
    """Registering a PR on an unauthorized base fails fast, before any write."""
    from development_ops.integration import UnauthorizedBaseBranchError

    run_id = uuid.uuid4()
    session = sessionmaker(bind=ops_engine, autoflush=False)()
    try:
        engine = CoordinatorEngine(
            session,
            github=None,
            recorder=ActivityRecorder(session, notify_slack=False),
            run_id=run_id,
            repository="example/test",
            backlog_path=backlog_file,
        )
        with pytest.raises(UnauthorizedBaseBranchError):
            engine.register_pull_request_opened(
                "TASK-B",
                pull_number=555,
                branch_name="cursor/x",
                title="t",
                base_branch="develop",
            )
    finally:
        session.close()

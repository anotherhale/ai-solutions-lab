"""Integration tests for the AI review gate (Phase 1A.6.2).

Runs against the guarded disposable ops-test database (``ops_test_engine``) with
stub GitHub clients. Covers coordinator independent verification (contract cases
17-20), the feature-flag behaviour, and verdict-mirror idempotency. No real
GitHub call, no real App credential, no real check run.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from development_ops.coordinator_engine import CoordinatorEngine
from development_ops.gate_github_client import (
    AI_REVIEW_CHECK_NAME,
    GATE_APP_ID,
)
from development_ops.github_client import (
    AutoMergeAttempt,
    PullRequestState,
)
from development_ops.github_client import (
    ReviewCheck as ClientReviewCheck,
)
from development_ops.persistence.verdict_repository import ReviewVerdictRepository
from development_ops.recorder import ActivityRecorder
from development_ops.review_gate import CONCLUSION_SUCCESS, GateDecision
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from wasatch_api.testing.postgres import assert_engine_is_disposable

HEAD = "c" * 40
OTHER_HEAD = "d" * 40
REPO = "anotherhale/everyones-heroes"


@pytest.fixture(autouse=True)
def _clean_disposable_ops_tables(ops_test_engine: Engine) -> None:
    assert_engine_is_disposable(ops_test_engine)
    with ops_test_engine.begin() as connection:
        connection.execute(text("DELETE FROM development_ops.review_verdicts"))
        connection.execute(text("DELETE FROM development_ops.activity_events"))
        connection.execute(text("DELETE FROM development_ops.coordinator_tasks"))


@pytest.fixture
def session(ops_test_engine: Engine) -> Session:
    factory = sessionmaker(bind=ops_test_engine, autoflush=False)
    session = factory()
    yield session
    session.close()


class _StubGitHub:
    """Stub coordinator GitHub client with a configurable AI review check."""

    def __init__(
        self,
        *,
        base_ref: str = "ai-dev",
        head_sha: str = HEAD,
        checks_green: bool = True,
    ) -> None:
        self._base_ref = base_ref
        self._head_sha = head_sha
        self._checks_green = checks_green
        self.check: ClientReviewCheck | None = ClientReviewCheck(
            name=AI_REVIEW_CHECK_NAME,
            app_id=GATE_APP_ID,
            head_sha=head_sha,
            status="completed",
            conclusion="success",
        )
        self.check_error: Exception | None = None
        self.merge_attempts = 0

    def _state(self) -> PullRequestState:
        return PullRequestState(
            number=7,
            state="OPEN",
            merged=False,
            mergeable="MERGEABLE",
            head_ref="cursor/task",
            base_ref=self._base_ref,
            node_id="PR_node_7",
            auto_merge_enabled=False,
            checks_green=self._checks_green,
            review_decision="APPROVED",
            checks_state="green" if self._checks_green else "none",
            head_sha=self._head_sha,
        )

    def get_pull_request(self, repository: str, number: int) -> PullRequestState:
        return self._state()

    def list_open_pull_requests(self, repository: str) -> list[PullRequestState]:
        return [self._state()]

    def enable_squash_auto_merge(
        self, repository: str, number: int
    ) -> AutoMergeAttempt:
        self.merge_attempts += 1
        return AutoMergeAttempt(
            pull_number=number,
            requested=True,
            auto_merge_request_present=True,
        )

    def get_review_check(
        self, repository: str, ref: str, check_name: str
    ) -> ClientReviewCheck | None:
        if self.check_error is not None:
            raise self.check_error
        return self.check


def _engine(
    session: Session,
    github: _StubGitHub,
    *,
    gate: object | None,
    gate_enabled: bool,
) -> CoordinatorEngine:
    return CoordinatorEngine(
        session,
        github=github,  # type: ignore[arg-type]
        recorder=ActivityRecorder(session, notify_slack=False),
        run_id=uuid.uuid4(),
        repository=REPO,
        gate=gate,  # type: ignore[arg-type]
        verdicts=ReviewVerdictRepository(session),
        gate_enabled=gate_enabled,
    )


def _attempt(engine: CoordinatorEngine, state: PullRequestState) -> tuple[list, list]:
    notes: list[str] = []
    attempts: list = []
    engine._maybe_attempt_auto_merge("T-1", state, attempts, notes)  # noqa: SLF001
    return attempts, notes


# --- case 17: wrong App -----------------------------------------------------


def test_coordinator_rejects_check_from_wrong_app(session: Session) -> None:
    github = _StubGitHub()
    github.check = ClientReviewCheck(
        name=AI_REVIEW_CHECK_NAME,
        app_id=999999,  # not the gate App
        head_sha=HEAD,
        status="completed",
        conclusion="success",
    )
    engine = _engine(session, github, gate=object(), gate_enabled=True)
    attempts, notes = _attempt(engine, github.get_pull_request(REPO, 7))
    assert attempts == []
    assert github.merge_attempts == 0
    assert any("gate App" in note for note in notes)


# --- case 18: wrong SHA -----------------------------------------------------


def test_coordinator_rejects_check_for_wrong_sha(session: Session) -> None:
    github = _StubGitHub()
    github.check = ClientReviewCheck(
        name=AI_REVIEW_CHECK_NAME,
        app_id=GATE_APP_ID,
        head_sha=OTHER_HEAD,  # not the live head
        status="completed",
        conclusion="success",
    )
    engine = _engine(session, github, gate=object(), gate_enabled=True)
    attempts, notes = _attempt(engine, github.get_pull_request(REPO, 7))
    assert attempts == []
    assert github.merge_attempts == 0
    assert any("different head sha" in note for note in notes)


def test_coordinator_rejects_when_head_moved(session: Session) -> None:
    github = _StubGitHub(head_sha=OTHER_HEAD)
    engine = _engine(session, github, gate=object(), gate_enabled=True)
    listed = github.get_pull_request(REPO, 7)
    # The listing saw HEAD; GitHub now reports OTHER_HEAD.
    listed = PullRequestState(
        number=7,
        state="OPEN",
        merged=False,
        mergeable="MERGEABLE",
        head_ref="cursor/task",
        base_ref="ai-dev",
        node_id="PR_node_7",
        auto_merge_enabled=False,
        checks_green=True,
        review_decision="APPROVED",
        checks_state="green",
        head_sha=HEAD,
    )
    attempts, notes = _attempt(engine, listed)
    assert attempts == []
    assert github.merge_attempts == 0
    assert any("changed between" in note for note in notes)


# --- case 19: non-success conclusion ---------------------------------------


@pytest.mark.parametrize("conclusion", ["failure", "action_required", None])
def test_coordinator_rejects_non_success(
    session: Session, conclusion: str | None
) -> None:
    github = _StubGitHub()
    github.check = ClientReviewCheck(
        name=AI_REVIEW_CHECK_NAME,
        app_id=GATE_APP_ID,
        head_sha=HEAD,
        status="completed",
        conclusion=conclusion,
    )
    engine = _engine(session, github, gate=object(), gate_enabled=True)
    attempts, notes = _attempt(engine, github.get_pull_request(REPO, 7))
    assert attempts == []
    assert github.merge_attempts == 0
    assert any("not success" in note for note in notes)


def test_coordinator_rejects_absent_check(session: Session) -> None:
    github = _StubGitHub()
    github.check = None
    engine = _engine(session, github, gate=object(), gate_enabled=True)
    attempts, notes = _attempt(engine, github.get_pull_request(REPO, 7))
    assert attempts == []
    assert any("absent" in note for note in notes)


def test_coordinator_rejects_when_check_lookup_fails(session: Session) -> None:
    github = _StubGitHub()
    github.check_error = RuntimeError("api down")
    engine = _engine(session, github, gate=object(), gate_enabled=True)
    attempts, notes = _attempt(engine, github.get_pull_request(REPO, 7))
    assert attempts == []
    assert any("lookup failed" in note for note in notes)


# --- case 20: wrong base branch --------------------------------------------


def test_coordinator_rejects_non_ai_dev_base(session: Session) -> None:
    github = _StubGitHub(base_ref="main")
    engine = _engine(session, github, gate=object(), gate_enabled=True)
    attempts, notes = _attempt(engine, github.get_pull_request(REPO, 7))
    assert attempts == []
    assert github.merge_attempts == 0
    assert any("is not ai-dev" in note for note in notes)


# --- valid path -------------------------------------------------------------


def test_coordinator_allows_merge_with_verified_success(session: Session) -> None:
    github = _StubGitHub()
    engine = _engine(session, github, gate=object(), gate_enabled=True)
    attempts, _ = _attempt(engine, github.get_pull_request(REPO, 7))
    assert github.merge_attempts == 1
    assert len(attempts) == 1


# --- feature flag: disabled preserves behavior ------------------------------


def test_disabled_gate_preserves_existing_behavior(session: Session) -> None:
    github = _StubGitHub()
    # Gate disabled: no check verification is performed at all.
    github.check = None
    engine = _engine(session, github, gate=None, gate_enabled=False)
    attempts, _ = _attempt(engine, github.get_pull_request(REPO, 7))
    assert github.merge_attempts == 1
    assert len(attempts) == 1


def test_enabled_but_unavailable_fails_closed(session: Session) -> None:
    github = _StubGitHub()
    # Enabled but no gate client (credentials missing): must not merge.
    engine = _engine(session, github, gate=None, gate_enabled=True)
    attempts, notes = _attempt(engine, github.get_pull_request(REPO, 7))
    assert attempts == []
    assert github.merge_attempts == 0
    assert any("unavailable" in note for note in notes)


# --- verdict mirror persistence --------------------------------------------


def _decision(review_id: int = 5820717173) -> GateDecision:
    return GateDecision(
        repository=REPO,
        pull_number=7,
        conclusion=CONCLUSION_SUCCESS,
        reason="ok",
        head_sha=HEAD,
        review_id=review_id,
        verdict_id="v-1",
        blocking_count=0,
        policy_version="1",
        reviewed_at=datetime(2026, 11, 9, 11, 30, tzinfo=UTC),
        reviewer_login="everyones-heroes-reviewer[bot]",
        reviewer_user_id=353895417,
    )


def test_verdict_mirror_is_idempotent(session: Session) -> None:
    repo = ReviewVerdictRepository(session)
    first, created_first = repo.record(
        repository=REPO,
        pull_number=7,
        head_sha=HEAD,
        review_id=5820717173,
        reviewer_login="bot",
        reviewer_user_id=353895417,
        verdict="success",
        blocking_count=0,
        policy_version="1",
        reviewed_at=datetime(2026, 11, 9, 11, 30, tzinfo=UTC),
    )
    second, created_second = repo.record(
        repository=REPO,
        pull_number=7,
        head_sha=HEAD,
        review_id=5820717173,
        reviewer_login="bot",
        reviewer_user_id=353895417,
        verdict="success",
        blocking_count=0,
        policy_version="1",
        reviewed_at=datetime(2026, 11, 9, 11, 30, tzinfo=UTC),
    )
    assert created_first is True
    assert created_second is False
    assert first.id == second.id
    assert len(repo.list_for_pull(REPO, 7)) == 1


def test_engine_mirrors_verdict_once(session: Session) -> None:
    github = _StubGitHub()
    engine = _engine(session, github, gate=object(), gate_enabled=True)
    state = github.get_pull_request(REPO, 7)
    notes: list[str] = []
    engine._mirror_verdict("T-1", state, _decision(), notes)  # noqa: SLF001
    engine._mirror_verdict("T-1", state, _decision(), notes)  # noqa: SLF001
    repo = ReviewVerdictRepository(session)
    assert len(repo.list_for_pull(REPO, 7)) == 1


def test_mirror_does_not_authorize_merge_on_its_own(session: Session) -> None:
    # A populated mirror with a bad check must still block auto-merge.
    repo = ReviewVerdictRepository(session)
    repo.record(
        repository=REPO,
        pull_number=7,
        head_sha=HEAD,
        review_id=1,
        reviewer_login="bot",
        reviewer_user_id=353895417,
        verdict="success",
        blocking_count=0,
        policy_version="1",
        reviewed_at=datetime(2026, 11, 9, 11, 30, tzinfo=UTC),
    )
    github = _StubGitHub()
    github.check = None  # GitHub has no check: mirror must not be trusted
    engine = _engine(session, github, gate=object(), gate_enabled=True)
    attempts, _ = _attempt(engine, github.get_pull_request(REPO, 7))
    assert attempts == []
    assert github.merge_attempts == 0


def test_review_verdicts_table_exists(ops_test_engine: Engine) -> None:
    with ops_test_engine.connect() as connection:
        exists = connection.execute(
            text(
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_schema = 'development_ops' "
                "AND table_name = 'review_verdicts'"
            )
        ).scalar()
    assert exists == 1

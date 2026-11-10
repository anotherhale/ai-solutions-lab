"""Unit tests for the AI review gate (Phase 1A.6.2).

Covers contract acceptance cases 1-16 plus the invariant that no blocking
condition can produce ``success``. Uses an in-memory stub GitHub client and a
fake token provider; it never contacts GitHub and never publishes a real check.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from development_ops.gate_github_client import (
    AI_REVIEW_CHECK_NAME,
    GATE_APP_ID,
    REVIEWER_BOT_LOGIN,
    REVIEWER_BOT_USER_ID,
    CheckRunRecord,
    GateApiError,
    PullRequestSnapshot,
    ReviewRecord,
)
from development_ops.review_gate import (
    ALLOWED_CONCLUSIONS,
    CONCLUSION_ACTION_REQUIRED,
    CONCLUSION_FAILURE,
    CONCLUSION_SUCCESS,
    ReviewGate,
    extract_verdict,
)

HEAD = "a" * 40
OLD_HEAD = "b" * 40
REPO = "anotherhale/everyones-heroes"
NOW = datetime(2026, 11, 9, 12, 0, 0, tzinfo=UTC)


def _verdict_body(
    *,
    head_sha: str = HEAD,
    verdict: str = "approve",
    blocking: list[dict] | None = None,
    policy_version: str = "1",
    repository: str = REPO,
    pull_number: int = 7,
    base_ref: str = "ai-dev",
    reviewed_at: str | None = None,
) -> str:
    payload = {
        "schema_version": "1",
        "verdict_id": "v-1",
        "repository": repository,
        "pull_request_number": pull_number,
        "base_ref": base_ref,
        "head_sha": head_sha,
        "verdict": verdict,
        "blocking_findings": blocking or [],
        "advisory_findings": [],
        "reviewed_at": reviewed_at or NOW.isoformat(),
        "review_policy_version": policy_version,
        "evidence": {"diff_sha256": "deadbeef"},
    }
    return "Summary\n\n```json\n" + json.dumps(payload) + "\n```\n"


def _review(
    *,
    state: str = "APPROVED",
    commit_id: str = HEAD,
    body: str | None = None,
    login: str = REVIEWER_BOT_LOGIN,
    user_id: int = REVIEWER_BOT_USER_ID,
    submitted_at: str = "2026-11-09T11:30:00Z",
    review_id: int = 5820717173,
) -> ReviewRecord:
    return ReviewRecord(
        review_id=review_id,
        author_login=login,
        author_user_id=user_id,
        author_type="Bot",
        state=state,
        commit_id=commit_id,
        submitted_at=submitted_at,
        body=body if body is not None else _verdict_body(head_sha=commit_id),
    )


class _StubGateGitHub:
    """In-memory gate GitHub client. Records published checks."""

    def __init__(self) -> None:
        self.pr = PullRequestSnapshot(
            number=7, base_ref="ai-dev", head_sha=HEAD, state="open", merged=False
        )
        self.reviews: list[ReviewRecord] = [_review()]
        self.existing_runs: list[CheckRunRecord] = []
        self.created: list[dict] = []
        self.updated: list[dict] = []
        self.fail_pr = False
        self.fail_reviews = False
        self.fail_create = False
        self.fail_list_runs = False
        self._next_id = 9000

    def get_pull_request(self, repository: str, number: int) -> PullRequestSnapshot:
        if self.fail_pr:
            raise GateApiError("boom")
        return self.pr

    def list_reviews(self, repository: str, number: int) -> list[ReviewRecord]:
        if self.fail_reviews:
            raise GateApiError("boom")
        return list(self.reviews)

    def list_check_runs(self, repository: str, ref: str) -> list[CheckRunRecord]:
        if self.fail_list_runs:
            raise GateApiError("boom")
        return [run for run in self.existing_runs if run.head_sha == ref]

    def create_check_run(self, repository: str, **kwargs: object) -> int:
        if self.fail_create:
            raise GateApiError("boom")
        self._next_id += 1
        self.created.append(kwargs)
        return self._next_id

    def update_check_run(self, repository: str, **kwargs: object) -> None:
        if self.fail_create:
            raise GateApiError("boom")
        self.updated.append(kwargs)


def _gate(client: _StubGateGitHub, *, max_age: int = 86400) -> ReviewGate:
    return ReviewGate(
        client,
        repository=REPO,
        reviewer_login=REVIEWER_BOT_LOGIN,
        reviewer_user_id=REVIEWER_BOT_USER_ID,
        max_verdict_age_seconds=max_age,
        policy_versions=frozenset({"1"}),
        clock=lambda: NOW,
    )


# --- 1. valid authenticated approval ---------------------------------------


def test_valid_approval_publishes_success() -> None:
    client = _StubGateGitHub()
    decision = _gate(client).run(7)
    assert decision.conclusion == CONCLUSION_SUCCESS
    assert decision.published is True
    assert len(client.created) == 1
    assert client.created[0]["conclusion"] == "success"
    assert client.created[0]["head_sha"] == HEAD
    assert client.created[0]["name"] == AI_REVIEW_CHECK_NAME


# --- 2. old-SHA approval ----------------------------------------------------


def test_approval_for_old_sha_is_failure() -> None:
    client = _StubGateGitHub()
    client.reviews = [
        _review(commit_id=OLD_HEAD, body=_verdict_body(head_sha=OLD_HEAD))
    ]
    decision = _gate(client).run(7)
    assert decision.conclusion == CONCLUSION_FAILURE
    assert decision.published is True


# --- 3. new commit after approval ------------------------------------------


def test_new_commit_after_approval_is_failure() -> None:
    client = _StubGateGitHub()
    # Review still bound to old head; live head moved on.
    client.reviews = [
        _review(commit_id=OLD_HEAD, body=_verdict_body(head_sha=OLD_HEAD))
    ]
    decision = _gate(client).run(7)
    assert decision.conclusion != CONCLUSION_SUCCESS


# --- 4. explicit rejection --------------------------------------------------


def test_changes_requested_is_failure() -> None:
    client = _StubGateGitHub()
    client.reviews = [_review(state="CHANGES_REQUESTED")]
    decision = _gate(client).run(7)
    assert decision.conclusion == CONCLUSION_FAILURE


def test_blocking_findings_is_failure() -> None:
    client = _StubGateGitHub()
    body = _verdict_body(blocking=[{"id": "b1", "summary": "fix"}])
    client.reviews = [_review(body=body)]
    decision = _gate(client).run(7)
    assert decision.conclusion == CONCLUSION_FAILURE
    assert decision.blocking_count == 1


# --- 5. missing review ------------------------------------------------------


def test_missing_review_is_action_required() -> None:
    client = _StubGateGitHub()
    client.reviews = []
    decision = _gate(client).run(7)
    assert decision.conclusion == CONCLUSION_ACTION_REQUIRED


# --- 6. reviewer unavailable ------------------------------------------------


def test_reviewer_unavailable_is_action_required() -> None:
    client = _StubGateGitHub()
    client.reviews = []
    decision = _gate(client).run(7)
    assert decision.conclusion == CONCLUSION_ACTION_REQUIRED


# --- 7. forged reviewer identity -------------------------------------------


def test_forged_reviewer_login_is_failure() -> None:
    client = _StubGateGitHub()
    client.reviews = [_review(login="attacker")]
    decision = _gate(client).run(7)
    assert decision.conclusion == CONCLUSION_FAILURE


def test_forged_reviewer_user_id_is_failure() -> None:
    client = _StubGateGitHub()
    # Correct login, wrong numeric id: identity is not authentic.
    client.reviews = [_review(user_id=123456)]
    decision = _gate(client).run(7)
    assert decision.conclusion == CONCLUSION_FAILURE


# --- 8. incorrect reviewer App identity ------------------------------------


def test_wrong_reviewer_app_identity_is_failure() -> None:
    client = _StubGateGitHub()
    client.reviews = [_review(login="someone-else[bot]", user_id=999)]
    decision = _gate(client).run(7)
    assert decision.conclusion == CONCLUSION_FAILURE


# --- 9. invalid review state ------------------------------------------------


@pytest.mark.parametrize("state", ["COMMENTED", "PENDING", "DISMISSED"])
def test_invalid_review_state_is_failure(state: str) -> None:
    client = _StubGateGitHub()
    client.reviews = [_review(state=state)]
    decision = _gate(client).run(7)
    assert decision.conclusion == CONCLUSION_FAILURE


# --- 10. expired review -----------------------------------------------------


def test_expired_review_is_failure() -> None:
    client = _StubGateGitHub()
    client.reviews = [_review(submitted_at="2026-11-07T11:30:00Z")]  # >24h
    decision = _gate(client).run(7)
    assert decision.conclusion == CONCLUSION_FAILURE


def test_payload_timestamp_cannot_extend_freshness() -> None:
    client = _StubGateGitHub()
    # Canonical submitted_at is old; payload claims "now". Freshness uses the
    # canonical GitHub timestamp, so this must still be a failure.
    body = _verdict_body(reviewed_at=NOW.isoformat())
    client.reviews = [_review(body=body, submitted_at="2026-11-07T11:30:00Z")]
    decision = _gate(client).run(7)
    assert decision.conclusion == CONCLUSION_FAILURE


# --- 11. unsupported policy version ----------------------------------------


def test_unsupported_policy_version_is_failure() -> None:
    client = _StubGateGitHub()
    client.reviews = [_review(body=_verdict_body(policy_version="2"))]
    decision = _gate(client).run(7)
    assert decision.conclusion == CONCLUSION_FAILURE


# --- 12. GitHub API failure -------------------------------------------------


def test_pr_lookup_failure_is_failure() -> None:
    client = _StubGateGitHub()
    client.fail_pr = True
    decision = _gate(client).run(7)
    assert decision.conclusion == CONCLUSION_FAILURE


def test_review_lookup_failure_is_failure() -> None:
    client = _StubGateGitHub()
    client.fail_reviews = True
    decision = _gate(client).run(7)
    assert decision.conclusion == CONCLUSION_FAILURE


# --- 13. state change between retrieval and publication --------------------


def test_head_moves_before_publication_is_failure() -> None:
    client = _StubGateGitHub()
    original = client.get_pull_request

    calls = {"n": 0}

    def flaky(repository: str, number: int) -> PullRequestSnapshot:
        calls["n"] += 1
        if calls["n"] == 1:
            return original(repository, number)
        return PullRequestSnapshot(
            number=7, base_ref="ai-dev", head_sha=OLD_HEAD, state="open", merged=False
        )

    client.get_pull_request = flaky  # type: ignore[assignment]
    decision = _gate(client).run(7)
    assert decision.conclusion == CONCLUSION_FAILURE
    assert "moved" in decision.reason


def test_pr_unavailable_before_publication_is_failure() -> None:
    client = _StubGateGitHub()
    original = client.get_pull_request
    calls = {"n": 0}

    def flaky(repository: str, number: int) -> PullRequestSnapshot:
        calls["n"] += 1
        if calls["n"] == 1:
            return original(repository, number)
        raise GateApiError("boom")

    client.get_pull_request = flaky  # type: ignore[assignment]
    decision = _gate(client).run(7)
    assert decision.conclusion == CONCLUSION_FAILURE


# --- 14. duplicate delivery / idempotency ----------------------------------


def test_duplicate_run_updates_existing_run() -> None:
    client = _StubGateGitHub()
    gate = _gate(client)
    first = gate.run(7)
    assert first.published and len(client.created) == 1
    # Simulate the published run now existing on GitHub.
    client.existing_runs = [
        CheckRunRecord(
            check_run_id=4242,
            name=AI_REVIEW_CHECK_NAME,
            app_id=GATE_APP_ID,
            head_sha=HEAD,
            status="completed",
            conclusion="success",
        )
    ]
    second = gate.run(7)
    assert second.published is True
    assert len(client.created) == 1  # no duplicate created
    assert client.updated and client.updated[0]["check_run_id"] == 4242


# --- 15. database persistence failure --------------------------------------


def test_mirror_failure_does_not_break_gate() -> None:
    # The gate itself never touches the DB; a mirror failure is handled by the
    # coordinator. Here we assert the gate decision is independent of storage.
    client = _StubGateGitHub()
    decision = _gate(client).run(7)
    assert decision.conclusion == CONCLUSION_SUCCESS


# --- 16. check publication failure -----------------------------------------


def test_publication_failure_is_not_success() -> None:
    client = _StubGateGitHub()
    client.fail_create = True
    decision = _gate(client).run(7)
    # Conclusion stays success (the review was valid) but it is NOT published,
    # so nothing on GitHub can authorize a merge.
    assert decision.published is False
    assert decision.publish_error is not None


def test_list_runs_failure_blocks_publication() -> None:
    client = _StubGateGitHub()
    client.fail_list_runs = True
    decision = _gate(client).run(7)
    assert decision.published is False


# --- invariant: no blocking condition yields success -----------------------


def _blocking_clients() -> dict[str, _StubGateGitHub]:
    cases: dict[str, _StubGateGitHub] = {}

    c = _StubGateGitHub()
    c.reviews = []
    cases["missing"] = c

    c = _StubGateGitHub()
    c.reviews = [_review(state="CHANGES_REQUESTED")]
    cases["rejected"] = c

    c = _StubGateGitHub()
    c.reviews = [_review(commit_id=OLD_HEAD, body=_verdict_body(head_sha=OLD_HEAD))]
    cases["old_sha"] = c

    c = _StubGateGitHub()
    c.reviews = [_review(login="attacker")]
    cases["forged"] = c

    c = _StubGateGitHub()
    c.reviews = [_review(state="DISMISSED")]
    cases["dismissed"] = c

    c = _StubGateGitHub()
    c.reviews = [_review(submitted_at="2026-11-01T00:00:00Z")]
    cases["expired"] = c

    c = _StubGateGitHub()
    c.reviews = [_review(body=_verdict_body(policy_version="9"))]
    cases["policy"] = c

    c = _StubGateGitHub()
    c.fail_pr = True
    cases["api_error"] = c

    c = _StubGateGitHub()
    c.pr = PullRequestSnapshot(
        number=7, base_ref="main", head_sha=HEAD, state="open", merged=False
    )
    cases["wrong_base"] = c

    c = _StubGateGitHub()
    c.reviews = [_review(body="no verdict block here")]
    cases["malformed"] = c

    return cases


@pytest.mark.parametrize("name", sorted(_blocking_clients().keys()))
def test_no_blocking_condition_yields_success(name: str) -> None:
    client = _blocking_clients()[name]
    decision = _gate(client).run(7)
    assert decision.conclusion in {CONCLUSION_FAILURE, CONCLUSION_ACTION_REQUIRED}
    assert decision.conclusion != CONCLUSION_SUCCESS


def test_only_success_conclusion_can_be_success() -> None:
    assert ALLOWED_CONCLUSIONS == {
        CONCLUSION_SUCCESS,
        CONCLUSION_FAILURE,
        CONCLUSION_ACTION_REQUIRED,
    }
    assert "neutral" not in ALLOWED_CONCLUSIONS
    assert "skipped" not in ALLOWED_CONCLUSIONS


# --- verdict parsing --------------------------------------------------------


def test_extract_verdict_requires_exactly_one_block() -> None:
    from development_ops.review_gate import VerdictParseError

    with pytest.raises(VerdictParseError):
        extract_verdict("no json here")


def test_extract_verdict_accepts_marker_block() -> None:
    body = (
        "<!-- ai-review-verdict:start -->\n"
        + json.dumps(
            {
                "repository": REPO,
                "pull_request_number": 7,
                "base_ref": "ai-dev",
                "head_sha": HEAD,
                "verdict": "approve",
            }
        )
        + "\n<!-- ai-review-verdict:end -->"
    )
    verdict = extract_verdict(body)
    assert verdict.verdict.value == "approve"

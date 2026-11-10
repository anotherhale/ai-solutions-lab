"""AI review gate: canonical verdict verification and check publication.

The gate is a *stateless* validator. It never authors the change, never reviews,
and never merges. It reads the canonical GitHub PR review (authored by the
reviewer App), verifies it against the live pull request, and publishes the
required ``AI review`` check as its own GitHub App.

Security-critical rules (Phase 1A.6.1 contract; AEE-ADR-009 Amendment 1):

* ``success`` is emitted **only** for an authenticated reviewer approval whose
  ``commit_id`` equals the **current live** PR head SHA, whose verdict is within
  the freshness window, whose policy version is accepted, and which has zero
  blocking findings.
* Every other condition yields ``failure`` or ``action_required``. ``neutral``
  and ``skipped`` are **never** used for a blocking condition (they count as
  passing for a required check).
* Reviewer identity is taken from the **GitHub review record** (login + numeric
  user id), never from fields inside the verdict payload.
* Freshness uses GitHub's canonical ``submitted_at``, never a timestamp inside
  the payload.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from development_ops.gate_github_client import (
    AI_REVIEW_CHECK_NAME,
    GATE_APP_ID,
    GateApiError,
    GateConfig,
    GateGitHubClient,
    ReviewRecord,
    _parse_github_timestamp,
    gate_config_from_env,
)

VERDICT_START_MARKER = "<!-- ai-review-verdict:start -->"
VERDICT_END_MARKER = "<!-- ai-review-verdict:end -->"

CONCLUSION_SUCCESS = "success"
CONCLUSION_FAILURE = "failure"
CONCLUSION_ACTION_REQUIRED = "action_required"

# Conclusions the gate may ever publish. ``neutral``/``skipped`` are excluded by
# construction: they would satisfy a required check and fail open.
ALLOWED_CONCLUSIONS = frozenset(
    {CONCLUSION_SUCCESS, CONCLUSION_FAILURE, CONCLUSION_ACTION_REQUIRED}
)

INTEGRATION_BRANCH = "ai-dev"


class VerdictKind(StrEnum):
    APPROVE = "approve"
    CHANGES_REQUESTED = "changes_requested"
    REVIEW_FAILED = "review_failed"
    REVIEW_UNAVAILABLE = "review_unavailable"


class ReviewFinding(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str | None = None
    severity: str | None = None
    summary: str | None = None
    location: str | None = None


class ReviewVerdict(BaseModel):
    """Machine-readable verdict embedded in the reviewer's PR review body."""

    model_config = ConfigDict(extra="allow")

    schema_version: str = "1"
    verdict_id: str | None = None
    repository: str
    pull_request_number: int = Field(ge=1)
    base_ref: str
    head_sha: str
    reviewer_app_id: int | None = None
    reviewer_identity: str | None = None
    verdict: VerdictKind
    blocking_findings: list[ReviewFinding] = Field(default_factory=list)
    advisory_findings: list[ReviewFinding] = Field(default_factory=list)
    reviewed_at: str | None = None
    review_policy_version: str = "1"
    evidence: dict = Field(default_factory=dict)

    @property
    def blocking_count(self) -> int:
        return len(self.blocking_findings)

    @property
    def is_approval(self) -> bool:
        return self.verdict == VerdictKind.APPROVE and self.blocking_count == 0


class VerdictParseError(ValueError):
    """The review body did not contain a single well-formed verdict block."""


def extract_verdict(body: str) -> ReviewVerdict:
    """Parse exactly one verdict block from a review body.

    Accepts an explicit marker-delimited block, else the last fenced ``json``
    block. Raises :class:`VerdictParseError` when absent, ambiguous, or invalid.
    """
    candidates: list[str] = []
    if VERDICT_START_MARKER in body and VERDICT_END_MARKER in body:
        start = body.index(VERDICT_START_MARKER) + len(VERDICT_START_MARKER)
        end = body.index(VERDICT_END_MARKER, start)
        candidates.append(body[start:end])
    else:
        fence = "```json"
        index = 0
        while True:
            found = body.find(fence, index)
            if found == -1:
                break
            close = body.find("```", found + len(fence))
            if close == -1:
                break
            candidates.append(body[found + len(fence) : close])
            index = close + 3
        if not candidates and body.strip().startswith("{"):
            candidates.append(body)

    parsed: list[ReviewVerdict] = []
    for raw in candidates:
        try:
            parsed.append(ReviewVerdict.model_validate(json.loads(raw.strip())))
        except (json.JSONDecodeError, ValidationError):
            continue
    if len(parsed) != 1:
        msg = "expected exactly one well-formed verdict block"
        raise VerdictParseError(msg)
    return parsed[0]


@dataclass(frozen=True, slots=True)
class GateDecision:
    """The gate's evaluation outcome for one pull request.

    ``conclusion`` is always one of :data:`ALLOWED_CONCLUSIONS`. ``published``
    records whether the check was actually written; a publish failure never
    converts the conclusion to ``success``.
    """

    repository: str
    pull_number: int
    conclusion: str
    reason: str
    head_sha: str
    review_id: int | None = None
    verdict_id: str | None = None
    blocking_count: int = 0
    policy_version: str | None = None
    reviewed_at: datetime | None = None
    reviewer_login: str | None = None
    reviewer_user_id: int | None = None
    verdict: ReviewVerdict | None = None
    published: bool = False
    publish_error: str | None = None

    @property
    def is_success(self) -> bool:
        return self.conclusion == CONCLUSION_SUCCESS


def _decision(
    *,
    repository: str,
    pull_number: int,
    conclusion: str,
    reason: str,
    head_sha: str,
    **extra: object,
) -> GateDecision:
    assert conclusion in ALLOWED_CONCLUSIONS, conclusion
    return GateDecision(
        repository=repository,
        pull_number=pull_number,
        conclusion=conclusion,
        reason=reason,
        head_sha=head_sha,
        **extra,  # type: ignore[arg-type]
    )


class ReviewGate:
    """Evaluates the canonical review and publishes the required check."""

    def __init__(
        self,
        client: GateGitHubClient,
        *,
        repository: str,
        reviewer_login: str,
        reviewer_user_id: int,
        max_verdict_age_seconds: int,
        policy_versions: frozenset[str],
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._client = client
        self._repository = repository
        self._reviewer_login = reviewer_login
        self._reviewer_user_id = reviewer_user_id
        self._max_age = max_verdict_age_seconds
        self._policy_versions = policy_versions
        self._clock = clock or (lambda: datetime.now(UTC))

    # -- evaluation -----------------------------------------------------------

    def evaluate(self, pull_number: int) -> GateDecision:
        """Read GitHub and decide, without publishing."""
        repository = self._repository
        try:
            pr = self._client.get_pull_request(repository, pull_number)
        except GateApiError:
            return _decision(
                repository=repository,
                pull_number=pull_number,
                conclusion=CONCLUSION_FAILURE,
                reason="github pull request state could not be verified",
                head_sha="",
            )

        head = pr.head_sha
        if not head:
            return _decision(
                repository=repository,
                pull_number=pull_number,
                conclusion=CONCLUSION_FAILURE,
                reason="pull request head sha unavailable",
                head_sha="",
            )
        if pr.base_ref != INTEGRATION_BRANCH:
            return _decision(
                repository=repository,
                pull_number=pull_number,
                conclusion=CONCLUSION_FAILURE,
                reason=f"base branch '{pr.base_ref}' is not '{INTEGRATION_BRANCH}'",
                head_sha=head,
            )
        if pr.merged or pr.state not in {"open", "OPEN"}:
            return _decision(
                repository=repository,
                pull_number=pull_number,
                conclusion=CONCLUSION_FAILURE,
                reason="pull request is not open",
                head_sha=head,
            )

        try:
            reviews = self._client.list_reviews(repository, pull_number)
        except GateApiError:
            return _decision(
                repository=repository,
                pull_number=pull_number,
                conclusion=CONCLUSION_FAILURE,
                reason="github review state could not be verified",
                head_sha=head,
            )

        by_identity = [
            review
            for review in reviews
            if review.author_login == self._reviewer_login
            and review.author_user_id == self._reviewer_user_id
        ]
        if not by_identity:
            if reviews:
                return _decision(
                    repository=repository,
                    pull_number=pull_number,
                    conclusion=CONCLUSION_FAILURE,
                    reason="no review from the expected reviewer identity",
                    head_sha=head,
                )
            return _decision(
                repository=repository,
                pull_number=pull_number,
                conclusion=CONCLUSION_ACTION_REQUIRED,
                reason="no review submitted for this pull request",
                head_sha=head,
            )

        for_current = [r for r in by_identity if r.commit_id == head]
        if not for_current:
            return _decision(
                repository=repository,
                pull_number=pull_number,
                conclusion=CONCLUSION_FAILURE,
                reason="review does not match the current head sha",
                head_sha=head,
            )

        review = self._newest(for_current)
        if review is None:
            return _decision(
                repository=repository,
                pull_number=pull_number,
                conclusion=CONCLUSION_FAILURE,
                reason="conflicting reviews for the current head sha",
                head_sha=head,
            )
        return self._judge(review, pull_number, head)

    def _newest(self, reviews: list[ReviewRecord]) -> ReviewRecord | None:
        """Newest by canonical ``submitted_at``; a tie fails closed."""
        ordered = sorted(reviews, key=lambda r: r.submitted_at)
        if len(ordered) >= 2 and ordered[-1].submitted_at == ordered[-2].submitted_at:
            return None
        return ordered[-1]

    def _judge(self, review: ReviewRecord, pull_number: int, head: str) -> GateDecision:
        common: dict[str, object] = {
            "head_sha": head,
            "review_id": review.review_id,
            "reviewer_login": review.author_login,
            "reviewer_user_id": review.author_user_id,
        }
        if review.state == "DISMISSED":
            return _decision(
                repository=self._repository,
                pull_number=pull_number,
                conclusion=CONCLUSION_FAILURE,
                reason="review was dismissed",
                **common,  # type: ignore[arg-type]
            )
        if review.state == "CHANGES_REQUESTED":
            return _decision(
                repository=self._repository,
                pull_number=pull_number,
                conclusion=CONCLUSION_FAILURE,
                reason="reviewer requested changes",
                **common,  # type: ignore[arg-type]
            )
        if review.state != "APPROVED":
            return _decision(
                repository=self._repository,
                pull_number=pull_number,
                conclusion=CONCLUSION_FAILURE,
                reason=f"review state '{review.state}' is not an approval",
                **common,  # type: ignore[arg-type]
            )

        try:
            verdict = extract_verdict(review.body)
        except VerdictParseError:
            return _decision(
                repository=self._repository,
                pull_number=pull_number,
                conclusion=CONCLUSION_FAILURE,
                reason="review body has no valid verdict block",
                **common,  # type: ignore[arg-type]
            )

        common["verdict"] = verdict
        common["verdict_id"] = verdict.verdict_id
        common["blocking_count"] = verdict.blocking_count
        common["policy_version"] = verdict.review_policy_version

        if (
            verdict.repository != self._repository
            or verdict.pull_request_number != pull_number
            or verdict.base_ref != INTEGRATION_BRANCH
            or verdict.head_sha != head
        ):
            return _decision(
                repository=self._repository,
                pull_number=pull_number,
                conclusion=CONCLUSION_FAILURE,
                reason="verdict fields do not match the live pull request",
                **common,  # type: ignore[arg-type]
            )
        if verdict.review_policy_version not in self._policy_versions:
            return _decision(
                repository=self._repository,
                pull_number=pull_number,
                conclusion=CONCLUSION_FAILURE,
                reason=(
                    f"policy version '{verdict.review_policy_version}' is not accepted"
                ),
                **common,  # type: ignore[arg-type]
            )

        submitted_at = _parse_github_timestamp(review.submitted_at)
        if submitted_at is None:
            return _decision(
                repository=self._repository,
                pull_number=pull_number,
                conclusion=CONCLUSION_FAILURE,
                reason="review timestamp unavailable",
                **common,  # type: ignore[arg-type]
            )
        common["reviewed_at"] = submitted_at
        age = (self._clock() - submitted_at).total_seconds()
        if age > self._max_age:
            return _decision(
                repository=self._repository,
                pull_number=pull_number,
                conclusion=CONCLUSION_FAILURE,
                reason="review is older than the freshness window",
                **common,  # type: ignore[arg-type]
            )

        if not verdict.is_approval:
            return _decision(
                repository=self._repository,
                pull_number=pull_number,
                conclusion=CONCLUSION_FAILURE,
                reason="verdict is not an approval or has blocking findings",
                **common,  # type: ignore[arg-type]
            )

        return _decision(
            repository=self._repository,
            pull_number=pull_number,
            conclusion=CONCLUSION_SUCCESS,
            reason="authenticated approval for the current head sha",
            **common,  # type: ignore[arg-type]
        )

    # -- publication ----------------------------------------------------------

    def run(self, pull_number: int) -> GateDecision:
        """Evaluate, re-verify the head immediately before publishing, publish."""
        decision = self.evaluate(pull_number)
        if not decision.head_sha:
            # Nothing to bind a check to; the required check stays absent.
            return replace(
                decision,
                published=False,
                publish_error="no head sha to publish against",
            )

        # Re-fetch the head immediately before publication. A move invalidates a
        # would-be success; we publish a blocking conclusion for the SHA we
        # actually evaluated.
        try:
            live = self._client.get_pull_request(self._repository, pull_number)
        except GateApiError:
            decision = replace(
                decision,
                conclusion=CONCLUSION_FAILURE,
                reason="github state could not be re-verified before publication",
            )
        else:
            if live.head_sha != decision.head_sha:
                decision = replace(
                    decision,
                    conclusion=CONCLUSION_FAILURE,
                    reason="head sha moved between evaluation and publication",
                )
        return self.publish(decision)

    def publish(self, decision: GateDecision) -> GateDecision:
        """Idempotently publish the check for ``decision.head_sha``."""
        if not decision.head_sha:
            return replace(
                decision,
                published=False,
                publish_error="no head sha to publish against",
            )
        title, summary = self._render_output(decision)
        external_id = (
            f"ai-review:{decision.repository}:{decision.pull_number}:"
            f"{decision.head_sha}:{decision.verdict_id or 'none'}"
        )
        try:
            existing = self._client.list_check_runs(
                decision.repository, decision.head_sha
            )
            matching = [
                run
                for run in existing
                if run.name == AI_REVIEW_CHECK_NAME and run.app_id == GATE_APP_ID
            ]
            if matching:
                self._client.update_check_run(
                    decision.repository,
                    check_run_id=matching[0].check_run_id,
                    conclusion=decision.conclusion,
                    title=title,
                    summary=summary,
                )
            else:
                self._client.create_check_run(
                    decision.repository,
                    name=AI_REVIEW_CHECK_NAME,
                    head_sha=decision.head_sha,
                    conclusion=decision.conclusion,
                    title=title,
                    summary=summary,
                    external_id=external_id,
                )
        except GateApiError as exc:
            # A publication failure must never become a success.
            return replace(decision, published=False, publish_error=str(exc))
        return replace(decision, published=True, publish_error=None)

    def _render_output(self, decision: GateDecision) -> tuple[str, str]:
        if decision.conclusion == CONCLUSION_SUCCESS:
            title = "AI review: approved"
        elif decision.conclusion == CONCLUSION_ACTION_REQUIRED:
            title = "AI review: action required"
        else:
            title = "AI review: blocked"
        parts = [
            f"head sha: {decision.head_sha or 'unknown'}",
            f"decision: {decision.conclusion} ({decision.reason})",
        ]
        if decision.reviewer_login:
            parts.append(f"reviewer: {decision.reviewer_login}")
        if decision.review_id is not None:
            parts.append(f"review id: {decision.review_id}")
        if decision.verdict_id:
            parts.append(f"verdict id: {decision.verdict_id}")
        if decision.policy_version:
            parts.append(f"policy version: {decision.policy_version}")
        parts.append(f"blocking findings: {decision.blocking_count}")
        return title, " | ".join(parts)


def build_gate_from_env(
    *,
    repository: str,
    transport: object | None = None,
    token_provider: object | None = None,
) -> tuple[ReviewGate | None, GateConfig]:
    """Build a :class:`ReviewGate` from the environment.

    Returns ``(gate, config)``. The gate is ``None`` when the gate is disabled or
    enabled-but-unavailable; ``config.enabled`` and ``config.available`` let the
    caller distinguish the two so it can fail closed when enabled.
    """
    config = gate_config_from_env(
        transport=transport,  # type: ignore[arg-type]
        token_provider=token_provider,  # type: ignore[arg-type]
    )
    if config.client is None:
        return None, config
    gate = ReviewGate(
        config.client,
        repository=repository,
        reviewer_login=config.reviewer_login,
        reviewer_user_id=config.reviewer_user_id,
        max_verdict_age_seconds=config.max_verdict_age_seconds,
        policy_versions=config.policy_versions,
    )
    return gate, config

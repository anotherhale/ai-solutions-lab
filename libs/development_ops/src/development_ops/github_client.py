"""GitHub pull request inspection and auto-merge (GraphQL only)."""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from development_ops.integration import (
    AUTONOMOUS_INTEGRATION_BRANCH,
    is_authorized_base_branch,
)

# A pull request must expose every required check context. Zero checks, or a
# missing required context, means "not scheduled", never "green". ``none`` is a
# distinct state from ``pending`` so the coordinator can tell "the workflow has
# not been triggered" apart from "the workflow is still running".
_CHECKS_GREEN = "green"
_CHECKS_FAILED = "failed"
_CHECKS_TIMED_OUT = "timed_out"
_CHECKS_RUNNING = "running"
_CHECKS_PENDING = "pending"
_CHECKS_NONE = "none"

_PASSING_CONCLUSIONS = {"SUCCESS", "NEUTRAL", "SKIPPED"}
_PENDING_CONCLUSIONS = {"PENDING", "QUEUED", "IN_PROGRESS", "WAITING", "EXPECTED"}
_RUNNING_STATUSES = {"IN_PROGRESS"}
_TIMED_OUT_CONCLUSIONS = {"TIMED_OUT", "STALE", "STARTUP_FAILURE"}

# How long a required check may stay unfinished before it is treated as timed
# out rather than still running. GitHub's own limit is six hours; the
# coordinator uses a much shorter bound so a wedged run is surfaced quickly.
CHECK_TIMEOUT_SECONDS = 45 * 60

# The check contexts the ``ai-dev`` branch ruleset marks as required. The
# coordinator verifies every one of them is present before arming auto-merge;
# a workflow whose trigger did not fire produces no check at all, and GitHub
# would otherwise report the pull request as "no required checks" rather than
# blocking it. Overridable for repositories with a different ruleset.
DEFAULT_REQUIRED_CHECKS: tuple[str, ...] = (
    "Format, lint, and conventions",
    "Wasatch review frontend",
    "Compose API smoke",
    "Wasatch API tests",
    "Review workbench browser tests",
)


def required_check_contexts() -> tuple[str, ...]:
    """Required status-check contexts for the integration branch ruleset."""
    override = os.environ.get("DEVELOPMENT_OPS_REQUIRED_CHECKS", "").strip()
    if override:
        return tuple(item.strip() for item in override.split(",") if item.strip())
    return DEFAULT_REQUIRED_CHECKS


@dataclass(frozen=True, slots=True)
class PullRequestState:
    number: int
    state: str
    merged: bool
    mergeable: str | None
    head_ref: str
    base_ref: str
    node_id: str | None
    auto_merge_enabled: bool
    checks_green: bool | None
    review_decision: str | None
    closed: bool = False
    checks_state: str = _CHECKS_NONE
    missing_required_checks: tuple[str, ...] = ()
    merge_state_status: str | None = None
    is_draft: bool = False
    unresolved_threads: int = 0
    head_sha: str = ""

    @property
    def targets_integration_branch(self) -> bool:
        return is_authorized_base_branch(self.base_ref)

    @property
    def closed_unmerged(self) -> bool:
        return self.closed and not self.merged

    @property
    def has_conflicts(self) -> bool:
        return (self.mergeable or "").upper() == "CONFLICTING" or (
            self.merge_state_status or ""
        ).upper() == "DIRTY"

    @property
    def threads_unresolved(self) -> bool:
        return self.unresolved_threads > 0

    def auto_merge_blockers(self) -> tuple[str, ...]:
        """Human-readable reasons the PR is not yet safe to auto-merge.

        Ordered from most to least fundamental. An empty tuple means every
        gate this client can observe is satisfied. Mergeability is reported
        separately because GitHub computes it asynchronously (``UNKNOWN``).
        """
        reasons: list[str] = []
        if self.merged:
            reasons.append("pull request already merged")
        elif self.closed:
            reasons.append("pull request is closed without merge")
        if not self.targets_integration_branch:
            reasons.append(
                f"base branch '{self.base_ref}' is not "
                f"'{AUTONOMOUS_INTEGRATION_BRANCH}'"
            )
        if self.is_draft:
            reasons.append("pull request is a draft")
        if self.checks_green is not True:
            reasons.append(f"checks are not all passing (state: {self.checks_state})")
        if self.missing_required_checks:
            reasons.append(
                "required check(s) not scheduled: "
                + ", ".join(self.missing_required_checks)
            )
        if self.threads_unresolved:
            reasons.append(f"{self.unresolved_threads} unresolved review thread(s)")
        if self.has_conflicts:
            reasons.append("pull request has merge conflicts")
        return tuple(reasons)


@dataclass(frozen=True, slots=True)
class AutoMergeAttempt:
    pull_number: int
    requested: bool
    auto_merge_request_present: bool
    error: str | None = None
    raw_response: str | None = None


@dataclass(frozen=True, slots=True)
class ReviewCheck:
    """A check run as seen by the coordinator's independent verification."""

    name: str
    app_id: int
    head_sha: str
    status: str
    conclusion: str | None


class GitHubClient(Protocol):
    def get_pull_request(self, repository: str, number: int) -> PullRequestState: ...

    def list_open_pull_requests(self, repository: str) -> list[PullRequestState]: ...

    def enable_squash_auto_merge(
        self, repository: str, number: int
    ) -> AutoMergeAttempt: ...

    def get_review_check(
        self, repository: str, ref: str, check_name: str
    ) -> ReviewCheck | None:
        """Return the named check run on ``ref`` for coordinator verification."""
        ...


@dataclass(frozen=True, slots=True)
class MergeVerification:
    """The result of checking whether a pull request is safely merged.

    Cleanup depends on this: a worktree is removed only when the *specific*
    pull request is confirmed merged into the autonomous integration branch of
    the expected repository. Anything else (open, closed-unmerged, wrong base,
    unknown) is ``verified=False`` with a human-readable ``reason``.
    """

    pull_number: int
    repository: str
    merged: bool
    base_ref: str
    state: str
    verified: bool
    reason: str


def verify_pull_request_merged(
    client: GitHubClient,
    *,
    repository: str,
    pull_number: int,
    integration_branch: str = AUTONOMOUS_INTEGRATION_BRANCH,
) -> MergeVerification:
    """Confirm a PR merged into ``integration_branch`` for ``repository``.

    Fails closed: any lookup error or ambiguity yields ``verified=False`` so a
    caller never deletes a worktree on an unverified merge.
    """
    try:
        state = client.get_pull_request(repository, pull_number)
    except RuntimeError as exc:
        return MergeVerification(
            pull_number=pull_number,
            repository=repository,
            merged=False,
            base_ref="",
            state="UNKNOWN",
            verified=False,
            reason=f"pull request lookup failed: {exc}",
        )
    if not state.merged:
        return MergeVerification(
            pull_number=pull_number,
            repository=repository,
            merged=False,
            base_ref=state.base_ref,
            state=state.state,
            verified=False,
            reason=(
                f"pull request #{pull_number} is not merged (state: {state.state})"
            ),
        )
    if state.base_ref != integration_branch:
        return MergeVerification(
            pull_number=pull_number,
            repository=repository,
            merged=True,
            base_ref=state.base_ref,
            state=state.state,
            verified=False,
            reason=(
                f"pull request #{pull_number} merged into '{state.base_ref}', "
                f"not '{integration_branch}'"
            ),
        )
    return MergeVerification(
        pull_number=pull_number,
        repository=repository,
        merged=True,
        base_ref=state.base_ref,
        state=state.state,
        verified=True,
        reason=f"pull request #{pull_number} merged into {integration_branch}",
    )


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _age_seconds(value: str | None, now: datetime) -> float | None:
    parsed = _parse_timestamp(value)
    if parsed is None:
        return None
    return (now - parsed).total_seconds()


def _check_identity(item: dict) -> str:
    """The rollup entry's display name, falling back to its context."""
    return str(item.get("name") or item.get("context") or "")


def _classify_check_rollup(
    rollup: list[dict],
    *,
    required: tuple[str, ...] = (),
    now: datetime | None = None,
    timeout_seconds: float = CHECK_TIMEOUT_SECONDS,
) -> tuple[str, tuple[str, ...]]:
    """Classify a status check rollup into one of six states.

    Returns ``(state, missing_required)`` where ``state`` is one of ``green``,
    ``failed``, ``timed_out``, ``running``, ``pending`` or ``none``:

    * ``none``    - no check of any kind has been reported (not scheduled).
    * ``running`` - at least one check is actively executing.
    * ``pending`` - at least one check is queued or waiting to start.
    * ``timed_out`` - an unfinished check exceeded ``timeout_seconds``.
    * ``failed``  - a check reported a failing conclusion.
    * ``green``   - every reported check passed and every required context is
      present.

    A missing or empty rollup is never green. When ``required`` contexts are
    supplied, a rollup that omits one is reported as ``none`` with the missing
    contexts listed, because GitHub will not run a required workflow whose
    trigger did not fire.
    """
    now = now or datetime.now(UTC)
    required_set = set(required)
    present: set[str] = set()

    if not rollup:
        return _CHECKS_NONE, tuple(sorted(required_set))

    saw_failed = False
    saw_timed_out = False
    saw_running = False
    saw_pending = False

    for item in rollup:
        name = _check_identity(item)
        if name:
            present.add(name)
        typename = item.get("__typename")
        if typename == "CheckRun":
            status = item.get("status")
            conclusion = (item.get("conclusion") or "").upper()
            if status not in {None, "COMPLETED"}:
                if _is_timed_out(item, now, timeout_seconds):
                    saw_timed_out = True
                elif status in _RUNNING_STATUSES:
                    saw_running = True
                else:
                    saw_pending = True
                continue
            if conclusion in _PASSING_CONCLUSIONS:
                continue
            if conclusion in _TIMED_OUT_CONCLUSIONS:
                saw_failed = True
                continue
            if conclusion in _PENDING_CONCLUSIONS or conclusion == "":
                saw_pending = True
                continue
            saw_failed = True
            continue
        # StatusContext or unknown node: use ``state``/``conclusion``.
        raw = (item.get("conclusion") or item.get("state") or "").upper()
        if raw in _PASSING_CONCLUSIONS:
            continue
        if raw in _TIMED_OUT_CONCLUSIONS:
            saw_failed = True
            continue
        if raw in _PENDING_CONCLUSIONS or raw == "":
            saw_pending = True
            continue
        saw_failed = True

    missing = tuple(sorted(required_set - present))
    if saw_failed:
        return _CHECKS_FAILED, missing
    if saw_timed_out:
        return _CHECKS_TIMED_OUT, missing
    if missing:
        return _CHECKS_NONE, missing
    if saw_running:
        return _CHECKS_RUNNING, missing
    if saw_pending:
        return _CHECKS_PENDING, missing
    return _CHECKS_GREEN, missing


def _is_timed_out(item: dict, now: datetime, timeout_seconds: float) -> bool:
    """True when an unfinished check has been waiting past the timeout."""
    started = item.get("startedAt") or item.get("createdAt")
    age = _age_seconds(started, now)
    if age is None:
        return False
    return age > timeout_seconds


def _classify_checks(rollup: list[dict]) -> str:
    """Backwards-compatible single-value classification (no required contexts).

    Kept for callers that only need the state string. Prefer
    :func:`_classify_check_rollup` when the required check contexts are known.
    """
    state, _ = _classify_check_rollup(rollup)
    return state


class GhCliGitHubClient:
    """Read-only and auto-merge operations via ``gh`` (no REST merge)."""

    def __init__(self, *, gh_path: str = "gh", page_size: int = 50) -> None:
        self._gh = gh_path
        self._page_size = page_size

    def _run(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [self._gh, *args],
            capture_output=True,
            text=True,
            check=False,
        )

    def get_pull_request(self, repository: str, number: int) -> PullRequestState:
        result = self._run(
            "pr",
            "view",
            str(number),
            "--repo",
            repository,
            "--json",
            "number,state,mergedAt,mergeable,mergeStateStatus,isDraft,"
            "headRefName,headRefOid,baseRefName,id,autoMergeRequest,"
            "statusCheckRollup,reviewDecision",
        )
        if result.returncode != 0:
            msg = result.stderr.strip() or result.stdout.strip()
            raise RuntimeError(msg)
        payload = json.loads(result.stdout)
        auto = payload.get("autoMergeRequest")
        rollup = payload.get("statusCheckRollup") or []
        checks_state, missing_required = _classify_check_rollup(
            rollup, required=required_check_contexts()
        )
        merged = payload.get("mergedAt") is not None or payload.get("state") == "MERGED"
        closed = payload.get("state") == "CLOSED" or merged
        base_ref = str(payload.get("baseRefName") or "")
        # Review threads require a separate GraphQL call and GitHub does not
        # expose the count through ``gh pr view``. Only fetch them for a pull
        # request that is otherwise a plausible candidate: an ineligible PR
        # (wrong base, not green, closed) is already blocked, and querying every
        # open pull request on every tick would be wasteful and rate-limited.
        threads = 0
        if (
            not merged
            and not closed
            and is_authorized_base_branch(base_ref)
            and checks_state == _CHECKS_GREEN
        ):
            threads = self.count_unresolved_threads(repository, number)
        return PullRequestState(
            number=int(payload["number"]),
            state=str(payload.get("state") or "OPEN"),
            merged=bool(merged),
            mergeable=payload.get("mergeable"),
            head_ref=str(payload.get("headRefName") or ""),
            base_ref=base_ref,
            node_id=str(payload.get("id") or "") or None,
            auto_merge_enabled=auto is not None,
            checks_green=checks_state == _CHECKS_GREEN,
            review_decision=payload.get("reviewDecision"),
            closed=bool(closed),
            checks_state=checks_state,
            missing_required_checks=missing_required,
            merge_state_status=payload.get("mergeStateStatus"),
            is_draft=bool(payload.get("isDraft")),
            unresolved_threads=threads,
            head_sha=str(payload.get("headRefOid") or ""),
        )

    def count_unresolved_threads(self, repository: str, number: int) -> int:
        """Number of unresolved, non-outdated review threads on the PR.

        GitHub's ruleset rule ``required_review_thread_resolution`` blocks a
        merge while any thread is unresolved, but neither ``gh pr view`` nor the
        REST PR payload exposes the count. This is the only signal available, so
        it is fetched separately and fails closed: a lookup error reports the
        threads as *unresolved* rather than silently allowing a merge.
        """
        owner, _, name = repository.partition("/")
        query = """
        query($owner: String!, $name: String!, $number: Int!) {
          repository(owner: $owner, name: $name) {
            pullRequest(number: $number) {
              reviewThreads(first: 100) {
                nodes { isResolved isOutdated }
              }
            }
          }
        }
        """
        result = self._run(
            "api",
            "graphql",
            "-f",
            f"query={query}",
            "-f",
            f"owner={owner}",
            "-f",
            f"name={name}",
            "-F",
            f"number={number}",
        )
        if result.returncode != 0:
            return 1
        try:
            body = json.loads(result.stdout)
        except json.JSONDecodeError:
            return 1
        if body.get("errors"):
            return 1
        nodes = (
            body.get("data", {})
            .get("repository", {})
            .get("pullRequest", {})
            .get("reviewThreads", {})
            .get("nodes", [])
        )
        return sum(
            1
            for node in nodes
            if not node.get("isResolved") and not node.get("isOutdated")
        )

    def list_open_pull_requests(self, repository: str) -> list[PullRequestState]:
        """List open pull requests.

        ``gh pr list --limit`` follows the REST pagination internally, so a limit
        above one page returns every open pull request up to that bound.
        """
        result = self._run(
            "pr",
            "list",
            "--repo",
            repository,
            "--state",
            "open",
            "--json",
            "number",
            "--limit",
            str(self._page_size),
        )
        if result.returncode != 0:
            msg = result.stderr.strip() or result.stdout.strip()
            raise RuntimeError(msg)
        numbers = json.loads(result.stdout)
        return [
            self.get_pull_request(repository, int(row["number"])) for row in numbers
        ]

    def enable_squash_auto_merge(
        self, repository: str, number: int
    ) -> AutoMergeAttempt:
        pr = self.get_pull_request(repository, number)
        if pr.auto_merge_enabled:
            return AutoMergeAttempt(
                pull_number=number,
                requested=False,
                auto_merge_request_present=True,
            )
        blockers = pr.auto_merge_blockers()
        if blockers:
            return AutoMergeAttempt(
                pull_number=number,
                requested=False,
                auto_merge_request_present=False,
                error="auto-merge refused: " + "; ".join(blockers),
            )
        node_id = pr.node_id
        if not node_id:
            return AutoMergeAttempt(
                pull_number=number,
                requested=True,
                auto_merge_request_present=False,
                error="missing pull request node id",
            )
        mutation = """
        mutation($id: ID!) {
          enablePullRequestAutoMerge(input: {pullRequestId: $id, mergeMethod: SQUASH}) {
            pullRequest {
              autoMergeRequest { enabledAt }
            }
          }
        }
        """
        # gh passes GraphQL variables as individual -f key=value fields.
        result = self._run(
            "api",
            "graphql",
            "-f",
            f"query={mutation}",
            "-f",
            f"id={node_id}",
        )
        raw = (result.stdout or "") + (result.stderr or "")
        if result.returncode != 0:
            return AutoMergeAttempt(
                pull_number=number,
                requested=True,
                auto_merge_request_present=False,
                error=raw.strip() or "graphql request failed",
                raw_response=raw,
            )
        try:
            body = json.loads(result.stdout)
        except json.JSONDecodeError:
            return AutoMergeAttempt(
                pull_number=number,
                requested=True,
                auto_merge_request_present=False,
                error="invalid graphql json response",
                raw_response=raw,
            )
        errors = body.get("errors")
        if errors:
            message = "; ".join(
                str(item.get("message", item)) for item in errors if item
            )
            return AutoMergeAttempt(
                pull_number=number,
                requested=True,
                auto_merge_request_present=False,
                error=message,
                raw_response=raw,
            )
        pr_payload = (
            body.get("data", {})
            .get("enablePullRequestAutoMerge", {})
            .get("pullRequest", {})
        )
        auto_merge = pr_payload.get("autoMergeRequest")
        present = auto_merge is not None
        refreshed = self.get_pull_request(repository, number)
        present = present or refreshed.auto_merge_enabled
        return AutoMergeAttempt(
            pull_number=number,
            requested=True,
            auto_merge_request_present=present,
            error=None if present else "autoMergeRequest remained null after GraphQL",
            raw_response=raw,
        )

    def get_review_check(
        self, repository: str, ref: str, check_name: str
    ) -> ReviewCheck | None:
        """Fetch the named check run on ``ref`` for independent verification."""
        result = self._run(
            "api",
            f"repos/{repository}/commits/{ref}/check-runs"
            f"?check_name={check_name}&per_page=100",
        )
        if result.returncode != 0:
            msg = result.stderr.strip() or result.stdout.strip()
            raise RuntimeError(msg)
        payload = json.loads(result.stdout)
        runs = payload.get("check_runs") or []
        for item in runs:
            app = item.get("app") or {}
            if str(item.get("name")) == check_name:
                return ReviewCheck(
                    name=str(item.get("name") or ""),
                    app_id=int(app.get("id") or 0),
                    head_sha=str(item.get("head_sha") or ""),
                    status=str(item.get("status") or ""),
                    conclusion=item.get("conclusion"),
                )
        return None


def github_client_from_env() -> GitHubClient | None:
    if os.environ.get("DEVELOPMENT_OPS_DISABLE_GITHUB") == "1":
        return None
    if not os.environ.get("GH_TOKEN") and not os.environ.get("GITHUB_TOKEN"):
        probe = subprocess.run(
            ["gh", "auth", "status"], capture_output=True, check=False
        )
        if probe.returncode != 0:
            return None
    return GhCliGitHubClient()

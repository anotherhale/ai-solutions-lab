"""GitHub pull request inspection and auto-merge (GraphQL only)."""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from typing import Protocol

from development_ops.integration import (
    AUTONOMOUS_INTEGRATION_BRANCH,
    is_authorized_base_branch,
)

# A pull request must expose at least one check. Zero checks means "unknown",
# never "green".
_CHECKS_GREEN = "green"
_CHECKS_FAILED = "failed"
_CHECKS_PENDING = "pending"
_CHECKS_NONE = "none"

_PASSING_CONCLUSIONS = {"SUCCESS", "NEUTRAL", "SKIPPED"}
_PENDING_CONCLUSIONS = {"PENDING", "QUEUED", "IN_PROGRESS", "WAITING", "EXPECTED"}


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
    merge_state_status: str | None = None
    is_draft: bool = False
    unresolved_threads: int = 0

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


class GitHubClient(Protocol):
    def get_pull_request(self, repository: str, number: int) -> PullRequestState: ...

    def list_open_pull_requests(self, repository: str) -> list[PullRequestState]: ...

    def enable_squash_auto_merge(
        self, repository: str, number: int
    ) -> AutoMergeAttempt: ...


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


def _classify_checks(rollup: list[dict]) -> str:
    """Classify a status check rollup.

    GitHub reports two node kinds: ``CheckRun`` (GitHub Actions) and
    ``StatusContext`` (legacy commit statuses). Both carry a conclusion or a
    state, and both must be considered. A missing or empty rollup is unknown,
    not green.
    """
    if not rollup:
        return _CHECKS_NONE
    saw_pending = False
    for item in rollup:
        typename = item.get("__typename")
        if typename == "CheckRun":
            if item.get("status") not in {None, "COMPLETED"}:
                saw_pending = True
                continue
            conclusion = (item.get("conclusion") or "").upper()
            if conclusion in _PASSING_CONCLUSIONS:
                continue
            if conclusion in _PENDING_CONCLUSIONS or conclusion == "":
                saw_pending = True
                continue
            return _CHECKS_FAILED
        # StatusContext or unknown node: use ``state``/``conclusion``.
        raw = (item.get("conclusion") or item.get("state") or "").upper()
        if raw in _PASSING_CONCLUSIONS:
            continue
        if raw in _PENDING_CONCLUSIONS or raw == "":
            saw_pending = True
            continue
        return _CHECKS_FAILED
    return _CHECKS_PENDING if saw_pending else _CHECKS_GREEN


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
            "headRefName,baseRefName,id,autoMergeRequest,statusCheckRollup,"
            "reviewDecision",
        )
        if result.returncode != 0:
            msg = result.stderr.strip() or result.stdout.strip()
            raise RuntimeError(msg)
        payload = json.loads(result.stdout)
        auto = payload.get("autoMergeRequest")
        rollup = payload.get("statusCheckRollup") or []
        checks_state = _classify_checks(rollup)
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
            merge_state_status=payload.get("mergeStateStatus"),
            is_draft=bool(payload.get("isDraft")),
            unresolved_threads=threads,
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

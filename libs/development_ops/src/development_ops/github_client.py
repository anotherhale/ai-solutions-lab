"""GitHub pull request inspection and auto-merge (GraphQL only)."""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from typing import Protocol

# Autonomy may only integrate into the autonomous development branch. ``main``
# is human-controlled and every other base is out of scope for auto-merge.
AUTONOMOUS_INTEGRATION_BRANCH = "ai-dev"

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

    @property
    def targets_integration_branch(self) -> bool:
        return self.base_ref == AUTONOMOUS_INTEGRATION_BRANCH

    @property
    def closed_unmerged(self) -> bool:
        return self.closed and not self.merged


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
            "number,state,mergedAt,mergeable,headRefName,baseRefName,id,"
            "autoMergeRequest,statusCheckRollup,reviewDecision",
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
        return PullRequestState(
            number=int(payload["number"]),
            state=str(payload.get("state") or "OPEN"),
            merged=bool(merged),
            mergeable=payload.get("mergeable"),
            head_ref=str(payload.get("headRefName") or ""),
            base_ref=str(payload.get("baseRefName") or ""),
            node_id=str(payload.get("id") or "") or None,
            auto_merge_enabled=auto is not None,
            checks_green=checks_state == _CHECKS_GREEN,
            review_decision=payload.get("reviewDecision"),
            closed=bool(closed),
            checks_state=checks_state,
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
        if pr.merged:
            return AutoMergeAttempt(
                pull_number=number,
                requested=False,
                auto_merge_request_present=False,
                error="pull request already merged",
            )
        if pr.closed:
            return AutoMergeAttempt(
                pull_number=number,
                requested=False,
                auto_merge_request_present=False,
                error="pull request is closed without merge",
            )
        if not pr.targets_integration_branch:
            return AutoMergeAttempt(
                pull_number=number,
                requested=False,
                auto_merge_request_present=False,
                error=(
                    f"auto-merge refused: base branch '{pr.base_ref}' is not "
                    f"'{AUTONOMOUS_INTEGRATION_BRANCH}'"
                ),
            )
        if pr.checks_green is not True:
            return AutoMergeAttempt(
                pull_number=number,
                requested=False,
                auto_merge_request_present=False,
                error=(
                    "auto-merge refused: required checks are not all passing "
                    f"(state: {pr.checks_state})"
                ),
            )
        if pr.auto_merge_enabled:
            return AutoMergeAttempt(
                pull_number=number,
                requested=False,
                auto_merge_request_present=True,
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

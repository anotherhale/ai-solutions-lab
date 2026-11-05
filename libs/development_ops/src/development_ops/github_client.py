"""GitHub pull request inspection and auto-merge (GraphQL only)."""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from typing import Protocol


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


class GhCliGitHubClient:
    """Read-only and auto-merge operations via ``gh`` (no REST merge)."""

    def __init__(self, *, gh_path: str = "gh") -> None:
        self._gh = gh_path

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
        checks = payload.get("statusCheckRollup") or []
        checks_green = None
        if checks:
            checks_green = all(
                (item.get("conclusion") or item.get("state"))
                in {"SUCCESS", "COMPLETED"}
                for item in checks
                if item.get("__typename") != "CheckRun"
            )
        merged = payload.get("mergedAt") is not None or payload.get("state") == "MERGED"
        return PullRequestState(
            number=int(payload["number"]),
            state=str(payload.get("state") or "OPEN"),
            merged=bool(merged),
            mergeable=payload.get("mergeable"),
            head_ref=str(payload.get("headRefName") or ""),
            base_ref=str(payload.get("baseRefName") or ""),
            node_id=str(payload.get("id") or "") or None,
            auto_merge_enabled=auto is not None,
            checks_green=checks_green,
            review_decision=payload.get("reviewDecision"),
        )

    def list_open_pull_requests(self, repository: str) -> list[PullRequestState]:
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
            "50",
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
        result = self._run(
            "api",
            "graphql",
            "-f",
            f"query={mutation}",
            "-f",
            f"variables={json.dumps({'id': node_id})}",
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

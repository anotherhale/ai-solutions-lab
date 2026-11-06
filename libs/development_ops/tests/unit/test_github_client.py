"""Unit tests for GitHub check classification and auto-merge safety."""

from __future__ import annotations

import json
import subprocess

from development_ops.github_client import (
    AUTONOMOUS_INTEGRATION_BRANCH,
    GhCliGitHubClient,
    PullRequestState,
    _classify_checks,
)


def _check_run(conclusion: str | None, status: str = "COMPLETED") -> dict:
    return {"__typename": "CheckRun", "status": status, "conclusion": conclusion}


def _status_context(state: str) -> dict:
    return {"__typename": "StatusContext", "state": state}


def test_empty_rollup_is_none_not_green() -> None:
    assert _classify_checks([]) == "none"


def test_all_check_runs_success_is_green() -> None:
    rollup = [_check_run("SUCCESS"), _check_run("SUCCESS")]
    assert _classify_checks(rollup) == "green"


def test_github_actions_check_run_success_is_green() -> None:
    """GitHub Actions produce CheckRuns; a green Actions-only PR is green."""
    rollup = [_check_run("SUCCESS"), _status_context("SUCCESS")]
    assert _classify_checks(rollup) == "green"


def test_check_run_failure_is_failed() -> None:
    assert _classify_checks([_check_run("FAILURE")]) == "failed"


def test_check_run_in_progress_is_pending() -> None:
    assert _classify_checks([_check_run(None, status="IN_PROGRESS")]) == "pending"


def test_check_run_without_conclusion_is_pending() -> None:
    assert _classify_checks([_check_run(None)]) == "pending"


def test_status_context_pending_is_pending() -> None:
    assert _classify_checks([_status_context("PENDING")]) == "pending"


def test_status_context_error_is_failed() -> None:
    assert _classify_checks([_status_context("ERROR")]) == "failed"


def test_mixed_success_and_failure_is_failed() -> None:
    rollup = [_check_run("SUCCESS"), _status_context("FAILURE")]
    assert _classify_checks(rollup) == "failed"


def test_neutral_and_skipped_conclusions_are_green() -> None:
    rollup = [_check_run("NEUTRAL"), _check_run("SKIPPED")]
    assert _classify_checks(rollup) == "green"


def test_unknown_node_type_is_conservative() -> None:
    """An unrecognised node with no state must not be treated as success."""
    assert _classify_checks([{"__typename": "Mystery"}]) == "pending"


# --- GhCliGitHubClient parsing and guards -------------------------------------


class _FakeRunner:
    """Records ``gh`` invocations and replays canned JSON per subcommand."""

    def __init__(self, pr_view: dict, pr_list: list[dict] | None = None) -> None:
        self.pr_view = pr_view
        self.pr_list = pr_list or []
        self.calls: list[tuple[str, ...]] = []

    def __call__(self, *args: str) -> subprocess.CompletedProcess[str]:
        self.calls.append(tuple(args))
        if args[:2] == ("pr", "view"):
            return subprocess.CompletedProcess(args, 0, json.dumps(self.pr_view), "")
        if args[:2] == ("pr", "list"):
            return subprocess.CompletedProcess(args, 0, json.dumps(self.pr_list), "")
        if args[:2] == ("api", "graphql"):
            return subprocess.CompletedProcess(
                args,
                0,
                json.dumps(
                    {
                        "data": {
                            "enablePullRequestAutoMerge": {
                                "pullRequest": {"autoMergeRequest": {"enabledAt": "x"}}
                            }
                        }
                    }
                ),
                "",
            )
        return subprocess.CompletedProcess(args, 1, "", "unexpected")


def _client(runner: _FakeRunner) -> GhCliGitHubClient:
    client = GhCliGitHubClient()
    client._run = runner  # type: ignore[assignment]
    return client


def _pr_view(
    *,
    base: str = "ai-dev",
    state: str = "OPEN",
    merged: bool = False,
    rollup: list[dict] | None = None,
    auto_merge: bool = False,
) -> dict:
    return {
        "number": 7,
        "state": state,
        "mergedAt": "2026-11-06T00:00:00Z" if merged else None,
        "mergeable": "MERGEABLE",
        "headRefName": "cursor/x",
        "baseRefName": base,
        "id": "PR_node_7",
        "autoMergeRequest": {"enabledAt": "x"} if auto_merge else None,
        "statusCheckRollup": rollup if rollup is not None else [_check_run("SUCCESS")],
        "reviewDecision": "REVIEW_REQUIRED",
    }


def test_get_pull_request_marks_actions_green() -> None:
    runner = _FakeRunner(_pr_view(rollup=[_check_run("SUCCESS")]))
    pr = _client(runner).get_pull_request("o/r", 7)
    assert pr.checks_green is True
    assert pr.checks_state == "green"
    assert pr.targets_integration_branch is True


def test_get_pull_request_empty_checks_is_not_green() -> None:
    runner = _FakeRunner(_pr_view(rollup=[]))
    pr = _client(runner).get_pull_request("o/r", 7)
    assert pr.checks_green is False
    assert pr.checks_state == "none"


def test_enable_auto_merge_refuses_main() -> None:
    runner = _FakeRunner(_pr_view(base="main"))
    attempt = _client(runner).enable_squash_auto_merge("o/r", 7)
    assert attempt.requested is False
    assert attempt.auto_merge_request_present is False
    assert attempt.error is not None and "main" in attempt.error
    assert not any(call[:2] == ("api", "graphql") for call in runner.calls)


def test_enable_auto_merge_refuses_non_green() -> None:
    runner = _FakeRunner(_pr_view(base="ai-dev", rollup=[_check_run("FAILURE")]))
    attempt = _client(runner).enable_squash_auto_merge("o/r", 7)
    assert attempt.requested is False
    assert attempt.error is not None and "checks" in attempt.error
    assert not any(call[:2] == ("api", "graphql") for call in runner.calls)


def test_enable_auto_merge_refuses_empty_checks() -> None:
    runner = _FakeRunner(_pr_view(base="ai-dev", rollup=[]))
    attempt = _client(runner).enable_squash_auto_merge("o/r", 7)
    assert attempt.requested is False
    assert attempt.error is not None
    assert not any(call[:2] == ("api", "graphql") for call in runner.calls)


def test_enable_auto_merge_refuses_closed_unmerged() -> None:
    runner = _FakeRunner(_pr_view(state="CLOSED"))
    attempt = _client(runner).enable_squash_auto_merge("o/r", 7)
    assert attempt.requested is False
    assert attempt.error is not None and "closed" in attempt.error


def test_enable_auto_merge_issues_graphql_for_green_ai_dev() -> None:
    runner = _FakeRunner(_pr_view(base="ai-dev", rollup=[_check_run("SUCCESS")]))
    attempt = _client(runner).enable_squash_auto_merge("o/r", 7)
    assert attempt.requested is True
    assert any(call[:2] == ("api", "graphql") for call in runner.calls)


def test_autonomous_branch_constant_is_ai_dev() -> None:
    assert AUTONOMOUS_INTEGRATION_BRANCH == "ai-dev"


def test_pull_request_state_closed_unmerged_property() -> None:
    pr = PullRequestState(
        number=1,
        state="CLOSED",
        merged=False,
        mergeable=None,
        head_ref="h",
        base_ref="ai-dev",
        node_id=None,
        auto_merge_enabled=False,
        checks_green=False,
        review_decision=None,
        closed=True,
    )
    assert pr.closed_unmerged is True


def test_list_open_pull_requests_uses_configured_page_size() -> None:
    runner = _FakeRunner(_pr_view(), pr_list=[{"number": 7}])
    client = GhCliGitHubClient(page_size=123)
    client._run = runner  # type: ignore[assignment]
    states = client.list_open_pull_requests("o/r")
    assert [s.number for s in states] == [7]
    list_calls = [call for call in runner.calls if call[:2] == ("pr", "list")]
    assert list_calls
    assert "123" in list_calls[0]

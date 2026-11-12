"""Unit tests for the child-execution lifecycle and concurrency policy.

These exercise the domain rules directly: the state machine, the transition
guard, and configuration validation including the phase hard ceiling and the
disabled-by-default enablement resolution. No database and no model calls.
"""

from __future__ import annotations

import pytest
from development_ops.child_config import (
    DEFAULT_MAX_CONCURRENT_CHILDREN,
    HARD_MAX_CONCURRENT_CHILDREN,
    ChildOrchestrationConfig,
    ChildOrchestrationConfigError,
    resolve_enabled,
)
from development_ops.child_lifecycle import (
    ACTIVE_STATES,
    LAUNCHED_STATES,
    TERMINAL_STATES,
    ChildExecutionState,
    IllegalChildTransition,
    allowed_transitions,
    is_legal_transition,
    require_legal_transition,
)

# --- lifecycle ------------------------------------------------------------


def test_required_states_exist() -> None:
    expected = {
        "queued",
        "claimed",
        "launch_pending",
        "running",
        "stalled",
        "failed",
        "completed",
        "pr_open",
        "awaiting_merge",
        "merged",
        "cancelled",
    }
    assert {state.value for state in ChildExecutionState} == expected


def test_happy_path_transitions_are_legal() -> None:
    path = [
        ChildExecutionState.QUEUED,
        ChildExecutionState.CLAIMED,
        ChildExecutionState.LAUNCH_PENDING,
        ChildExecutionState.RUNNING,
        ChildExecutionState.COMPLETED,
        ChildExecutionState.PR_OPEN,
        ChildExecutionState.AWAITING_MERGE,
        ChildExecutionState.MERGED,
    ]
    for current, target in zip(path, path[1:], strict=False):
        assert is_legal_transition(current, target), f"{current} -> {target}"


def test_illegal_backwards_transition_is_refused() -> None:
    assert not is_legal_transition(
        ChildExecutionState.MERGED, ChildExecutionState.RUNNING
    )
    assert not is_legal_transition(
        ChildExecutionState.CANCELLED, ChildExecutionState.CLAIMED
    )
    with pytest.raises(IllegalChildTransition):
        require_legal_transition(
            ChildExecutionState.MERGED, ChildExecutionState.RUNNING
        )


def test_self_transition_is_not_legal() -> None:
    for state in ChildExecutionState:
        assert not is_legal_transition(state, state)


def test_terminal_states_have_no_transitions() -> None:
    for state in TERMINAL_STATES:
        assert allowed_transitions(state) == frozenset()


def test_pr_open_releases_slot_and_is_launched() -> None:
    # A child that opened a PR is no longer consuming an implementation slot...
    assert ChildExecutionState.PR_OPEN not in ACTIVE_STATES
    assert ChildExecutionState.AWAITING_MERGE not in ACTIVE_STATES
    # ...but it did launch, so it must not be relaunched.
    assert ChildExecutionState.PR_OPEN in LAUNCHED_STATES


def test_stalled_still_consumes_a_slot() -> None:
    # A stalled child has not been proven dead, so it still holds its slot.
    assert ChildExecutionState.STALLED in ACTIVE_STATES


def test_stalled_can_recover_to_running() -> None:
    assert is_legal_transition(ChildExecutionState.STALLED, ChildExecutionState.RUNNING)


def test_completed_can_fail_without_pr() -> None:
    # A child that ended without a PR is not a success.
    assert is_legal_transition(
        ChildExecutionState.COMPLETED, ChildExecutionState.FAILED
    )


def test_failed_can_retry_via_launch_pending() -> None:
    assert is_legal_transition(
        ChildExecutionState.FAILED, ChildExecutionState.LAUNCH_PENDING
    )


# --- configuration --------------------------------------------------------


def test_default_is_two() -> None:
    config = ChildOrchestrationConfig()
    assert config.max_concurrent_children == DEFAULT_MAX_CONCURRENT_CHILDREN == 2


def test_hard_ceiling_is_two() -> None:
    assert HARD_MAX_CONCURRENT_CHILDREN == 2
    with pytest.raises(ChildOrchestrationConfigError):
        ChildOrchestrationConfig(max_concurrent_children=3)


def test_zero_concurrency_is_rejected() -> None:
    with pytest.raises(ChildOrchestrationConfigError):
        ChildOrchestrationConfig(max_concurrent_children=0)


def test_one_and_two_are_accepted() -> None:
    assert ChildOrchestrationConfig(max_concurrent_children=1).max_concurrent_children
    assert ChildOrchestrationConfig(max_concurrent_children=2).max_concurrent_children


def test_stall_must_exceed_heartbeat() -> None:
    with pytest.raises(ChildOrchestrationConfigError):
        ChildOrchestrationConfig(heartbeat_seconds=100, stall_seconds=50)


def test_env_parsing_and_ceiling(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEVELOPMENT_OPS_MAX_CONCURRENT_CHILDREN", "2")
    monkeypatch.setenv("DEVELOPMENT_OPS_CHILD_STALL_SECONDS", "600")
    monkeypatch.setenv("DEVELOPMENT_OPS_CHILD_HEARTBEAT_SECONDS", "60")
    config = ChildOrchestrationConfig.from_env()
    assert config.max_concurrent_children == 2
    assert config.stall_seconds == 600

    monkeypatch.setenv("DEVELOPMENT_OPS_MAX_CONCURRENT_CHILDREN", "5")
    with pytest.raises(ChildOrchestrationConfigError):
        ChildOrchestrationConfig.from_env()


def test_env_non_numeric_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEVELOPMENT_OPS_MAX_CONCURRENT_CHILDREN", "two")
    with pytest.raises(ChildOrchestrationConfigError):
        ChildOrchestrationConfig.from_env()


# --- enablement resolution ------------------------------------------------


def test_disabled_by_default() -> None:
    enabled, reason = resolve_enabled(
        persisted_enabled=False, config=ChildOrchestrationConfig()
    )
    assert enabled is False
    assert "disabled" in reason


def test_environment_alone_never_enables() -> None:
    """An exported variable must not switch on paid model calls."""
    config = ChildOrchestrationConfig(env_enable_requested=True)
    enabled, reason = resolve_enabled(persisted_enabled=False, config=config)
    assert enabled is False
    assert "durable operator flag" in reason


def test_operator_flag_enables() -> None:
    enabled, _ = resolve_enabled(
        persisted_enabled=True, config=ChildOrchestrationConfig()
    )
    assert enabled is True

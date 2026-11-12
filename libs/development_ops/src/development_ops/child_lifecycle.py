"""Durable lifecycle for one child-agent execution.

A child execution is the durable record of one attempt to implement one backlog
task in one isolated worktree with one child conversation. It is distinct from
:class:`development_ops.scheduling.RuntimeTaskStatus`, which owns *scheduling*
(slots, dependencies, leases). This module owns the *execution* lifecycle: has a
conversation been launched, is it making progress, did it open a pull request,
and is that pull request merged.

The states and the legal transitions between them are the contract. They are
enforced in the repository layer (single conditional ``UPDATE`` per transition)
so a stale or out-of-order caller cannot move an execution backwards.

Two distinctions matter and are encoded here:

* A launched conversation is not a running worker. ``running`` requires an
  observed progress signal, not merely a successful launch.
* A child that opened a pull request is no longer consuming an implementation
  slot, and a closed-but-unmerged pull request is not a successful completion.
"""

from __future__ import annotations

from enum import StrEnum


class ChildExecutionState(StrEnum):
    QUEUED = "queued"
    CLAIMED = "claimed"
    LAUNCH_PENDING = "launch_pending"
    RUNNING = "running"
    STALLED = "stalled"
    FAILED = "failed"
    COMPLETED = "completed"
    PR_OPEN = "pr_open"
    AWAITING_MERGE = "awaiting_merge"
    MERGED = "merged"
    CANCELLED = "cancelled"


# States in which a child genuinely consumes a concurrency slot. ``pr_open`` and
# ``awaiting_merge`` describe finished implementation handed to GitHub, so they
# release the slot. ``stalled`` still holds its slot until an operator or the
# recovery policy acts: a stalled worker has not yet been proven dead.
ACTIVE_STATES: frozenset[ChildExecutionState] = frozenset(
    {
        ChildExecutionState.CLAIMED,
        ChildExecutionState.LAUNCH_PENDING,
        ChildExecutionState.RUNNING,
        ChildExecutionState.STALLED,
    }
)

# States from which no further automatic transition occurs.
TERMINAL_STATES: frozenset[ChildExecutionState] = frozenset(
    {
        ChildExecutionState.MERGED,
        ChildExecutionState.CANCELLED,
    }
)

# A conversation may exist in these states, so a relaunch would duplicate work.
LAUNCHED_STATES: frozenset[ChildExecutionState] = frozenset(
    {
        ChildExecutionState.RUNNING,
        ChildExecutionState.STALLED,
        ChildExecutionState.COMPLETED,
        ChildExecutionState.PR_OPEN,
        ChildExecutionState.AWAITING_MERGE,
        ChildExecutionState.MERGED,
    }
)


# Legal transitions. Each entry maps a state to the states a real code path may
# move it to. Anything absent is refused.
_LEGAL: dict[ChildExecutionState, frozenset[ChildExecutionState]] = {
    ChildExecutionState.QUEUED: frozenset(
        {
            ChildExecutionState.CLAIMED,
            ChildExecutionState.CANCELLED,
            ChildExecutionState.FAILED,
        }
    ),
    ChildExecutionState.CLAIMED: frozenset(
        {
            ChildExecutionState.LAUNCH_PENDING,
            ChildExecutionState.FAILED,
            ChildExecutionState.CANCELLED,
        }
    ),
    ChildExecutionState.LAUNCH_PENDING: frozenset(
        {
            ChildExecutionState.RUNNING,
            ChildExecutionState.FAILED,
            ChildExecutionState.CANCELLED,
        }
    ),
    ChildExecutionState.RUNNING: frozenset(
        {
            ChildExecutionState.STALLED,
            ChildExecutionState.FAILED,
            ChildExecutionState.COMPLETED,
            ChildExecutionState.PR_OPEN,
            ChildExecutionState.AWAITING_MERGE,
            ChildExecutionState.MERGED,
            ChildExecutionState.CANCELLED,
        }
    ),
    # A stalled child may recover (progress observed again) or be failed out.
    ChildExecutionState.STALLED: frozenset(
        {
            ChildExecutionState.RUNNING,
            ChildExecutionState.FAILED,
            ChildExecutionState.COMPLETED,
            ChildExecutionState.PR_OPEN,
            ChildExecutionState.AWAITING_MERGE,
            ChildExecutionState.MERGED,
            ChildExecutionState.CANCELLED,
        }
    ),
    ChildExecutionState.COMPLETED: frozenset(
        {
            ChildExecutionState.PR_OPEN,
            ChildExecutionState.AWAITING_MERGE,
            ChildExecutionState.FAILED,
            ChildExecutionState.CANCELLED,
        }
    ),
    ChildExecutionState.PR_OPEN: frozenset(
        {
            ChildExecutionState.AWAITING_MERGE,
            ChildExecutionState.MERGED,
            ChildExecutionState.FAILED,
            ChildExecutionState.CANCELLED,
        }
    ),
    ChildExecutionState.AWAITING_MERGE: frozenset(
        {
            ChildExecutionState.MERGED,
            ChildExecutionState.FAILED,
            ChildExecutionState.CANCELLED,
        }
    ),
    ChildExecutionState.FAILED: frozenset(
        {
            ChildExecutionState.LAUNCH_PENDING,
            ChildExecutionState.CANCELLED,
        }
    ),
    ChildExecutionState.MERGED: frozenset(),
    ChildExecutionState.CANCELLED: frozenset(),
}


class IllegalChildTransition(RuntimeError):
    """A requested child-execution state change is not allowed."""


def is_legal_transition(
    current: ChildExecutionState, target: ChildExecutionState
) -> bool:
    """True when ``current`` may move to ``target``."""
    if current == target:
        return False
    return target in _LEGAL.get(current, frozenset())


def allowed_transitions(
    current: ChildExecutionState,
) -> frozenset[ChildExecutionState]:
    return _LEGAL.get(current, frozenset())


def require_legal_transition(
    current: ChildExecutionState, target: ChildExecutionState
) -> None:
    if not is_legal_transition(current, target):
        msg = f"illegal child execution transition: {current.value} -> {target.value}"
        raise IllegalChildTransition(msg)

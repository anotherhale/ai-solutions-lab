"""Authoritative autonomous integration branch configuration.

One source of truth for the branch autonomous agents integrate into. The
worktree base, the child-agent brief, the pull-request base guard, the
auto-merge gate, and the coordinator CLI all import this module, so the value
cannot drift between them (ADR 0010).

``main`` is the human release branch and ``develop`` is the human integration
branch. Autonomy targets neither: a pull request based on anything other than
the autonomous integration branch is unauthorized.
"""

from __future__ import annotations

AUTONOMOUS_INTEGRATION_BRANCH = "ai-dev"

# Branches that exist for humans. Named so an error can explain the boundary
# rather than only reporting a mismatch.
HUMAN_CONTROLLED_BRANCHES = frozenset({"main", "develop"})


class UnauthorizedBaseBranchError(ValueError):
    """An autonomous operation attempted to use an unauthorized base branch."""


def is_authorized_base_branch(branch: str | None) -> bool:
    return branch == AUTONOMOUS_INTEGRATION_BRANCH


def assert_authorized_base_branch(
    branch: str | None,
    *,
    operation: str = "autonomous operation",
) -> str:
    """Fail fast when an autonomous operation targets an unauthorized base.

    Returns the branch unchanged when it is authorized so callers can use it
    inline, for example ``base = assert_authorized_base_branch(branch)``.
    """
    if not is_authorized_base_branch(branch):
        raise UnauthorizedBaseBranchError(
            f"{operation} must target '{AUTONOMOUS_INTEGRATION_BRANCH}', not {branch!r}"
        )
    return branch  # type: ignore[return-value]


def delegation_instruction(task_id: str) -> str:
    """The brief handed to an implementation agent for ``task_id``.

    Built here, not hand-written in a shell script, so the base branch named to
    the agent can never drift from the branch the coordinator can auto-merge.
    """
    return (
        f"Implement backlog task {task_id} on a cursor/* branch from "
        f"{AUTONOMOUS_INTEGRATION_BRANCH}. Record activity milestones, run "
        f"tests, open a PR to {AUTONOMOUS_INTEGRATION_BRANCH}, then run "
        "scripts/coordinator_tick.sh again without waiting for merge."
    )

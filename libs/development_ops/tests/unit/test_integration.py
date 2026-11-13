"""Authoritative integration-branch configuration and delegation brief."""

from __future__ import annotations

import pytest
from development_ops.integration import (
    AUTONOMOUS_INTEGRATION_BRANCH,
    HUMAN_CONTROLLED_BRANCHES,
    UnauthorizedBaseBranchError,
    assert_authorized_base_branch,
    delegation_instruction,
    is_authorized_base_branch,
)


def test_autonomous_branch_is_ai_dev() -> None:
    assert AUTONOMOUS_INTEGRATION_BRANCH == "ai-dev"


def test_human_branches_are_not_authorized() -> None:
    for branch in HUMAN_CONTROLLED_BRANCHES:
        assert is_authorized_base_branch(branch) is False
        with pytest.raises(UnauthorizedBaseBranchError):
            assert_authorized_base_branch(branch)


def test_ai_dev_is_authorized() -> None:
    assert is_authorized_base_branch("ai-dev") is True
    assert assert_authorized_base_branch("ai-dev") == "ai-dev"


def test_none_and_unknown_branch_are_refused() -> None:
    for branch in (None, "", "release", "AI-DEV"):
        with pytest.raises(UnauthorizedBaseBranchError):
            assert_authorized_base_branch(branch)


def test_error_names_the_branch_and_the_expected_target() -> None:
    with pytest.raises(UnauthorizedBaseBranchError) as excinfo:
        assert_authorized_base_branch("develop", operation="registering pr #99")
    message = str(excinfo.value)
    assert "develop" in message
    assert "ai-dev" in message
    assert "registering pr #99" in message


def test_delegation_instruction_targets_ai_dev_only() -> None:
    instruction = delegation_instruction("TASK-1")
    assert "ai-dev" in instruction
    assert "develop" not in instruction
    assert "TASK-1" in instruction


def test_delegation_cli_emits_ai_dev_base(capsys: pytest.CaptureFixture[str]) -> None:
    import json

    from development_ops.cli import main

    assert main(["delegation", "--task-id", "TASK-7"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["base_branch"] == AUTONOMOUS_INTEGRATION_BRANCH == "ai-dev"
    assert payload["task_id"] == "TASK-7"
    assert "develop" not in json.dumps(payload)


def test_automation_entrypoint_does_not_hardcode_a_branch() -> None:
    """The entrypoint must delegate the brief to the CLI, not name a branch."""
    from pathlib import Path

    script = (
        Path(__file__).resolve().parents[4]
        / "scripts"
        / "coordinator_automation_entrypoint.sh"
    ).read_text(encoding="utf-8")
    assert "development-ops-record delegation" in script
    assert "--update-catalog" in script
    assert "from develop" not in script
    assert "PR to develop" not in script

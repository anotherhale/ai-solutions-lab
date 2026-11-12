"""Child-agent launch tests.

Payload construction is exercised directly (real code, no stub). The HTTP path
is exercised against a real local ``httpx`` transport backed by a stub handler,
so the client's request/response handling runs for real.
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from development_ops.child_agents import (
    ChildAgentLaunch,
    ChildAgentLaunchError,
    HttpChildAgentLauncher,
    build_conversation_payload,
    build_worktree_prompt,
)
from development_ops.worktrees import WorktreeSpec


def _spec(tmp_path: Path) -> WorktreeSpec:
    return WorktreeSpec(
        task_id="PHASE-C-1",
        branch_name="cursor/PHASE-C-1",
        worktree_path=tmp_path / "worktrees" / "repo" / "PHASE-C-1",
        base_ref="origin/ai-dev",
        base_sha="a" * 40,
    )


def _launch(tmp_path: Path) -> ChildAgentLaunch:
    spec = _spec(tmp_path)
    return ChildAgentLaunch(
        task_id="PHASE-C-1",
        task_title="Isolated worktrees",
        branch_name=spec.branch_name,
        worktree_path=spec.worktree_path,
        base_ref=spec.base_ref,
        prompt=build_worktree_prompt(
            spec,
            task_id="PHASE-C-1",
            task_title="Isolated worktrees",
            repository="anotherhale/ai-solutions-lab",
        ),
    )


def test_payload_points_workspace_at_worktree(tmp_path: Path) -> None:
    launch = _launch(tmp_path)
    payload = build_conversation_payload(launch, agent_settings={"llm": {}})
    assert payload["workspace"]["working_dir"] == str(launch.worktree_path)
    assert payload["workspace"]["kind"] == "LocalWorkspace"


def test_payload_disables_server_side_worktree(tmp_path: Path) -> None:
    """worktree must be false: the coordinator already created the worktree."""
    launch = _launch(tmp_path)
    payload = build_conversation_payload(launch, agent_settings={"llm": {}})
    assert payload["worktree"] is False
    assert "worktree_options" not in payload


def test_payload_runs_initial_message(tmp_path: Path) -> None:
    launch = _launch(tmp_path)
    payload = build_conversation_payload(launch, agent_settings={"llm": {}})
    assert payload["initial_message"]["run"] is True
    assert payload["secrets_encrypted"] is True


def test_payload_requires_agent_settings(tmp_path: Path) -> None:
    launch = _launch(tmp_path)
    with pytest.raises(ChildAgentLaunchError):
        build_conversation_payload(launch, agent_settings={})


def test_prompt_names_worktree_branch_and_integration_branch(tmp_path: Path) -> None:
    launch = _launch(tmp_path)
    prompt = launch.prompt
    assert str(launch.worktree_path) in prompt
    assert launch.branch_name in prompt
    assert "origin/ai-dev" in prompt
    assert "ai-dev" in prompt
    assert "main" in prompt
    assert "force-push" in prompt


def test_http_launcher_returns_conversation_id() -> None:
    credential = "test-session-value"

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/conversations"
        assert request.headers["X-Session-API-Key"] == credential
        return httpx.Response(200, json={"id": "conv-123"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    launcher = HttpChildAgentLauncher(
        base_url="http://localhost:18000", api_key=credential, client=client
    )
    assert launcher.launch({"workspace": {"working_dir": "/tmp/x"}}) == "conv-123"


def test_http_launcher_raises_on_error_status() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(422, text="bad request")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    launcher = HttpChildAgentLauncher(client=client)
    with pytest.raises(ChildAgentLaunchError):
        launcher.launch({"workspace": {}})


def test_http_launcher_raises_without_id() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"title": "no id here"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    launcher = HttpChildAgentLauncher(client=client)
    with pytest.raises(ChildAgentLaunchError):
        launcher.launch({"workspace": {}})

"""Launch child agents inside a pre-created worktree.

The OpenHands agent-server builds its own worktree only under
``/tmp/conversation-worktrees/<conversation_id>/`` and names the branch from the
conversation UUID, so it cannot be told to use a coordinator-chosen path or
branch. The supported way to run a child inside *our* worktree is to point the
conversation's workspace at that path with ``worktree=false``.

This module therefore:

1. builds the exact conversation payload the agent-server accepts, with
   ``workspace.working_dir`` set to the worktree and worktree creation disabled;
2. posts that payload to the agent-server and returns the conversation id.

Credential material is never synthesized here. The caller forwards an
``agent_settings`` mapping (encrypted secrets included) exactly as the
agent-server expects; the library only adds the worktree-specific fields.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import httpx

from development_ops.worktrees import WorktreeSpec

DEFAULT_AGENT_SERVER_URL = "http://localhost:18000"


class ChildAgentLaunchError(RuntimeError):
    """The child conversation could not be created."""


@dataclass(frozen=True, slots=True)
class ChildAgentLaunch:
    """Everything needed to start one child agent in its worktree."""

    task_id: str
    task_title: str
    branch_name: str
    worktree_path: Path
    base_ref: str
    prompt: str


def build_worktree_prompt(
    spec: WorktreeSpec,
    *,
    task_id: str,
    task_title: str,
    repository: str,
    integration_branch: str = "ai-dev",
    extra_instructions: str | None = None,
) -> str:
    """Self-contained brief for a child agent working in an isolated worktree."""
    lines = [
        "You are an autonomous development agent for a repository that uses an "
        "autonomous integration branch.",
        "",
        f"- Repository: {repository}",
        f"- Task: {task_id} — {task_title}",
        f"- Your worktree: {spec.worktree_path}",
        f"- Your branch: {spec.branch_name}",
        f"- Branch base: {spec.base_ref}",
        "",
        "Rules:",
        f"1. Work only inside {spec.worktree_path}. Do not touch any other checkout.",
        f"2. Commit on the existing branch {spec.branch_name}. Do not create a "
        "different branch and do not switch branches.",
        "3. Never force-push.",
        f"4. Open a pull request targeting {integration_branch}. Never open or "
        "merge a pull request into main.",
        "5. You may request squash auto-merge into "
        f"{integration_branch} once checks pass, but never merge directly.",
        "6. Run the repository's tests and validators before opening the pull "
        "request, and report the exact commands and results.",
        "7. If the task cannot be completed, stop and report the blocker honestly.",
    ]
    if extra_instructions:
        lines += ["", "Additional instructions:", extra_instructions]
    return "\n".join(lines)


def build_conversation_payload(
    launch: ChildAgentLaunch,
    *,
    agent_settings: dict[str, Any],
    secrets_encrypted: bool = True,
    tool_module_qualnames: dict[str, str] | None = None,
    max_iterations: int = 1000,
) -> dict[str, Any]:
    """Build a StartConversationRequest payload bound to the worktree.

    ``worktree`` is false on purpose: the coordinator already created the
    worktree, and a second server-side worktree would start from the default
    branch and defeat the isolation.
    """
    if not agent_settings:
        msg = "agent_settings is required to launch a child conversation"
        raise ChildAgentLaunchError(msg)
    payload: dict[str, Any] = {
        "agent_settings": agent_settings,
        "secrets_encrypted": secrets_encrypted,
        "workspace": {
            "kind": "LocalWorkspace",
            "working_dir": str(launch.worktree_path),
        },
        "worktree": False,
        "max_iterations": max_iterations,
        "stuck_detection": True,
        "initial_message": {
            "role": "user",
            "content": [{"type": "text", "text": launch.prompt}],
            "run": True,
        },
    }
    if tool_module_qualnames:
        payload["tool_module_qualnames"] = tool_module_qualnames
    return payload


class ChildAgentLauncher(Protocol):
    def launch(self, payload: dict[str, Any]) -> str: ...


class HttpChildAgentLauncher:
    """Create child conversations on a running agent-server over HTTP."""

    def __init__(
        self,
        *,
        base_url: str = DEFAULT_AGENT_SERVER_URL,
        api_key: str | None = None,
        timeout: float = 60.0,
        client: httpx.Client | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout
        self._client = client

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["X-Session-API-Key"] = self._api_key
        return headers

    def launch(self, payload: dict[str, Any]) -> str:
        url = f"{self._base_url}/api/conversations"
        try:
            if self._client is not None:
                response = self._client.post(url, json=payload, headers=self._headers())
            else:
                response = httpx.post(
                    url,
                    json=payload,
                    headers=self._headers(),
                    timeout=self._timeout,
                )
        except httpx.HTTPError as exc:  # pragma: no cover - network failure path
            msg = f"child conversation request failed: {exc}"
            raise ChildAgentLaunchError(msg) from exc
        if response.status_code >= 400:
            msg = (
                f"child conversation rejected ({response.status_code}): "
                f"{response.text[:500]}"
            )
            raise ChildAgentLaunchError(msg)
        try:
            body = response.json()
        except ValueError as exc:
            msg = "child conversation response was not JSON"
            raise ChildAgentLaunchError(msg) from exc
        conversation_id = body.get("id") or body.get("conversation_id")
        if not conversation_id:
            msg = f"child conversation response lacked an id: {body!r}"
            raise ChildAgentLaunchError(msg)
        return str(conversation_id)

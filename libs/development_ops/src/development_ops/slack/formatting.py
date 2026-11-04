"""Human-readable Slack message bodies for activity events."""

from __future__ import annotations

from development_ops.models import ActivityEvent


def format_slack_message(event: ActivityEvent) -> str:
    parts = [
        f"*{event.title}*",
        f"`{event.event_type.value}` · `{event.severity.value}`",
    ]
    if event.summary:
        parts.append(event.summary)
    parts.append(f"run `{event.run_id}`")
    if event.task_id:
        parts.append(f"task `{event.task_id}`")
    if event.agent_name:
        parts.append(f"agent `{event.agent_name}`")
    github = event.github
    if github.repository and github.pull_number:
        parts.append(f"PR {github.repository}#{github.pull_number}")
    elif github.repository and github.commit_sha:
        parts.append(f"{github.repository} @ `{github.commit_sha[:12]}`")
    if github.actions_run_url:
        parts.append(f"<{github.actions_run_url}|Actions run>")
    return "\n".join(parts)

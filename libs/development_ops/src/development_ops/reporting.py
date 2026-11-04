"""Summaries over persisted development activity."""

from __future__ import annotations

import uuid
from collections import Counter
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from development_ops.models import ActivityEvent
from development_ops.persistence.repository import (
    ActivityEventQuery,
    ActivityEventRepository,
)
from development_ops.taxonomy import EventSeverity, EventType


def _day_bounds(day: datetime, tz: ZoneInfo) -> tuple[datetime, datetime]:
    local = day.astimezone(tz)
    start = datetime(local.year, local.month, local.day, tzinfo=tz)
    end = start + timedelta(days=1) - timedelta(microseconds=1)
    return start.astimezone(UTC), end.astimezone(UTC)


def fetch_events(session: Session, query: ActivityEventQuery) -> list[ActivityEvent]:
    return ActivityEventRepository(session).search(query)


def _github_pr_link(event: ActivityEvent) -> str:
    repo = event.github.repository
    number = event.github.pull_number
    if not repo or not number:
        return ""
    url = f"https://github.com/{repo}/pull/{number}"
    return f" · [PR #{number}]({url})"


def render_run_summary(
    events: list[ActivityEvent],
    *,
    run_id: uuid.UUID,
    timezone: ZoneInfo,
) -> str:
    lines = [f"# Development run `{run_id}`", ""]
    if not events:
        lines.append("_No events recorded for this run._")
        lines.append("")
        lines.append("> Missing telemetry is not evidence of successful execution.")
        return "\n".join(lines)

    ordered = sorted(events, key=lambda item: item.occurred_at)
    task_ids = {event.task_id for event in ordered if event.task_id}
    agents = {event.agent_name for event in ordered if event.agent_name}
    lines.append(f"- Events: **{len(ordered)}**")
    if task_ids:
        lines.append(f"- Tasks: {', '.join(f'`{item}`' for item in sorted(task_ids))}")
    if agents:
        lines.append(f"- Agents: {', '.join(f'`{item}`' for item in sorted(agents))}")
    lines.append("")
    lines.append("## Milestones")
    for event in ordered:
        ts = event.occurred_at.astimezone(timezone).strftime("%Y-%m-%d %H:%M %Z")
        gh = _github_pr_link(event)
        if event.github.actions_run_url:
            gh += f" · [Actions]({event.github.actions_run_url})"
        status = event.slack.delivery_status.value
        lines.append(
            f"- **{ts}** `{event.event_type.value}` ({event.severity.value}) — "
            f"{event.title}{gh} · slack `{status}`"
        )
        if event.summary:
            lines.append(f"  - {event.summary}")
    return "\n".join(lines)


def run_summary(
    session: Session,
    run_id: uuid.UUID,
    *,
    timezone: ZoneInfo | None = None,
) -> str:
    tz = timezone or ZoneInfo("America/Denver")
    events = fetch_events(
        session,
        ActivityEventQuery(run_id=run_id, limit=5000),
    )
    return render_run_summary(events, run_id=run_id, timezone=tz)


def render_daily_summary(
    events: list[ActivityEvent],
    *,
    label: str,
    timezone: ZoneInfo,
) -> str:
    lines = [f"# Development activity — {label}", ""]
    if not events:
        lines.append("_No events recorded for this period._")
        lines.append("")
        lines.append("> Missing telemetry is not evidence of successful execution.")
        return "\n".join(lines)

    by_severity = Counter(event.severity.value for event in events)
    by_type = Counter(event.event_type.value for event in events)
    runs = {str(event.run_id) for event in events}

    lines.append(f"- Events: **{len(events)}**")
    lines.append(f"- Distinct runs: **{len(runs)}**")
    lines.append(f"- Timezone: `{timezone.key}`")
    lines.append("")
    lines.append("## By severity")
    for severity in EventSeverity:
        count = by_severity.get(severity.value, 0)
        if count:
            lines.append(f"- `{severity.value}`: {count}")
    lines.append("")
    lines.append("## By event type")
    for event_type in EventType:
        count = by_type.get(event_type.value, 0)
        if count:
            lines.append(f"- `{event_type.value}`: {count}")
    lines.append("")
    lines.append("## Timeline")
    for event in sorted(events, key=lambda item: item.occurred_at):
        ts = event.occurred_at.astimezone(timezone).strftime("%Y-%m-%d %H:%M %Z")
        gh = _github_pr_link(event)
        if not gh and event.github.repository and event.github.commit_sha:
            gh = f" · {event.github.repository} @ `{event.github.commit_sha[:12]}`"
        if event.github.actions_run_url:
            gh += f" · [Actions]({event.github.actions_run_url})"
        slack = ""
        if event.slack.delivery_status.value == "delivered" and event.slack.message_ts:
            slack = f" · slack `{event.slack.message_ts}`"
        lines.append(
            f"- **{ts}** `{event.event_type.value}` — {event.title}{gh}{slack}"
        )
    return "\n".join(lines)


def daily_summary(
    session: Session,
    day: datetime,
    *,
    timezone: ZoneInfo | None = None,
) -> str:
    tz = timezone or ZoneInfo("America/Denver")
    since, until = _day_bounds(day, tz)
    events = fetch_events(
        session,
        ActivityEventQuery(since=since, until=until, limit=5000),
    )
    label = since.astimezone(tz).strftime("%Y-%m-%d")
    return render_daily_summary(events, label=label, timezone=tz)


def weekly_summary(
    session: Session,
    week_start: datetime,
    *,
    timezone: ZoneInfo | None = None,
) -> str:
    tz = timezone or ZoneInfo("America/Denver")
    start_local = week_start.astimezone(tz)
    start = datetime(
        start_local.year, start_local.month, start_local.day, tzinfo=tz
    ).astimezone(UTC)
    end = (
        start.astimezone(tz) + timedelta(days=7) - timedelta(microseconds=1)
    ).astimezone(UTC)
    events = fetch_events(
        session,
        ActivityEventQuery(since=start, until=end, limit=5000),
    )
    label = (
        f"{start.astimezone(tz).strftime('%Y-%m-%d')} – "
        f"{end.astimezone(tz).strftime('%Y-%m-%d')}"
    )
    return render_daily_summary(events, label=f"week {label}", timezone=tz)

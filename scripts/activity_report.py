#!/usr/bin/env python3
"""Report development activity from development_ops.activity_events."""

from __future__ import annotations

import argparse
import os
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "libs" / "development_ops" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "libs" / "development_ops" / "src"))

from development_ops.persistence.repository import ActivityEventQuery  # noqa: E402
from development_ops.reporting import (  # noqa: E402
    daily_summary,
    fetch_events,
    render_daily_summary,
    weekly_summary,
)
from development_ops.taxonomy import EventSeverity, EventType  # noqa: E402


def _database_url() -> str:
    return os.environ.get(
        "WASATCH_DATABASE_URL",
        "postgresql+psycopg://wasatch:replace-me@localhost:5432/wasatch",
    )


def _parse_day(value: str, tz: ZoneInfo) -> datetime:
    parsed = datetime.strptime(value, "%Y-%m-%d")
    return datetime(parsed.year, parsed.month, parsed.day, tzinfo=tz).astimezone(UTC)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--timezone",
        default=os.environ.get("DEVELOPMENT_OPS_REPORT_TZ", "America/Denver"),
        help="IANA timezone for day boundaries (default: America/Denver)",
    )
    parser.add_argument("--date", help="Daily report for YYYY-MM-DD")
    parser.add_argument(
        "--week-start",
        help="Weekly report starting YYYY-MM-DD (inclusive, local timezone)",
    )
    parser.add_argument("--run-id", help="Filter by agent run UUID")
    parser.add_argument("--task-id", help="Filter by task id")
    parser.add_argument("--event-type", choices=[item.value for item in EventType])
    parser.add_argument("--severity", choices=[item.value for item in EventSeverity])
    parser.add_argument("--since", help="ISO8601 lower bound (UTC if no offset)")
    parser.add_argument("--until", help="ISO8601 upper bound")
    parser.add_argument("--limit", type=int, default=500)
    args = parser.parse_args(argv)

    tz = ZoneInfo(args.timezone)
    engine = create_engine(_database_url(), pool_pre_ping=True)
    session_factory = sessionmaker(bind=engine, autoflush=False)

    with session_factory() as session:
        if args.date:
            day = _parse_day(args.date, tz)
            print(daily_summary(session, day, timezone=tz))
            return 0
        if args.week_start:
            week_start = _parse_day(args.week_start, tz)
            print(weekly_summary(session, week_start, timezone=tz))
            return 0

        query = ActivityEventQuery(
            run_id=uuid.UUID(args.run_id) if args.run_id else None,
            task_id=args.task_id,
            event_type=EventType(args.event_type) if args.event_type else None,
            severity=EventSeverity(args.severity) if args.severity else None,
            since=datetime.fromisoformat(args.since) if args.since else None,
            until=datetime.fromisoformat(args.until) if args.until else None,
            limit=args.limit,
        )
        events = fetch_events(session, query)
        label = "filtered query"
        print(render_daily_summary(events, label=label, timezone=tz))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

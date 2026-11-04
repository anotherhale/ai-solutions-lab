"""Timestamp helpers for fixture and API mapping."""

from __future__ import annotations

from datetime import UTC, date, datetime


def parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def parse_date(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value)


def dump_datetime(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def dump_date(value: date | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()

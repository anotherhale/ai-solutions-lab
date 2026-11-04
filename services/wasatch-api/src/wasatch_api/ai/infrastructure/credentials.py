"""Decide whether an API key is usable. Placeholders are not credentials."""

from __future__ import annotations

_PLACEHOLDERS = frozenset(
    {"", "replace-me", "changeme", "example", "placeholder", "todo"}
)


def usable_api_key(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() not in _PLACEHOLDERS

"""Shared helpers for Wasatch synthetic fixture generation."""

from __future__ import annotations

import hashlib
from decimal import Decimal

TWOPLACES = Decimal("0.01")
TAX_RATE = Decimal("0.0725")


def money(value: Decimal | str | int) -> dict[str, str]:
    amount = Decimal(str(value)).quantize(TWOPLACES)
    return {"amount": f"{amount:.2f}", "currency": "USD"}


def ts(month: int, day: int, hour: int = 15, minute: int = 0) -> str:
    return f"2026-{month:02d}-{day:02d}T{hour:02d}:{minute:02d}:00Z"


def day(month: int, day_number: int) -> str:
    return f"2026-{month:02d}-{day_number:02d}"


def id_for(prefix: str, number: int) -> str:
    return f"{prefix}_{number:04d}"


def checksum(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()

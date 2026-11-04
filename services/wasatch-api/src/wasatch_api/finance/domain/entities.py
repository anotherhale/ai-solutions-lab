"""Invoice read model for the laboratory slice."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class Invoice:
    """Persisted invoice reference row. Money fields stay in fixtures only."""

    id: str
    customer_id: str
    status: str
    created_at: datetime
    updated_at: datetime

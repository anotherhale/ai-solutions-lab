"""Retrieval records for one customer's history and procedure pages."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

SUPPORT_TICKET = "support_ticket"
MESSAGE = "message"
INTERACTION = "interaction"
WORK_ORDER = "work_order"


@dataclass(frozen=True)
class HistoryPassage:
    source: str
    source_id: str
    text: str


@dataclass(frozen=True)
class ProcedurePage:
    """One synthetic procedure page. The text is untrusted input."""

    id: str
    title: str
    path: str
    text: str
    synthetic: Literal[True]


@dataclass(frozen=True)
class RetrievalResult:
    support_ticket_id: str
    customer_id: str
    history: tuple[HistoryPassage, ...]
    procedures: tuple[ProcedurePage, ...]

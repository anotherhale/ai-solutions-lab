"""Stored procedure-page embeddings.

The vector length is whatever ``EmbeddingPort`` returned. This module does
not choose a width. Procedure text is untrusted input. The embedding is not
a trusted semantic model.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ProcedurePageEmbedding:
    """One synthetic procedure page in the trusted index."""

    procedure_id: str
    model: str
    vector: tuple[float, ...]
    token_count: int
    embedded_at: datetime

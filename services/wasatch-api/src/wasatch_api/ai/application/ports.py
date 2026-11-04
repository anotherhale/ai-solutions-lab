"""Chat and embedding ports.

Use cases depend on these protocols. Vendor clients, model names, retries,
and token accounting stay in infrastructure adapters.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ChatMessage:
    role: str
    content: str


@dataclass(frozen=True)
class ChatCompletion:
    content: str
    model: str
    prompt_tokens: int
    completion_tokens: int


@dataclass(frozen=True)
class Embedding:
    vector: tuple[float, ...]
    model: str
    token_count: int


class ChatPort(Protocol):
    """Complete one chat. Tool calls are not part of this slice."""

    def complete(self, messages: Sequence[ChatMessage]) -> ChatCompletion:
        """Return the assistant text and token counts for the messages."""


class EmbeddingPort(Protocol):
    """Embed text. This slice does not write a vector column."""

    def embed(self, texts: Sequence[str]) -> tuple[Embedding, ...]:
        """Return one embedding per text, in the same order."""

"""In-process chat and embedding stand-in.

The laboratory default. It does not open a socket and does not read an API
key. The reply quotes source ids from the user message, then adds one
commitment so the approval guard can be exercised without a provider.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence

from wasatch_api.ai.application.ports import (
    ChatCompletion,
    ChatMessage,
    Embedding,
)

_SOURCE_ID = re.compile(r"\b(?:msg|tkt|ixn|wo|proc)_\d+\b")
_VECTOR_WIDTH = 8


class FakeModelPort:
    """Deterministic chat and embedding port for tests and local runs."""

    chat_model = "fake-chat"
    embedding_model = "fake-embedding"

    def complete(self, messages: Sequence[ChatMessage]) -> ChatCompletion:
        user = ""
        for message in messages:
            if message.role == "user":
                user = message.content
        source_ids = list(dict.fromkeys(_SOURCE_ID.findall(user)))
        cited = ", ".join(source_ids) if source_ids else "none"
        excerpt = _excerpt(user)
        content = (
            f"Sources: {cited}. {excerpt} "
            "We will send a technician on Thursday at 08:00."
        ).strip()
        return ChatCompletion(
            content=content,
            model=self.chat_model,
            prompt_tokens=len(user.split()),
            completion_tokens=len(content.split()),
        )

    def embed(self, texts: Sequence[str]) -> tuple[Embedding, ...]:
        return tuple(
            Embedding(
                vector=_vector(text),
                model=self.embedding_model,
                token_count=len(text.split()),
            )
            for text in texts
        )


def _excerpt(user: str) -> str:
    lines = [line.strip() for line in user.splitlines() if _SOURCE_ID.search(line)]
    text = " ".join(lines)
    if len(text) <= 1200:
        return text
    return text[:1200].rstrip()


def _vector(text: str) -> tuple[float, ...]:
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    return tuple((byte - 128) / 128 for byte in digest[:_VECTOR_WIDTH])

"""OpenAI adapter for the chat and embedding ports.

The SDK client is created on the first call. Importing this module does not
contact the network. Model names, retries, and token counts stay here.
"""

from __future__ import annotations

from collections.abc import Sequence

from wasatch_api.ai.application.ports import (
    ChatCompletion,
    ChatMessage,
    Embedding,
)
from wasatch_api.ai.infrastructure.credentials import usable_api_key
from wasatch_api.shared.errors import ProviderConfigurationError


class OpenAIProvider:
    """Chat and embeddings through the OpenAI API."""

    def __init__(self, *, api_key: str, chat_model: str, embedding_model: str) -> None:
        if not usable_api_key(api_key):
            raise ProviderConfigurationError(
                "OPENAI_API_KEY is missing or still a placeholder. "
                "The OpenAI adapter does not call the network without a key."
            )
        self._api_key = api_key
        self._chat_model = chat_model
        self._embedding_model = embedding_model
        self._sdk = None

    def complete(self, messages: Sequence[ChatMessage]) -> ChatCompletion:
        response = self._client().chat.completions.create(
            model=self._chat_model,
            messages=[
                {"role": message.role, "content": message.content}
                for message in messages
            ],
        )
        content = ""
        if response.choices:
            content = response.choices[0].message.content or ""
        usage = response.usage
        model = getattr(response, "model", None) or self._chat_model
        return ChatCompletion(
            content=content,
            model=model,
            prompt_tokens=_usage_count(usage, "prompt_tokens", "input_tokens"),
            completion_tokens=_usage_count(usage, "completion_tokens", "output_tokens"),
        )

    def embed(self, texts: Sequence[str]) -> tuple[Embedding, ...]:
        if not texts:
            return ()
        # The SDK treats an omitted encoding as base64. Ask for floats so the
        # vector is numeric and is not written anywhere by this adapter.
        response = self._client().embeddings.create(
            model=self._embedding_model,
            input=list(texts),
            encoding_format="float",
        )
        ordered = sorted(response.data, key=lambda item: item.index)
        model = getattr(response, "model", None) or self._embedding_model
        total = _usage_count(response.usage, "total_tokens", "prompt_tokens")
        return tuple(
            Embedding(
                vector=tuple(float(value) for value in item.embedding),
                model=model,
                token_count=total if index == 0 else 0,
            )
            for index, item in enumerate(ordered)
        )

    def _client(self):
        if self._sdk is None:
            from openai import OpenAI

            self._sdk = OpenAI(api_key=self._api_key, max_retries=2, timeout=30.0)
        return self._sdk


def _usage_count(usage: object, *names: str) -> int:
    if usage is None:
        return 0
    for name in names:
        value = getattr(usage, name, None)
        if isinstance(value, int):
            return value
    return 0

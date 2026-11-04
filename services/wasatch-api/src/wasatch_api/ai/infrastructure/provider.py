"""Select the chat and embedding adapter from configuration."""

from __future__ import annotations

from wasatch_api.ai.application.ports import ChatPort
from wasatch_api.ai.infrastructure.credentials import usable_api_key
from wasatch_api.ai.infrastructure.fake import FakeModelPort
from wasatch_api.config import Settings
from wasatch_api.shared.errors import ProviderConfigurationError


def build_model_provider(settings: Settings) -> ChatPort:
    """Return the configured provider.

    ``fake`` is the default. It does not read an API key. ``openai`` is
    constructed only when a non-placeholder key is present, and the SDK
    import waits until that branch.
    """

    selected = settings.ai_provider.strip().lower() or "fake"
    if selected == "fake":
        return FakeModelPort()
    if selected == "openai":
        if not usable_api_key(settings.openai_api_key):
            raise ProviderConfigurationError(
                "AI_PROVIDER=openai requires OPENAI_API_KEY from the "
                "environment. The placeholder replace-me is not a credential. "
                "Tests and CI keep the fake provider and do not call the network."
            )
        from wasatch_api.ai.infrastructure.openai_provider import OpenAIProvider

        return OpenAIProvider(
            api_key=settings.openai_api_key.strip(),
            chat_model=settings.openai_model,
            embedding_model=settings.openai_embedding_model,
        )
    raise ProviderConfigurationError(f"unsupported AI provider: {settings.ai_provider}")

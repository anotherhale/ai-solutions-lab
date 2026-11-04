"""Provider selection stays off the network unless OpenAI is configured."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from wasatch_api.ai.application.ports import ChatMessage
from wasatch_api.ai.infrastructure.fake import FakeModelPort
from wasatch_api.ai.infrastructure.openai_provider import OpenAIProvider
from wasatch_api.ai.infrastructure.provider import build_model_provider
from wasatch_api.config import get_settings
from wasatch_api.shared.errors import ProviderConfigurationError

PACKAGE = Path(__file__).resolve().parents[2] / "src" / "wasatch_api"
ADAPTER = PACKAGE / "ai" / "infrastructure" / "openai_provider.py"
BANNED = {"openai", "httpx", "urllib", "requests", "anthropic", "socket"}


def test_default_provider_is_the_fake_and_does_not_need_a_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AI_PROVIDER", "fake")
    monkeypatch.setenv("OPENAI_API_KEY", "replace-me")
    get_settings.cache_clear()
    provider = build_model_provider(get_settings())
    assert isinstance(provider, FakeModelPort)
    completion = provider.complete(
        (ChatMessage(role="user", content="message msg_0015: Rooftop unit is down."),)
    )
    assert completion.model == "fake-chat"
    assert "msg_0015" in completion.content
    assert "rooftop" in completion.content.lower()
    assert "08:00" in completion.content
    embedded = provider.embed(("Rooftop unit is down.",))
    assert len(embedded) == 1
    assert embedded[0].model == "fake-embedding"
    assert len(embedded[0].vector) == 8
    assert provider.embed(("Rooftop unit is down.",))[0].vector == embedded[0].vector
    assert provider.embed(("boiler lockout",))[0].vector != embedded[0].vector
    assert provider.embed(()) == ()
    get_settings.cache_clear()


def test_openai_without_a_usable_key_is_rejected_before_the_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import openai

    def _reject_client(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("OpenAI client constructed")

    monkeypatch.setattr(openai, "OpenAI", _reject_client)
    monkeypatch.setenv("AI_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "replace-me")
    get_settings.cache_clear()
    with pytest.raises(ProviderConfigurationError, match="OPENAI_API_KEY"):
        build_model_provider(get_settings())
    with pytest.raises(ProviderConfigurationError, match="placeholder"):
        OpenAIProvider(
            api_key="replace-me",
            chat_model="gpt-4o-mini",
            embedding_model="text-embedding-3-small",
        )
    get_settings.cache_clear()


def test_unknown_provider_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_PROVIDER", "local-llm")
    get_settings.cache_clear()
    with pytest.raises(ProviderConfigurationError, match="unsupported AI provider"):
        build_model_provider(get_settings())
    get_settings.cache_clear()


def test_openai_sdk_imports_without_calling_the_api() -> None:
    import openai

    assert isinstance(openai.__version__, str)


def test_only_the_openai_adapter_imports_the_provider_sdk() -> None:
    assert "openai" in _imported_modules(ADAPTER)
    offenders: list[str] = []
    for path in PACKAGE.rglob("*.py"):
        if path.resolve() == ADAPTER.resolve():
            continue
        imported = _imported_modules(path)
        if imported & BANNED:
            offenders.append(f"{path.name}: {sorted(imported & BANNED)}")
    assert offenders == []


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".", 1)[0])
    return imported

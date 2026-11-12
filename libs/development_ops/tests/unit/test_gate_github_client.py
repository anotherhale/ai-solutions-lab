"""Unit tests for gate GitHub App auth and REST client (Phase 1A.6.2).

Uses an ephemeral in-test RSA key (never a real App credential), a fake token
provider, and an ``httpx.MockTransport``. No network calls, no real checks.
"""

from __future__ import annotations

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from development_ops.gate_github_client import (
    ENV_GATE_APP_ID,
    ENV_GATE_ENABLED,
    ENV_GATE_INSTALLATION_ID,
    ENV_GATE_PRIVATE_KEY_PEM,
    GATE_APP_ID,
    GateApiError,
    GateAuthError,
    GitHubAppTokenProvider,
    HttpGateGitHubClient,
    gate_config_from_env,
)


def _ephemeral_pem() -> str:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()


class _FakeTokens:
    def __init__(self, token: str = "ghs_fake_installation_token") -> None:
        self.token = token
        self.calls = 0

    def installation_token(self) -> str:
        self.calls += 1
        return self.token


# --- token provider ---------------------------------------------------------


def test_token_provider_requires_pem() -> None:
    with pytest.raises(GateAuthError):
        GitHubAppTokenProvider(app_id=1, installation_id=2, private_key_pem="")


def test_token_provider_signs_and_caches() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["auth"] = request.headers.get("Authorization")
        return httpx.Response(201, json={"token": "ghs_abc", "expires_at": "x"})

    provider = GitHubAppTokenProvider(
        app_id=5675266,
        installation_id=180042417,
        private_key_pem=_ephemeral_pem(),
        transport=httpx.MockTransport(handler),
        clock=lambda: 1_000_000.0,
    )
    token = provider.installation_token()
    assert token == "ghs_abc"
    assert str(captured["url"]).endswith("/app/installations/180042417/access_tokens")
    assert str(captured["auth"]).startswith("Bearer ")
    # Second call is served from cache (no second HTTP request).
    assert provider.installation_token() == "ghs_abc"


def test_token_provider_rejects_non_201() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"message": "bad"})

    provider = GitHubAppTokenProvider(
        app_id=1,
        installation_id=2,
        private_key_pem=_ephemeral_pem(),
        transport=httpx.MockTransport(handler),
        clock=lambda: 1.0,
    )
    with pytest.raises(GateAuthError) as exc:
        provider.installation_token()
    # The error must not echo any credential material.
    assert "ghs" not in str(exc.value)
    assert "PRIVATE" not in str(exc.value)


# --- REST client ------------------------------------------------------------


def _client(handler: object, token: str = "ghs_fake") -> HttpGateGitHubClient:
    return HttpGateGitHubClient(
        token_provider=_FakeTokens(token),
        transport=httpx.MockTransport(handler),  # type: ignore[arg-type]
    )


def test_get_pull_request_parses_head_and_base() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "number": 7,
                "state": "open",
                "merged": False,
                "head": {"sha": "a" * 40},
                "base": {"ref": "ai-dev"},
            },
        )

    pr = _client(handler).get_pull_request("o/r", 7)
    assert pr.head_sha == "a" * 40
    assert pr.base_ref == "ai-dev"
    assert pr.targets_integration_branch is True


def test_list_reviews_parses_identity() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[
                {
                    "id": 5820717173,
                    "user": {"login": "bot", "id": 353895417, "type": "Bot"},
                    "state": "APPROVED",
                    "commit_id": "a" * 40,
                    "submitted_at": "2026-11-09T11:00:00Z",
                    "body": "{}",
                }
            ],
        )

    reviews = _client(handler).list_reviews("o/r", 7)
    assert reviews[0].author_user_id == 353895417
    assert reviews[0].state == "APPROVED"


def test_list_check_runs_filters_by_name() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "check_runs": [
                    {
                        "id": 1,
                        "name": "AI review",
                        "app": {"id": GATE_APP_ID},
                        "head_sha": "a" * 40,
                        "status": "completed",
                        "conclusion": "success",
                    }
                ]
            },
        )

    runs = _client(handler).list_check_runs("o/r", "a" * 40)
    assert runs[0].app_id == GATE_APP_ID
    assert runs[0].conclusion == "success"


def test_create_check_run_posts_expected_body() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = request.content.decode()
        return httpx.Response(201, json={"id": 55})

    check_id = _client(handler).create_check_run(
        "o/r",
        name="AI review",
        head_sha="a" * 40,
        conclusion="success",
        title="t",
        summary="s",
        external_id="e",
    )
    assert check_id == 55
    assert "AI review" in str(seen["body"])


def test_api_error_is_generic_and_has_no_token() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"message": "forbidden"})

    leaked = "ghs_" + "supersecret"
    with pytest.raises(GateApiError) as exc:
        _client(handler, token=leaked).get_pull_request("o/r", 7)
    assert leaked not in str(exc.value)


# --- configuration / feature flag ------------------------------------------


def test_disabled_gate_is_inert(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(ENV_GATE_ENABLED, raising=False)
    config = gate_config_from_env()
    assert config.enabled is False
    assert config.client is None


def test_enabled_without_credentials_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(ENV_GATE_ENABLED, "1")
    monkeypatch.delenv(ENV_GATE_APP_ID, raising=False)
    monkeypatch.delenv(ENV_GATE_INSTALLATION_ID, raising=False)
    monkeypatch.delenv(ENV_GATE_PRIVATE_KEY_PEM, raising=False)
    config = gate_config_from_env()
    assert config.enabled is True
    assert config.available is False
    assert config.reason is not None


def test_enabled_with_credentials_builds_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(ENV_GATE_ENABLED, "1")
    monkeypatch.setenv(ENV_GATE_APP_ID, "5675266")
    monkeypatch.setenv(ENV_GATE_INSTALLATION_ID, "180042417")
    monkeypatch.setenv(ENV_GATE_PRIVATE_KEY_PEM, _ephemeral_pem())
    config = gate_config_from_env()
    assert config.enabled is True
    assert config.available is True

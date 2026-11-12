"""GitHub App authentication and REST client for the AI review gate.

This module is the gate's *own* least-privilege GitHub access. It is deliberately
separate from :mod:`development_ops.github_client` (which shells out to the ``gh``
CLI for the coordinator's PR/auto-merge work): the gate authenticates as its own
GitHub App installation, so it must never borrow the builder's or reviewer's
identity.

Design constraints (Phase 1A.6.1 contract, AEE-ADR-009 Amendment 1):

* **Lazy authentication.** No JWT is signed and no installation token is fetched
  until a gate call is actually made. A disabled gate never touches credentials.
* **Fail closed.** When the gate is enabled but credentials are missing or
  invalid, construction raises :class:`GateAuthError`; callers treat that as
  "enabled but unavailable" and must refuse auto-merge.
* **No secret disclosure.** Private keys, JWTs and installation tokens are never
  logged, embedded in exception messages, or returned to callers. Errors carry a
  generic reason only.
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol

import httpx

GITHUB_API_BASE = "https://api.github.com"
GITHUB_API_VERSION = "2022-11-28"

# The required check the gate publishes. Must match the ruleset's context name.
AI_REVIEW_CHECK_NAME = "AI review"

# The gate App identity. The coordinator binds the required check to this App.
GATE_APP_ID = 5675266

# The reviewer App's bot identity. The gate authenticates the review author
# against this, not against any field inside the verdict payload.
REVIEWER_BOT_LOGIN = "everyones-heroes-reviewer[bot]"
REVIEWER_BOT_USER_ID = 353895417

# Approved policy values (Phase 1A.6.1.2).
DEFAULT_MAX_VERDICT_AGE_SECONDS = 24 * 60 * 60
DEFAULT_POLICY_VERSIONS = frozenset({"1"})

ENV_GATE_ENABLED = "DEVELOPMENT_OPS_GATE_ENABLED"
ENV_GATE_APP_ID = "DEVELOPMENT_OPS_GATE_APP_ID"
ENV_GATE_INSTALLATION_ID = "DEVELOPMENT_OPS_GATE_INSTALLATION_ID"
ENV_GATE_PRIVATE_KEY_PATH = "DEVELOPMENT_OPS_GATE_PRIVATE_KEY_PATH"
ENV_GATE_PRIVATE_KEY_PEM = "DEVELOPMENT_OPS_GATE_PRIVATE_KEY_PEM"
ENV_REVIEWER_BOT_LOGIN = "DEVELOPMENT_OPS_REVIEWER_BOT_LOGIN"
ENV_REVIEWER_BOT_USER_ID = "DEVELOPMENT_OPS_REVIEWER_BOT_USER_ID"
ENV_MAX_VERDICT_AGE_SECONDS = "DEVELOPMENT_OPS_GATE_MAX_VERDICT_AGE_SECONDS"
ENV_POLICY_VERSIONS = "DEVELOPMENT_OPS_GATE_POLICY_VERSIONS"

# Installation tokens live ~1 hour; refresh early to avoid edge expiry.
_TOKEN_REFRESH_MARGIN_SECONDS = 120


class GateAuthError(RuntimeError):
    """Gate credentials are missing, unreadable, or rejected by GitHub."""


class GateApiError(RuntimeError):
    """A gate GitHub API call failed. The message never contains credentials."""


@dataclass(frozen=True, slots=True)
class PullRequestSnapshot:
    """Minimal live PR view used for base-branch and head-SHA checks."""

    number: int
    base_ref: str
    head_sha: str
    state: str
    merged: bool

    @property
    def targets_integration_branch(self) -> bool:
        return self.base_ref == "ai-dev"


@dataclass(frozen=True, slots=True)
class ReviewRecord:
    """A canonical GitHub PR review, as returned by the Reviews API."""

    review_id: int
    author_login: str
    author_user_id: int
    author_type: str
    state: str
    commit_id: str
    submitted_at: str
    body: str


@dataclass(frozen=True, slots=True)
class CheckRunRecord:
    """A check run on a commit ref."""

    check_run_id: int
    name: str
    app_id: int
    head_sha: str
    status: str
    conclusion: str | None


class TokenProvider(Protocol):
    """Supplies a GitHub App installation token on demand."""

    def installation_token(self) -> str: ...


class GateGitHubClient(Protocol):
    """The gate's GitHub surface. Tests inject a stub of this protocol."""

    def get_pull_request(self, repository: str, number: int) -> PullRequestSnapshot: ...

    def list_reviews(self, repository: str, number: int) -> list[ReviewRecord]: ...

    def list_check_runs(self, repository: str, ref: str) -> list[CheckRunRecord]: ...

    def create_check_run(
        self,
        repository: str,
        *,
        name: str,
        head_sha: str,
        conclusion: str,
        title: str,
        summary: str,
        external_id: str,
    ) -> int: ...

    def update_check_run(
        self,
        repository: str,
        *,
        check_run_id: int,
        conclusion: str,
        title: str,
        summary: str,
    ) -> None: ...


class GitHubAppTokenProvider:
    """RS256 GitHub App JWT → installation token, with lazy caching.

    The private key is held in memory only. Nothing about it is ever logged.
    """

    def __init__(
        self,
        *,
        app_id: int,
        installation_id: int,
        private_key_pem: str,
        base_url: str = GITHUB_API_BASE,
        transport: httpx.BaseTransport | None = None,
        timeout: float = 30.0,
        clock: Callable[[], float] = time.time,
    ) -> None:
        if not private_key_pem or "PRIVATE KEY" not in private_key_pem:
            raise GateAuthError("gate private key is missing or not a PEM key")
        self._app_id = app_id
        self._installation_id = installation_id
        self._private_key_pem = private_key_pem
        self._base_url = base_url.rstrip("/")
        self._transport = transport
        self._timeout = timeout
        self._clock = clock
        self._cached: tuple[str, float] | None = None

    def _sign_jwt(self) -> str:
        import jwt  # imported lazily so a disabled gate needs no crypto

        now = int(self._clock())
        payload = {"iat": now - 60, "exp": now + 540, "iss": str(self._app_id)}
        try:
            return jwt.encode(payload, self._private_key_pem, algorithm="RS256")
        except Exception as exc:  # noqa: BLE001 - never leak key material
            raise GateAuthError("failed to sign gate App JWT") from exc

    def installation_token(self) -> str:
        now = self._clock()
        if self._cached is not None:
            token, expires_at = self._cached
            if now < expires_at - _TOKEN_REFRESH_MARGIN_SECONDS:
                return token
        assertion = self._sign_jwt()
        url = (
            f"{self._base_url}/app/installations/{self._installation_id}/access_tokens"
        )
        try:
            with httpx.Client(
                timeout=self._timeout, transport=self._transport
            ) as client:
                response = client.post(
                    url,
                    headers={
                        "Authorization": f"Bearer {assertion}",
                        "Accept": "application/vnd.github+json",
                        "X-GitHub-Api-Version": GITHUB_API_VERSION,
                    },
                )
        except httpx.HTTPError as exc:
            raise GateAuthError("gate installation-token request failed") from exc
        if response.status_code != 201:
            raise GateAuthError(
                f"gate installation-token request rejected "
                f"(status {response.status_code})"
            )
        try:
            body = response.json()
            token = str(body["token"])
        except (KeyError, ValueError) as exc:
            raise GateAuthError(
                "gate installation-token response was malformed"
            ) from exc
        # Refresh well before the real expiry.
        expires_at = now + 55 * 60
        self._cached = (token, expires_at)
        return token


class HttpGateGitHubClient:
    """REST client authenticated as the gate App installation."""

    def __init__(
        self,
        *,
        token_provider: TokenProvider,
        base_url: str = GITHUB_API_BASE,
        transport: httpx.BaseTransport | None = None,
        timeout: float = 30.0,
        page_size: int = 100,
    ) -> None:
        self._tokens = token_provider
        self._base_url = base_url.rstrip("/")
        self._transport = transport
        self._timeout = timeout
        self._page_size = page_size

    def _request(
        self, method: str, path: str, *, json: dict[str, Any] | None = None
    ) -> Any:
        headers = {
            "Authorization": f"Bearer {self._tokens.installation_token()}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": GITHUB_API_VERSION,
        }
        try:
            with httpx.Client(
                timeout=self._timeout, transport=self._transport
            ) as client:
                response = client.request(
                    method, f"{self._base_url}{path}", headers=headers, json=json
                )
        except httpx.HTTPError as exc:
            raise GateApiError("gate GitHub request failed") from exc
        if response.status_code >= 400:
            # Never include the response body: it may echo request context.
            raise GateApiError(
                f"gate GitHub request failed (status {response.status_code})"
            )
        if not response.content:
            return None
        try:
            return response.json()
        except ValueError as exc:
            raise GateApiError("gate GitHub response was not JSON") from exc

    def get_pull_request(self, repository: str, number: int) -> PullRequestSnapshot:
        payload = self._request("GET", f"/repos/{repository}/pulls/{number}")
        head = payload.get("head") or {}
        base = payload.get("base") or {}
        state = str(payload.get("state") or "unknown")
        return PullRequestSnapshot(
            number=int(payload.get("number") or number),
            base_ref=str(base.get("ref") or ""),
            head_sha=str(head.get("sha") or ""),
            state=state,
            merged=bool(payload.get("merged")) or state == "closed",
        )

    def list_reviews(self, repository: str, number: int) -> list[ReviewRecord]:
        payload = self._request(
            "GET",
            f"/repos/{repository}/pulls/{number}/reviews?per_page={self._page_size}",
        )
        records: list[ReviewRecord] = []
        for item in payload or []:
            user = item.get("user") or {}
            records.append(
                ReviewRecord(
                    review_id=int(item["id"]),
                    author_login=str(user.get("login") or ""),
                    author_user_id=int(user.get("id") or 0),
                    author_type=str(user.get("type") or ""),
                    state=str(item.get("state") or ""),
                    commit_id=str(item.get("commit_id") or ""),
                    submitted_at=str(item.get("submitted_at") or ""),
                    body=str(item.get("body") or ""),
                )
            )
        return records

    def list_check_runs(self, repository: str, ref: str) -> list[CheckRunRecord]:
        payload = self._request(
            "GET",
            f"/repos/{repository}/commits/{ref}/check-runs"
            f"?check_name={AI_REVIEW_CHECK_NAME}&per_page={self._page_size}",
        )
        runs: list[CheckRunRecord] = []
        for item in (payload or {}).get("check_runs", []):
            app = item.get("app") or {}
            runs.append(
                CheckRunRecord(
                    check_run_id=int(item["id"]),
                    name=str(item.get("name") or ""),
                    app_id=int(app.get("id") or 0),
                    head_sha=str(item.get("head_sha") or ""),
                    status=str(item.get("status") or ""),
                    conclusion=item.get("conclusion"),
                )
            )
        return runs

    def create_check_run(
        self,
        repository: str,
        *,
        name: str,
        head_sha: str,
        conclusion: str,
        title: str,
        summary: str,
        external_id: str,
    ) -> int:
        payload = self._request(
            "POST",
            f"/repos/{repository}/check-runs",
            json={
                "name": name,
                "head_sha": head_sha,
                "status": "completed",
                "conclusion": conclusion,
                "external_id": external_id,
                "output": {"title": title, "summary": summary},
            },
        )
        return int(payload["id"])

    def update_check_run(
        self,
        repository: str,
        *,
        check_run_id: int,
        conclusion: str,
        title: str,
        summary: str,
    ) -> None:
        self._request(
            "PATCH",
            f"/repos/{repository}/check-runs/{check_run_id}",
            json={
                "status": "completed",
                "conclusion": conclusion,
                "output": {"title": title, "summary": summary},
            },
        )


@dataclass(frozen=True, slots=True)
class GateConfig:
    """Resolved gate configuration.

    ``enabled`` distinguishes "operator turned the gate on" from the credential
    situation. ``client`` is ``None`` only when the gate is disabled or when it
    is enabled but unavailable (``reason`` then explains, generically, why).
    """

    enabled: bool
    client: GateGitHubClient | None
    reason: str | None = None
    reviewer_login: str = REVIEWER_BOT_LOGIN
    reviewer_user_id: int = REVIEWER_BOT_USER_ID
    max_verdict_age_seconds: int = DEFAULT_MAX_VERDICT_AGE_SECONDS
    policy_versions: frozenset[str] = field(default=DEFAULT_POLICY_VERSIONS)

    @property
    def available(self) -> bool:
        return self.client is not None


def _read_private_key() -> str | None:
    inline = os.environ.get(ENV_GATE_PRIVATE_KEY_PEM, "").strip()
    if inline:
        return inline
    path = os.environ.get(ENV_GATE_PRIVATE_KEY_PATH, "").strip()
    if not path:
        return None
    try:
        from pathlib import Path

        return Path(path).read_text(encoding="utf-8")
    except OSError:
        return None


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _policy_versions_from_env() -> frozenset[str]:
    raw = os.environ.get(ENV_POLICY_VERSIONS, "").strip()
    if not raw:
        return DEFAULT_POLICY_VERSIONS
    return frozenset(part.strip() for part in raw.split(",") if part.strip())


def gate_config_from_env(
    *,
    transport: httpx.BaseTransport | None = None,
    token_provider: TokenProvider | None = None,
) -> GateConfig:
    """Resolve gate configuration from the environment.

    Disabled (default) returns an inert config. Enabled resolves the App
    credentials and builds the client; if credentials are missing or invalid it
    returns an *enabled but unavailable* config so callers fail closed.
    """
    enabled = os.environ.get(ENV_GATE_ENABLED, "0").strip() == "1"
    common = {
        "reviewer_login": os.environ.get(ENV_REVIEWER_BOT_LOGIN, "").strip()
        or REVIEWER_BOT_LOGIN,
        "reviewer_user_id": _int_env(ENV_REVIEWER_BOT_USER_ID, REVIEWER_BOT_USER_ID),
        "max_verdict_age_seconds": _int_env(
            ENV_MAX_VERDICT_AGE_SECONDS, DEFAULT_MAX_VERDICT_AGE_SECONDS
        ),
        "policy_versions": _policy_versions_from_env(),
    }
    if not enabled:
        return GateConfig(enabled=False, client=None, **common)

    if token_provider is None:
        app_id = _int_env(ENV_GATE_APP_ID, 0)
        installation_id = _int_env(ENV_GATE_INSTALLATION_ID, 0)
        private_key = _read_private_key()
        if app_id <= 0 or installation_id <= 0 or not private_key:
            return GateConfig(
                enabled=True,
                client=None,
                reason="gate enabled but App credentials are not configured",
                **common,
            )
        token_provider = GitHubAppTokenProvider(
            app_id=app_id,
            installation_id=installation_id,
            private_key_pem=private_key,
            transport=transport,
        )
    client = HttpGateGitHubClient(token_provider=token_provider, transport=transport)
    return GateConfig(enabled=True, client=client, **common)


def _parse_github_timestamp(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return None

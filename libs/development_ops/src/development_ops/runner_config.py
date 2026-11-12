"""Configuration for the persistent coordinator runner.

Values come from the environment, matching the existing development-ops
convention. Defaults are safe for a single-workstation laboratory host; every
field is validated so a typo fails fast at startup instead of mid-run.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from development_ops.persistence.coordinator_repository import DEFAULT_LEASE_SECONDS

DEFAULT_POLL_SECONDS = 30.0
DEFAULT_HEARTBEAT_SECONDS = 300.0
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_LOG_FORMAT = "json"
_VALID_LOG_LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})
_VALID_LOG_FORMATS = frozenset({"json", "text"})


class RunnerConfigError(ValueError):
    """Raised when runner configuration is missing or invalid."""


def default_state_dir() -> Path:
    """Directory for the instance lock and runner state.

    Kept under the user's state area so it survives restarts and is not part of
    the checkout. Override with ``DEVELOPMENT_OPS_RUNNER_STATE_DIR``.
    """
    override = os.environ.get("DEVELOPMENT_OPS_RUNNER_STATE_DIR", "").strip()
    if override:
        return Path(override).expanduser()
    return Path.home() / ".local" / "state" / "ai-solutions-lab" / "coordinator"


def _bool_env(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip() not in {"0", "false", "False", "no", "off"}


def _float_env(name: str, default: float) -> float:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError as exc:
        msg = f"{name} must be a number, got {raw!r}"
        raise RunnerConfigError(msg) from exc


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        msg = f"{name} must be an integer, got {raw!r}"
        raise RunnerConfigError(msg) from exc


@dataclass(frozen=True, slots=True)
class RunnerConfig:
    """Validated, immutable runner configuration."""

    repository: str
    poll_interval_seconds: float = DEFAULT_POLL_SECONDS
    heartbeat_interval_seconds: float = DEFAULT_HEARTBEAT_SECONDS
    lease_seconds: int = DEFAULT_LEASE_SECONDS
    recover_on_startup: bool = True
    reclaim_expired_leases: bool = True
    state_dir: Path = Path()
    lock_path: Path | None = None
    log_level: str = DEFAULT_LOG_LEVEL
    log_format: str = DEFAULT_LOG_FORMAT
    backlog_path: Path | None = None
    update_catalog: bool = False

    def __post_init__(self) -> None:
        if not self.repository.strip():
            raise RunnerConfigError("repository must not be blank")
        if self.poll_interval_seconds <= 0:
            raise RunnerConfigError("poll_interval_seconds must be positive")
        if self.heartbeat_interval_seconds <= 0:
            raise RunnerConfigError("heartbeat_interval_seconds must be positive")
        if self.lease_seconds <= 0:
            raise RunnerConfigError("lease_seconds must be positive")
        if self.heartbeat_interval_seconds > self.lease_seconds:
            raise RunnerConfigError(
                "heartbeat_interval_seconds must not exceed lease_seconds, "
                "or a live task's lease would expire between heartbeats"
            )
        level = self.log_level.upper()
        if level not in _VALID_LOG_LEVELS:
            raise RunnerConfigError(
                f"log_level must be one of {sorted(_VALID_LOG_LEVELS)}"
            )
        if self.log_format.lower() not in _VALID_LOG_FORMATS:
            raise RunnerConfigError(
                f"log_format must be one of {sorted(_VALID_LOG_FORMATS)}"
            )
        object.__setattr__(self, "log_level", level)
        object.__setattr__(self, "log_format", self.log_format.lower())

    @property
    def resolved_lock_path(self) -> Path:
        if self.lock_path is not None:
            return Path(self.lock_path).expanduser()
        return self.state_dir / "coordinator.lock"

    @classmethod
    def from_env(cls, *, repository: str | None = None) -> RunnerConfig:
        state_dir = default_state_dir()
        lock_override = os.environ.get("DEVELOPMENT_OPS_RUNNER_LOCK_PATH", "").strip()
        backlog_override = os.environ.get("DEVELOPMENT_OPS_BACKLOG_PATH", "").strip()
        resolved_repository = (
            repository
            or os.environ.get("DEVELOPMENT_OPS_GITHUB_REPOSITORY", "").strip()
            or "anotherhale/ai-solutions-lab"
        )
        return cls(
            repository=resolved_repository,
            poll_interval_seconds=_float_env(
                "DEVELOPMENT_OPS_RUNNER_POLL_SECONDS", DEFAULT_POLL_SECONDS
            ),
            heartbeat_interval_seconds=_float_env(
                "DEVELOPMENT_OPS_RUNNER_HEARTBEAT_SECONDS", DEFAULT_HEARTBEAT_SECONDS
            ),
            lease_seconds=_int_env(
                "DEVELOPMENT_OPS_LEASE_SECONDS", DEFAULT_LEASE_SECONDS
            ),
            recover_on_startup=_bool_env("DEVELOPMENT_OPS_RUNNER_RECOVER", True),
            reclaim_expired_leases=_bool_env("DEVELOPMENT_OPS_RUNNER_RECLAIM", True),
            state_dir=state_dir,
            lock_path=Path(lock_override) if lock_override else None,
            log_level=os.environ.get(
                "DEVELOPMENT_OPS_RUNNER_LOG_LEVEL", DEFAULT_LOG_LEVEL
            ),
            log_format=os.environ.get(
                "DEVELOPMENT_OPS_RUNNER_LOG_FORMAT", DEFAULT_LOG_FORMAT
            ),
            backlog_path=Path(backlog_override) if backlog_override else None,
            update_catalog=_bool_env("DEVELOPMENT_OPS_UPDATE_CATALOG", False),
        )

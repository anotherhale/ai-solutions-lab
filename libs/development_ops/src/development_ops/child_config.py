"""Child-agent execution configuration and concurrency policy.

Phase D bounds concurrent child-agent execution. The hard default is two, the
configurable maximum may not exceed a hard ceiling of two in this phase, and
live child execution is **disabled by default**: it requires an explicit,
durable operator enablement and can never be switched on by an environment
variable alone.

All values come from the environment, matching the development-ops convention.
Every field is validated so a typo fails fast at startup rather than launching a
child with the wrong limit.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

# Absolute ceiling for this phase. Raising it requires a later ADR and code
# change, not a configuration edit.
HARD_MAX_CONCURRENT_CHILDREN = 2
DEFAULT_MAX_CONCURRENT_CHILDREN = 2
DEFAULT_CHILD_HEARTBEAT_SECONDS = 300.0
DEFAULT_CHILD_STALL_SECONDS = 1800.0
DEFAULT_LAUNCH_TIMEOUT_SECONDS = 60.0
DEFAULT_CHILD_MAX_ATTEMPTS = 3


class ChildOrchestrationConfigError(ValueError):
    """Raised when child-orchestration configuration is invalid."""


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
        raise ChildOrchestrationConfigError(msg) from exc


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        msg = f"{name} must be an integer, got {raw!r}"
        raise ChildOrchestrationConfigError(msg) from exc


@dataclass(frozen=True, slots=True)
class ChildOrchestrationConfig:
    """Validated, immutable child-orchestration configuration."""

    max_concurrent_children: int = DEFAULT_MAX_CONCURRENT_CHILDREN
    heartbeat_seconds: float = DEFAULT_CHILD_HEARTBEAT_SECONDS
    stall_seconds: float = DEFAULT_CHILD_STALL_SECONDS
    launch_timeout_seconds: float = DEFAULT_LAUNCH_TIMEOUT_SECONDS
    max_attempts: int = DEFAULT_CHILD_MAX_ATTEMPTS
    # Environment-provided *intent* to run children. This is never sufficient on
    # its own: the durable enabled flag must also be set by an operator.
    env_enable_requested: bool = False

    def __post_init__(self) -> None:
        if self.max_concurrent_children < 1:
            raise ChildOrchestrationConfigError(
                "max_concurrent_children must be at least 1"
            )
        if self.max_concurrent_children > HARD_MAX_CONCURRENT_CHILDREN:
            raise ChildOrchestrationConfigError(
                "max_concurrent_children may not exceed the phase hard ceiling of "
                f"{HARD_MAX_CONCURRENT_CHILDREN}"
            )
        if self.heartbeat_seconds <= 0:
            raise ChildOrchestrationConfigError("heartbeat_seconds must be positive")
        if self.stall_seconds <= self.heartbeat_seconds:
            raise ChildOrchestrationConfigError(
                "stall_seconds must exceed heartbeat_seconds, or a live child "
                "would be classified stalled between heartbeats"
            )
        if self.launch_timeout_seconds <= 0:
            raise ChildOrchestrationConfigError(
                "launch_timeout_seconds must be positive"
            )
        if self.max_attempts < 1:
            raise ChildOrchestrationConfigError("max_attempts must be at least 1")

    @classmethod
    def from_env(cls) -> ChildOrchestrationConfig:
        return cls(
            max_concurrent_children=_int_env(
                "DEVELOPMENT_OPS_MAX_CONCURRENT_CHILDREN",
                DEFAULT_MAX_CONCURRENT_CHILDREN,
            ),
            heartbeat_seconds=_float_env(
                "DEVELOPMENT_OPS_CHILD_HEARTBEAT_SECONDS",
                DEFAULT_CHILD_HEARTBEAT_SECONDS,
            ),
            stall_seconds=_float_env(
                "DEVELOPMENT_OPS_CHILD_STALL_SECONDS",
                DEFAULT_CHILD_STALL_SECONDS,
            ),
            launch_timeout_seconds=_float_env(
                "DEVELOPMENT_OPS_CHILD_LAUNCH_TIMEOUT_SECONDS",
                DEFAULT_LAUNCH_TIMEOUT_SECONDS,
            ),
            max_attempts=_int_env(
                "DEVELOPMENT_OPS_CHILD_MAX_ATTEMPTS", DEFAULT_CHILD_MAX_ATTEMPTS
            ),
            env_enable_requested=_bool_env(
                "DEVELOPMENT_OPS_ENABLE_CHILD_EXECUTION", False
            ),
        )


def resolve_enabled(
    *,
    persisted_enabled: bool,
    config: ChildOrchestrationConfig,
) -> tuple[bool, str]:
    """Resolve whether child execution is enabled.

    Returns ``(enabled, reason)``. The durable, operator-set flag is
    authoritative. An environment variable alone may never *enable* execution:
    at most it is recorded as intent, and it can never override a persisted
    disabled state. This prevents an accidental export (or a service
    environment file) from switching on paid model calls.
    """
    if persisted_enabled:
        return True, "enabled by operator (durable flag)"
    if config.env_enable_requested:
        return False, (
            "environment requested child execution but the durable operator "
            "flag is not set; run 'child enable' to activate"
        )
    return False, "child execution is disabled"
